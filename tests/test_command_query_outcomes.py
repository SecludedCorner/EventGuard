"""Real CLI and DiagnosticAPI with fixed source states, never Windows data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from eventguard.processes import spawn, finish

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''import sys
from eventguard.diagnostics import api
class FixedCollector:
    def collect(self,*args,**kwargs):
        if sys.argv[2]=="forbidden": raise AssertionError("collector must not run")
        return {"status":sys.argv[2],"rows":[]}
original=api.DiagnosticAPI
api.DiagnosticAPI=lambda **kwargs: original(collectors=FixedCollector())
from eventguard.cli import main
raise SystemExit(main(["--format","json",*sys.argv[3:]],root=sys.argv[1]))
'''


class CommandQueryOutcomeTests(unittest.TestCase):
    def call(self, source, operation, values=None):
        with tempfile.TemporaryDirectory() as temporary:
            child = spawn([sys.executable, "-B", "-c", PROGRAM, temporary, source,
                "query", operation, "--args", json.dumps(values or {})],
                env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                out, err = child.communicate(timeout=10)
            finally:
                receipt = finish(child, reason="test_teardown", grace=1)
            self.assertTrue(receipt["child_exited"])
            self.assertFalse(receipt["forcibly_terminated"])
            self.assertEqual(receipt["remaining_owned_processes"], 0)
            self.assertFalse(bool(err), "unexpected_stderr_omitted")
            self.assertEqual(list(Path(temporary).iterdir()), [])
            return child.returncode, json.loads(out)

    def test_unavailable_and_unrequested_source_results_are_non_success(self):
        for status in ("not_applicable", "not_requested"):
            with self.subTest(status=status):
                code, value = self.call(status, "query_defender")
                self.assertEqual((value["status"], value["error_code"], value["rows"]), (status, "source_" + status, []))
                self.assertEqual(code, 5)

    def test_unsupported_view_is_invalid_before_collection(self):
        code, value = self.call("forbidden", "query_defender", {"view": "history"})
        self.assertEqual((value["status"], value["error_code"]), ("not_applicable", "operation_view_not_supported"))
        self.assertEqual(code, 2)

    def test_unapproved_product_retains_invalid_exit(self):
        code, value = self.call("forbidden", "query_version", {"product_id": "other"})
        self.assertEqual((code, value["error_code"]), (2, "product_not_allowlisted"))

    def test_health_retains_success_without_source_collection(self):
        code, value = self.call("forbidden", "health", {"request_id": "outcome-health"})
        self.assertEqual((code, value["status"], value["request_id"]), (0, "ok", "outcome-health"))
