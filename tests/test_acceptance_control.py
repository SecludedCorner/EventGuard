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
from eventguard.acceptance_process import capture
from eventguard.local_wait import _guard, LocalWaitError
from eventguard.codex_acceptance import main, run, retry, ROOT


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
        try:
            result = subprocess.run([sys.executable, "-B", "-c", source, str(path)], env=environment, timeout=5)
            self.assertEqual(result.returncode, 3)
        finally:
            lease.release()
        result = subprocess.run([sys.executable, "-B", "-c", source, str(path)], env=environment, timeout=5)
        self.assertEqual(result.returncode, 0)
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

    def test_capture_receipt_survives_actual_runner_process_exit(self):
        run_dir = self.root / "run"
        script = self.root / "runner.py"
        source = '''import sys
from pathlib import Path
from unittest.mock import patch
from eventguard.codex_acceptance import run
with patch("eventguard.codex_acceptance.command",return_value=[sys.executable,"-c","import time; time.sleep(.5)"]), patch("eventguard.codex_acceptance.importlib.util.find_spec",return_value=True), patch("eventguard.codex_acceptance.shutil.which",return_value="fake"):
 raise SystemExit(run(Path(sys.argv[1]),deadline_seconds=.05))
'''
        script.write_text(source)
        result = subprocess.run([sys.executable, "-B", str(script), str(run_dir)],
                                env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), timeout=5)
        self.assertEqual(result.returncode, 3)
        receipt_path = run_dir / "capture-exit.json"
        deadline = time.monotonic() + 5
        while not receipt_path.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        receipt = read_json(receipt_path)
        self.assertTrue(receipt["capture_complete"])
        self.assertEqual(receipt["codex_exit_code"], 0)
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
        with patch("eventguard.codex_acceptance.shutil.which", return_value=None):
            run(run_dir)
        original = read_json(run_dir / "status.json")
        for field, value in (("cli_started", None), ("run_id", None), ("attempt_id", "z" * 32),
                             ("attempt", True), ("state", []), ("wait_ids_before", [[]])):
            changed = dict(original, **{field: value})
            write_json(run_dir / "status.json", changed)
            with self.subTest(field=field), patch("eventguard.codex_acceptance.subprocess.Popen") as launch:
                self.assertEqual(main(["retry", "--run-dir", str(run_dir)]), 2)
                launch.assert_not_called()
        write_json(run_dir / "status.json", original)
        lease = FileLease(run_dir / "runtime/stdio-owner.lock")
        self.assertTrue(lease.acquire())
        try:
            with self.assertRaisesRegex(LocalWaitError, "stdio_server_still_owned"):
                retry(run_dir)
        finally:
            lease.release()
