"""Inject real unittest suites into worker; no child, collection or model."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import verify


class VerificationParentCountTests(unittest.TestCase):
    def run_suite(self, suite, cleanup=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'reports'
            output.mkdir()
            with patch.object(verify, 'ROOT', root), \
                 patch.object(verify.unittest.defaultTestLoader, 'loadTestsFromNames', return_value=suite), \
                 patch.object(verify, 'cleanup_owned', return_value=cleanup or []), \
                 patch.object(verify, 'current_job_members', return_value={}):
                code = verify.worker(output, None, modules=('test_fixture',))
            return code, json.loads((output / 'worker-summary.json').read_text(encoding='utf-8'))

    def test_multiple_failed_subtests_do_not_erase_other_successful_parent(self):
        class Cases(unittest.TestCase):
            def test_bad(self):
                for number in range(3):
                    with self.subTest(number=number):
                        self.fail('synthetic subtest failure')
            def test_good(self):
                pass
        code, result = self.run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
        self.assertEqual(code, 1)
        self.assertEqual((result['tests_run'], result['passed'], len(result['failures'])), (2, 1, 3))

    def test_skipped_subtests_are_disclosed_without_negative_pass_count(self):
        class Cases(unittest.TestCase):
            def test_partial(self):
                for number in range(2):
                    with self.subTest(number=number):
                        self.skipTest('synthetic unavailable input')
            def test_good(self):
                pass
        code, result = self.run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
        self.assertEqual(code, 0)
        self.assertEqual((result['tests_run'], result['passed'], len(result['skipped'])), (2, 1, 2))

    def test_cleanup_failure_retracts_success_instead_of_counting_it_as_passed(self):
        suite = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
        code, result = self.run_suite(suite, [{'forcibly_terminated': True}])
        self.assertEqual(code, 1)
        self.assertEqual((result['passed'], len(result['failures']), len(result['per_test_residuals'])), (0, 1, 1))
