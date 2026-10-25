"""Finite synthetic storage/recovery exercise, never agent or 24-hour proof."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import time

from .acceptance_control import read_json, write_json
from .events.schema import validate_event
from .events.store import CapacityError, EventStore, event_payload_hash
from .local_paths import _guard
from .processes import finish, spawn
from .queue_inbox import QueueInbox, QueueInboxError

PROJECT = Path(__file__).resolve().parents[2]
KIND = "eventguard-finite-synthetic-soak-v1"
MAX_REPORT_BYTES = 64 * 1024 * 1024
RESERVE_BYTES = 32768


class SoakError(RuntimeError):
    """Only fixed reason codes cross the harness boundary."""


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def options(duration_seconds=30, max_events=64, max_report_bytes=8*1024*1024):
    if (type(duration_seconds) not in (int, float) or not math.isfinite(duration_seconds)
            or not 1 <= duration_seconds <= 3600 or type(max_events) is not int
            or not 4 <= max_events <= 128 or type(max_report_bytes) is not int
            or not 524288 <= max_report_bytes <= MAX_REPORT_BYTES):
        raise SoakError("finite_soak_bounds_invalid")
    return {"duration_seconds": duration_seconds, "max_events": max_events,
            "max_report_bytes": max_report_bytes}


def usage(root):
    return sum(_guard(path).stat().st_size for path in root.rglob("*") if path.is_file())


def save(root, name, value, limit, *, reserve=True):
    path = _guard(root / name)
    encoded = json.dumps(value, indent=2, allow_nan=False).encode("utf-8")
    prior = path.stat().st_size if path.exists() else 0
    if usage(root)-prior+len(encoded)+(RESERVE_BYTES if reserve else 0) > limit:
        raise SoakError("soak_report_capacity_preserved")
    write_json(path, value)


def synthetic(identity, sequence):
    return validate_event({"schema_version": "2.0", "event_id": identity,
        "host_id": "synthetic-soak-host", "episode_id": "synthetic-soak",
        "correlation_id": "synthetic-soak", "sequence": sequence,
        "event_type": "listener.changed", "transition": "new", "severity": "warning",
        "synthetic": True, "observed_at": "2026-10-25T00:00:00Z",
        "persisted_at": "2026-10-25T00:00:00Z", "evidence": {"protocol": "TCP", "port": 18080},
        "coverage": {"status": "unknown", "gaps": []}})


def verify_sets(producer_hashes, accepted, acknowledgments, pending_hashes):
    """Check conservation independently of saved passed/phase claims."""
    ack_ids = [row["event_id"] for row in acknowledgments]
    errors = []
    if len(accepted) != len(set(accepted)) or len(ack_ids) != len(set(ack_ids)):
        errors.append("duplicate_business_identity")
    if set(accepted) != set(ack_ids) | set(pending_hashes) or set(ack_ids) & set(pending_hashes):
        errors.append("accepted_ack_pending_partition_mismatch")
    if not set(accepted).issubset(producer_hashes):
        errors.append("accepted_identity_not_in_producer")
    for identity, digest in pending_hashes.items():
        if producer_hashes.get(identity) != digest:
            errors.append("pending_payload_hash_changed")
    for row in acknowledgments:
        receipt = row.get("receipt") or {}
        if (producer_hashes.get(row["event_id"]) != row.get("payload_hash")
                or receipt.get("ack_type") != "receiver_persisted" or receipt.get("event_id") != row["event_id"]
                or receipt.get("receiver_receipt_id") != row.get("result_id")
                or not row.get("query_id") or not row.get("result_id")):
            errors.append("ack_identity_or_payload_hash_mismatch")
    return {"passed": not errors, "errors": sorted(set(errors)),
        "accepted_count": len(accepted), "unique_ack_count": len(set(ack_ids)),
        "pending_count": len(pending_hashes), "unaccepted": sorted(set(producer_hashes)-set(accepted))}


def _pending(store):
    return {row["event_id"]: event_payload_hash(validate_event(row))
            for row in store.list_events(1000) if row["delivery_status"] != "ack"}


def _receipt(store, identity):
    with closing(sqlite3.connect(store.path.as_uri()+"?mode=ro", uri=True)) as db:
        row = db.execute("SELECT payload_hash,receipt,acked_at,pending_finalization FROM receipts WHERE event_id=?",
                         (identity,)).fetchone()
    if row is None:
        raise SoakError("durable_receipt_missing")
    return {"payload_hash": row[0], "receipt": json.loads(row[1]),
            "acked_at": row[2], "pending_finalization": row[3]}


class _CompletionFaultInbox(QueueInbox):
    injected = False

    def _immutable(self, path, value):
        if path.name.startswith("completed-") and not self.injected:
            self.injected = True
            raise QueueInboxError("synthetic_soak_completion_write_failure")
        return super()._immutable(path, value)


def exercise(root, config, *, stop_requested=None):
    """Use a fresh directory; callers supply only synthetic workload bounds."""
    root = _guard(root)
    config = options(**config)
    if root.exists():
        raise SoakError("existing_soak_directory_refused")
    root.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = start+config["duration_seconds"]
    capacity = min(8, config["max_events"]-2)
    events = [synthetic("evt-soak-"+str(index), index+1) for index in range(config["max_events"])]
    hashes = {event["event_id"]: event_payload_hash(event) for event in events}
    producer = {"kind": KIND, "synthetic_harness": True, "model_calls": 0,
        "native_scan_executed": False, "real_agent_woken": False, "twenty_four_hour_proof": False,
        "resource_sampling_performed": False,
        "created_at": utc(), "options": config,
        "events": [{"event": event, "payload_hash": hashes[event["event_id"]]} for event in events]}
    save(root, "producer-manifest.json", producer, config["max_report_bytes"])
    progress = {"kind": KIND, "accepted": [], "rejected": [], "acknowledgments": [], "phases": []}
    summary = {"kind": KIND, "passed": False, "synthetic_harness": True, "model_calls": 0,
        "native_scan_executed": False, "real_agent_woken": False, "twenty_four_hour_proof": False,
        "started_at": utc(), "options": config}
    store = None
    def checkpoint(phase=None):
        if phase:
            progress["phases"].append({"phase": phase, "at": utc()})
        save(root, "progress.json", progress, config["max_report_bytes"])
        if stop_requested and stop_requested():
            raise SoakError("soak_cooperative_stop_requested")
        if time.monotonic() >= deadline:
            raise SoakError("soak_work_deadline_reached")
    try:
        store = EventStore(root/"source", max_events=capacity, max_bytes=262144,
            acked_retention_seconds=0, receipt_retention_seconds=3600, receipt_limit=capacity)
        state = root/"inbox"
        inbox_limits = {"max_events": capacity, "max_completed": capacity, "max_bytes": 262144,
                        "completed_retention_seconds": 3600}
        checkpoint("idle")
        if store.stats()["pending"] != 0:
            raise SoakError("idle_source_not_empty")
        time.sleep(.02)
        for event in events[:capacity]:
            if not store.enqueue(event):
                raise SoakError("fresh_synthetic_admission_failed")
            progress["accepted"].append(event["event_id"])
            checkpoint()
        held = _pending(store)
        refused = events[capacity]
        try:
            store.enqueue(refused)
        except CapacityError:
            progress["rejected"].append({"event_id": refused["event_id"],
                "payload_hash": hashes[refused["event_id"]], "reason": "outbox_capacity"})
        else:
            raise SoakError("capacity_fixture_did_not_block")
        if _pending(store) != held:
            raise SoakError("pending_changed_under_backpressure")
        progress["backpressure"] = {"pending_before": held, "pending_after": _pending(store),
            "refused_event_id": refused["event_id"], "refused_payload_hash": hashes[refused["event_id"]]}
        checkpoint("consumer_paused_capacity")

        first = events[0]["event_id"]
        inbox = _CompletionFaultInbox(store.directory, state, first, limits=inbox_limits)
        inbox.receive_event()
        query = inbox.query_evidence(first)
        try:
            inbox.ack_event(first, query["query_id"], "reviewed_metadata")
        except QueueInboxError as error:
            if error.args != ("synthetic_soak_completion_write_failure",):
                raise
        else:
            raise SoakError("completion_fault_not_observed")
        pinned = _receipt(store, first)
        if pinned["pending_finalization"] != 1:
            raise SoakError("unfinalized_receipt_not_protected")
        store.maintain()
        if _receipt(store, first) != pinned:
            raise SoakError("maintenance_changed_pinned_receipt")
        checkpoint("completion_write_fault")

        def consume(identity, *, expected_query=None):
            current = QueueInbox(store.directory, state, identity, limits=inbox_limits)
            if expected_query is None:
                current.receive_event()
            found = current.query_evidence(identity)
            if expected_query is not None and found != expected_query:
                raise SoakError("restarted_query_identity_changed")
            result = current.ack_event(identity, found["query_id"], "reviewed_metadata")
            receipt = _receipt(store, identity)
            replay = current.ack_event(identity, found["query_id"], "reviewed_metadata")
            if result != replay or _receipt(store, identity) != receipt or receipt["pending_finalization"] != 0:
                raise SoakError("ack_replay_not_idempotent")
            progress["acknowledgments"].append({"event_id": identity, "query_id": found["query_id"],
                "result_id": result["result_id"], **receipt})
            checkpoint()
        consume(first, expected_query=query)
        progress["recovery"] = {"event_id": first, "query_id": query["query_id"],
            "same_query_after_restart": True, "pinned_receipt_maintained": True,
            "receipt_before_maintenance": pinned}
        checkpoint("consumer_recreated_same_query")
        if not store.enqueue(refused):
            raise SoakError("rejected_producer_not_readmitted")
        progress["accepted"].append(refused["event_id"])
        if _pending(store).get(refused["event_id"]) != hashes[refused["event_id"]]:
            raise SoakError("readmitted_producer_hash_changed")
        progress["readmission"] = {"event_id": refused["event_id"],
            "original_payload_hash": hashes[refused["event_id"]],
            "recovered_payload_hash": _pending(store)[refused["event_id"]]}
        checkpoint("same_rejected_identity_readmitted")
        for event in events[1:capacity+1]:
            consume(event["event_id"])
        for event in events[capacity+1:]:
            checkpoint()
            if not store.enqueue(event):
                raise SoakError("fresh_synthetic_admission_failed")
            progress["accepted"].append(event["event_id"])
            consume(event["event_id"])
        store.maintain()
        checkpoint("drained")
        proof = verify_sets(hashes, progress["accepted"], progress["acknowledgments"], _pending(store))
        summary.update(conservation=proof, outbox=store.stats(), rejected_recovered=True,
            completion_fault_count=1, consumer_recreated=True,
            passed=bool(proof["passed"] and not proof["pending_count"] and not proof["unaccepted"]))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, sqlite3.Error) as error:
        known = str(error) if type(error) is SoakError else "synthetic_soak_operation_failed"
        summary.update(reason=known, raw_error_omitted=True)
    finally:
        summary.update(finished_at=utc(), elapsed_seconds=round(time.monotonic()-start, 6),
            report_bytes=usage(root), accepted_count=len(progress["accepted"]),
            unique_ack_count=len({row["event_id"] for row in progress["acknowledgments"]}))
        save(root, "summary.json", summary, config["max_report_bytes"], reserve=False)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=float, default=30,
                        help="Maximum worker wall time; finishes early at the event limit.")
    parser.add_argument("--max-events", type=int, default=64, help="4-128 synthetic events; finite manifest budget.")
    parser.add_argument("--max-report-bytes", type=int, default=8*1024*1024)
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    child, receipt = None, None
    try:
        config = options(args.duration_seconds, args.max_events, args.max_report_bytes)
        root = _guard(args.root)
        if not root.is_relative_to(PROJECT/"reports"):
            raise SoakError("dedicated_reports_scope_required")
        if args._worker:
            manifest = read_json(root/"manifest.json")
            if (manifest.get("kind") != KIND or manifest.get("synthetic_harness") is not True
                    or manifest.get("options") != config):
                raise SoakError("prepared_synthetic_worker_scope_required")
            result = exercise(root/"exercise", config, stop_requested=lambda: (root/"stop.request").exists())
            return 0 if result["passed"] else 2
        if root.exists():
            raise SoakError("existing_soak_directory_refused")
        root.mkdir(parents=True, exist_ok=False)
        files = [Path(__file__), PROJECT/"scripts/soak.py", PROJECT/"src/eventguard/events/store.py",
                 PROJECT/"src/eventguard/events/schema.py", PROJECT/"src/eventguard/queue_inbox.py",
                 PROJECT/"src/eventguard/processes.py", PROJECT/"src/eventguard/storage_policy.py"]
        source_hashes = {path.relative_to(PROJECT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in files}
        write_json(root/"manifest.json", {"kind": KIND, "synthetic_harness": True, "model_calls": 0,
            "native_scan_executed": False, "created_at": utc(), "options": config, "source_sha256": source_hashes})
        arguments = [sys.executable, "-B", str(PROJECT/"scripts/soak.py"), "--_worker", "--root", str(root),
            "--duration-seconds", str(args.duration_seconds), "--max-events", str(args.max_events),
            "--max-report-bytes", str(args.max_report_bytes)]
        child = spawn(arguments)
        try:
            write_json(root/"guardian-start.json", {"pid": child.pid, "created_at": child.created_at,
                "started_at": utc(), "original_handle_retained": True})
            deadline = time.monotonic()+args.duration_seconds+3
            while child.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            if child.poll() is None:
                write_json(root/"stop.request", {"reason": "finite_soak_deadline", "at": utc()})
            receipt = finish(child, "timeout" if child.poll() is None else "descendants_remaining", grace=3)
        finally:
            receipt = finish(child, "owner_exception", grace=1)
            write_json(root/"guardian-exit.json", receipt)
        result = read_json(root/"exercise/summary.json")
        source_unchanged = all(hashlib.sha256((PROJECT/name).read_bytes()).hexdigest() == digest
                               for name, digest in source_hashes.items())
        passed = bool(result.get("passed") is True and receipt.get("exit_code") == 0 and source_unchanged
            and receipt.get("child_exited") is True and receipt.get("remaining_owned_processes") == 0
            and receipt.get("forcibly_terminated") is False and usage(root) <= args.max_report_bytes)
        write_json(root/"validation.json", {"passed": passed, "synthetic_harness": True,
            "model_calls": 0, "native_scan_executed": False, "real_agent_woken": False,
            "twenty_four_hour_proof": False, "guardian": receipt, "exercise": result,
            "source_unchanged": source_unchanged, "report_bytes": usage(root), "verified_at": utc()})
        print(json.dumps({"passed": passed, "scope": "finite_synthetic_harness_not_agent_or_24h",
            "accepted": result.get("accepted_count"), "unique_ack": result.get("unique_ack_count"),
            "guardian": receipt}))
        return 0 if passed else 2
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        print(json.dumps({"passed": False, "reason": "finite_soak_blocked_or_failed", "raw_error_omitted": True}))
        return 2
