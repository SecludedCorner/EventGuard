"""Local rule classification and Monitor integration. All observations are fixtures."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from eventguard.events.schema import validate_event
from eventguard.events.store import EventStore
from eventguard.monitor import Monitor
from eventguard.rules.configured import (DEFAULT_RULES, MAX_RULE_BYTES, RulesValidationError,
                                        apply_rules, load_rules, validate_rules)
from eventguard.rules.detector import evaluate
from eventguard.runtime import Runtime, atomic_json


def source(identity, rows=None, status="ok"):
    return {"id": identity, "status": status, "rows": rows or [],
            "observed_at": "2026-10-23T00:00:00Z", "elapsed_ms": 0,
            "coverage": {"status": status}}


def listener(port=8080):
    return source("listeners", [{"protocol": "TCP", "address": "0.0.0.0", "port": port,
                                  "pid": 42, "scope": "all_interfaces", "status": "ok"}])


def single_rule(conditions, severity="critical", identity="custom-listener"):
    return {"id": identity, "name": "自訂條件", "severity": severity,
            "enabled": True, "conditions": conditions}


def condition(field, op, value):
    return {"field": field, "op": op, "value": value}


class ConfiguredRulesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()

    def save(self, rules):
        atomic_json(self.root / "config/rules.json", {"schema_version": "1.0", "rules": rules}, MAX_RULE_BYTES)

    def test_shipped_five_rules_equal_missing_file_defaults(self):
        defaults = load_rules(self.root)
        self.assertEqual(len(defaults), 5)
        self.assertEqual(defaults, load_rules(BASE))
        defaults[0]["severity"] = "info"
        self.assertEqual(load_rules(self.root)[0]["severity"], "high")
        self.assertFalse((self.root / "data").exists())

    def test_defaults_preserve_detector_classification_and_all_ids(self):
        sections = [source("defender", [{"property": "AntivirusEnabled", "value": False, "status": "ok"},
                                        {"property": "RealTimeProtectionEnabled", "value": False, "status": "ok"}]),
                    listener(), source("startup", [{"kind": "registry", "name": "Fixture", "status": "ok"}]),
                    source("tasks", status="unknown"), source("versions", status="timeout")]
        state, first = evaluate(sections, now=1000)
        state, second = evaluate([source("startup", [{"kind": "registry", "name": "Fixture", "status": "ok"},
                                                     {"kind": "registry", "name": "Added", "status": "ok"}])], state, now=1001)
        original = first + second
        classified = apply_rules(original, DEFAULT_RULES)
        self.assertEqual(classified, original)
        self.assertEqual(len(classified), 6)
        self.assertEqual([item["event_id"] for item in classified], [item["event_id"] for item in original])

    def test_custom_source_port_and_transition_conditions_use_and(self):
        _, events = evaluate([listener()], now=1000)
        rules = [single_rule([condition("source", "eq", "listeners"), condition("evidence.port", "gte", 8000),
                              condition("evidence.port", "lte", 9000), condition("transition", "eq", "new")])]
        changed = apply_rules(events, rules)
        self.assertEqual(changed[0]["severity"], "critical")
        self.assertEqual(events[0]["severity"], "warning")
        self.assertEqual(changed[0]["event_id"], events[0]["event_id"])
        self.assertEqual(changed[0]["rule_ref"], events[0]["rule_ref"])
        self.assertEqual(validate_event(changed[0])["severity"], "critical")
        rules[0]["conditions"][-1]["value"] = "resolved"
        self.assertEqual(apply_rules(events, rules), events)

    def test_defaults_preserve_listener_escalation_and_every_resolved_severity(self):
        _, events = evaluate([listener()], now=1000)
        escalated = copy.deepcopy(events[0])
        escalated.update(transition="escalated", severity="high")
        self.assertEqual(apply_rules([escalated], DEFAULT_RULES), [escalated])
        for event_type, evidence in (
                ("listener.changed", {"port": 8080}),
                ("protection.changed", {"count": 2}),
                ("persistence.changed", {"reason": "added_metadata", "section": "startup"}),
                ("persistence.changed", {"reason": "initial_inventory", "section": "startup"}),
                ("coverage.degraded", {"section": "tasks", "status": "error"})):
            resolved = copy.deepcopy(events[0])
            resolved.update(event_type=event_type, transition="resolved", severity="info",
                            evidence={"previous": evidence, "status": "resolved_by_two_complete_observations"})
            # Even a degraded recovery payload cannot activate a default
            # classification rule. Recovery severity belongs to its detector.
            resolved["coverage"]["status"] = "error"
            with self.subTest(event_type=event_type, evidence=evidence):
                self.assertEqual(apply_rules([resolved], DEFAULT_RULES), [resolved])

    def test_last_matching_rule_wins_and_disabled_is_preserved(self):
        _, events = evaluate([listener()], now=1000)
        first = single_rule([condition("event_type", "eq", "listener.changed")], severity="high", identity="first")
        second = single_rule([condition("evidence.protocol", "in", ["TCP", "UDP"])], severity="critical", identity="second")
        self.assertEqual(apply_rules(events, [first, second])[0]["severity"], "critical")
        second["enabled"] = False
        self.assertEqual(apply_rules(events, [first, second])[0]["severity"], "high")
        first["enabled"] = False
        self.assertEqual(apply_rules(events, [first, second]), events)

    def test_missing_numeric_fact_does_not_match_or_become_zero(self):
        _, events = evaluate([source("tasks", status="denied")], now=1000)
        rules = [single_rule([condition("evidence.port", "eq", 0)])]
        self.assertEqual(apply_rules(events, rules), events)
        for malformed in (True, "0", None, -1, 70000):
            events[0]["evidence"]["port"] = malformed
            self.assertEqual(apply_rules(events, rules), events)

    def test_unknown_and_denied_events_cannot_be_silently_dropped(self):
        _, events = evaluate([source("tasks", status="unknown"), source("defender", status="denied")], now=1000)
        rules = [single_rule([condition("event_type", "eq", "listener.changed")])]
        self.assertEqual(apply_rules(events, rules), events)
        self.assertEqual({event["coverage"]["status"] for event in events}, {"unknown", "denied"})
        self.assertTrue(all(event["inference"]["compromise_conclusion"] == "undetermined" for event in events))

    def test_recovery_uses_previous_typed_source_and_evidence(self):
        state, events = evaluate([listener()], now=1000)
        state, _ = evaluate([source("listeners")], state, now=1010)
        state, recovered = evaluate([source("listeners")], state, now=1020)
        rule = single_rule([condition("source", "eq", "listeners"), condition("evidence.port", "eq", 8080),
                            condition("transition", "eq", "resolved")], severity="info")
        changed = apply_rules(recovered, [rule])
        self.assertEqual(changed[0]["transition"], "resolved")
        self.assertEqual(changed[0]["severity"], "info")
        self.assertEqual(changed[0]["evidence"], recovered[0]["evidence"])

    def test_code_paths_free_text_and_actions_are_not_valid_conditions(self):
        for field, op, value in (("command", "eq", "whoami"), ("evidence.name", "eq", "run shell"),
                                 ("source", "regex", ".*"), ("source", "eq", "__import__('os')"),
                                 ("evidence.port", "eq", True), ("evidence.port", "gte", 65536)):
            with self.subTest(field=field, op=op, value=value), self.assertRaises(RulesValidationError):
                validate_rules([single_rule([condition(field, op, value)])])
        rule = single_rule([condition("source", "eq", "listeners")])
        rule["allowed_actions"] = ["stop_service"]
        with self.assertRaisesRegex(RulesValidationError, "rules_invalid_rule"):
            validate_rules([rule])

    def test_rule_names_are_bounded_and_control_characters_rejected(self):
        rule = single_rule([condition("source", "eq", "listeners")])
        for name in ("", " ", "x" * 81, "文字\r\n指令", "文字\x00指令", "文字\u202e指令"):
            rule["name"] = name
            with self.subTest(name=repr(name)), self.assertRaisesRegex(RulesValidationError, "rules_invalid_name"):
                validate_rules([rule])

    def test_duplicate_ids_empty_conditions_and_excess_rules_fail(self):
        rule = single_rule([condition("source", "eq", "listeners")])
        for rules in ([rule, rule], [{**rule, "conditions": []}], [], [rule] * 65):
            with self.assertRaises(RulesValidationError):
                validate_rules(rules)

    def test_malformed_json_duplicate_keys_and_oversize_do_not_select_defaults(self):
        path = self.root / "config/rules.json"
        for value, reason in ((b"{", "rules_invalid_json"),
                              (b'{"schema_version":"1.0","rules":[],"rules":[]}', "rules_duplicate_json_key"),
                              (b" " * (MAX_RULE_BYTES + 1), "rules_file_too_large"),
                              (b"\xff", "rules_invalid_json")):
            path.write_bytes(value)
            with self.subTest(reason=reason), self.assertRaisesRegex(RulesValidationError, reason):
                load_rules(self.root)

    def test_unknown_document_fields_and_invalid_rule_fail_explicitly(self):
        for document in ({"schema_version": "2.0", "rules": DEFAULT_RULES},
                         {"schema_version": "1.0", "rules": DEFAULT_RULES, "shell": "anything"},
                         {"schema_version": "1.0", "rules": "not-a-list"}):
            (self.root / "config/rules.json").write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(RulesValidationError):
                load_rules(self.root)

    def test_read_failure_does_not_select_defaults_or_echo_os_error(self):
        with patch("pathlib.Path.open", side_effect=PermissionError("private path must not appear")):
            with self.assertRaisesRegex(RulesValidationError, "^rules_read_failed$"):
                load_rules(self.root)


class MonitorRuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        shutil.copy2(BASE / "config/default.json", self.root / "config/default.json")
        (self.root / "tests/fixtures").mkdir(parents=True)
        self.fixture = self.root / "tests/fixtures/rules.json"
        self.fixture.write_text(json.dumps({"frames": [{"sections": [listener(8080)]},
                                                       {"sections": [listener(8081)]}]}), encoding="utf-8")
        self.enterContext(patch.object(Monitor, "_own_low_priority", return_value="fixture"))

    def rules(self, severity):
        rules = copy.deepcopy(DEFAULT_RULES)
        rules[1]["severity"] = severity
        atomic_json(self.root / "config/rules.json", {"schema_version": "1.0", "rules": rules})

    def test_real_monitor_fixture_persists_user_severity_and_reloads_next_round(self):
        self.rules("high")
        monitor = Monitor(self.root)
        def completed(health):
            if health["cycles"] == 1:
                self.rules("critical")
        result = monitor.run(max_cycles=2, fixture="tests/fixtures/rules.json", on_cycle=completed)
        self.assertEqual(result["state"], "stopped")
        events = EventStore(Runtime(self.root).data_dir("test")).list_events()
        by_port = {event["evidence"]["port"]: event for event in events if event["event_type"] == "listener.changed"}
        self.assertEqual({port: event["severity"] for port, event in by_port.items()}, {8080: "high", 8081: "critical"})
        self.assertTrue(all(event["synthetic"] for event in by_port.values()))
        self.assertTrue(all(event["delivery_status"] == "pending" for event in by_port.values()))
        self.assertEqual(result["model_calls"], 0)

    def test_bad_startup_rules_prevent_collection_and_leave_no_new_runtime(self):
        (self.root / "config/rules.json").write_text("{", encoding="utf-8")
        with patch("eventguard.collectors.windows.WindowsCollectors") as collectors:
            with self.assertRaisesRegex(RulesValidationError, "rules_invalid_json"):
                Monitor(self.root).run(max_cycles=1)
        collectors.assert_not_called()
        self.assertFalse((self.root / "data").exists())

    def test_bad_reload_preserves_first_events_and_stops_before_next_collection(self):
        def completed(health):
            (self.root / "config/rules.json").write_text("{", encoding="utf-8")
        result = Monitor(self.root).run(max_cycles=2, fixture="tests/fixtures/rules.json", on_cycle=completed)
        self.assertEqual(result["state"], "blocked_rules")
        self.assertEqual(result["last_error"], "rules_invalid_json")
        self.assertEqual(result["cycles"], 1)
        events = EventStore(Runtime(self.root).data_dir("test")).list_events()
        self.assertEqual([event["evidence"]["port"] for event in events if event["event_type"] == "listener.changed"], [8080])
        self.assertTrue(all(event["delivery_status"] == "pending" for event in events))

    def test_bad_reload_still_finishes_owned_runner(self):
        class FixtureRunner:
            pending = True
            shutdown_called = False
            def shutdown(self):
                self.shutdown_called = True
                self.pending = False
                return {"managed": False, "child_exited": True}
        class FixtureCollectors:
            runner = FixtureRunner()
        collectors = FixtureCollectors()
        def completed(health):
            (self.root / "config/rules.json").write_text("{", encoding="utf-8")
        result = Monitor(self.root, collectors=collectors).run(
            max_cycles=2, fixture="tests/fixtures/rules.json", on_cycle=completed)
        self.assertTrue(collectors.runner.shutdown_called)
        self.assertFalse(collectors.runner.pending)
        self.assertEqual(result["state"], "blocked_rules")
        self.assertFalse(result["monitoring"])


if __name__ == "__main__":
    unittest.main()
