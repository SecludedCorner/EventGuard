"""Synthetic saved-result API, corruption and anchor-retention boundaries."""
from pathlib import Path
import json
import tempfile
import unittest

from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.synthetic import make_synthetic


class DispositionOperationReadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root / "data/test")
        self.event = dict(make_synthetic("listener"), event_id="evt-operation-read")
        self.store.enqueue(self.event)
        self.catalog = EventCatalog(self.root, "test")

    def read(self):
        before = self.store.path.read_bytes()
        result = self.catalog.operation_result(self.event["event_id"], "original")
        self.assertEqual(self.store.path.read_bytes(), before)
        return result

    def save(self):
        self.catalog.set_status(self.event["event_id"], "read", source="gui", operation_id="original")

    def test_original_result_survives_later_changes_and_read_does_not_ack(self):
        self.save()
        original = self.read()["operation"]
        self.catalog.set_status(self.event["event_id"], "handled", source="cli", operation_id="later")
        result = self.read()
        self.assertEqual(result["state"], "available")
        self.assertEqual(result["operation"], original)
        self.assertEqual((original["previous_status"], original["status"], original["source"], original["changed"]), ("new", "read", "gui", True))
        self.assertEqual(result["current"]["status"], "handled")
        self.assertEqual(result, self.read())
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))

    def test_known_anchor_with_no_record_differs_from_missing_store_or_anchor(self):
        self.assertEqual(self.read()["state"], "not_recorded")
        missing = self.root / "missing"
        self.assertEqual(EventCatalog(missing, "test").operation_result("evt-missing", "original")["state"], "unknown")
        self.assertFalse(missing.exists())
        self.save()
        other = dict(make_synthetic("startup"), event_id="evt-other")
        self.store.enqueue(other)
        self.assertEqual(self.catalog.operation_result("evt-other", "original")["state"], "not_recorded")
        with self.store._connect() as db:
            db.execute("DELETE FROM events WHERE event_id=?", (self.event["event_id"],))
        self.assertEqual(self.read()["state"], "unknown")  # Retained operations cannot prove a missing anchor.

    def test_corrupt_bound_row_is_unknown_without_repair(self):
        self.save()
        with self.store._connect() as db:
            original = dict(db.execute("SELECT * FROM event_disposition_operations").fetchone())
        for field, value in (("payload_hash", None), ("payload_hash", "0"*64), ("changed", 0),
                             ("source", "untrusted"), ("at", -1), ("status", "invalid")):
            with self.store._connect() as db:
                db.execute("UPDATE event_disposition_operations SET " + field + "=?", (value,))
            self.assertEqual((self.read()["state"], self.read()["operation"]), ("unknown", None))
            with self.store._connect() as db:
                db.execute("UPDATE event_disposition_operations SET " + field + "=?", (original[field],))
        with self.store._connect() as db:
            payload = json.loads(db.execute("SELECT payload FROM events").fetchone()[0])
            payload["evidence"]["port"] = 18082
            db.execute("UPDATE events SET payload=?,payload_hash=?", (json.dumps(payload), event_payload_hash(payload)))
        self.assertEqual(self.read()["state"], "unknown")

    def test_invalid_identifiers_and_legacy_schema_do_not_migrate(self):
        with self.assertRaises(ValueError):
            self.catalog.operation_result(self.event["event_id"], "bad operation")
        with self.store._connect() as db:
            db.execute("CREATE TABLE event_disposition_operations(operation_id TEXT)")
        self.assertEqual(self.read()["state"], "unknown")

    def test_noop_result_is_recorded_and_unconsumed_gui_intent_stays_pending(self):
        from eventguard.events.schema import validate_event
        self.store._prepare_desktop_request({"namespace": "test", "event_id": self.event["event_id"],
            "status": "new", "operation_id": "original", "payload_hash": event_payload_hash(validate_event(self.event))}, namespace="test")
        self.catalog.set_status(self.event["event_id"], "new", source="gui", operation_id="original")
        result = self.read()
        self.assertEqual((result["state"], result["operation"]["changed"]), ("available", False))
        requests = self.catalog.detail(self.event["event_id"])["pending_handling_requests"]
        self.assertEqual(len(requests["requests"]), 1)
