"""Synthetic rule decisions; neither OS collection nor model calls."""
import copy
import unittest

from eventguard.rules.decisions import classify, validate_decision, fingerprint
from eventguard.rules.detector import evaluate
from test_configured_rules import listener, single_rule, condition


class RuleDecisionTests(unittest.TestCase):
    def setUp(self):
        _, self.events = evaluate([listener()], now=1000)
        self.rules = [single_rule([condition("event_type", "eq", "listener.changed")], "high", "first"),
                      single_rule([condition("evidence.port", "eq", 8080)], "critical", "last")]

    def test_snapshot_identifies_last_matching_rule_and_keeps_detector_identity(self):
        before = copy.deepcopy((self.events, self.rules))
        result = classify(self.events, self.rules)[0]
        decision = result["classification"]
        self.assertEqual((result["severity"], decision["base_severity"], decision["rule_index"]), ("critical", "warning", 1))
        self.assertEqual(decision["rule"]["id"], "last")
        self.assertEqual(decision["rule_hash"], fingerprint(decision["rule"]))
        self.assertNotIn("name", decision["rule"])
        self.assertEqual(result["rule_ref"], self.events[0]["rule_ref"])
        self.assertEqual((self.events, self.rules), before)

    def test_reclassification_is_idempotent_and_old_decisions_survive_config_change(self):
        saved = classify(self.events, self.rules)
        original = copy.deepcopy(saved)
        self.assertEqual(classify(saved, self.rules), saved)
        self.rules[-1]["enabled"] = False
        changed = classify(saved, self.rules)[0]
        self.assertEqual(changed["severity"], "high")
        self.assertEqual(changed["classification"]["base_severity"], "warning")
        self.assertNotEqual(changed["classification"]["rule_set_hash"], saved[0]["classification"]["rule_set_hash"])
        self.assertEqual(saved, original)

    def test_unmatched_and_disabled_keep_original_severity_without_fabricated_winner(self):
        for rule in self.rules:
            rule["enabled"] = False
        result = classify(self.events, self.rules)[0]
        self.assertEqual(result["severity"], "warning")
        decision = result["classification"]
        self.assertFalse(decision["matched"])
        self.assertEqual([decision[key] for key in ("rule", "rule_hash", "rule_index")], [None] * 3)

    def test_tampered_hash_binding_conditions_and_unknown_fields_are_refused(self):
        event = classify(self.events, self.rules)[0]
        for field, value in (("rule_hash", "0" * 64), ("rule_index", True), ("rule_set_hash", "bad"), ("extra", "inert")):
            decision = dict(event["classification"], **{field: value})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "classification_invalid"):
                validate_decision(decision, event)
        decision = copy.deepcopy(event["classification"])
        decision["rule"]["conditions"][0]["value"] = 9999
        decision["rule_hash"] = fingerprint(decision["rule"])
        with self.assertRaisesRegex(ValueError, "classification_invalid"):
            validate_decision(decision, event)

    def test_batch_limit_is_checked_before_processing(self):
        from eventguard.rules.decisions import MAX_CLASSIFICATION_EVENTS
        with self.assertRaisesRegex(ValueError, "rules_invalid_events"):
            classify(self.events * (MAX_CLASSIFICATION_EVENTS + 1), self.rules)
