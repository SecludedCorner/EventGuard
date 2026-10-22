"""Atomic runtime metadata persistence under synthetic Windows sharing races."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard.runtime import atomic_json, read_json


class RuntimeAtomicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "health.json"
        atomic_json(self.path, {"generation": 1})

    def assert_no_temporary_files(self):
        self.assertEqual(list(self.root.glob(".eventguard-*.tmp")), [])

    @unittest.skipUnless(os.name == "nt", "Windows metadata replace semantics")
    def test_short_windows_sharing_race_retries_same_complete_file_then_commits(self):
        real_replace = os.replace
        for code in (5, 32, 33):
            with self.subTest(winerror=code):
                calls = []
                denied = PermissionError("synthetic transient sharing")
                denied.winerror = code
                def replace(source, destination):
                    calls.append(source)
                    self.assertEqual(read_json(source), {"generation": 2})
                    if len(calls) < 3:
                        self.assertEqual(read_json(destination), {"generation": 1})
                        raise denied
                    return real_replace(source, destination)
                with patch("eventguard.runtime.os.replace", side_effect=replace), \
                     patch("eventguard.runtime.time.sleep") as sleep:
                    atomic_json(self.path, {"generation": 2})
                self.assertEqual(len(calls), 3)
                self.assertEqual(len(set(calls)), 1, "retry must not rewrite/fsync a new generation")
                self.assertEqual(sleep.call_count, 2)
                self.assertTrue(all(call.args == (.01,) for call in sleep.call_args_list))
                self.assertEqual(read_json(self.path), {"generation": 2})
                self.assert_no_temporary_files()
                atomic_json(self.path, {"generation": 1})

    @unittest.skipUnless(os.name == "nt", "Windows metadata replace semantics")
    def test_permanent_access_denial_is_bounded_and_preserves_previous_generation(self):
        denied = PermissionError("synthetic permanent access denial")
        denied.winerror = 5
        with patch("eventguard.runtime.os.replace", side_effect=denied) as replace, \
             patch("eventguard.runtime.time.sleep") as sleep:
            with self.assertRaises(PermissionError) as caught:
                atomic_json(self.path, {"generation": 2})
        self.assertIs(caught.exception, denied)
        self.assertEqual(replace.call_count, 20)
        self.assertEqual(sleep.call_count, 19)
        self.assertAlmostEqual(sum(call.args[0] for call in sleep.call_args_list), .19)
        self.assertEqual(read_json(self.path), {"generation": 1})
        self.assert_no_temporary_files()

    def test_storage_failure_is_not_retried_or_misclassified_as_sharing(self):
        full = OSError("synthetic storage full")
        full.winerror = 112
        with patch("eventguard.runtime.os.replace", side_effect=full) as replace, \
             patch("eventguard.runtime.time.sleep") as sleep:
            with self.assertRaises(OSError) as caught:
                atomic_json(self.path, {"generation": 2})
        self.assertIs(caught.exception, full)
        replace.assert_called_once()
        sleep.assert_not_called()
        self.assertEqual(read_json(self.path), {"generation": 1})
        self.assert_no_temporary_files()

    def test_permission_without_windows_evidence_is_not_retried(self):
        denied = PermissionError("synthetic non-Windows access denial")
        with patch("eventguard.runtime.os.replace", side_effect=denied) as replace, \
             patch("eventguard.runtime.time.sleep") as sleep:
            with self.assertRaises(PermissionError):
                atomic_json(self.path, {"generation": 2})
        replace.assert_called_once()
        sleep.assert_not_called()
        self.assertEqual(read_json(self.path), {"generation": 1})
        self.assert_no_temporary_files()

    def test_fsync_denial_never_enters_replace_retry(self):
        denied = PermissionError("synthetic fsync denial")
        denied.winerror = 5
        with patch("eventguard.runtime.os.fsync", side_effect=denied), \
             patch("eventguard.runtime.os.replace") as replace, \
             patch("eventguard.runtime.time.sleep") as sleep:
            with self.assertRaises(PermissionError):
                atomic_json(self.path, {"generation": 2})
        replace.assert_not_called()
        sleep.assert_not_called()
        self.assertEqual(read_json(self.path), {"generation": 1})
        self.assert_no_temporary_files()


if __name__ == "__main__":
    unittest.main()
