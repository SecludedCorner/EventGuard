"""Synthetic SQLite admission tests; no model, host scan or subprocess."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from eventguard.dispatch_policy import (DEFAULT_POLICY, DispatchPolicyError,
                                       load_policy, select_pending, validate_policy)
from eventguard.events.store import EventStore
from eventguard.queue_inbox import QueueInbox, QueueInboxError


def event(identity="evt-one", severity="high", kind="listener.changed", synthetic=True):
    return {"schema_version": "2.0", "event_id": identity, "host_id": "host-synthetic",
            "episode_id": "episode-one", "correlation_id": "correlation-one", "sequence": 1,
            "event_type": kind, "transition": "new", "severity": severity,
            "synthetic": synthetic, "observed_at": "2026-10-24T00:00:00Z",
            "persisted_at": "2026-10-24T00:00:00Z", "evidence": {},
            "coverage": {"status": "partial", "gaps": []}}


class PolicyConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_defaults_and_published_config_match_and_are_detached(self):
        path = Path(__file__).resolve().parents[1] / "config" / "agent-dispatch.json"
        self.assertEqual(load_policy(path), load_policy())
        value = load_policy()
        value["severities"].append("warning")
        self.assertEqual(load_policy()["severities"], ["high", "critical"])

    def test_only_enum_conditions_no_commands_paths_or_recipient(self):
        for key in ("command", "prompt", "target", "tools", "budget", "path", "auto_invoke"):
            value = load_policy()
            value[key] = "run unknown program"
            with self.subTest(key=key), self.assertRaisesRegex(DispatchPolicyError, "fields_invalid"):
                validate_policy(value)

    def test_invalid_values_empty_duplicate_and_nested_conditions_fail(self):
        for key, value in (("severities", []), ("severities", ["high", "high"]),
                           ("severities", ["critical; execute"]), ("event_types", ["unknown"]),
                           ("event_types", [{"name": "listener.changed"}]), ("human_statuses", ["handled"]),
                           ("human_statuses", ["ignored"]), ("human_statuses", "new")):
            policy = load_policy()
            policy[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(DispatchPolicyError):
                validate_policy(policy)

    def test_malformed_large_duplicate_and_deep_files_fail_fixed_codes(self):
        for index, raw in enumerate(("not JSON private-secret", "x" * 8193,
                                     '{"severities":[],"severities":[]}', "[" * 1500 + "0" + "]" * 1500)):
            path = self.root / (str(index) + ".json")
            path.write_text(raw, encoding="utf-8")
            with self.subTest(index=index), self.assertRaises(DispatchPolicyError) as caught:
                load_policy(path)
            self.assertNotIn("private-secret", str(caught.exception))

    def test_missing_file_and_non_dict_profiles_fail(self):
        with self.assertRaisesRegex(DispatchPolicyError, "read_failed"):
            load_policy(self.root / "missing.json")
        for value in (None, [], "run command", {"severities": ["high"]}):
            with self.subTest(value=value), self.assertRaises(DispatchPolicyError):
                validate_policy(value)


class DispatchSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.state = self.root / "source", self.root / "inbox"
        self.store = EventStore(self.source)
        self.inbox = QueueInbox(self.source, self.state)

    def files(self):
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file()}

    def sql(self, statement, parameters=()):
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute(statement, parameters)
            db.commit()

    def test_empty_no_match_and_selection_are_read_only(self):
        self.store.enqueue(event(severity="info"))
        before = self.files()
        with patch.object(QueueInbox, "receive_event", side_effect=AssertionError("must not receive")), \
             patch.object(QueueInbox, "ack_event", side_effect=AssertionError("must not ACK")):
            self.assertIsNone(select_pending(self.inbox))
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.stats()["pending"], 1)
        self.assertEqual(self.store.get_event("evt-one")["severity"], "info")

    def test_over_first_page_of_low_priority_cannot_hide_high(self):
        items = [event("evt-low-" + str(i).zfill(3), severity="warning") for i in range(215)]
        items.append(event("evt-z-high"))
        self.store.commit_evaluation({}, items)
        before = self.files()
        self.assertEqual(select_pending(self.inbox), "evt-z-high")
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.stats()["pending"], 216)
        # Legacy API retains its original behavior; selector does not alter it.
        self.assertTrue(self.inbox.pending_event_id().startswith("evt-low-"))

    def test_later_critical_precedes_earlier_high(self):
        self.store.commit_evaluation({}, [event("evt-a-high"), event("evt-z-critical", severity="critical")])
        self.assertEqual(select_pending(self.inbox), "evt-z-critical")

    def test_handled_and_ignored_remain_pending_and_are_excluded(self):
        self.store.commit_evaluation({}, [event("evt-a-handled", severity="critical"),
                                         event("evt-b-ignored", severity="critical"), event("evt-c-new")])
        self.store.set_disposition("evt-a-handled", "handled")
        self.store.set_disposition("evt-b-ignored", "ignored")
        self.assertEqual(select_pending(self.inbox), "evt-c-new")
        self.assertEqual(self.store.stats()["pending"], 3)
        self.store.set_disposition("evt-c-new", "handled")
        self.assertIsNone(select_pending(self.inbox))
        self.assertEqual(self.store.stats()["pending"], 3)

    def test_explicit_severity_type_and_human_read_filter(self):
        self.store.commit_evaluation({}, [event("evt-a-high"), event("evt-b-advisory", kind="advisory.changed"),
                                         event("evt-c-warning", severity="warning", kind="advisory.changed")])
        self.store.set_disposition("evt-b-advisory", "read")
        self.store.set_disposition("evt-c-warning", "read")
        policy = {"severities": ["warning"], "event_types": ["advisory.changed"], "human_statuses": ["read"]}
        self.assertEqual(select_pending(self.inbox, policy), "evt-c-warning")

    def test_failed_acked_future_and_leased_candidates_are_not_due(self):
        self.store.commit_evaluation({}, [event("evt-a-failed", severity="critical"),
                                         event("evt-b-future", severity="critical"),
                                         event("evt-c-leased", severity="critical"), event("evt-d-due")])
        self.sql("UPDATE events SET delivery_status='failed' WHERE event_id='evt-a-failed'")
        self.sql("UPDATE events SET next_retry_at=? WHERE event_id='evt-b-future'", (time.time() + 600,))
        self.sql("UPDATE events SET lease_until=? WHERE event_id='evt-c-leased'", (time.time() + 600,))
        self.assertEqual(select_pending(self.inbox), "evt-d-due")

    def test_live_namespace_requires_existing_explicit_profile(self):
        self.store.enqueue(event("evt-live", synthetic=False))
        self.assertIsNone(select_pending(self.inbox))
        live = QueueInbox(self.source, self.root / "live-inbox", allow_live=True)
        self.assertEqual(select_pending(live), "evt-live")

    def test_matching_invalid_hash_fails_visibly_and_preserves_pending(self):
        self.store.enqueue(event())
        self.sql("UPDATE events SET payload_hash=?", ("a" * 64,))
        before = self.files()
        with self.assertRaisesRegex(QueueInboxError, "source_identity_conflict"):
            select_pending(self.inbox)
        self.assertEqual(self.files(), before)

    def test_malformed_or_oversized_nonmatching_json_cannot_crash_sql_or_hide_high(self):
        self.store.commit_evaluation({}, [event("evt-a-invalid"), event("evt-b-too-large"), event("evt-z-good")])
        self.sql("UPDATE events SET payload=? WHERE event_id='evt-a-invalid'", ("{ invalid-json",))
        self.sql("UPDATE events SET payload=? WHERE event_id='evt-b-too-large'", (json.dumps({"severity": "high", "x": "x" * 9000}),))
        before = self.files()
        self.assertEqual(select_pending(self.inbox), "evt-z-good")
        self.assertEqual(self.files(), before)

    def test_actual_selection_validates_source_hash_and_returns_id_only(self):
        self.store.enqueue(event())
        with patch.object(self.inbox, "_source_record", wraps=self.inbox._source_record) as reader:
            value = select_pending(self.inbox)
            reader.assert_called_once_with("evt-one")
        self.assertIsInstance(value, str)
        self.assertEqual(value, "evt-one")

    def test_readonly_inbox_profile_and_restart_produce_same_selection(self):
        self.store.enqueue(event())
        original = select_pending(self.inbox)
        readonly = QueueInbox.open_readonly(self.source, self.state)
        before = self.files()
        self.assertEqual(select_pending(readonly), original)
        self.assertEqual(select_pending(readonly), original)
        self.assertEqual(self.files(), before)

    def test_invalid_inbox_rejected_without_any_external_action(self):
        with self.assertRaisesRegex(DispatchPolicyError, "inbox_required"):
            select_pending(object())


if __name__ == "__main__":
    unittest.main()
