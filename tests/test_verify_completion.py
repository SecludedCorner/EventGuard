"""Injected suites exercise complete, cancelled and empty runs without children."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import verify


class VerificationCompletionTests(unittest.TestCase):
    def run_suite(self, functions):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name)
        output = project / "reports"
        output.mkdir()
        suite = unittest.TestSuite(unittest.FunctionTestCase(lambda f=f: f(output)) for f in functions)
        with patch.object(verify, "ROOT", project), \
                patch.object(verify.unittest.defaultTestLoader, "loadTestsFromNames", return_value=suite), \
                patch.object(verify, "cleanup_owned", return_value=[]), \
                patch.object(verify, "current_job_members", return_value={}):
            code = verify.worker(output, None, modules=("test_fixture",))
        return code, json.loads((output / "worker-summary.json").read_text(encoding="utf-8"))

    def test_complete_nonempty_suite_passes(self):
        code, summary = self.run_suite([lambda output: None, lambda output: None])
        self.assertEqual(code, 0)
        self.assertEqual((summary["expected_tests"], summary["tests_run"]), (2, 2))
        self.assertTrue(verify.suite_completed(summary))

    def test_cooperative_stop_cannot_pass_partial_successful_suite(self):
        ran = []
        def stop(output):
            (output / "guardian-stop.request").write_text("synthetic stop", encoding="utf-8")
        code, summary = self.run_suite([stop, lambda output: ran.append(True)])
        self.assertEqual(code, 1)
        self.assertEqual((summary["expected_tests"], summary["tests_run"]), (2, 1))
        self.assertTrue(summary["stopped_early"])
        self.assertTrue(summary["stop_requested"])
        self.assertFalse(ran)
        self.assertFalse(verify.suite_completed(summary))

    def test_stop_after_last_case_is_still_cancellation(self):
        def stop(output):
            (output / "guardian-stop.request").write_text("synthetic stop", encoding="utf-8")
        code, summary = self.run_suite([stop])
        self.assertEqual(summary["expected_tests"], summary["tests_run"])
        self.assertEqual(code, 1)
        self.assertFalse(verify.suite_completed(summary))

    def test_empty_discovery_and_missing_or_boolean_counts_fail_closed(self):
        code, summary = self.run_suite([])
        self.assertEqual(code, 1)
        self.assertFalse(verify.suite_completed(summary))
        for value in ({}, {"expected_tests": True, "tests_run": 1, "stopped_early": False, "stop_requested": False},
                      {"expected_tests": 2, "tests_run": 1, "stopped_early": False, "stop_requested": False}):
            self.assertFalse(verify.suite_completed(value))
