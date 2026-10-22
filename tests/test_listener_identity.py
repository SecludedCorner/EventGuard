"""Event-bound listener identity using synthetic metadata and mocked native calls."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard.collectors.contract import payload
from eventguard.collectors.native import NativeBackend
from eventguard.collectors.winapi import NativeError
from eventguard.collectors.windows import WindowsCollectors, process_reference


class Backend:
    def __init__(self, value):
        self.value = value
    def collect(self, source, cancel=None):
        return self.value


class ListenerIdentityTests(unittest.TestCase):
    def test_current_table_owner_creation_before_capture_is_bound(self):
        errors = []
        captured = {42: datetime(2026, 10, 23, tzinfo=timezone.utc)}
        with patch("eventguard.collectors.native.process_created_at", return_value="2026-10-22T23:00:00+00:00") as query:
            result = NativeBackend()._listener_identities(captured, None, errors)
        self.assertEqual(query.call_count, 1)
        self.assertEqual(result[42]["status"], "ok")
        self.assertEqual(errors, [])

    def test_pid_reuse_after_capture_is_unknown_and_not_bound(self):
        errors = []
        captured = {42: datetime(2026, 10, 23, tzinfo=timezone.utc)}
        with patch("eventguard.collectors.native.process_created_at", return_value="2026-10-23T00:00:01+00:00"):
            result = NativeBackend()._listener_identities(captured, None, errors)
        self.assertIsNone(result[42]["created_at"])
        self.assertEqual(errors[0]["reason_code"], "listener_pid_reused")
        self.assertEqual(errors[0]["status"], "unknown")

    def test_owner_denial_keeps_typed_reason_without_private_text(self):
        errors = []
        captured = {42: datetime(2026, 10, 23, tzinfo=timezone.utc)}
        with patch("eventguard.collectors.native.process_created_at", side_effect=NativeError("ListenerOpenProcess", 5, "object")):
            result = NativeBackend()._listener_identities(captured, None, errors)
        self.assertEqual(result[42]["status"], "denied")
        self.assertEqual((errors[0]["stage"], errors[0]["win32_error"]), ("object", 5))
        self.assertIsNone(result[42]["created_at"])

    def test_listener_and_process_canonical_reference_agree(self):
        created = "2026-10-23T08:00:00.0000000+08:00"
        row = {"protocol": "TCP", "address": "0.0.0.0", "port": 18080, "pid": 42,
               "created_at": created, "process_identity_status": "ok", "status": "ok"}
        listener = WindowsCollectors(native=Backend(payload([row])), backend="native").collect("listeners")
        expected = process_reference(42, "2026-10-23T00:00:00Z")
        self.assertEqual((listener["rows"][0]["created_at"], listener["rows"][0]["process_instance_ref"]), expected)
        self.assertEqual(listener["coverage"]["process_identity_status"], "ok")

    def test_missing_fallback_identity_is_explicit_and_endpoint_remains_usable(self):
        row = {"protocol": "TCP", "address": "0.0.0.0", "port": 18080, "pid": 42, "status": "ok"}
        result = WindowsCollectors(native=Backend(payload([row])), backend="native").collect("listeners")
        self.assertEqual(result["rows"][0]["status"], "ok")
        self.assertIsNone(result["rows"][0]["created_at"])
        self.assertIsNone(result["rows"][0]["process_instance_ref"])
        self.assertEqual(result["coverage"]["process_identity_status"], "unknown")
        self.assertEqual(result["coverage"]["process_identity_missing_count"], 1)

    def test_unproved_backend_created_time_does_not_forge_binding(self):
        row = {"protocol": "TCP", "address": "0.0.0.0", "port": 18080, "pid": 42,
               "created_at": "2026-10-23T00:00:00Z", "process_instance_ref": "proc-" + "f" * 24, "status": "ok"}
        result = WindowsCollectors(native=Backend(payload([row])), backend="native").collect("listeners")
        self.assertIsNone(result["rows"][0]["process_instance_ref"])


if __name__ == "__main__":
    unittest.main()
