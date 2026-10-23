"""Saved synthetic events only. No Windows collection, child or model calls."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from eventguard.diagnostics.review import review
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import CapacityError, EventStore, StoreError
from eventguard.synthetic import make_synthetic


class EventCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog = EventCatalog(self.root, "test")
        self.directory = self.root / "data/test"
        self.path = self.directory / "eventguard.sqlite3"

    def add(self, identity="evt-one", *, severity="warning", source=None, kind="listener", store=None):
        event = make_synthetic(kind)
        event["event_id"] = identity
        event["severity"] = severity
        if source is not None:
            event["evidence"]["section"] = source
        (store or EventStore(self.directory)).enqueue(event)
        return event

    def database_rows(self):
        with closing(sqlite3.connect(self.path)) as db:
            return {row[0]: row for row in db.execute("SELECT event_id,payload,payload_hash,delivery_status,attempts,created_at,updated_at,receipt FROM events")}

    def test_empty_list_and_missing_detail_never_create_runtime_files(self):
        result = self.catalog.list()
        self.assertEqual(result["events"], [])
        self.assertEqual(result["total"], 0)
        self.assertFalse(result["has_more"])
        for operation in (lambda: self.catalog.detail("evt-missing"), lambda: self.catalog.set_status("evt-missing", "read")):
            with self.assertRaisesRegex(ValueError, "^event_not_found$"):
                operation()
        self.assertFalse((self.root / "data").exists())

    def test_legacy_database_reads_remain_identical_and_do_not_create_status_table(self):
        event = self.add()
        before = self.path.read_bytes()
        with patch.object(EventStore, "__init__", side_effect=AssertionError("read initialized writable store")):
            result = self.catalog.list()
            detail = self.catalog.detail(event["event_id"])
        self.assertEqual(result["events"][0]["status"], "new")
        self.assertEqual(detail["status"], "new")
        self.assertIsNone(detail["status_updated_at"])
        self.assertEqual(self.path.read_bytes(), before)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_dispositions'").fetchone())

    def test_filter_applies_before_paging_across_the_whole_database(self):
        store = EventStore(self.directory)
        target = self.add("evt-old-target", severity="high", source="tasks", store=store)
        for number in range(120):
            self.add("evt-new-" + str(number), severity="info", source="services", store=store)
        self.catalog.set_status(target["event_id"], "handled")
        result = self.catalog.list(severity="high", source="tasks", status="handled", limit=1)
        self.assertEqual(result["total"], 1)
        self.assertEqual([row["event_id"] for row in result["events"]], [target["event_id"]])
        self.assertFalse(result["has_more"])
        self.assertEqual(self.catalog.list(severity="critical")["total"], 0)

    def test_pagination_is_stable_with_tied_creation_times(self):
        store = EventStore(self.directory)
        with patch("eventguard.events.store.time.time", return_value=1000):
            for identity in ("evt-c", "evt-a", "evt-b", "evt-d", "evt-e"):
                self.add(identity, store=store)
        first = self.catalog.list(limit=2)
        second = self.catalog.list(limit=2, offset=2)
        last = self.catalog.list(limit=2, offset=4)
        self.assertEqual([row["event_id"] for row in first["events"]], ["evt-a", "evt-b"])
        self.assertEqual([row["event_id"] for row in second["events"]], ["evt-c", "evt-d"])
        self.assertEqual([row["event_id"] for row in last["events"]], ["evt-e"])
        self.assertTrue(first["has_more"])
        self.assertTrue(second["has_more"])
        self.assertFalse(last["has_more"])
        self.assertEqual(last["total"], 5)
        self.assertEqual(self.catalog.list(offset=8)["events"], [])

    def test_status_is_durable_and_never_changes_evidence_or_delivery(self):
        event = self.add()
        before = self.database_rows()
        for state in ("read", "handled", "ignored", "new"):
            result = self.catalog.set_status(event["event_id"], state)
            self.assertTrue(result["changed"])
            self.assertFalse(result["ack_performed"])
            self.assertEqual(EventCatalog(self.root, "test").detail(event["event_id"])["status"], state)
            self.assertEqual(self.database_rows(), before)
        self.assertEqual(EventStore(self.directory).stats()["pending"], 1)
        self.assertEqual(EventStore(self.directory).stats()["receipt_count"], 0)

    def test_unchanged_status_is_idempotent(self):
        event = self.add()
        initial = self.catalog.set_status(event["event_id"], "new")
        self.assertFalse(initial["changed"])
        self.assertIsNone(initial["status_updated_at"])
        first = self.catalog.set_status(event["event_id"], "read")
        again = self.catalog.set_status(event["event_id"], "read")
        self.assertFalse(again["changed"])
        self.assertEqual(first["status_updated_at"], again["status_updated_at"])

    def test_status_filters_include_implicit_new_and_ack_is_not_handled(self):
        first = self.add("evt-first")
        second = self.add("evt-second")
        self.catalog.set_status(second["event_id"], "ignored")
        EventStore(self.directory).acknowledge(first["event_id"], {
            "ack_type": "receiver_persisted", "event_id": first["event_id"], "receipt_id": "fixture-receipt"})
        result = self.catalog.list(status="new")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["events"][0]["event_id"], first["event_id"])
        self.assertEqual(result["events"][0]["delivery_status"], "ack")
        self.assertEqual(self.catalog.list(status="ignored")["total"], 1)

    def test_sources_cover_seven_collectors_and_monitor_without_free_text(self):
        store = EventStore(self.directory)
        for source in ("defender", "listeners", "processes", "startup", "services", "tasks", "versions"):
            self.add("evt-" + source, source=source, store=store)
            result = self.catalog.list(source=source)
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["events"][0]["source"], source)
        gap = make_synthetic()
        gap.update(event_id="evt-gap", event_type="monitor_gap", evidence={})
        store.enqueue(gap)
        self.assertEqual(self.catalog.list(source="monitor")["total"], 1)

    def test_source_uses_resolved_previous_binding_and_fixed_kind_fallback(self):
        event = make_synthetic("startup")
        event.update(event_id="evt-resolved", transition="resolved", evidence={"previous": {"section": "tasks"}})
        store = EventStore(self.directory)
        store.enqueue(event)
        self.assertEqual(self.catalog.detail(event["event_id"])["source"], "tasks")
        event = make_synthetic("startup")
        event.update(event_id="evt-startup", evidence={"source": "<script>alert(1)</script>", "kind": "startup"})
        store.enqueue(event)
        self.assertEqual(self.catalog.detail(event["event_id"])["source"], "startup")

    def test_bad_inputs_have_fixed_errors_and_no_writes(self):
        for arguments, code in (
            ({"severity": "high' OR 1=1 --"}, "invalid_event_severity_filter"),
            ({"source": "tasks' OR 1=1 --"}, "invalid_event_source_filter"),
            ({"status": "closed"}, "invalid_event_status"),
            ({"status": []}, "invalid_event_status"),
            ({"limit": True}, "event_limit_out_of_bounds"),
            ({"limit": 1001}, "event_limit_out_of_bounds"),
            ({"offset": -1}, "event_offset_out_of_bounds"),
            ({"offset": 2**31}, "event_offset_out_of_bounds"),
        ):
            with self.subTest(arguments=arguments), self.assertRaisesRegex(ValueError, "^" + code + "$"):
                self.catalog.list(**arguments)
        for identity in ("evt-one' OR 1=1 --", "", None, ["evt-one"]):
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, "^invalid_event_identifier$"):
                self.catalog.detail(identity)
        with self.assertRaisesRegex(ValueError, "^invalid_event_status$"):
            self.catalog.set_status("evt-one", "delete")
        self.assertFalse((self.root / "data").exists())

    def test_missing_event_in_existing_database_does_not_create_handling_table(self):
        self.add()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "^event_not_found$"):
            self.catalog.set_status("evt-missing", "read")
        self.assertEqual(self.path.read_bytes(), before)

    def test_namespace_does_not_mix_live_and_test_events(self):
        self.add("evt-test")
        self.add("evt-live", store=EventStore(self.root / "data/live"))
        self.catalog.set_status("evt-test", "handled")
        live = EventCatalog(self.root)
        self.assertEqual([row["event_id"] for row in live.list()["events"]], ["evt-live"])
        self.assertEqual(live.detail("evt-live")["status"], "new")
        with self.assertRaisesRegex(ValueError, "^event_not_found$"):
            live.set_status("evt-test", "ignored")

    def test_expiry_removes_disposition_and_pending_events_are_preserved(self):
        store = EventStore(self.directory, acked_retention_seconds=0)
        first = self.add("evt-acked", store=store)
        pending = self.add("evt-pending", store=store)
        self.catalog.set_status(first["event_id"], "handled")
        self.catalog.set_status(pending["event_id"], "ignored")
        store.acknowledge(first["event_id"], {"ack_type": "receiver_persisted", "event_id": first["event_id"], "receipt_id": "fixture-r"})
        store.maintain(now=4000000000)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT event_id FROM event_dispositions").fetchall(), [(pending["event_id"],)])
        self.assertEqual(self.catalog.list()["total"], 1)
        self.assertEqual(self.catalog.detail(pending["event_id"])["status"], "ignored")

    def test_count_pressure_prunes_only_acknowledged_event_disposition(self):
        store = EventStore(self.directory, max_events=1)
        event = self.add("evt-acked", store=store)
        self.catalog.set_status(event["event_id"], "handled")
        store.acknowledge(event["event_id"], {"ack_type": "receiver_persisted", "event_id": event["event_id"], "receipt_id": "fixture-r"})
        self.add("evt-next", store=store)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM event_dispositions").fetchone()[0], 0)
        self.assertEqual(self.catalog.detail("evt-next")["status"], "new")

    def test_byte_rotation_removes_only_completed_dispositions(self):
        store = EventStore(self.directory)
        event = self.add("evt-acked", store=store)
        self.add("evt-pending", store=store)
        self.catalog.set_status(event["event_id"], "handled")
        self.catalog.set_status("evt-pending", "read")
        store.acknowledge(event["event_id"], {"ack_type": "receiver_persisted", "event_id": event["event_id"], "receipt_id": "fixture-r"})
        with store._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.assertEqual(store._rotate_completed(db, 4000000000), 1)
        self.assertEqual([row["event_id"] for row in self.catalog.list()["events"]], ["evt-pending"])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT event_id FROM event_dispositions").fetchall(), [("evt-pending",)])

    def test_handling_capacity_failure_rolls_back_and_keeps_pending_ack_reserve(self):
        store = EventStore(self.directory)
        event = self.add(store=store)
        before = self.database_rows()
        with patch.object(EventStore, "_used_bytes", return_value=store.max_bytes):
            with self.assertRaisesRegex(CapacityError, "^event_status_capacity_pending_and_ack_space_preserved$"):
                self.catalog.set_status(event["event_id"], "read")
        self.assertEqual(self.database_rows(), before)
        self.assertEqual(self.catalog.detail(event["event_id"])["status"], "new")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_dispositions'").fetchone())
        self.assertTrue(self.catalog.set_status(event["event_id"], "read")["changed"])

    def test_detail_returns_saved_evidence_without_os_query_or_free_text_execution(self):
        event = self.add()
        with patch("eventguard.diagnostics.review.DiagnosticAPI", side_effect=AssertionError("implicit query")):
            detail = self.catalog.detail(event["event_id"])
        self.assertEqual(detail["event"]["event_id"], event["event_id"])
        self.assertEqual(detail["interpretation"]["mode"], "stored_observation")
        self.assertFalse(detail["interpretation"]["system_query_executed"])
        self.assertEqual(detail["incident_conclusion"], "not_assessed")
        self.assertEqual(detail["model_calls"], 0)
        self.assertEqual(detail["guidance"]["incident_conclusion"], "not_assessed")
        self.assertIsNone(detail["latest_diagnosis"])

    def test_saved_diagnosis_is_bound_to_the_unchanged_event(self):
        event = self.add()
        store = EventStore(self.directory)
        fixture_api = SimpleNamespace(query=lambda *args: {"source": "listeners", "status": "denied", "rows": [],
            "coverage": {}, "observed_at": event["observed_at"]})
        result = review(store.get_event(event["event_id"]), fixture_api, refresh=True)
        result["namespace"] = "test"
        store.save_review(event["event_id"], result["payload_hash"], result)
        saved = self.catalog.detail(event["event_id"])["latest_diagnosis"]
        self.assertEqual(saved["payload_hash"], result["payload_hash"])
        self.assertEqual(saved["event"]["event_id"], event["event_id"])
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE event_reviews SET payload_hash=?", ("0" * 64,))
            db.commit()
        with self.assertRaisesRegex(ValueError, "^saved_review_identity_conflict$"):
            self.catalog.detail(event["event_id"])

    def test_payload_tampering_is_not_projected_or_marked_as_read(self):
        event = self.add()
        with closing(sqlite3.connect(self.path)) as db:
            raw = json.loads(db.execute("SELECT payload FROM events").fetchone()[0])
            raw["severity"] = "critical"
            db.execute("UPDATE events SET payload=?", (json.dumps(raw),))
            db.commit()
        with self.assertRaisesRegex(StoreError, "^stored_event_identity_mismatch$"):
            self.catalog.list()
        with self.assertRaisesRegex(StoreError, "^stored_event_identity_mismatch$"):
            self.catalog.set_status(event["event_id"], "read")

    def test_invalid_saved_status_timestamps_have_fixed_errors_without_writes(self):
        event = self.add()
        self.catalog.set_status(event["event_id"], "read")
        store = EventStore(self.directory)
        before = self.database_rows()
        for value in ("not-a-time", float("inf"), -float("inf"), 1e30, -1e30):
            with self.subTest(value=value):
                with closing(sqlite3.connect(self.path)) as db:
                    db.execute("UPDATE event_dispositions SET updated_at=?", (value,))
                    db.commit()
                for operation in (self.catalog.list, lambda: self.catalog.detail(event["event_id"]),
                                  lambda: store.set_disposition(event["event_id"], "read"),
                                  lambda: store.set_disposition(event["event_id"], "handled")):
                    with self.assertRaisesRegex(StoreError, "^stored_event_disposition_invalid$"):
                        operation()
                self.assertEqual(self.database_rows(), before)
                with closing(sqlite3.connect(self.path)) as db:
                    self.assertEqual(db.execute("SELECT status FROM event_dispositions").fetchone()[0], "read")

    def test_status_write_rechecks_payload_after_the_catalog_read(self):
        event = self.add()
        original_detail = self.catalog.detail
        def change_after_read(event_id):
            result = original_detail(event_id)
            with closing(sqlite3.connect(self.path)) as db:
                raw = json.loads(db.execute("SELECT payload FROM events WHERE event_id=?", (event_id,)).fetchone()[0])
                raw["severity"] = "critical"
                db.execute("UPDATE events SET payload=? WHERE event_id=?", (json.dumps(raw), event_id))
                db.commit()
            return result
        with patch.object(self.catalog, "detail", side_effect=change_after_read):
            with self.assertRaisesRegex(StoreError, "^stored_event_identity_mismatch$"):
                self.catalog.set_status(event["event_id"], "read")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_dispositions'").fetchone())
            self.assertEqual(db.execute("SELECT delivery_status FROM events").fetchone()[0], "pending")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 0)

    def test_database_path_that_is_a_directory_is_an_error_instead_of_empty(self):
        self.path.mkdir(parents=True)
        for operation in (self.catalog.list, lambda: self.catalog.detail("evt-one"),
                          lambda: self.catalog.set_status("evt-one", "read")):
            with self.assertRaisesRegex(StoreError, "^event_catalog_read_failed$"):
                operation()
        self.assertEqual(list(self.path.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
