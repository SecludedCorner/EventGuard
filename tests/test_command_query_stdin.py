"""Actual Windows command pipeline; fixed inert health metadata only."""
import json
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eventguard.cli import main
from eventguard.processes import spawn, finish

ROOT = Path(__file__).resolve().parents[1]


class CommandQueryStdinTests(unittest.TestCase):
    def call(self, content, *, keep_open=False, input_file=None):
        with tempfile.TemporaryDirectory() as temporary:
            child = spawn([sys.executable, "-B", "-c",
                "import sys; from eventguard.cli import main; raise SystemExit(main(sys.argv[2:],root=sys.argv[1]))",
                temporary, "--format", "json", "query", "health", "--args", "-"],
                env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), stdin=input_file if input_file is not None else subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                if keep_open:
                    child.stdin.write(content)
                    child.stdin.flush()
                    child.wait(timeout=10)  # Size refusal must not wait for producer EOF.
                    out, err = child.stdout.read(), child.stderr.read()
                    child.stdin.close()
                elif isinstance(content, tuple):
                    for chunk in content:
                        child.stdin.write(chunk)
                        child.stdin.flush()
                        with self.assertRaises(subprocess.TimeoutExpired):
                            child.wait(timeout=.1)  # No dispatch before real EOF.
                    out, err = child.communicate(timeout=10)
                else:
                    out, err = child.communicate(input=content if input_file is None else None, timeout=10)
            finally:
                receipt = finish(child, reason="test_teardown", grace=1)
            self.assertTrue(receipt["child_exited"])
            self.assertFalse(receipt["forcibly_terminated"])
            self.assertEqual(receipt["remaining_owned_processes"], 0)
            self.assertEqual(err, b"")
            self.assertEqual(list(Path(temporary).iterdir()), [])
            return child.returncode, json.loads(out)

    def test_utf8_bom_and_plain_input_retain_request_identity(self):
        for prefix in (b"", b"\xef\xbb\xbf"):
            code, value = self.call(prefix + b'{"request_id":"stdin-json"}\n')
            self.assertEqual((code, value["status"], value["request_id"]), (0, "ok", "stdin-json"))

    def test_invalid_duplicate_depth_and_oversized_input_never_dispatch(self):
        for content, error in ((b'{"request_id":"first","request_id":"second"}', "query_input_duplicate_key"),
                               (b'{"max_rows":' + b'['*32 + b'0' + b']'*32 + b'}', "query_input_depth_exceeded"),
                               (b'\xff', "input_or_config_validation_failed"),
                               (b'{', "input_or_config_validation_failed")):
            code, value = self.call(content)
            self.assertEqual((code, value["status"], value["error_code"]), (2, "invalid_request", error))
        self.assertEqual(self.call(b" "*8193, keep_open=True)[0], 2)

    def test_interactive_stdin_is_refused_without_reading(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True
            def read(self, *_args):
                raise AssertionError("terminal must not block")
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as temporary, patch("sys.stdin", Terminal()), redirect_stdout(output):
            code = main(["--format", "json", "query", "health", "--args", "-"], root=temporary)
        self.assertEqual((code, json.loads(output.getvalue())["status"]), (2, "invalid_request"))

    def test_fragmented_bom_and_json_wait_for_eof_then_preserve_identity(self):
        code, value = self.call((b"\xef", b"\xbb", b'\xbf{"request_id":', b'"fragmented-input"}'))
        self.assertEqual((code, value["status"], value["request_id"]), (0, "ok", "fragmented-input"))

    def test_exact_byte_limit_and_regular_file_redirection(self):
        raw = b'{"request_id":"exact-byte-limit"}'
        exact = raw + b" " * (8192 - len(raw))
        for from_file in (False, True):
            with self.subTest(from_file=from_file), tempfile.TemporaryFile() as source:
                source.write(exact)
                source.seek(0)
                code, value = self.call(exact, input_file=source if from_file else None)
                self.assertEqual((code, value["status"], value["request_id"]), (0, "ok", "exact-byte-limit"))
        code, value = self.call(exact + b" ", keep_open=True)
        self.assertEqual((code, value["status"]), (2, "invalid_request"))

    @unittest.skipUnless(os.name == "nt" and shutil.which("pwsh.exe"), "Windows PowerShell unavailable")
    def test_windows_wrapper_accepts_json_pipeline(self):
        entry = str(ROOT / "EventGuard.cmd").replace("'", "''")
        script = "'{\"request_id\":\"stdin-wrapper\"}' | & '" + entry + "' --format json query health --args -; exit $LASTEXITCODE"
        child = spawn([shutil.which("pwsh.exe"), "-NoProfile", "-Command", script],
                      cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = child.communicate(timeout=20)
        finally:
            receipt = finish(child, reason="test_teardown", grace=1)
        self.assertTrue(receipt["child_exited"])
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.assertEqual(stderr, b"")
        value = json.loads(stdout)
        self.assertEqual(child.returncode, 0)
        self.assertEqual(value["request_id"], "stdin-wrapper")
