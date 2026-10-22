"""Local ownership, bounded capture and leaf-path safety. No model or network."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from eventguard.acceptance_control import FileLease, read_json, write_json
from eventguard.acceptance_process import main as capture_main
from eventguard.capture_receipt import validate_receipt
from eventguard.local_wait import _guard, LocalWaitError
from eventguard import codex_acceptance as legacy
from eventguard.processes import spawn, finish, remaining_owned
from budget_fixtures import capture_fixture as capture

ROOT = legacy.ROOT


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_lease_is_exclusive_between_processes_and_released_naturally(self):
        path = self.root / "owner.lock"
        lease = FileLease(path)
        self.assertTrue(lease.acquire())
        source = 'from pathlib import Path; from eventguard.acceptance_control import FileLease; import sys; lease=FileLease(Path(sys.argv[1])); ok=lease.acquire(); lease.release(); raise SystemExit(0 if ok else 3)'
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        def check_exit(expected):
            child = spawn([sys.executable, "-B", "-c", source, str(path)], env=environment,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                output, errors = child.communicate(timeout=5)
                self.assertEqual(child.returncode, expected, errors)
            finally:
                receipt = finish(child, "test_teardown", grace=.1)
                self.assertFalse(receipt["forcibly_terminated"])
                if os.name == "nt":
                    self.assertEqual(receipt["remaining_owned_processes"], 0)
        try:
            check_exit(3)
        finally:
            lease.release()
        check_exit(0)
        self.assertTrue(path.exists(), "Never unlink a shared OS lock file")

    def test_capture_drains_both_streams_but_caps_saved_bytes(self):
        source = 'import sys; sys.stdout.buffer.write(b"a"*100000); sys.stderr.buffer.write(b"b"*100000)'
        self.assertEqual(capture([sys.executable, "-c", source], self.root, "a" * 32, "fixture", limit=1024), 0)
        receipt = read_json(self.root / "capture-exit.json")
        self.assertTrue(receipt["capture_complete"])
        self.assertTrue(receipt["stdout_truncated"])
        self.assertTrue(receipt["stderr_truncated"])
        self.assertEqual((self.root / "codex.jsonl").stat().st_size, 1024)
        self.assertEqual((self.root / "codex.stderr.txt").stat().st_size, 1024)

    @unittest.skipUnless(os.name == "nt", "real Windows Job Object timeout behavior")
    def test_owned_timeout_runner_waits_for_receipt_and_exits_without_residuals(self):
        run_dir = self.root / "run"
        run_dir.mkdir()
        baseline = remaining_owned()
        token = "c" * 32
        # Shared capture owns a real private Windows Job. This is Python, not Codex.
        began = time.monotonic()
        result = capture([sys.executable, "-B", "-c", "import time; time.sleep(.5)"],
                         run_dir, token, "synthetic timeout fixture", timeout_seconds=.05)
        self.assertEqual(result, 0, "Complete capture does not itself mean successful delivery")
        self.assertLess(time.monotonic() - began, 5)
        receipt_path = run_dir / "capture-exit.json"
        receipt = read_json(receipt_path)
        started = read_json(run_dir / "capture-start.json")
        self.assertTrue(receipt["capture_complete"])
        self.assertEqual(receipt["codex_exit_code"], 0)
        self.assertTrue(receipt["child_exited"])
        self.assertEqual(receipt["process"]["remaining_owned_processes"], 0)
        self.assertTrue(receipt["process"]["managed"])
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(receipt["stop_reason"], "timeout")
        self.assertEqual(validate_receipt(receipt, started, token), [])
        self.assertIn("natural_capture_exit_not_verified", validate_receipt(receipt, started, token, require_success=True))
        self.assertFalse((run_dir / "summary.json").exists(), "Capture must not invent tool delivery success")
        self.assertEqual(remaining_owned(), baseline)
        self.evidence = {"scope": "real_windows_job_synthetic_python_not_codex", "case": "capture_timeout_receipt",
                         "capture": receipt, "known_exit": True, "successful_delivery": False,
                         "remaining_owned_after": remaining_owned()}
        lease = FileLease(run_dir / "capture.lock")
        deadline = time.monotonic() + 3
        while not lease.acquire() and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertIsNotNone(lease.stream)
        lease.release()

    def test_metadata_limit_and_parent_alias_refused(self):
        path = self.root / "large.json"
        path.write_text('{"x":"' + 'a' * 1000 + '"}')
        with self.assertRaisesRegex(LocalWaitError, "capacity"):
            read_json(path, limit=100)
        with self.assertRaisesRegex(LocalWaitError, "parent_path"):
            _guard(self.root / "child" / "..")

    @unittest.skipUnless(os.name == "nt", "Windows metadata sharing")
    def test_metadata_replace_retries_transient_sharing_but_preserves_persistent_denial(self):
        path = self.root / "shared.json"
        original = os.replace
        sharing = PermissionError("synthetic metadata sharing")
        sharing.winerror = 32
        calls = []
        def transient(source, destination):
            calls.append(True)
            if len(calls) == 1:
                raise sharing
            return original(source, destination)
        with patch("eventguard.acceptance_control.os.replace", side_effect=transient):
            write_json(path, {"version": 1})
        self.assertEqual(len(calls), 2)
        self.assertEqual(read_json(path), {"version": 1})
        with patch("eventguard.acceptance_control.os.replace", side_effect=sharing) as replace, \
             patch("eventguard.acceptance_control.time.sleep"):
            with self.assertRaises(PermissionError):
                write_json(path, {"version": 2})
            self.assertEqual(replace.call_count, 20)
        self.assertEqual(read_json(path), {"version": 1})
        self.assertEqual(list(self.root.glob(".acceptance-*.tmp")), [])

    def test_symlink_write_and_capture_never_follow_leaf(self):
        target = self.root / "unrelated.txt"
        target.write_text("PRIVATE_SENTINEL")
        leaf = self.root / "metadata.json"
        try:
            leaf.symlink_to(target)
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaisesRegex(LocalWaitError, "redirect"):
            write_json(leaf, {"replace": True})
        (self.root / "codex.jsonl").symlink_to(target)
        self.assertEqual(capture([sys.executable, "-c", "pass"], self.root, "b" * 32, "fixture"), 2)
        self.assertEqual(target.read_text(), "PRIVATE_SENTINEL")

    def test_corrupt_state_and_foreign_directory_refuse_retry_without_launch(self):
        run_dir = self.root / "run"
        run_dir.mkdir()
        original = {"run_id": "a" * 32, "attempt_id": "b" * 32, "attempt": 1,
                    "state": "pending_child_exit", "cli_started": True, "wait_ids_before": []}
        write_json(run_dir / "acceptance.json", {"kind": legacy.KIND, "run_id": original["run_id"]})
        write_json(run_dir / "status.json", original)
        for field, value in (("cli_started", None), ("run_id", None), ("attempt_id", "z" * 32),
                             ("attempt", True), ("state", []), ("wait_ids_before", [[]])):
            changed = dict(original, **{field: value})
            write_json(run_dir / "status.json", changed)
            before = (run_dir / "status.json").read_bytes()
            with self.subTest(field=field), patch.object(legacy, "spawn") as launch:
                self.assertEqual(legacy.main(["status", "--run-dir", str(run_dir)]), 2)
                self.assertEqual(legacy.main(["retry", "--run-dir", str(run_dir)]), 2)
                launch.assert_not_called()
            self.assertEqual((run_dir / "status.json").read_bytes(), before)
        write_json(run_dir / "status.json", original)
        (run_dir / "runtime").mkdir()
        lease = FileLease(run_dir / "runtime/stdio-owner.lock")
        self.assertTrue(lease.acquire())
        try:
            self.assertEqual(legacy.retry(run_dir), 2)
            self.assertEqual(legacy.status(run_dir), original)
        finally:
            lease.release()

    def test_generic_capture_entry_is_retired_and_does_not_spawn_or_create_directory(self):
        run_dir = self.root / "absent"
        with patch("eventguard.acceptance_process.spawn") as launch:
            self.assertEqual(capture_main(["--attempt-dir", str(run_dir), "--attempt-id", "d" * 32,
                                          "--", sys.executable, "-c", "raise SystemExit(0)"]), 2)
            launch.assert_not_called()
        self.assertFalse(run_dir.exists())
