"""Bounded CLI proof inspection. Synthetic SQLite and fake protocol only.

No subprocess, model, network or independent model provenance is exercised.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from budget_fixtures import isolated_launch
from eventguard import agent_dispatch as dispatch
from eventguard.acceptance_control import read_json, write_json
from eventguard.events.schema import validate_event
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.queue_inbox import QueueInbox
from eventguard.synthetic import make_synthetic


def build_inspection_fixture(root, *, allow_live=False):
    """Reusable temporary-root backend; all CLI/Job records are fabricated.

    Return source/state/event/payload_hash/run_dir/attempt_dir/record. Never use
    the real checkout as root. No executable is launched or stored as a command.
    """
    root = Path(root).absolute()
    if root == dispatch.ROOT:
        raise ValueError("temporary_synthetic_root_required")
    source = root / ("data/live" if allow_live else "data/test")
    state = root / ("data/agent-delivery" if allow_live else "data/agent-delivery-test")
    base = datetime(2026, 10, 24, tzinfo=timezone.utc)
    stamp = lambda seconds: (base+timedelta(seconds=seconds)).isoformat()
    clock = [1]
    event = make_synthetic("listener")
    event["severity"] = "high"
    event = validate_event(event)
    store = EventStore(source)
    with patch("eventguard.events.store.time.time", side_effect=lambda: (base+timedelta(seconds=clock[0])).timestamp()), \
            patch("eventguard.queue_inbox._utc", side_effect=lambda: stamp(clock[0])):
        store.enqueue(event)
        inbox = QueueInbox(source, state, event_id=event["event_id"], allow_live=allow_live)
        reference = inbox.delivery_reference(event["event_id"])
        binding = dispatch._binding(source, state, event["event_id"], reference, allow_live=allow_live)
        clock[0] = 4
        received = inbox.receive_event()
        clock[0] = 5
        queried = inbox.query_evidence(event["event_id"])
        clock[0] = 6
        acked = inbox.ack_event(event["event_id"], queried["query_id"], "reviewed_metadata")
    run_dir = root / "data/agent-service/runs" / ("a"*32)
    token, run_id, nonce = "b"*32, "c"*32, "d"*32
    attempt = run_dir / "attempts" / token
    attempt.mkdir(parents=True)
    worker = {"attempt_id": token, "run_id": run_id, "nonce": nonce, "pid": 301, "created_at": stamp(2)}
    record = {"event_id": event["event_id"], "run_id": run_id, "attempt_id": token, "run_dir": str(run_dir),
        "state": "complete", "passed": True, "ack_verified": True, "child_exited": True,
        "tree_exit_verified": True, "finished_at": stamp(7), "supervisor_identity_required": True,
        "supervisor_exit_required": True, "supervisor_nonce": nonce, "supervisor_start": worker,
        "binding_hash": dispatch._binding_hash(binding)}
    write_json(attempt / "attempt.json", record)
    dispatch._save_binding(attempt / "binding.json", binding)
    write_json(attempt / "supervisor-start.json", worker)
    write_json(attempt / "supervisor-exit.json", {"managed": True, "pid": 301, "created_at": stamp(2),
        "child_exited": True, "remaining_owned_processes": 0, "exit_code": 0, "forcibly_terminated": False,
        "reason": "natural_exit"})
    started = {"attempt_id": token, "codex_pid": 302, "created_at": stamp(3)}
    write_json(attempt / "capture-start.json", started)
    write_json(attempt / "capture-exit.json", {"attempt_id": token, "codex_pid": 302, "codex_exit_code": 0,
        "capture_complete": True, "child_exited": True, "stdout_truncated": False, "stderr_truncated": False,
        "forcibly_terminated": False, "stop_reason": "descendants_remaining", "process": {
            "managed": True, "pid": 302, "created_at": stamp(3), "child_exited": True,
            "remaining_owned_processes": 0, "exit_code": 0, "forcibly_terminated": False,
            "reason": "natural_exit", "shutdown_requested_reason": "descendants_remaining"}})
    (attempt / "capture.lock").write_bytes(b"0")
    replies = (received, queried, acked)
    arguments = ({}, {"event_id": event["event_id"]}, {"event_id": event["event_id"], "query_id": queried["query_id"],
                                                            "decision": "reviewed_metadata"})
    trace = [{"type": "thread.started", "thread_id": "fixture-thread"}, {"type": "turn.started"}]
    trace.extend({"type": "item.completed", "item": {"id": "fixture-"+tool, "type": "mcp_tool_call",
        "server": "eventguard_inbox", "tool": tool, "status": "completed", "error": None, "arguments": args,
        "result": {"content": [{"type": "text", "text": json.dumps(reply)}]}}}
        for tool, args, reply in zip(dispatch.TOOLS, arguments, replies))
    trace.append({"type": "turn.completed"})
    (attempt / "codex.jsonl").write_text("\n".join(map(json.dumps, trace)), encoding="utf-8")
    write_json(run_dir / "dispatch.json", {"kind": dispatch.KIND, "run_id": run_id})
    write_json(run_dir / "status.json", {"kind": dispatch.KIND, "run_id": run_id, "state": "stopped"})
    write_json(state / "dispatcher-attempts.json", {"kind": dispatch.KIND, "events": {event["event_id"]: [record]}})
    return {"source": source, "state": state, "event": event, "payload_hash": event_payload_hash(event),
            "run_dir": run_dir, "attempt_dir": attempt, "record": record}


class DispatchInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = build_inspection_fixture(self.root)

    def inspect(self, fixture=None, **overrides):
        item = fixture or self.fixture
        return dispatch.inspect_event_attempts(item["source"], item["state"], item["event"]["event_id"],
                                               overrides.get("payload_hash", item["payload_hash"]), root=self.root)

    def test_bound_protocol_stages_are_not_independent_model_provenance(self):
        result = self.inspect()
        self.assertEqual(result["stages"]["notification_submitted"]["status"], "not_applicable")
        for stage in ("agent_started", "agent_turn_completed", "agent_process_exited"):
            self.assertEqual(result["stages"][stage]["status"], "confirmed")
        self.assertFalse(result["real_agent_wake_verified"])
        self.assertEqual(result["scope"], "cli_protocol_evidence_not_independent_model_provenance")
        text = json.dumps(result)
        self.assertLess(len(text), 65536)
        for forbidden in ("run_dir", "payload_hash", '"pid"', "arguments", str(self.root)):
            self.assertNotIn(forbidden, text)

    def test_readonly_inspection_changes_no_files_and_uses_no_launch_or_spawn(self):
        snapshot = lambda: {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in self.root.rglob("*") if path.is_file()}
        before = snapshot()
        with patch("eventguard.acceptance_process.launch_gate") as gate, patch.object(dispatch, "spawn") as spawn, \
                patch("eventguard.agent_budget.BudgetAuthority.open_existing") as budget, \
                patch.object(dispatch, "write_json") as save:
            result = self.inspect()
        self.assertTrue(result["read_only"])
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(snapshot(), before)
        gate.assert_not_called()
        budget.assert_not_called()
        spawn.assert_not_called()
        save.assert_not_called()

    def test_success_archive_keeps_every_ref_and_survives_another_host_run(self):
        item = self.fixture
        inbox = QueueInbox.open_readonly(item["source"], item["state"])
        _, archive, _ = dispatch.maintain_ledger(item["state"] / "dispatcher-attempts.json", inbox,
            now=datetime(2026, 10, 24, tzinfo=timezone.utc).timestamp()+8)
        refs = archive["events"][item["event"]["event_id"]]["attempt_refs"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["run_id"], item["record"]["run_id"])
        self.assertEqual(refs[0]["binding_hash"], item["record"]["binding_hash"])
        write_json(self.root / "data/agent-service/run.json", {"run_id": "e"*32, "state": "running"})
        self.assertEqual(self.inspect()["stages"]["agent_process_exited"]["status"], "confirmed")

    def test_mismatched_payload_or_scope_binding_is_unknown(self):
        self.assertEqual(self.inspect(payload_hash="0"*64)["stages"]["agent_started"]["status"], "unknown")
        path = self.fixture["attempt_dir"] / "binding.json"
        binding = read_json(path)
        binding["state_scope_hash"] = "0"*64
        write_json(path, binding)  # Explicitly corrupt fixture, not the immutable production writer.
        self.assertEqual(self.inspect()["stages"]["agent_started"]["status"], "unknown")

    def test_binding_writer_never_overwrites_existing_identity(self):
        path = self.fixture["attempt_dir"] / "binding.json"
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            dispatch._save_binding(path, {"kind": "fixture-replacement"})
        self.assertEqual(path.read_bytes(), before)

    def test_foreign_reference_does_not_read_private_paths(self):
        item = self.fixture
        path = item["state"] / "dispatcher-attempts.json"
        ledger = read_json(path)
        foreign = self.root / ".codex/sessions" / ("f"*32)
        ledger["events"][item["event"]["event_id"]][0]["run_dir"] = str(foreign)
        write_json(path, ledger)
        original = dispatch.read_json
        seen = []
        def read(target, *args, **kwargs):
            seen.append(Path(target))
            return original(target, *args, **kwargs)
        with patch.object(dispatch, "read_json", side_effect=read):
            result = self.inspect()
        self.assertEqual(result["stages"]["agent_started"]["status"], "unknown")
        self.assertFalse(any(target.is_relative_to(foreign) for target in seen))

    def test_old_summary_passed_without_binding_does_not_upgrade(self):
        attempt = self.fixture["attempt_dir"]
        (attempt / "binding.json").unlink()
        write_json(attempt / "summary.json", {"passed": True, "real_agent_wake_verified": True})
        self.assertEqual(self.inspect()["stages"]["agent_turn_completed"]["status"], "unknown")

    def test_bad_trace_preserves_verified_process_exit_but_not_turn(self):
        (self.fixture["attempt_dir"] / "codex.jsonl").write_text("fixture malformed", encoding="utf-8")
        result = self.inspect()
        self.assertEqual(result["stages"]["agent_started"]["status"], "observed")
        self.assertEqual(result["stages"]["agent_turn_completed"]["status"], "unknown")
        self.assertEqual(result["stages"]["agent_process_exited"]["status"], "confirmed")

    def test_live_inbox_can_contain_synthetic_namespace_without_profile_confusion(self):
        alternate = self.root / "live-profile-fixture"
        item = build_inspection_fixture(alternate, allow_live=True)
        result = dispatch.inspect_event_attempts(item["source"], item["state"], item["event"]["event_id"],
                                                item["payload_hash"], root=alternate)
        self.assertEqual(result["stages"]["agent_turn_completed"]["status"], "confirmed")
        self.assertFalse(result["real_agent_wake_verified"])

    def test_unknown_later_attempt_does_not_hide_behind_old_process_exit(self):
        item = self.fixture
        path = item["state"] / "dispatcher-attempts.json"
        ledger = read_json(path)
        other = deepcopy(item["record"])
        other.update(attempt_id="f"*32, run_id="e"*32,
                     run_dir=str(self.root / "data/agent-service/runs" / ("e"*32)))
        ledger["events"][item["event"]["event_id"]].append(other)
        write_json(path, ledger)
        result = self.inspect()
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(result["stages"]["agent_process_exited"]["status"], "unknown")

    def test_binding_save_failure_keeps_pending_without_launch_or_worker(self):
        root = self.root / "write-failure"
        source, state = root / "data/test", root / "data/agent-delivery-test"
        store = EventStore(source)
        event = make_synthetic("listener")
        store.enqueue(event)
        before = store.path.read_bytes()
        config = root / "config/default.json"
        config.parent.mkdir(parents=True)
        config.write_bytes((dispatch.ROOT / "config/default.json").read_bytes())
        with isolated_launch(root) as launch, \
                patch.object(dispatch.shutil, "which", return_value=sys.executable), \
                patch.object(dispatch.importlib.util, "find_spec", return_value=True), \
                patch.object(dispatch, "command", return_value=["fixture-never-launched.exe"]), \
                patch.object(dispatch, "_save_binding", side_effect=OSError("fixture storage failure")), \
                patch.object(dispatch, "spawn") as spawn:
            code = dispatch.run(root / "run", source, state, execute=True, root=root, max_seconds=1)
        self.assertEqual(code, 1)
        self.assertEqual(store.get_event(event["event_id"])["delivery_status"], "pending")
        self.assertEqual(store.path.read_bytes(), before)
        self.assertFalse(launch.gate_entered())
        spawn.assert_not_called()
        record = read_json(state / "dispatcher-attempts.json")["events"][event["event_id"]][0]
        self.assertEqual(record["state"], "not_started")
        self.assertTrue(record["child_exited"])
