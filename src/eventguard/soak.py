"""Finite synthetic storage/recovery exercise, never agent or 24-hour proof."""
from __future__ import annotations

import argparse
from contextlib import closing
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
import os
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
RESOURCE_MAX_BYTES = 512 * 1024
RESOURCE_MAX_SAMPLES = 1024
RESOURCE_FIELDS = ("cpu_seconds", "private_bytes", "working_set_bytes", "handles")


class SoakError(RuntimeError):
    """Only fixed reason codes cross the harness boundary."""


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def options(duration_seconds=30, max_events=64, max_report_bytes=8*1024*1024,
            min_wall_seconds=0, pacing_seconds=0):
    if (type(duration_seconds) not in (int, float) or not math.isfinite(duration_seconds)
            or not 1 <= duration_seconds <= 3600 or type(max_events) is not int
            or not 4 <= max_events <= 128 or type(max_report_bytes) is not int
            or not 524288 <= max_report_bytes <= MAX_REPORT_BYTES
            or type(min_wall_seconds) not in (int, float) or not math.isfinite(min_wall_seconds)
            or not 0 <= min_wall_seconds < duration_seconds
            or type(pacing_seconds) not in (int, float) or not math.isfinite(pacing_seconds)
            or not 0 <= pacing_seconds <= 5 or pacing_seconds*max_events >= duration_seconds):
        raise SoakError("finite_soak_bounds_invalid")
    return {"duration_seconds": duration_seconds, "max_events": max_events,
            "max_report_bytes": max_report_bytes, "min_wall_seconds": min_wall_seconds,
            "pacing_seconds": pacing_seconds}


