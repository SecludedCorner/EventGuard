"""Saved synthetic metadata and loopback Web only; never collector/model/ACK."""
from contextlib import closing, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import http.client
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.cli import main
from eventguard.events.catalog import EventCatalog
from eventguard.events.investigation import build, project, validate_saved
from eventguard.events.store import CapacityError, EventStore, StoreError
from eventguard.synthetic import make_synthetic
from eventguard.web import LocalWeb

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/investigation-metadata.json"
NOW = "2026-10-26T08:00:00+00:00"


def fixture_events(now=NOW):
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    clock = datetime.fromisoformat(now)
    events = []
    for row in document["events"]:
        event = make_synthetic("listener")
        event.update(event_id=row["id"], host_id=row.get("host", "synthetic-host"), sequence=row["sequence"],
                     observed_at=(clock+timedelta(seconds=row["offset"])).isoformat())
        event["persisted_at"] = event["observed_at"]
        event["window"] = {"start": event["observed_at"], "end": event["observed_at"]}
        event["evidence"].update(port=row["port"], section=row.get("source", "listeners"))
        if "pid" in row:
            event["evidence"].update(pid=row["pid"], process_created_at=row["created"], process_instance_ref="proc-"+row["ref"])
        events.append(event)
    return events


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "data/test"
        self.catalog = EventCatalog(self.root, "test")
        self.events = fixture_events()
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("no child, model or native query")))

    def populate(self, events=None, **options):
        store = EventStore(self.source, **options)
        for event in self.events if events is None else events:
            store.enqueue(event)
        return store

    def rows(self):
        with closing(sqlite3.connect(self.source / "eventguard.sqlite3")) as db:
            return db.execute("SELECT event_id,payload_hash,delivery_status,receipt FROM events ORDER BY event_id").fetchall()

    def test_missing_read_does_not_create_database_or_case(self):
        with self.assertRaisesRegex(ValueError, "event_not_found"):
            self.catalog.investigate("evt-anchor", now=NOW)
        self.assertFalse(self.source.exists())

    def test_fixture_related_only_stable_entity_not_time_port_pid_owner_or_source(self):
        self.populate()
        before = self.rows()
        value = self.catalog.investigate("evt-anchor", now=NOW)
        case = value["case"]
        self.assertEqual([v["event_id"] for v in case["timeline"]], ["evt-anchor", "evt-related"])
        self.assertEqual(case["correlation"]["excluded"], {"different_entity": 2, "different_owner": 1,
                         "different_source": 1, "missing_binding": 1, "outside_window": 1})
        self.assertEqual(case["status"], "related_metadata_only")
        self.assertEqual(case["allowed_actions"], [])
        self.assertEqual(case["incident_conclusion"], "not_assessed")
        self.assertEqual(before, self.rows())
        path = self.source / "eventguard.sqlite3"
        frozen = path.read_bytes()
        self.assertEqual(EventCatalog(self.root, "test").detail("evt-anchor")["investigation"], value)
        self.assertEqual(path.read_bytes(), frozen)

    def test_pid_without_creation_never_creates_relationship(self):
        one, two = deepcopy(self.events[:2])
        for event in (one, two):
            event["evidence"].pop("process_instance_ref")
            event["evidence"].pop("process_created_at")
        self.populate([one, two])
        case = self.catalog.investigate("evt-anchor", now=NOW)["case"]
        self.assertEqual(len(case["timeline"]), 1)
        self.assertIn("stable_entity_missing", [g["reason"] for g in case["gaps"]])

    def test_pid_creation_pair_works_but_ref_conflict_and_reuse_do_not(self):
        one, two = deepcopy(self.events[:2])
        for event in (one, two):
            event["evidence"].pop("process_instance_ref")
        self.populate([one, two, self.events[3]])
        self.assertEqual(len(self.catalog.investigate("evt-anchor", now=NOW)["case"]["timeline"]), 2)
        a, b = project(one, "listeners"), project(two, "listeners")
        a["entity"]["ref"], b["entity"]["ref"] = "proc-"+"a"*24, "proc-"+"b"*24
        self.assertEqual(len(build(a, [b], as_of=NOW)["timeline"]), 1)

    def test_same_ref_with_conflicting_creation_is_rejected(self):
        one, two = deepcopy(self.events[:2])
        two["evidence"]["process_created_at"] = "2026-10-26T00:01:00+00:00"
        self.populate([one, two])
        self.assertEqual(len(self.catalog.investigate("evt-anchor", now=NOW)["case"]["timeline"]), 1)

    def test_missing_source_stale_future_and_partial_remain_limited(self):
        for change, expected in (("stale", "saved_observation_stale"), ("future", "observation_in_future"),
                                 ("partial", "source_incomplete")):
            with self.subTest(change=change):
                event = deepcopy(self.events[0])
                record = project(event, "listeners")
                if change == "stale":
                    record["observed_at"] = "2026-10-26T00:00:00.000000+00:00"
                elif change == "future":
                    record["observed_at"] = "2026-10-26T09:00:00.000000+00:00"
                else:
                    record["coverage_status"] = "partial"
                case = build(record, [], as_of=NOW)
                self.assertEqual(case["status"], "limited")
                self.assertIn(expected, [g["reason"] for g in case["gaps"]])
        record = project(self.events[0], "unknown")
        self.assertIn("source_unknown", [g["reason"] for g in build(record, [], as_of=NOW)["gaps"]])

    def test_simultaneous_and_sequence_conflict_are_not_attack_verdict(self):
        one, two = deepcopy(self.events[:2])
        two.update(observed_at=one["observed_at"], sequence=one["sequence"])
        two["episode_id"] = one["episode_id"]
        self.populate([one, two])
        case = self.catalog.investigate("evt-anchor", now=NOW)["case"]
        self.assertIn("simultaneous_metadata_conflict", [g["reason"] for g in case["gaps"]])
        self.assertEqual(case["incident_conclusion"], "not_assessed")
        a, b = project(self.events[0], "listeners"), project(self.events[1], "listeners")
        b["sequence"] = 1
        a["sequence"] = 3
        b["episode_ref"] = a["episode_ref"]
        self.assertIn("sequence_time_conflict", [g["reason"] for g in build(a, [b], as_of=NOW)["gaps"]])

    def test_normal_distinct_episodes_do_not_create_false_sequence_or_simultaneous_conflict(self):
        a, b = project(self.events[0], "listeners"), project(self.events[1], "listeners")
        a["sequence"], b["sequence"] = 20, 1
        case = build(a, [b], as_of=NOW)
        self.assertNotIn("sequence_time_conflict", [g["reason"] for g in case["gaps"]])
        b["observed_at"], b["sequence"] = a["observed_at"], a["sequence"]
        case = build(a, [b], as_of=NOW)
        self.assertNotIn("simultaneous_metadata_conflict", [g["reason"] for g in case["gaps"]])
        self.assertEqual(len(case["timeline"]), 2)

    def test_persistence_only_single_stable_entry_not_display_name(self):
        one, two = deepcopy(self.events[:2])
        for item in (one, two):
            item.update(event_type="persistence.changed")
            item["evidence"] = {"kind": "services", "entry_ref": "a"*32, "name": "same-display"}
        self.populate([one, two])
        self.assertEqual(len(self.catalog.investigate("evt-anchor", now=NOW)["case"]["timeline"]), 2)
        for item in (one, two):
            item["evidence"].pop("entry_ref")
        a, b = project(one, "services"), project(two, "services")
        self.assertEqual(len(build(a, [b], as_of=NOW)["timeline"]), 1)

    def test_member_disappearance_or_hash_change_is_unknown_without_rewriting_case(self):
        self.populate(self.events[:2])
        saved = self.catalog.investigate("evt-anchor", now=NOW)
        path = self.source / "eventguard.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.execute("UPDATE events SET payload_hash=? WHERE event_id='evt-related'", ("b"*64,))
            db.commit()
        changed = self.catalog.detail("evt-anchor")["investigation"]
        self.assertEqual(changed["evidence_status"], "unknown")
        self.assertEqual(changed["case"], saved["case"])
        self.assertEqual(changed["changed_event_ids"], ["evt-related"])
        with closing(sqlite3.connect(path)) as db:
            db.execute("DELETE FROM events WHERE event_id='evt-related'")
            db.commit()
        self.assertEqual(self.catalog.detail("evt-anchor")["investigation"]["missing_event_ids"], ["evt-related"])

    def test_tampered_saved_action_or_timeline_is_rejected(self):
        self.populate(self.events[:2])
        value = self.catalog.investigate("evt-anchor", now=NOW)["case"]
        for field, replacement in (("allowed_actions", ["kill"]), ("incident_conclusion", "safe"), ("as_of", "bad")):
            changed = deepcopy(value)
            changed[field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "saved_investigation_invalid"):
                validate_saved(changed, self.events[0])

    def test_member_race_during_save_preserves_previous_case_and_delivery(self):
        store = self.populate(self.events[:2])
        saved = self.catalog.investigate("evt-anchor", now=NOW)
        changed = deepcopy(saved["case"])
        changed["timeline"][1]["payload_hash"] = "b"*64
        with self.assertRaisesRegex(StoreError, "investigation_member_identity_conflict"):
            store.save_investigation("evt-anchor", saved["case"]["anchor_payload_hash"], changed)
        self.assertEqual(self.catalog.detail("evt-anchor")["investigation"], saved)

    def test_capacity_failure_does_not_create_table_or_ack(self):
        store = self.populate(self.events[:2])
        anchor = project(self.events[0], "listeners")
        value = build(anchor, [project(self.events[1], "listeners")], as_of=NOW)
        before = self.rows()
        with patch.object(store, "_used_bytes", return_value=store.max_bytes), self.assertRaises(CapacityError):
            store.save_investigation("evt-anchor", anchor["payload_hash"], value)
        self.assertEqual(self.rows(), before)
        with closing(sqlite3.connect(store.path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_investigations'").fetchone())

    def test_member_limit_is_visible_not_complete_relationship(self):
        anchor = project(self.events[0], "listeners")
        items = []
        for index in range(25):
            item = deepcopy(anchor)
            item["event_id"] = "evt-many-"+str(index)
            items.append(item)
        case = build(anchor, items, as_of=NOW)
        self.assertEqual(len(case["timeline"]), 16)
        self.assertTrue(case["correlation"]["truncated"])
        self.assertEqual(case["status"], "limited")

    def test_os_account_owner_is_unknown_not_invented_from_host_or_process(self):
        self.populate(self.events[:2])
        case = self.catalog.investigate("evt-anchor", now=NOW)["case"]
        self.assertEqual(case["os_owner_status"], "unknown")
        self.assertEqual(case["correlation"]["basis"], "same_host_source_stable_entity")
        self.assertIn("os_account_owner_not_observed", case["limitations"])

    def test_payload_tamper_without_hash_change_is_unknown(self):
        self.populate(self.events[:2])
        saved = self.catalog.investigate("evt-anchor", now=NOW)
        with closing(sqlite3.connect(self.source / "eventguard.sqlite3")) as db:
            db.execute("UPDATE events SET payload='{}' WHERE event_id='evt-related'")
            db.commit()
        changed = self.catalog.detail("evt-anchor")["investigation"]
        self.assertEqual(changed["case"], saved["case"])
        self.assertEqual(changed["changed_event_ids"], ["evt-related"])

    def test_saved_snapshot_age_is_separate_from_original_case(self):
        self.populate(self.events[:2])
        saved = self.catalog.investigate("evt-anchor", now="2020-01-01T00:00:00+00:00")
        self.assertEqual(saved["snapshot_freshness"], "stale")
        self.assertEqual(saved["case"], self.catalog.detail("evt-anchor")["investigation"]["case"])

    def test_candidate_scan_cap_is_visible(self):
        self.populate()
        with patch("eventguard.events.investigation.MAX_CANDIDATES", 3):
            case = self.catalog.investigate("evt-anchor", now=NOW)["case"]
        self.assertEqual(case["correlation"]["examined"], 3)
        self.assertTrue(case["correlation"]["truncated"])
        self.assertIn("candidate_or_member_limit", [g["reason"] for g in case["gaps"]])

    def test_expiration_cleans_only_case_of_expired_acked_anchor(self):
        store = self.populate(self.events[:2], acked_retention_seconds=0)
        self.catalog.investigate("evt-anchor", now=NOW)
        store.acknowledge("evt-anchor", {"ack_type": "receiver_persisted", "event_id": "evt-anchor", "receipt_id": "receipt-anchor"})
        store.maintain(now=datetime.now(timezone.utc).timestamp()+60)
        with closing(sqlite3.connect(store.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM event_investigations").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT delivery_status FROM events WHERE event_id='evt-related'").fetchone()[0], "pending")

    def test_web_cli_same_case_reopen_and_csrf_no_side_effect(self):
        self.populate()
        web = LocalWeb(self.root, "test", port=0, status_provider=lambda: {})
        web.start()
        self.addCleanup(web.close)
        def request(method, suffix="", body=None, approved=False):
            connection = http.client.HTTPConnection("127.0.0.1", web.server.server_port, timeout=5)
            headers = {"Content-Type": "application/json"}
            if approved:
                headers.update(Origin=web.url, **{"X-EventGuard-CSRF": web.token})
            try:
                connection.request(method, "/api/events/evt-anchor"+suffix, body, headers)
                reply = connection.getresponse()
                return reply.status, json.loads(reply.read())
            finally:
                connection.close()
        self.assertIsNone(request("GET")[1]["investigation"])
        self.assertEqual(request("POST", "/investigation", "{}")[0], 403)
        self.assertEqual(request("POST", "/investigation", '{"allowed_actions":["kill"]}', True)[0], 400)
        self.assertIsNone(self.catalog.detail("evt-anchor")["investigation"])
        status, saved = request("POST", "/investigation", "{}", True)
        self.assertEqual(status, 200)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--format", "json", "events", "detail", "--namespace", "test", "--event-id", "evt-anchor"], root=self.root), 0)
        self.assertEqual(json.loads(output.getvalue())["investigation"], saved)
        self.assertEqual(request("GET")[1]["investigation"], saved)
        self.assertEqual(EventCatalog(self.root, "test").detail("evt-anchor")["investigation"], saved)
        self.assertTrue(all(row[2] == "pending" and row[3] is None for row in self.rows()))


if __name__ == "__main__":
    unittest.main()
