"""Acceptance evidence rejection and owned fake-CLI orchestration; no model calls."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eventguard.codex_acceptance import assess, command, main, run


class AcceptanceTests(unittest.TestCase):
    def evidence(self):
        identity, query = "evt-test", "query-test"
        ledger = {"events": {identity: {"query_id": query, "result": {
            "event_id": identity, "query_id": query, "decision": "reviewed_synthetic"}}},
            "waits": [{"status": "event_available", "started_at": "start", "finished_at": "end"}]}
        calls = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "eventguard_local",
                 "tool": name, "status": "completed", "arguments": args}}
                 for name, args in [("wait_for_event", {"timeout_seconds": 30}),
                                    ("query_evidence", {"event_id": identity}),
                                    ("ack_event", {"event_id": identity, "query_id": query,
                                                   "decision": "reviewed_synthetic"})]]
        return calls, ledger, identity

    def test_requires_tool_trace_and_durable_ack_not_final_prose(self):
        calls, ledger, identity = self.evidence()
        self.assertTrue(assess(calls, ledger, identity, 0, True)["passed"])
        for trace, code, ack in [([], 0, True), (calls, 1, True), (calls, 0, False),
                                  (calls + calls[:1], 0, True), (calls[::-1], 0, True)]:
            self.assertFalse(assess(trace, ledger, identity, code, ack)["passed"])
        calls[2]["item"]["arguments"]["event_id"] = "evt-other"
        self.assertFalse(assess(calls, ledger, identity, 0, True)["passed"])

    def test_tool_error_and_wrong_server_and_missing_result_fail(self):
        calls, ledger, identity = self.evidence()
        calls[0]["item"]["error"] = {"message": "synthetic_failure"}
        self.assertFalse(assess(calls, ledger, identity, 0, True)["passed"])
        calls[0]["item"].pop("error")
        calls[0]["item"]["server"] = "other"
        self.assertFalse(assess(calls, ledger, identity, 0, True)["passed"])
        self.assertFalse(assess([], {}, None, 0, False)["passed"])

    def test_command_is_scoped_and_shell_free_with_windows_paths(self):
        args = command("codex", Path('C:/Python313/python.exe'), Path('C:/test folder/runtime'))
        self.assertIn("--ephemeral", args)
        self.assertIn("--ignore-user-config", args)
        self.assertIn("read-only", args)
        self.assertIn("features.shell_tool=false", args)
        self.assertTrue(any("tool_timeout_sec=60" in arg for arg in args))
        self.assertFalse(any("bypass" in arg for arg in args))

    def test_missing_capability_and_evidence_directory_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            with patch("eventguard.codex_acceptance.shutil.which", return_value=None):
                self.assertEqual(run(root), 2)
            self.assertEqual(json.loads((root / "status.json").read_text())["state"],
                             "blocked_missing_codex_or_sdk")
            with self.assertRaises(FileExistsError):
                run(root)
            self.assertEqual(main(["status", "--run-dir", str(root)]), 0)
            self.assertEqual(main(["stop", "--run-dir", str(root)]), 0)
            self.assertTrue((root / "stop.request").exists())

    def test_owned_fake_cli_exercises_producer_timing_and_ack(self):
        # Explicit protocol fixture, NOT real-agent evidence. Executes in an owned child.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            script = Path(temp) / "fake.py"
            script.write_text('''import asyncio,json,sys
from eventguard.local_wait import LocalWait
backend=LocalWait(sys.argv[1])
reply=asyncio.run(backend.wait_for_event(5))
event=reply["event_id"]
query=backend.query_evidence(event)["query_id"]
backend.ack_event(event,query,"reviewed_synthetic")
for tool,args in [("wait_for_event",{"timeout_seconds":30}),("query_evidence",{"event_id":event}),("ack_event",{"event_id":event,"query_id":query,"decision":"reviewed_synthetic"})]:
 print(json.dumps({"type":"item.completed","item":{"type":"mcp_tool_call","tool":tool,"server":"eventguard_local","status":"completed","arguments":args}}))
''')
            from eventguard.codex_acceptance import ROOT
            with patch("eventguard.codex_acceptance.command", return_value=[sys.executable, "-B", str(script), str(root / "runtime")]), patch("eventguard.codex_acceptance.importlib.util.find_spec", return_value=True), patch("eventguard.codex_acceptance.shutil.which", return_value="fake"):
                # Child needs only the source package, never authentication.
                import os
                with patch.dict(os.environ, {"PYTHONPATH": str(ROOT / "src")}):
                    self.assertEqual(run(root, idle_seconds=.2, deadline_seconds=10), 0)
            summary = json.loads((root / "summary.json").read_text())
            self.assertTrue(summary["outbox_acknowledged"])
            self.assertGreaterEqual(summary["waits"][0]["duration_seconds"], .2)
            self.assertEqual(json.loads((root / "status.json").read_text())["state"], "passed")

    def test_stop_suppresses_producer_and_child_exits_naturally(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            script = Path(temp) / "idle.py"
            script.write_text('import asyncio,sys\nfrom eventguard.local_wait import LocalWait\n'
                              'asyncio.run(LocalWait(sys.argv[1]).wait_for_event(1))\n')
            original_popen = subprocess.Popen
            children = []

            def launch(*args, **kwargs):
                child = original_popen(*args, **kwargs)
                children.append(child)
                (root / "stop.request").touch()
                return child

            from eventguard.codex_acceptance import ROOT
            import os
            with patch("eventguard.codex_acceptance.command", return_value=[sys.executable, "-B", str(script), str(root / "runtime")]), patch("eventguard.codex_acceptance.importlib.util.find_spec", return_value=True), patch("eventguard.codex_acceptance.shutil.which", return_value="fake"), patch("eventguard.codex_acceptance.subprocess.Popen", side_effect=launch), patch.dict(os.environ, {"PYTHONPATH": str(ROOT / "src")}):
                self.assertEqual(run(root, idle_seconds=.1, deadline_seconds=5), 1)
            self.assertEqual(children[0].poll(), 0)
            self.assertEqual(json.loads((root / "status.json").read_text())["state"], "stopped")
            summary = json.loads((root / "summary.json").read_text())
            self.assertIsNone(summary["event_id"])
            self.assertFalse(summary["passed"])

    def test_observation_timeout_reports_pending_without_killing_child(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            original_popen = subprocess.Popen
            children = []

            def launch(*args, **kwargs):
                child = original_popen(*args, **kwargs)
                children.append(child)
                return child

            with patch("eventguard.codex_acceptance.command", return_value=[sys.executable, "-c", "import time; time.sleep(.8)"]), patch("eventguard.codex_acceptance.importlib.util.find_spec", return_value=True), patch("eventguard.codex_acceptance.shutil.which", return_value="fake"), patch("eventguard.codex_acceptance.subprocess.Popen", side_effect=launch):
                self.assertEqual(run(root, deadline_seconds=.05), 3)
            self.assertIsNone(children[0].poll())
            self.assertEqual(json.loads((root / "status.json").read_text())["state"], "pending_child_exit")
            self.assertFalse((root / "summary.json").exists())
            self.assertEqual(children[0].wait(timeout=5), 0)