@lru_cache(maxsize=1)
def _self_api():
    """Bind documented APIs to this process's pseudo HANDLE only."""
    if sys.platform != "win32":
        raise OSError("self_resources_require_windows")
    kernel = C.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    psapi = C.WinDLL("psapi.dll", use_last_error=True, winmode=0x800)
    class Counters(C.Structure):
        _fields_ = [("cb", W.DWORD), ("PageFaultCount", W.DWORD),
            *((name, C.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage"))]
    kernel.GetCurrentProcess.argtypes, kernel.GetCurrentProcess.restype = [], W.HANDLE
    kernel.GetProcessTimes.argtypes = [W.HANDLE, *([C.POINTER(W.FILETIME)]*4)]
    kernel.GetProcessTimes.restype = W.BOOL
    kernel.GetProcessHandleCount.argtypes = [W.HANDLE, C.POINTER(W.DWORD)]
    kernel.GetProcessHandleCount.restype = W.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [W.HANDLE, C.POINTER(Counters), W.DWORD]
    psapi.GetProcessMemoryInfo.restype = W.BOOL
    return kernel, psapi, Counters


def _self_resources():
    result = {name: None for name in RESOURCE_FIELDS}
    result.update(status="unknown", error_codes=[])
    try:
        kernel, psapi, counter_type = _self_api()
        handle = kernel.GetCurrentProcess()  # A pseudo HANDLE: never OpenProcess/foreign PID.
        if not handle:
            raise OSError("self_process_handle_unavailable")
        created, exited, system, user = (W.FILETIME() for _ in range(4))
        if kernel.GetProcessTimes(handle, C.byref(created), C.byref(exited), C.byref(system), C.byref(user)):
            ticks = lambda value: value.dwLowDateTime | (value.dwHighDateTime << 32)
            result["cpu_seconds"] = (ticks(system)+ticks(user))/10000000
        else:
            result["error_codes"].append("self_cpu_unavailable")
        memory = counter_type()
        memory.cb = C.sizeof(memory)
        if psapi.GetProcessMemoryInfo(handle, C.byref(memory), memory.cb):
            result.update(private_bytes=int(memory.PrivateUsage), working_set_bytes=int(memory.WorkingSetSize))
        else:
            result["error_codes"].append("self_memory_unavailable")
        handles = W.DWORD()
        if kernel.GetProcessHandleCount(handle, C.byref(handles)):
            result["handles"] = int(handles.value)
        else:
            result["error_codes"].append("self_handle_count_unavailable")
    except (OSError, ValueError, AttributeError, TypeError):
        result["error_codes"].append("self_resource_api_unavailable")
    measured = sum(result[name] is not None for name in RESOURCE_FIELDS)
    result["status"] = "measured" if measured == len(RESOURCE_FIELDS) else "partial" if measured else "unknown"
    return result


class _ResourceLog:
    """Bounded worker-only observations; unknown metrics remain JSON null."""
    def __init__(self, root, start, config):
        self.root, self.start, self.config = root, start, config
        self.path = _guard(root/"resource-samples.jsonl")
        self.path.open("xb").close()
        self.interval = max(1.0, config["duration_seconds"]/512)
        self.max_bytes = min(RESOURCE_MAX_BYTES, config["max_report_bytes"]//4)
        self.count, self.truncated, self.error_code = 0, False, None
        self.previous, self.windows, self.unknown = None, [], 0

    def record(self, phase, *, force=False):
        now = time.monotonic()
        if not self.windows or self.windows[-1]["phase"] != phase:
            if self.windows:
                self.windows[-1]["ended_elapsed_seconds"] = now-self.start
            self.windows.append({"phase": phase, "started_elapsed_seconds": now-self.start,
                                 "ended_elapsed_seconds": now-self.start})
            force = True
        self.windows[-1]["ended_elapsed_seconds"] = now-self.start
        if not force and self.previous and now-self.previous["monotonic"] < self.interval:
            return
        if self.truncated or self.error_code:
            return
        row = {"at": utc(), "monotonic": now, "elapsed_seconds": now-self.start,
               "phase": phase, "pid": os.getpid(), **_self_resources(),
               "interval_cpu_percent_single_core": None}
        old = self.previous
        if (old and old["phase"] == phase and row["cpu_seconds"] is not None
                and old["cpu_seconds"] is not None and now > old["monotonic"]
                and row["cpu_seconds"] >= old["cpu_seconds"]):
            row["interval_cpu_percent_single_core"] = 100*(row["cpu_seconds"]-old["cpu_seconds"])/(now-old["monotonic"])
        encoded = (json.dumps(row, ensure_ascii=True, allow_nan=False)+"\n").encode("ascii")
        try:
            if (self.count >= RESOURCE_MAX_SAMPLES or len(encoded) > 4096
                    or self.path.stat().st_size+len(encoded) > self.max_bytes
                    or usage(self.root)+len(encoded)+RESERVE_BYTES > self.config["max_report_bytes"]):
                self.truncated = True
                return
            with self.path.open("ab") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            self.count += 1
            self.unknown += row["status"] != "measured"
            self.previous = row
        except (OSError, ValueError):
            self.error_code = "self_resource_sample_persist_failed"

    def status(self):
        return {"scope": "worker_process_only_not_job_aggregate", "sampled_pid": os.getpid(),
            "sample_count": self.count, "unknown_or_partial_samples": self.unknown,
            "truncated": self.truncated, "error_code": self.error_code, "unknown_is_null": True,
            "sample_interval_seconds": self.interval, "sample_byte_limit": self.max_bytes,
            "phase_windows": self.windows, "path": self.path.name}


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
        "resource_sampling_performed": True, "resource_scope": "worker_process_only",
        "created_at": utc(), "options": config,
        "events": [{"event": event, "payload_hash": hashes[event["event_id"]]} for event in events]}
    save(root, "producer-manifest.json", producer, config["max_report_bytes"])
    progress = {"kind": KIND, "accepted": [], "rejected": [], "acknowledgments": [], "phases": []}
    summary = {"kind": KIND, "passed": False, "synthetic_harness": True, "model_calls": 0,
        "native_scan_executed": False, "real_agent_woken": False, "twenty_four_hour_proof": False,
        "started_at": utc(), "options": config}
    store = None
    resources = _ResourceLog(root, start, config)
    resource_phase = "idle_before"
    def check_limits():
        if stop_requested and stop_requested():
            raise SoakError("soak_cooperative_stop_requested")
        if time.monotonic() >= deadline:
            raise SoakError("soak_work_deadline_reached")
    def wait_until(until):
        while time.monotonic() < until:
            check_limits()
            resources.record(resource_phase)
            time.sleep(min(.25, max(0, until-time.monotonic())))
    def checkpoint(phase=None):
        if phase:
            progress["phases"].append({"phase": phase, "at": utc(),
                                       "elapsed_seconds": time.monotonic()-start})
        save(root, "progress.json", progress, config["max_report_bytes"])
        resources.record(resource_phase)
        check_limits()
    try:
        store = EventStore(root/"source", max_events=capacity, max_bytes=262144,
            acked_retention_seconds=0, receipt_retention_seconds=3600, receipt_limit=capacity)
        state = root/"inbox"
        inbox_limits = {"max_events": capacity, "max_completed": capacity, "max_bytes": 262144,
                        "completed_retention_seconds": 3600}
        checkpoint("idle")
        if store.stats()["pending"] != 0:
            raise SoakError("idle_source_not_empty")
        wait_until(time.monotonic()+.02)
        resource_phase = "work"
        resources.record(resource_phase, force=True)
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
            if config["pacing_seconds"]:
                wait_until(time.monotonic()+config["pacing_seconds"])
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
        resource_phase = "idle_after"
        resources.record(resource_phase, force=True)
        wait_until(start+config["min_wall_seconds"])
        resources.record(resource_phase, force=True)
        check_limits()
        summary.update(conservation=proof, outbox=store.stats(), rejected_recovered=True,
            completion_fault_count=1, consumer_recreated=True,
            passed=bool(proof["passed"] and not proof["pending_count"] and not proof["unaccepted"]))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, sqlite3.Error) as error:
        known = str(error) if type(error) is SoakError else "synthetic_soak_operation_failed"
        summary.update(reason=known, raw_error_omitted=True)
    finally:
        summary.update(finished_at=utc(), elapsed_seconds=round(time.monotonic()-start, 6),
            report_bytes=usage(root), accepted_count=len(progress["accepted"]),
            resource_sampling=resources.status(),
            unique_ack_count=len({row["event_id"] for row in progress["acknowledgments"]}))
        save(root, "summary.json", summary, config["max_report_bytes"], reserve=False)
    return summary


def _shutdown_owned(child, root, reason, *, grace=3):
    """Persist cooperation before grace/owned-Job cleanup on every failure path."""
    errors = []
    try:
        alive = child.poll() is None
    except (OSError, ValueError, RuntimeError):
        alive = True
        errors.append("owned_liveness_unconfirmed")
    cooperative = {"state": "not_needed", "reason": "owned_process_already_exited"}
    if alive:
        try:
            write_json(root/"stop.request", {"reason": reason, "at": utc()})
            cooperative = {"state": "requested", "reason": "durable_stop_request"}
        except (OSError, ValueError, RuntimeError, TypeError):
            cooperative = {"state": "unconfirmed", "reason": "cooperative_stop_persist_failed"}
            errors.append("cooperative_stop_persist_failed")
    try:
        receipt = finish(child, reason, grace=grace, request_stop=True)
    except (OSError, ValueError, RuntimeError, TypeError):
        errors.append("owned_exit_unconfirmed")
        receipt = {"pid": child.pid, "created_at": child.created_at, "child_exited": None,
                   "exit_code": None, "remaining_owned_processes": None, "forcibly_terminated": None}
    receipt.update(cooperative_stop=cooperative, cleanup_errors=errors,
                   raw_error_omitted=bool(errors))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=float, default=30,
                        help="Maximum worker wall time; finishes early at the event limit.")
    parser.add_argument("--max-events", type=int, default=64, help="4-128 synthetic events; finite manifest budget.")
    parser.add_argument("--max-report-bytes", type=int, default=8*1024*1024)
    parser.add_argument("--min-wall-seconds", type=float, default=0,
                        help="Explicit minimum elapsed worker time, strictly below duration-seconds.")
    parser.add_argument("--pacing-seconds", type=float, default=0,
                        help="Cooperative 0-5 second pause after each unique synthetic ACK.")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    child, receipt = None, None
    try:
        config = options(args.duration_seconds, args.max_events, args.max_report_bytes,
                         args.min_wall_seconds, args.pacing_seconds)
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
            "--max-report-bytes", str(args.max_report_bytes), "--min-wall-seconds", str(args.min_wall_seconds),
            "--pacing-seconds", str(args.pacing_seconds)]
        child = spawn(arguments)
        reason, guardian_failed = "owner_exception", False
        try:
            write_json(root/"guardian-start.json", {"pid": child.pid, "created_at": child.created_at,
                "started_at": utc(), "original_handle_retained": True})
            deadline = time.monotonic()+args.duration_seconds+3
            while child.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            reason = "timeout" if child.poll() is None else "descendants_remaining"
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, KeyboardInterrupt):
            guardian_failed = True
        finally:
            receipt = _shutdown_owned(child, root, reason, grace=3)
            receipt["guardian_operation_failed"] = guardian_failed
            try:
                write_json(root/"guardian-exit.json", receipt)
            except (OSError, ValueError, RuntimeError, TypeError):
                receipt["exit_receipt_persisted"] = False
                raise SoakError("guardian_exit_receipt_unconfirmed") from None
        if guardian_failed:
            raise SoakError("guardian_post_spawn_operation_failed")
        result = read_json(root/"exercise/summary.json")
        source_unchanged = all(hashlib.sha256((PROJECT/name).read_bytes()).hexdigest() == digest
                               for name, digest in source_hashes.items())
        passed = bool(result.get("passed") is True and receipt.get("exit_code") == 0 and source_unchanged
            and receipt.get("child_exited") is True and receipt.get("remaining_owned_processes") == 0
            and receipt.get("forcibly_terminated") is False and not receipt.get("cleanup_errors")
            and usage(root) <= args.max_report_bytes)
        write_json(root/"validation.json", {"passed": passed, "synthetic_harness": True,
            "model_calls": 0, "native_scan_executed": False, "real_agent_woken": False,
            "twenty_four_hour_proof": False, "guardian": receipt, "exercise": result,
            "source_unchanged": source_unchanged, "report_bytes": usage(root), "verified_at": utc()})
        print(json.dumps({"passed": passed, "scope": "finite_synthetic_harness_not_agent_or_24h",
            "accepted": result.get("accepted_count"), "unique_ack": result.get("unique_ack_count"),
            "guardian": receipt}))
        return 0 if passed else 2
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        print(json.dumps({"passed": False, "reason": "finite_soak_blocked_or_failed",
                          "raw_error_omitted": True, "guardian": receipt}))
        return 2
