"""Read existing legacy LocalWait evidence only; no new CLI/model execution."""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eventguard.acceptance_control import read_json, write_json
from eventguard.acceptance_evidence import assess, _tool_result
from eventguard.acceptance_process import capture, CAPTURE_LIMIT
from eventguard.codex_acceptance import command
from eventguard.local_wait import LocalWait, LocalWaitError, _guard, _identifier, KIND as WAIT_KIND
from eventguard.events.store import EventStore
from eventguard.storage_policy import limits
from eventguard.synthetic import make_synthetic

KIND = "eventguard-finite-real-delivery-validation"


class ReadOnlyStore(EventStore):
    """Reuse schema validators and reads without running schema/policy migrations."""
    def __init__(self, directory):
        self.directory = _guard(directory)
        self.path = _guard(self.directory / "eventguard.sqlite3")
        self._lock = threading.RLock()
        with self._connect() as db:
            row = db.execute("SELECT value FROM meta WHERE key='storage_policy'").fetchone()
        self.policy = limits("outbox", json.loads(row[0]) if row else {"max_events": 64})
        self.max_events, self.max_bytes = self.policy["max_events"], self.policy["max_bytes"]
        self.ack_reserve_bytes = min(2*1024*1024, self.max_bytes//4)

    @contextmanager
    def _connect(self):
        _guard(self.path)
        with closing(sqlite3.connect(self.path.as_uri()+"?mode=ro", uri=True, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            yield db


class EvidenceReader(LocalWait):
    def __init__(self, directory):
        self.directory = _guard(directory)
        self.ledger_path = _guard(self.directory / "local-wait-results.json")
        marker = self._read(self.directory / "local-wait-experiment.json", 1024)
        if (not isinstance(marker, dict) or set(marker) != {"kind", "schema_version", "experiment_id"}
                or marker.get("kind") != WAIT_KIND or marker.get("schema_version") != "1.0"):
            raise LocalWaitError("foreign_experiment_directory")
        self.experiment_id = _identifier(marker["experiment_id"])
        self.store = ReadOnlyStore(self.directory / "outbox")
        self._load()

    def _atomic(self, path, value):
        raise LocalWaitError("legacy_evidence_read_only")


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def prepare(root, case):
    root = _guard(root)
    marker = root / "manifest.json"
    if marker.exists():
        manifest = read_json(marker)
        if manifest.get("kind") != KIND or manifest.get("case") != case:
            raise ValueError("foreign_validation_directory")
        EvidenceReader(root / "runtime")
        return manifest
    root.mkdir(parents=True, exist_ok=False)
    count = {"continuous": 2, "batch": 3, "recovery": 1}[case]
    manifest = {"kind": KIND, "case": case, "generated_at": utc(),
                "events": [make_synthetic("listener") for _ in range(count)],
                "enqueued": [], "attempts": {}}
    LocalWait(root / "runtime")
    write_json(marker, manifest)
    return manifest






def argv(runtime, evidence, count, read_only=False, native_executable="codex"):
    native = shutil.which(native_executable)
    if not native or Path(native).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        raise ValueError("native_codex_required")
    args = command(native, sys.executable, runtime, evidence_dir=evidence,
                   single_wait=count == 1, allow_ack=not read_only)
    args[-1:-1] = ["-c", "features.unbounded_connection_retries=false"]
    return args




def load_stage(root, manifest, name):
    evidence = _guard(root / name)
    receipt = read_json(evidence / "capture-exit.json")
    expected_token = manifest["attempts"][name]["attempt_id"]
    if (receipt.get("attempt_id") != expected_token or receipt.get("capture_complete") is not True
            or type(receipt.get("codex_exit_code")) is not int or receipt.get("codex_exit_code") != 0
            or receipt.get("stdout_truncated") is not False
            or receipt.get("stderr_truncated") is not False):
        raise ValueError("real_cli_exit_not_verified")
    raw = _guard(evidence / "codex.jsonl").read_bytes()
    if len(raw) > CAPTURE_LIMIT:
        raise ValueError("trace_too_large")
    trace = [json.loads(line) for line in raw.splitlines()]
    if len(trace) > 4096 or any(not isinstance(row, dict) for row in trace):
        raise ValueError("invalid_real_trace")
    if sum(row.get("type") == "turn.completed" for row in trace) != 1:
        raise ValueError("completed_real_turn_missing")
    if any(row.get("type") in {"turn.failed", "error"} for row in trace):
        raise ValueError("real_cli_reported_failure")
    calls = []
    for row in trace:
        item = row.get("item", {})
        if row.get("type") in {"item.started", "item.updated", "item.completed"}:
            if not isinstance(item, dict) or item.get("type") not in {"mcp_tool_call", "agent_message", "reasoning", "todo_list"}:
                raise ValueError("unexpected_cli_action")
            if item.get("type") == "mcp_tool_call" and item.get("server") != "eventguard_local":
                raise ValueError("unexpected_mcp_server")
            if row["type"] == "item.completed" and item.get("type") == "mcp_tool_call":
                if item.get("status") != "completed" or item.get("error") is not None or not isinstance(_tool_result(item), dict):
                    raise ValueError("actual_tool_return_missing")
                calls.append(item)
    return trace, calls


def verify_read(root, manifest):
    trace, calls = load_stage(root, manifest, "read-before-ack")
    if [item.get("tool") for item in calls] != ["wait_for_event", "query_evidence"]:
        raise ValueError("read_phase_tool_sequence")
    waited, queried = map(_tool_result, calls)
    expected = manifest["events"][0]["event_id"]
    backend = EvidenceReader(root / "runtime")
    record = backend.store.get_event(expected)
    ledger = backend._load()
    if (waited.get("status") != "event_available" or waited.get("event_id") != expected
            or queried.get("status") != "synthetic_snapshot" or queried.get("event_id") != expected
            or queried.get("query_id") != ledger["events"][expected].get("query_id")
            or calls[0].get("arguments") != {"timeout_seconds": 30}
            or calls[1].get("arguments") != {"event_id": expected}
            or record["delivery_status"] != "pending" or "result" in ledger["events"][expected]):
        raise ValueError("read_before_ack_not_preserved")
    snapshot = {"passed": True, "event_id": expected, "query_id": queried["query_id"],
                "delivery_status": record["delivery_status"], "result_present": False,
                "ledger": ledger, "verified_at": utc()}
    write_json(root / "read-before-ack" / "pending-proof.json", snapshot)
    return snapshot


def verify_full(root, manifest, name):
    trace, calls = load_stage(root, manifest, name)
    expected = [event["event_id"] for event in manifest["events"]]
    if [item.get("tool") for item in calls] != ["wait_for_event", "query_evidence", "ack_event"] * len(expected):
        raise ValueError("full_tool_sequence_mismatch")
    backend = EvidenceReader(root / "runtime")
    ledger = backend._load()
    received, queried_ids, acked = [], [], []
    summaries = []
    for offset in range(0, len(calls), 3):
        group = calls[offset:offset + 3]
        waited, queried, ack = map(_tool_result, group)
        identity = waited.get("event_id")
        received.append(identity)
        queried_ids.append(queried.get("event_id"))
        if ack.get("outbox_acknowledged") is True:
            acked.append(ack.get("event_id"))
        ids = {item.get("id") for item in group}
        subset = [row for row in trace if row.get("type") == "turn.completed" or
                  (row.get("type") in {"item.started", "item.updated", "item.completed"}
                   and row.get("item", {}).get("type") == "mcp_tool_call"
                   and row["item"].get("id") in ids)]
        before = [row["wait_id"] for row in ledger["waits"] if row["wait_id"] != waited.get("wait_id")]
        durable_ack = bool(backend.store.get_event(identity) and backend.store.get_event(identity)["delivery_status"] == "ack")
        checked = assess(subset, ledger, identity, 0, durable_ack, wait_ids_before=before)
        summaries.append(checked)
    durable = [identity for identity in expected if backend.store.get_event(identity)["delivery_status"] == "ack"]
    wanted = Counter(expected)
    outbox = backend.store.stats()
    passed = (outbox["pending"] == 0 and outbox["retry"] == 0 and outbox["failed"] == 0
              and outbox["total"] == len(expected) and all(row["passed"] for row in summaries) and
              all(Counter(values) == wanted for values in (received, queried_ids, acked, durable)) and
              Counter(row["event_id"] for row in manifest["enqueued"]) == wanted)
    proof = {"passed": passed, "case": manifest["case"], "generated": expected, "received": received,
             "queried": queried_ids, "acked": acked, "durable_acked": durable, "outbox": outbox,
             "missing": sorted(set(expected) - set(acked)), "per_event": summaries,
             "verified_at": utc(), "real_cli_trace": str(root / name / "codex.jsonl"),
             "idle_backend_model_requests": "not_observable; no zero-usage claim"}
    if manifest["case"] == "recovery":
        prior = read_json(root / "read-before-ack" / "pending-proof.json")
        proof["recovered_same_event_and_query"] = (prior.get("passed") is True and
            prior.get("event_id") == received[0] and prior.get("query_id") == summaries[0].get("query_id"))
        proof["passed"] = proof["passed"] and proof["recovered_same_event_and_query"]
    write_json(root / "validation.json", proof)
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("continuous", "batch", "recovery"))
    parser.add_argument("--root", type=Path)
    parser.add_argument("--execute", action="store_true", help="Explicitly invoke real account/model tasks.")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--codex-executable", default="codex", help="Existing native Codex binary; .cmd/.bat/.ps1 wrappers are refused.")
    args = parser.parse_args()
    if args.execute or not args.verify_only:
        raise ValueError("legacy_execution_retired_use_queue_acceptance")
    root = _guard(args.root or ROOT / "reports" / ("delivery-" + args.case + "-001"))
    if args.verify_only and not (root / "manifest.json").exists():
        raise ValueError("existing_validation_evidence_required")
    manifest = prepare(root, args.case)
    if args.execute and args.verify_only:
        raise ValueError("choose_execute_or_verify_only")
    if args.execute or args.verify_only:
        proof = verify_full(root, manifest, "recover-and-ack" if args.case == "recovery" else "process")
        print(json.dumps({key: value for key, value in proof.items() if key != "per_event"}))
        return 0 if proof["passed"] else 1
    print(json.dumps({"state": "prepared_only_no_model_invoked", "case": args.case,
                      "count": len(manifest["events"]), "root": str(root),
                      "next": "Use --execute only after the model network route works."}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        print(json.dumps({"state": "validation_blocked_or_failed", "note": "Inspect local evidence; no model retry or success claim."}))
        raise SystemExit(2)
