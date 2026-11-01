"""Immutable classification payloads in synthetic outboxes, never live data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from eventguard.events.schema import validate_event, EventValidationError, MAX_EVENT_BYTES
from eventguard.events.store import EventStore, event_payload_hash, CapacityError
from eventguard.rules.decisions import classify
from eventguard.rules.detector import evaluate
from test_configured_rules import listener, single_rule, condition


class RuleDecisionStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = EventStore(Path(temporary.name) / "data/test")
        self.state, self.events = evaluate([listener()], now=1000)
        self.rules = [single_rule([condition("event_type", "eq", "listener.changed")], "critical")]

    def test_payload_hash_and_reopened_event_retain_original_decision(self):
        event = classify(self.events, self.rules)[0]
        clean = validate_event(event)
        self.assertEqual(clean["classification"], event["classification"])
        self.assertNotEqual(event_payload_hash(clean), event_payload_hash(validate_event(self.events[0])))
        self.store.commit_evaluation(self.state, [event])
        self.rules[0]["severity"] = "info"
        saved = EventStore(self.store.directory).get_event(event["event_id"])
        self.assertEqual(saved["classification"]["rule"]["severity"], "critical")
        self.assertEqual(saved["classification"], clean["classification"])
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))

    def test_invalid_decision_rolls_back_entire_state_event_batch(self):
        event = classify(self.events, self.rules)[0]
        event["classification"]["rule_hash"] = "0" * 64
        with self.assertRaisesRegex(EventValidationError, "invalid_classification"):
            self.store.commit_evaluation(self.state, [self.events[0], event])
        self.assertEqual(self.store.list_events(), [])
        self.assertIsNone(self.store.load_detector_state())

    def test_capacity_failure_commits_neither_decisions_nor_detector_state(self):
        store = EventStore(self.store.directory.parent / "capacity", max_events=1)
        event = classify(self.events, self.rules)[0]
        second = copy.deepcopy(event)
        second["event_id"] += "-second"
        second["sequence"] += 1
        with self.assertRaises(CapacityError):
            store.commit_evaluation(self.state, [event, second])
        self.assertEqual(store.list_events(), [])
        self.assertIsNone(store.load_detector_state())

    def test_legacy_event_remains_without_fabricated_classification(self):
        event = validate_event(self.events[0])
        digest = event_payload_hash(event)
        self.store.enqueue(event)
        saved = self.store.get_event(event["event_id"])
        self.assertNotIn("classification", saved)
        self.assertEqual(event_payload_hash(validate_event(saved)), digest)

    def test_classification_shares_existing_event_byte_limit(self):
        event = classify(self.events, self.rules)[0]
        keys = ("summary", "name", "source_name", "path", "display_name", "item", "profile", "actual", "expected", "result_code", "operation", "binding_scope", "name_ref", "error_code")
        for key in keys:
            event["evidence"][key] = "x" * 512
        event["evidence"]["error_code"] += "x" * 512
        self.assertGreater(len(json.dumps(event).encode("utf-8")), MAX_EVENT_BYTES)
        with self.assertRaisesRegex(EventValidationError, "event_size_limit"):
            validate_event(event)

    def test_historical_review_without_trace_is_readable_but_forged_trace_is_not(self):
        from eventguard.diagnostics.review import review, validate_saved_review
        event = classify(self.events, self.rules)[0]
        event["synthetic"] = True
        self.store.enqueue(event)
        saved = self.store.get_event(event["event_id"])
        api = SimpleNamespace(query=lambda *_args, **_kw: {"status": "ok", "source": "listeners", "rows": [], "coverage": {}})
        value = dict(review(saved, api, refresh=True), namespace="test")
        value["event"].pop("classification")
        self.store.save_review(event["event_id"], value["payload_hash"], value)
        self.assertEqual(validate_saved_review(value, saved), value)
        forged = copy.deepcopy(value)
        forged["event"]["classification"] = dict(event["classification"], rule_hash="0" * 64)
        with self.assertRaisesRegex(ValueError, "saved_review_invalid"):
            validate_saved_review(forged, saved)
        for field, spoof in (("matched", 1), ("rule_index", False)):
            forged = copy.deepcopy(value)
            forged["event"]["classification"] = dict(event["classification"], **{field: spoof})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "saved_review_invalid"):
                validate_saved_review(forged, saved)
