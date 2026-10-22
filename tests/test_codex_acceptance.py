"""Owned fake-CLI orchestration only; these tests never invoke a model or CI."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from unittest.mock import patch

from eventguard.codex_acceptance import ROOT, command, main, run, retry, status
from eventguard.acceptance_control import read_json, FileLease
from eventguard.local_wait import LocalWait, LocalWaitError


# Real LocalWait/SQLite behind an explicitly fake CLI; never real-agent proof.
FAKE = '''import asyncio,json,sys
from eventguard.local_wait import LocalWait
from eventguard.events.store import StoreError
backend=LocalWait(sys.argv[1])
mode=sys.argv[2]
if mode=="idle":
 asyncio.run(backend.wait_for_event(1))
 raise SystemExit(0)
if mode=="slow":
 import time
 time.sleep(.8)
 raise SystemExit(0)
reply=asyncio.run(backend.wait_for_event(5))
event=reply["event_id"]
query=backend.query_evidence(event)
def output(tool,args,result):
 print(json.dumps({"type":"item.completed","item":{"type":"mcp_tool_call","tool":tool,"server":"eventguard_local","status":"completed","error":None,"arguments":args,"result":{"content":[{"type":"text","text":json.dumps(result)}]}}}),flush=True)
output("wait_for_event",{"timeout_seconds":30},reply)
output("query_evidence",{"event_id":event},query)
if mode=="fail_query":
 print(json.dumps({"type":"turn.failed"}))
 raise SystemExit(7)
if mode=="fail_ack":
 def broken(*args): raise StoreError("fixture_failure")
 backend.store.acknowledge=broken
 backend.ack_event(event,query["query_id"],"reviewed_synthetic")
ack=backend.ack_event(event,query["query_id"],"reviewed_synthetic")
output("ack_event",{"event_id":event,"query_id":query["query_id"],"decision":"reviewed_synthetic"},ack)
print(json.dumps({"type":"turn.completed"}))
'''


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "run"
        self.script = Path(self.temp.name) / "fake.py"
        self.script.write_text(FAKE)
        self.children = []
        self.addCleanup(self.wait_for_owned_children)

    def wait_for_owned_children(self):
        for child in self.children:
            self.assertIsNotNone(child.wait(timeout=8), "Owned fixture must exit naturally")

    def fake_cli(self, mode="success", stop=False):
        stack = ExitStack()
        original_popen = subprocess.Popen

        def launch(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            self.children.append(child)
            if stop:
                (self.root / "stop.request").touch()
            return child

        stack.enter_context(patch("eventguard.codex_acceptance.command", return_value=[sys.executable, "-B", str(self.script), str(self.root / "runtime"), mode]))
        stack.enter_context(patch("eventguard.codex_acceptance.importlib.util.find_spec", return_value=True))
        stack.enter_context(patch("eventguard.codex_acceptance.shutil.which", return_value="fake"))
        stack.enter_context(patch("eventguard.codex_acceptance.subprocess.Popen", side_effect=launch))
        stack.enter_context(patch.dict(os.environ, {"PYTHONPATH": str(ROOT / "src")}))
        return stack

    def test_command_is_scoped_and_shell_free_with_windows_paths(self):
        args = command("codex", Path('C:/Python313/python.exe'), Path('C:/test folder/runtime'))
        self.assertIn("--ephemeral", args)
        self.assertIn("--ignore-user-config", args)
        self.assertIn("read-only", args)
        self.assertIn("features.shell_tool=false", args)
        self.assertTrue(any("tool_timeout_sec=60" in arg and "--single-wait" in arg for arg in args))
        self.assertFalse(any("bypass" in arg for arg in args))
        config = tomllib.loads(next(value for value in args if value.startswith("mcp_servers.")))
        server = config["mcp_servers"]["eventguard_local"]
        self.assertEqual(server["enabled_tools"], ["wait_for_event", "query_evidence", "ack_event"])
        self.assertEqual(server["tools"], {name: {"approval_mode": "approve"}
                                         for name in server["enabled_tools"]})
        self.assertNotIn("default_tools_approval_mode", server)
        self.assertNotIn("approval_policy", config)

    def test_missing_capability_and_directory_not_overwritten(self):
        with patch("eventguard.codex_acceptance.shutil.which", return_value=None):
            self.assertEqual(run(self.root), 2)
        self.assertEqual(status(self.root)["state"], "blocked_missing_codex_or_sdk")
        with self.assertRaises(FileExistsError):
            run(self.root)
        self.assertEqual(main(["run", "--run-dir", str(self.root)]), 2)
        self.assertEqual(main(["status", "--run-dir", str(self.root)]), 0)
        self.assertEqual(main(["stop", "--run-dir", str(self.root)]), 0)
        self.assertFalse((self.root / "stop.request").exists())

    def test_owned_fake_cli_producer_timing_and_ack(self):
        with self.fake_cli():
            self.assertEqual(run(self.root, idle_seconds=.2, deadline_seconds=10), 0)
        summary = read_json(self.root / "summary.json")
        self.assertTrue(summary["outbox_acknowledged"])
        self.assertGreaterEqual(summary["waits"][0]["duration_seconds"], .2)
        self.assertEqual(status(self.root)["state"], "passed")
        self.assertTrue(read_json(self.root / "capture-exit.json")["capture_complete"])
        with self.fake_cli(), self.assertRaisesRegex(LocalWaitError, "already_acknowledged"):
            retry(self.root)
        self.assertEqual(len(self.children), 1, "ACK must prevent another model launch")

    def test_stop_suppresses_producer_and_child_exits_naturally(self):
        with self.fake_cli("idle", stop=True):
            self.assertEqual(run(self.root, idle_seconds=.1, deadline_seconds=5), 1)
        self.assertEqual(self.children[0].poll(), 0)
        self.assertEqual(status(self.root)["state"], "stopped")
        self.assertFalse((self.root / "synthetic-event.json").exists())

    def test_timeout_capture_survives_parent_and_status_finishes(self):
        with self.fake_cli("slow"):
            self.assertEqual(run(self.root, deadline_seconds=.05), 3)
            with self.assertRaisesRegex(LocalWaitError, "exit_unconfirmed"):
                retry(self.root)
        self.assertIsNone(self.children[0].poll())
        self.assertEqual(status(self.root)["state"], "pending_child_exit")
        self.children[0].wait(timeout=5)
        self.assertEqual(status(self.root)["state"], "failed")
        self.assertTrue(status(self.root)["child_exited"])
        self.assertTrue((self.root / "summary.json").exists())

    def test_same_event_retry_preserves_all_attempt_evidence(self):
        with self.fake_cli("fail_query"):
            self.assertEqual(run(self.root, idle_seconds=.1, deadline_seconds=8), 1)
        before = LocalWait(self.root / "runtime")._load()
        identity = status(self.root)["event_id"]
        query = before["events"][identity]["query_id"]
        first_trace = (self.root / "codex.jsonl").read_bytes()
        first_summary = (self.root / "attempt-summary.json").read_bytes()
        (self.root / "stop.request").touch()  # An old attempt's stop must not poison retry.
        with self.fake_cli():
            self.assertEqual(retry(self.root, deadline_seconds=8), 0)
        after = LocalWait(self.root / "runtime")._load()
        self.assertEqual(list(after["events"]), [identity])
        self.assertEqual(after["events"][identity]["query_id"], query)
        self.assertEqual(len(after["waits"]), 2)
        self.assertEqual((self.root / "codex.jsonl").read_bytes(), first_trace)
        self.assertEqual((self.root / "attempt-summary.json").read_bytes(), first_summary)
        self.assertEqual(status(self.root)["attempt"], 2)
        self.assertTrue(read_json(self.root / "attempts/0002/summary.json")["passed"])
        self.assertEqual(len(read_json(self.root / "summary.json")["waits"]), 1)

    def test_retry_reuses_result_persisted_before_ack_failure(self):
        with self.fake_cli("fail_ack"):
            self.assertEqual(run(self.root, idle_seconds=.1, deadline_seconds=8), 1)
        backend = LocalWait(self.root / "runtime")
        identity = status(self.root)["event_id"]
        result = backend._load()["events"][identity]["result"]
        self.assertNotEqual(backend.store.get_event(identity)["delivery_status"], "ack")
        with self.fake_cli():
            self.assertEqual(retry(self.root, deadline_seconds=8), 0)
        self.assertEqual(LocalWait(self.root / "runtime")._load()["events"][identity]["result"], result)

    def test_retry_budget_and_cross_process_owner_refuse_launch(self):
        with patch("eventguard.codex_acceptance.shutil.which", return_value=None):
            self.assertEqual(run(self.root), 2)
            lease = FileLease(self.root / "runner.lock")
            self.assertTrue(lease.acquire())
            try:
                with self.assertRaisesRegex(LocalWaitError, "runner_busy"):
                    retry(self.root)
            finally:
                lease.release()
            self.assertEqual(retry(self.root), 2)
            self.assertEqual(retry(self.root), 2)
            with self.assertRaisesRegex(LocalWaitError, "budget_exhausted"):
                retry(self.root)
        self.assertEqual(status(self.root)["attempt"], 3)

    def test_batch_wrapper_is_refused_without_starting_model(self):
        with patch("eventguard.codex_acceptance.shutil.which", return_value="C:/npm/codex.cmd"), patch("eventguard.codex_acceptance.importlib.util.find_spec", return_value=True), patch("eventguard.codex_acceptance.subprocess.Popen") as launch:
            self.assertEqual(run(self.root), 2)
            launch.assert_not_called()
        self.assertEqual(status(self.root)["state"], "blocked_native_codex_required")

    def test_symlinked_status_and_stop_leaf_never_followed(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink not available")
        with patch("eventguard.codex_acceptance.shutil.which", return_value=None):
            run(self.root)
        target = Path(self.temp.name) / "unrelated.txt"
        target.write_text("PRIVATE_SENTINEL")
        (self.root / "status.json").unlink()
        try:
            (self.root / "status.json").symlink_to(target)
        except OSError:
            self.skipTest("symlink creation unavailable")
        self.assertEqual(main(["status", "--run-dir", str(self.root)]), 2)
        self.assertEqual(target.read_text(), "PRIVATE_SENTINEL")
