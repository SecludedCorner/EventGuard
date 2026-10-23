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

import eventguard.dispatch_policy as policy_module
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

    def test_errors_expose_only_fixed_codes_to_host_status(self):
        for value in ("private-path-and-instruction", None, [], {"reason": "private"}):
            with self.subTest(kind=type(value).__name__):
                error = DispatchPolicyError(value)
                self.assertEqual(error.code, "dispatch_selection_failed_pending_preserved")
                self.assertEqual(str(error), error.code)
        known = DispatchPolicyError("dispatch_pending_identity_conflict")
        self.assertEqual(known.code, "dispatch_pending_identity_conflict")


class DispatchSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.state = self.root / "source", self.root / "inbox"
        self.store = EventStore(self.source)
        self.inbox = QueueInbox(self.source, self.state)
        policy_module._validated_pending_payload.cache_clear()
        self.addCleanup(policy_module._validated_pending_payload.cache_clear)

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

    def test_bad_retry_or_lease_cannot_silently_exclude_pending(self):
        self.store.enqueue(event(severity="info"))
        for field in ("next_retry_at", "lease_until"):
            for value in ("broken private-text", float("inf"), -1, policy_module.MAX_SCHEDULE_TIME):
                self.sql("UPDATE events SET " + field + "=?", (value,))
                before = self.files()
                with self.subTest(field=field, value=value), self.assertRaisesRegex(
                        DispatchPolicyError, "^dispatch_pending_schedule_invalid$"):
                    select_pending(self.inbox)
                self.assertEqual(self.files(), before)
                self.assertEqual(self.store.stats()["pending"], 1)
            self.sql("UPDATE events SET " + field + "=NULL")
        self.assertIsNone(select_pending(self.inbox))  # Valid low severity remains filtered.
        self.sql("UPDATE events SET next_retry_at=?", (time.time() + 3600,))
        self.assertIsNone(select_pending(self.inbox))  # A valid future is waiting, not damaged.

    def test_matching_invalid_hash_fails_visibly_and_preserves_pending(self):
        self.store.enqueue(event())
        self.sql("UPDATE events SET payload_hash=?", ("a" * 64,))
        before = self.files()
        with self.assertRaisesRegex(DispatchPolicyError, "dispatch_pending_identity_conflict"):
            select_pending(self.inbox)
        self.assertEqual(self.files(), before)

    def test_malformed_pending_is_blocked_not_empty_and_preserves_raw_event(self):
        self.store.enqueue(event(severity="info"))
        self.sql("UPDATE events SET payload=?", ("{ invalid-json private-instruction",))
        before = self.files()
        with self.assertRaisesRegex(DispatchPolicyError, "^dispatch_pending_payload_malformed$") as caught:
            select_pending(self.inbox)
        self.assertNotIn("private-instruction", str(caught.exception))
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.stats()["pending"], 1)

    def test_oversized_pending_is_blocked_before_cache_even_when_other_high_exists(self):
        self.store.commit_evaluation({}, [event("evt-a-invalid", severity="info"), event("evt-z-good")])
        oversized = json.dumps({"severity": "info", "x": "x" * 9000})
        self.sql("UPDATE events SET payload=? WHERE event_id='evt-a-invalid'", (oversized,))
        before = self.files()
        with self.assertRaisesRegex(DispatchPolicyError, "^dispatch_pending_payload_capacity$"):
            select_pending(self.inbox)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.stats()["pending"], 2)
        # Query planning may inspect the other valid row first. The oversized
        # raw text itself cannot add an entry or cache miss in either order.
        cached = policy_module._validated_pending_payload.cache_info()
        self.assertLessEqual(cached.currsize, 1)
        self.assertEqual(policy_module._pending_payload_reason("evt-a-invalid", oversized, "a" * 64),
                         "dispatch_pending_payload_capacity")
        self.assertEqual(policy_module._validated_pending_payload.cache_info(), cached)

    def test_missing_core_fields_unknown_schema_and_wrong_type_are_blocked(self):
        self.store.enqueue(event(severity="info"))
        from eventguard.events.schema import validate_event
        original = validate_event(event(severity="info"))
        cases = []
        for missing in ("schema_version", "event_id", "host_id", "episode_id", "correlation_id",
                        "sequence", "event_type", "transition", "severity", "synthetic", "observed_at", "persisted_at"):
            changed = dict(original)
            del changed[missing]
            cases.append(("missing-" + missing, changed))
        cases.extend((("unknown-schema", dict(original, schema_version="99.0")),
                      ("invalid-boolean", dict(original, synthetic=1)),
                      ("invalid-coverage", dict(original, coverage={"status": "safe"})),
                      ("array-root", [])))
        for label, changed in cases:
            self.sql("UPDATE events SET payload=?", (json.dumps(changed),))
            before = self.files()
            with self.subTest(label=label), self.assertRaisesRegex(DispatchPolicyError, "^dispatch_pending_schema_invalid$"):
                select_pending(self.inbox)
            self.assertEqual(self.files(), before)
        self.assertEqual(self.store.stats()["pending"], 1)

    def test_invalid_human_status_blocks_instead_of_becoming_filtered(self):
        self.store.enqueue(event())
        self.sql("CREATE TABLE event_dispositions(event_id TEXT PRIMARY KEY,status,updated_at REAL)")
        for invalid in (None, "closed_by_unknown_rule", 77):
            self.sql("INSERT OR REPLACE INTO event_dispositions VALUES(?,?,?)", ("evt-one", invalid, time.time()))
            before = self.files()
            with self.subTest(status=invalid), self.assertRaisesRegex(DispatchPolicyError, "^dispatch_pending_human_status_invalid$"):
                select_pending(self.inbox)
            self.assertEqual(self.files(), before)
            self.assertEqual(self.store.stats()["pending"], 1)

    def test_unknown_conditions_cannot_exclude_their_own_validation(self):
        self.store.enqueue(event(synthetic=False, severity="info"))
        # Neither namespace nor future retry can establish trusted exclusion
        # after the schema has become unreadable.
        changed = event(synthetic=False, severity="info")
        changed["schema_version"] = "future"
        self.sql("UPDATE events SET payload=?,next_retry_at=?", (json.dumps(changed), time.time() + 3600))
        with self.assertRaisesRegex(DispatchPolicyError, "^dispatch_pending_schema_invalid$"):
            select_pending(self.inbox)

    def test_duplicate_json_conditions_are_blocked_not_interpreted_differently(self):
        self.store.enqueue(event())
        raw = json.dumps(event()).replace('"severity": "high"', '"severity": "info", "severity": "high"')
        self.sql("UPDATE events SET payload=?", (raw,))
        before = self.files()
        with self.assertRaisesRegex(DispatchPolicyError, "^dispatch_pending_payload_malformed$"):
            select_pending(self.inbox)
        self.assertEqual(self.files(), before)

    def test_same_valid_low_content_uses_lru_without_full_parse_each_poll(self):
        self.store.enqueue(event(severity="info"))
        with patch.object(policy_module, "validate_event", wraps=policy_module.validate_event) as validator:
            self.assertIsNone(select_pending(self.inbox))
            self.assertIsNone(select_pending(self.inbox))
            self.assertIsNone(select_pending(self.inbox))
            self.assertEqual(validator.call_count, 1)
        info = policy_module._validated_pending_payload.cache_info()
        self.assertEqual(info.currsize, 1)
        self.assertGreaterEqual(info.hits, 2)
        self.assertEqual(self.store.stats()["pending"], 1)

    def test_same_stored_hash_with_changed_raw_content_does_not_hit_old_validation(self):
        self.store.enqueue(event(severity="info"))
        self.assertIsNone(select_pending(self.inbox))
        from eventguard.events.schema import validate_event
        changed = validate_event(event(severity="info"))
        changed["severity"] = "critical"
        self.sql("UPDATE events SET payload=?", (json.dumps(changed),))
        before = self.files()
        with patch.object(policy_module, "validate_event", wraps=policy_module.validate_event) as validator:
            with self.assertRaisesRegex(DispatchPolicyError, "^dispatch_pending_identity_conflict$"):
                select_pending(self.inbox)
            self.assertEqual(validator.call_count, 1)
        self.assertEqual(self.files(), before)

    def test_cache_is_finite_and_oversized_keys_are_not_admitted(self):
        from eventguard.events.schema import validate_event
        from eventguard.events.store import event_payload_hash
        for index in range(1001):
            clean = validate_event(event("evt-cache-" + str(index), severity="info"))
            self.assertIsNone(policy_module._pending_payload_reason(clean["event_id"], json.dumps(clean), event_payload_hash(clean)))
        info = policy_module._validated_pending_payload.cache_info()
        self.assertEqual(info.maxsize, 1000)
        self.assertEqual(info.currsize, 1000)
        for identity, raw, stored_hash in (("evt-one", "x" * 8193, "a" * 64),
                                           ("x" * 8193, "{}", "a" * 64),
                                           ("evt-one", "{}", "a" * 8193)):
            self.assertIsNotNone(policy_module._pending_payload_reason(identity, raw, stored_hash))
        after = policy_module._validated_pending_payload.cache_info()
        self.assertEqual(after.currsize, info.currsize)
        self.assertEqual(after.misses, info.misses)

    def test_pending_count_above_bound_blocks_before_schema_scan(self):
        self.store.commit_evaluation({}, [event("evt-one"), event("evt-two")])
        before = self.files()
        with patch.object(policy_module, "MAX_CANDIDATES", 1), \
             patch.object(policy_module, "validate_event", side_effect=AssertionError("must bound before parsing")):
            with self.assertRaisesRegex(DispatchPolicyError, "^dispatch_pending_capacity_pending_preserved$"):
                select_pending(self.inbox)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.stats()["pending"], 2)

    def test_repair_is_observed_without_clearing_pending_or_restarting(self):
        from eventguard.events.schema import validate_event
        clean = validate_event(event())
        self.store.enqueue(clean)
        self.sql("UPDATE events SET payload=?", ("{ damaged",))
        with self.assertRaises(DispatchPolicyError):
            select_pending(self.inbox)
        self.sql("UPDATE events SET payload=?", (json.dumps(clean),))
        self.assertEqual(select_pending(self.inbox), "evt-one")
        self.assertEqual(self.store.stats()["pending"], 1)

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
