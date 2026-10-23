"""Stop ownership fixtures: no monitor, OS collection, model or subprocess."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard import runtime as runtime_module
from eventguard.runtime import Runtime, atomic_json, read_json


class StopBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runtime = Runtime(self.root)
        self.runtime.ensure()
        self.owner = self.root / "data/monitor-owner.json"
        self.request = self.root / "data/stop-request.json"

    def test_matching_expected_owner_gets_only_its_instance_request(self):
        atomic_json(self.owner, {"instance_id": "a" * 32})
        value = self.runtime.request_stop(expected_instance_id="a" * 32)
        self.assertEqual(value["status"], "stop_requested")
        self.assertEqual(read_json(self.request)["instance_id"], "a" * 32)
        self.assertFalse(value["process_terminated"])

    def test_replaced_owner_does_not_receive_request_or_overwrite_old_request(self):
        atomic_json(self.owner, {"instance_id": "b" * 32})
        atomic_json(self.request, {"instance_id": "c" * 32, "fixture": True})
        before = self.request.read_bytes()
        value = self.runtime.request_stop(expected_instance_id="a" * 32)
        self.assertEqual((value["status"], value["reason"]), ("busy", "monitor_owner_changed"))
        self.assertEqual(self.request.read_bytes(), before)
        self.assertFalse(value["process_terminated"])

    def test_missing_expected_owner_reports_change_and_writes_nothing(self):
        value = self.runtime.request_stop(expected_instance_id="a" * 32)
        self.assertEqual(value["reason"], "monitor_owner_changed")
        self.assertFalse(self.request.exists())

    def test_owner_disappearing_during_read_returns_change_without_a_request(self):
        atomic_json(self.owner, {"instance_id": "a" * 32})
        with patch.object(runtime_module, "read_json", side_effect=FileNotFoundError):
            value = self.runtime.request_stop(expected_instance_id="a" * 32)
        self.assertEqual((value["status"], value["reason"]), ("busy", "monitor_owner_changed"))
        self.assertFalse(self.request.exists())

    def test_owner_replaced_after_read_never_redirects_to_new_instance(self):
        atomic_json(self.owner, {"instance_id": "a" * 32})
        original = runtime_module.read_json

        def replace_after_read(path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            if path == self.owner:
                atomic_json(self.owner, {"instance_id": "b" * 32})
            return value

        with patch.object(runtime_module, "read_json", side_effect=replace_after_read):
            value = self.runtime.request_stop(expected_instance_id="a" * 32)
        self.assertEqual(value["status"], "stop_requested")
        self.assertEqual(read_json(self.request)["instance_id"], "a" * 32)
        self.assertEqual(read_json(self.owner)["instance_id"], "b" * 32)

    def test_unscoped_human_stop_keeps_existing_behavior(self):
        atomic_json(self.owner, {"instance_id": "b" * 32})
        value = self.runtime.request_stop()
        self.assertEqual(value["status"], "stop_requested")
        self.assertEqual(read_json(self.request)["instance_id"], "b" * 32)

    def test_invalid_expected_instance_is_rejected_without_writing(self):
        for value in ("a" * 31, "x" * 32, 1, [], True):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "invalid_expected_monitor_instance"):
                self.runtime.request_stop(expected_instance_id=value)
        self.assertFalse(self.request.exists())
