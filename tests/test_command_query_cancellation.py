"""Injected cancellation through actual CLI processes; never query Windows."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from eventguard.processes import spawn, finish

ROOT = Path(__file__).resolve().parents[1]


class CommandQueryCancellationTests(unittest.TestCase):
    def invoke(self, setup, arguments):
        with tempfile.TemporaryDirectory() as temporary:
            script = "import sys\nfrom eventguard.cli import main\n" + setup + "\nraise SystemExit(main(sys.argv[2:],root=sys.argv[1]))"
            child = spawn([sys.executable, "-B", "-c", script, temporary, "--format", "json", "query", "health", *arguments],
                env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                out, err = child.communicate(timeout=10)
            finally:
                receipt = finish(child, reason="test_teardown", grace=1)
            self.assertTrue(receipt["child_exited"])
            self.assertFalse(receipt["forcibly_terminated"])
            self.assertEqual(receipt["remaining_owned_processes"], 0)
            self.assertEqual(child.returncode, 130)
            self.assertFalse(bool(err), "unexpected_stderr_omitted")
            value = json.loads(out)
            self.assertEqual(value["status"], "cancelled")
            self.assertNotIn("SYNTHETIC_PRIVATE", out.decode("utf-8"))
            self.assertEqual(list(Path(temporary).iterdir()), [])
            return value

    def test_stdin_interrupt_is_structured_and_never_dispatches(self):
        setup = '''from eventguard.diagnostics.api import DiagnosticAPI
def forbidden(*_args, **_kw):
    raise AssertionError("query must not dispatch")
DiagnosticAPI.query = forbidden
class Interrupted:
    def isatty(self): return False
    def read(self, _limit): raise KeyboardInterrupt("SYNTHETIC_PRIVATE")
sys.stdin = Interrupted()'''
        result = self.invoke(setup, ["--args", "-"])
        self.assertEqual(result["error_code"], "query_input_cancelled")
        self.assertFalse(result["system_query_executed"])
        self.assertEqual(result["model_calls"], 0)

    def test_cancelled_api_result_has_non_success_exit(self):
        setup = '''from eventguard.diagnostics.api import DiagnosticAPI
DiagnosticAPI.query = lambda *_args, **_kw: {"schema_version":"1.0", "status":"cancelled", "error_code":"cancelled_before_query"}'''
        self.invoke(setup, [])
