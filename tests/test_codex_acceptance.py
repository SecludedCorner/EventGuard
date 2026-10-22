"""Legacy evidence semantics and retired entry safety; no real model or native query."""
import asyncio
from contextlib import closing
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from eventguard import codex_acceptance as legacy
from eventguard import delivery_validation
from eventguard.acceptance_control import read_json, write_json, FileLease
from eventguard.acceptance_evidence import assess
from eventguard.capture_receipt import validate_receipt
from eventguard.events.store import StoreError
from eventguard.local_wait import LocalWait, LocalWaitError
from eventguard.synthetic import make_synthetic
from test_capture_receipt import fixture as receipt_fixture

ROOT = legacy.ROOT


def trace(replies):
    """Explicit legacy-shaped fixture trace, never evidence of a real agent."""
    tools = ("wait_for_event", "query_evidence", "ack_event")
    args = ({"timeout_seconds": 30}, {"event_id": replies[0]["event_id"]},
            {"event_id": replies[0]["event_id"], "query_id": replies[1]["query_id"], "decision": "reviewed_synthetic"})
    return [{"type": "item.completed", "item": {"id": "fixture-" + str(n),
            "type": "mcp_tool_call", "tool": tool, "server": "eventguard_local",
            "status": "completed", "error": None, "arguments": arguments,
            "result": {"content": [{"type": "text", "text": json.dumps(reply)}]}}}
            for n, (tool, arguments, reply) in enumerate(zip(tools, args, replies))] + [{"type": "turn.completed"}]


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "run"

    def saved_state(self, **changes):
        """Create a labelled historical fixture, rather than invoking a retired writer."""
        self.root.mkdir(parents=True, exist_ok=True)
        state = {"state": "pending_child_exit", "cli_started": True, "run_id": "c" * 32,
                 "attempt": 1, "attempt_id": "a" * 32, "wait_ids_before": [], **changes}
        write_json(self.root / "acceptance.json", {"kind": legacy.KIND, "run_id": state["run_id"]})
        write_json(self.root / "status.json", state)
        return state

    def bytes_before(self):
        # Windows locks the owned byte against readers too; inspect metadata and
        # runtime payloads, while lease tests separately prove lock ownership.
        return {p.relative_to(self.root).as_posix():
                ("lock", p.stat().st_size, p.stat().st_mtime_ns) if p.suffix == ".lock" else p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def test_command_is_scoped_and_shell_free_with_windows_paths(self):
        args = legacy.command("codex", Path("C:/Python313/python.exe"), Path("C:/test folder/runtime"))
        self.assertIn("--ephemeral", args)
        self.assertIn("--ignore-user-config", args)
        self.assertIn("read-only", args)
        self.assertIn("features.shell_tool=false", args)
        self.assertTrue(any("tool_timeout_sec=60" in arg and "--single-wait" in arg for arg in args))
        self.assertFalse(any("bypass" in arg for arg in args))
        config = tomllib.loads(next(value for value in args if value.startswith("mcp_servers.")))
        server = config["mcp_servers"]["eventguard_local"]
        self.assertEqual(server["enabled_tools"], ["wait_for_event", "query_evidence", "ack_event"])
        self.assertEqual(server["tools"], {name: {"approval_mode": "approve"} for name in server["enabled_tools"]})
        self.assertNotIn("default_tools_approval_mode", server)
        self.assertNotIn("approval_policy", config)

    def test_retired_launchers_never_create_or_overwrite_directory_even_when_capability_exists(self):
        with patch.object(legacy, "spawn") as launch, patch.object(legacy.shutil, "which", return_value="codex.exe"):
            for action in ("run", "retry"):
                self.assertEqual(getattr(legacy, action)(self.root), 2)
                self.assertEqual(legacy.main([action, "--run-dir", str(self.root)]), 2)
            launch.assert_not_called()
        self.assertFalse(self.root.exists())
        saved = self.saved_state(state="passed")
        before = self.bytes_before()
        self.assertEqual(legacy.run(self.root), 2)
        self.assertEqual(legacy.retry(self.root), 2)
        self.assertEqual(legacy.status(self.root), saved)
        self.assertEqual(legacy.main(["status", "--run-dir", str(self.root)]), 0)
        self.assertEqual(legacy.main(["stop", "--run-dir", str(self.root)]), 0)
        self.assertEqual(self.bytes_before(), before)
        self.assertFalse((self.root / "stop.request").exists())

    def test_program_producer_wait_timing_and_legacy_ack_remain_assessable(self):
        backend = LocalWait(self.root / "runtime")
        event = make_synthetic("listener")
        async def receive():
            waiter = asyncio.create_task(backend.wait_for_event(1))
            await asyncio.sleep(.03)
            self.assertFalse(waiter.done())
            backend.store.enqueue(event)
            return await waiter
        waited = asyncio.run(receive())
        query = backend.query_evidence(event["event_id"])
        ack = backend.ack_event(event["event_id"], query["query_id"], "reviewed_synthetic")
        summary = assess(trace((waited, query, ack)), backend._load(), event["event_id"], 0, True)
        self.assertTrue(summary["passed"], summary)
        self.assertTrue(summary["outbox_acknowledged"])
        self.assertGreaterEqual(summary["waits"][0]["duration_seconds"], .03)
        self.assertEqual(backend.store.get_event(event["event_id"])["delivery_status"], "ack")
        self.assertEqual(backend.ack_event(event["event_id"], query["query_id"], "reviewed_synthetic"), ack)
        with closing(sqlite3.connect(backend.store.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 1)
        self.assertFalse(ack["real_agent_wake_verified"])

    def test_cancelled_wait_suppresses_producer_and_retired_stop_is_scoped(self):
        backend = LocalWait(self.root / "runtime")
        async def cancel():
            waiter = asyncio.create_task(backend.wait_for_event(1))
            await asyncio.sleep(.01)
            self.assertFalse(waiter.done())
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
        asyncio.run(cancel())
        self.assertEqual(backend._load()["waits"][-1]["status"], "cancelled")
        self.assertEqual(backend.store.stats()["total"], 0)
        state = self.saved_state(state="pending_child_exit")
        self.assertEqual(legacy.main(["stop", "--run-dir", str(self.root)]), 0)
        self.assertEqual(read_json(self.root / "stop.request")["attempt_id"], state["attempt_id"])
        self.assertFalse((self.root / "synthetic-event.json").exists())

    def test_status_does_not_finalize_pending_evidence_or_mutate_any_saved_bytes(self):
        saved = self.saved_state()
        write_json(self.root / "capture-exit.json", {"attempt_id": saved["attempt_id"],
                   "capture_complete": True, "codex_exit_code": 0})
        before = self.bytes_before()
        with patch.object(legacy, "_complete", side_effect=AssertionError("reader must not finalize")), \
             patch.object(legacy, "write_json", side_effect=AssertionError("reader must not write")):
            self.assertEqual(legacy.status(self.root), saved)
        self.assertEqual(self.bytes_before(), before)
        self.assertEqual(legacy.status(self.root)["state"], "pending_child_exit")
        self.assertFalse((self.root / "summary.json").exists())
        self.assertFalse((self.root / "runtime").exists())

    def test_same_event_retry_semantics_preserve_query_and_first_attempt_bytes(self):
        backend = LocalWait(self.root / "runtime")
        event = make_synthetic("listener")
        backend.store.enqueue(event)
        waited = asyncio.run(backend.wait_for_event(1))
        query = backend.query_evidence(event["event_id"])
        initial = backend._load()
        first_trace = trace((waited, query))[:-1] + [{"type": "turn.failed"}]
        first_summary = assess(first_trace, initial, event["event_id"], 7, False)
        self.assertFalse(first_summary["passed"])
        self.assertEqual(backend.store.get_event(event["event_id"])["delivery_status"], "pending")
        write_json(self.root / "attempt-summary.json", first_summary)
        (self.root / "codex.jsonl").write_bytes(b"\n".join(json.dumps(r).encode() for r in first_trace))
        before = {name: (self.root / name).read_bytes() for name in ("codex.jsonl", "attempt-summary.json")}
        (self.root / "stop.request").touch()  # Old orchestration data cannot alter a durable backend.
        restarted = LocalWait(self.root / "runtime")
        second_wait = asyncio.run(restarted.wait_for_event(1))
        second_query = restarted.query_evidence(event["event_id"])
        ack = restarted.ack_event(event["event_id"], second_query["query_id"], "reviewed_synthetic")
        after = restarted._load()
        summary = assess(trace((second_wait, second_query, ack)), after, event["event_id"], 0, True,
                         wait_ids_before=[w["wait_id"] for w in initial["waits"]])
        self.assertEqual(list(after["events"]), [event["event_id"]])
        self.assertEqual(second_query["query_id"], query["query_id"])
        self.assertEqual(len(after["waits"]), 2)
        self.assertTrue(summary["passed"], summary)
        self.assertEqual(len(summary["waits"]), 1)
        self.assertEqual({name: (self.root / name).read_bytes() for name in before}, before)

    def test_forced_exit_never_upgrades_otherwise_valid_fake_tool_proof(self):
        backend = LocalWait(self.root / "runtime")
        event = make_synthetic("listener"); backend.store.enqueue(event)
        waited = asyncio.run(backend.wait_for_event(1)); query = backend.query_evidence(event["event_id"])
        ack = backend.ack_event(event["event_id"], query["query_id"], "reviewed_synthetic")
        summary = assess(trace((waited, query, ack)), backend._load(), event["event_id"], 0, True)
        self.assertTrue(summary["passed"])
        receipt, started = receipt_fixture()
        self.assertEqual(validate_receipt(receipt, started, "a" * 32, require_success=True), [])
        receipt["forcibly_terminated"] = receipt["process"]["forcibly_terminated"] = True
        errors = validate_receipt(receipt, started, "a" * 32, require_success=True)
        self.assertIn("owned_tree_forced_or_unknown", errors)
        self.assertFalse(summary["passed"] and not errors)

    def test_result_persisted_before_ack_failure_is_reused_after_restart(self):
        backend = LocalWait(self.root / "runtime")
        event = make_synthetic("listener"); backend.store.enqueue(event)
        waited = asyncio.run(backend.wait_for_event(1)); query = backend.query_evidence(waited["event_id"])
        with patch.object(backend.store, "acknowledge", side_effect=StoreError("fixture_failure")):
            with self.assertRaisesRegex(LocalWaitError, "result_preserved"):
                backend.ack_event(event["event_id"], query["query_id"], "reviewed_synthetic")
        result = deepcopy(backend._load()["events"][event["event_id"]]["result"])
        self.assertNotEqual(backend.store.get_event(event["event_id"])["delivery_status"], "ack")
        restarted = LocalWait(self.root / "runtime")
        ack = restarted.ack_event(event["event_id"], query["query_id"], "reviewed_synthetic")
        self.assertEqual(restarted._load()["events"][event["event_id"]]["result"], result)
        self.assertEqual(ack["result_id"], result["result_id"])
        self.assertTrue(ack["outbox_acknowledged"])

    def test_historical_attempt_limit_and_live_lease_cannot_reenable_retired_retry(self):
        saved = self.saved_state(attempt=3, state="failed")
        lease = FileLease(self.root / "runner.lock")
        self.assertTrue(lease.acquire())
        try:
            before = self.bytes_before()
            with patch.object(legacy, "spawn") as launch:
                for _ in range(4):
                    self.assertEqual(legacy.retry(self.root), 2)
                    self.assertEqual(legacy.main(["retry", "--run-dir", str(self.root)]), 2)
                launch.assert_not_called()
            self.assertEqual(self.bytes_before(), before)
            self.assertEqual(legacy.status(self.root), saved)
        finally:
            lease.release()
        with self.assertRaisesRegex(LocalWaitError, "invalid_acceptance_attempt"):
            legacy._attempt_dir(self.root, 4)

    def test_current_wrapper_preflight_is_refused_without_enqueuing_or_model(self):
        manifest = delivery_validation.prepare(self.root, "single")
        with patch.object(delivery_validation.shutil, "which", return_value="C:/npm/codex.cmd"), \
             patch.object(delivery_validation, "capture") as launch:
            with self.assertRaisesRegex(ValueError, "native_codex_required"):
                delivery_validation.execute(self.root, manifest, "codex")
            launch.assert_not_called()
        self.assertEqual(manifest["enqueued"], [])
        self.assertEqual(manifest["stages"], [])

    def test_symlinked_status_and_stop_leaf_never_followed(self):
        self.saved_state()
        target = Path(self.temp.name) / "unrelated.txt"
        target.write_text("PRIVATE_SENTINEL")
        (self.root / "status.json").unlink()
        try:
            (self.root / "status.json").symlink_to(target)
        except OSError:
            self.skipTest("symlink creation unavailable")
        self.assertEqual(legacy.main(["status", "--run-dir", str(self.root)]), 2)
        self.assertEqual(legacy.main(["stop", "--run-dir", str(self.root)]), 2)
        self.assertEqual(target.read_text(), "PRIVATE_SENTINEL")
