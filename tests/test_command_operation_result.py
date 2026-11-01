"""Cross-process set/query pipeline, including unknown and missing records."""
from pathlib import Path
import tempfile
import unittest

import test_command_status_retry as status_fixture
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class CommandOperationResultTests(unittest.TestCase):
    cli = status_fixture.CommandStatusRetryTests.cli

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root / "data/test")
        self.event = dict(make_synthetic("listener"), event_id="evt-command-operation")
        self.store.enqueue(self.event)

    def update(self, status, operation):
        return self.cli("events", "set-status", "--namespace", "test", "--event-id", self.event["event_id"],
                        "--status", status, "--operation-id", operation)

    def result(self, operation="original"):
        return self.cli("events", "operation-result", "--namespace", "test", "--event-id", self.event["event_id"],
                        "--operation-id", operation)

    def test_write_query_later_write_query_preserves_original_result(self):
        self.assertEqual(self.update("read", "original")[0], 0)
        code, first = self.result()
        self.assertEqual((code, first["schema_version"], first["state"]), (0, "1.0", "available"))
        self.assertEqual(self.update("ignored", "later")[0], 0)
        before = self.store.path.read_bytes()
        code, second = self.result()
        self.assertEqual(code, 0)
        self.assertEqual(second["operation"], first["operation"])
        self.assertEqual((second["operation"]["status"], second["current"]["status"]), ("read", "ignored"))
        self.assertEqual(self.result()[1], second)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))

    def test_missing_operation_invalid_identity_and_absent_store_are_distinct(self):
        before = self.store.path.read_bytes()
        code, result = self.result("not-recorded")
        self.assertEqual((code, result["state"], result["operation"]), (0, "not_recorded", None))
        code, result = self.result("bad operation")
        self.assertEqual((code, result["status"]), (2, "invalid_request"))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.root = self.root / "absent"
        code, result = self.result()
        self.assertEqual((code, result["state"], result["current"]), (5, "unknown", None))
        self.assertFalse(self.root.exists())

    def test_unbound_legacy_operation_and_retained_row_without_anchor_stay_unknown(self):
        self.assertEqual(self.update("read", "original")[0], 0)
        with self.store._connect() as db:
            db.execute("UPDATE event_disposition_operations SET payload_hash=NULL")
        before = self.store.path.read_bytes()
        self.assertEqual((self.result()[0], self.result()[1]["state"]), (5, "unknown"))
        self.assertEqual(self.store.path.read_bytes(), before)
        with self.store._connect() as db:
            db.execute("DELETE FROM events")
        before = self.store.path.read_bytes()
        self.assertEqual((self.result()[0], self.result()[1]["state"]), (5, "unknown"))
        self.assertEqual(self.store.path.read_bytes(), before)
