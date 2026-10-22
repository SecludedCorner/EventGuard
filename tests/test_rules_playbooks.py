"""Synthetic rule/playbook contracts. Never queries the host or executes tools."""
import copy
import json
from pathlib import Path
import sys
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from eventguard.rules.detector import evaluate, DetectorCapacityError, StateValidationError
from eventguard.rules.playbooks import validate_playbooks, simulate


def section(name, rows=None, status="ok"):
    return {"id": name, "status": status, "rows": [] if rows is None else rows,
            "observed_at": "2026-10-22T00:00:00Z", "elapsed_ms": 0, "coverage": {"status": status}}


def defender(first=True, second=True):
    return section("defender", [{"property": "AntivirusEnabled", "value": first, "status": "ok"},
                                {"property": "RealTimeProtectionEnabled", "value": second, "status": "ok"}])


def endpoint(port=8080, address="0.0.0.0", pid=42):
    return {"protocol": "TCP", "address": address, "port": port, "pid": pid, "scope": "all_interfaces", "status": "ok"}


class DetectorTests(unittest.TestCase):
    def test_normal_empty_and_consistent_have_zero_events(self):
        sources = [defender(), section("listeners"), section("processes"), section("startup"), section("services"), section("tasks")]
        state, events = evaluate(sources, now=1000)
        self.assertEqual(events, [])
        state, events = evaluate(sources, state, now=1120)
        self.assertEqual(events, [])

    def test_first_baseline_reveals_existing_protection_and_listener(self):
        state, events = evaluate([defender(False, False), section("listeners", [endpoint()])], now=1000)
        self.assertEqual({event["event_type"] for event in events}, {"protection.changed", "listener.changed"})
        for event in events:
            self.assertEqual(event["schema_version"], "2.0")
            self.assertEqual(event["inference"]["compromise_conclusion"], "undetermined")
            self.assertFalse(event["synthetic"])

    def test_endpoint_scope_is_not_an_internet_verdict(self):
        state, events = evaluate([section("listeners", [endpoint(address="127.0.0.1"), endpoint(8081, "192.168.1.2")])], now=1000)
        self.assertEqual(events, [])
        state, events = evaluate([section("listeners", [endpoint(address="::")])], state, now=1120)
        self.assertEqual(len(events), 1)
        self.assertIn("未知", events[0]["inference"]["summary"])

    def test_escalation_preserves_episode_and_increments_sequence(self):
        state, first = evaluate([defender(False, True)], now=1000)
        state, second = evaluate([defender(False, False)], state, now=1001)
        self.assertEqual(second[0]["transition"], "escalated")
        self.assertEqual(second[0]["severity"], "high")
        self.assertEqual(first[0]["episode_id"], second[0]["episode_id"])
        self.assertNotEqual(first[0]["event_id"], second[0]["event_id"])
        self.assertEqual(second[0]["sequence"], 2)

    def test_resolved_requires_two_complete_observations(self):
        state, events = evaluate([defender(False, False)], now=1000)
        state, events = evaluate([defender()], state, now=1120)
        self.assertEqual(events, [])
        state, events = evaluate([defender()], state, now=1240)
        self.assertEqual(events[0]["transition"], "resolved")
        self.assertIn("previous", events[0]["evidence"])
        self.assertNotIn("current", events[0]["evidence"])

    def test_missing_partial_denied_and_unknown_never_resolve_risk(self):
        for mode in ("partial", "denied", "unknown", "error"):
            state, _ = evaluate([section("listeners", [endpoint()])], now=1000)
            for stamp in (1120, 1240, 1360):
                state, events = evaluate([section("listeners", [], mode)], state, now=stamp)
                self.assertFalse(any(e["event_type"] == "listener.changed" and e["transition"] == "resolved" for e in events))
            state, events = evaluate([], state, now=1480)
            self.assertEqual(events, [])

    def test_failed_observation_breaks_recovery_streak(self):
        state, _ = evaluate([defender(False, True)], now=1000)
        state, _ = evaluate([defender()], state, now=1120)
        state, _ = evaluate([section("defender", [], "denied")], state, now=1240)
        state, events = evaluate([defender()], state, now=1360)
        self.assertFalse(any(e["event_type"] == "protection.changed" and e["transition"] == "resolved" for e in events))
        state, events = evaluate([defender()], state, now=1480)
        self.assertTrue(any(e["event_type"] == "protection.changed" and e["transition"] == "resolved" for e in events))

    def test_malformed_success_rows_are_partial_and_not_recovery(self):
        state, _ = evaluate([section("listeners", [endpoint()])], now=1000)
        for stamp in (1120, 1240):
            state, events = evaluate([section("listeners", [{"protocol":"TCP","port":None,"address":None,"status":"ok"}])], state, now=stamp)
            self.assertFalse(any(e["event_type"] == "listener.changed" and e["transition"] == "resolved" for e in events))
        self.assertIn("listener:", json.dumps(state))

    def test_coverage_fault_deduplicates_and_is_not_infection(self):
        state, events = evaluate([section("processes", [], "denied")], now=1000)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "coverage.degraded")
        state, events = evaluate([section("processes", [], "denied")], state, now=1120)
        self.assertEqual(events, [])
        state, events = evaluate([section("processes")], state, now=1240)
        self.assertEqual(events, [])
        state, events = evaluate([section("processes")], state, now=1360)
        self.assertEqual(events[0]["transition"], "resolved")

    def test_optional_registry_missing_allows_startup_baseline(self):
        missing = {"source":"HKCU/RunOnce","name":"(key absent)","kind":"registry_missing","status":"not_applicable"}
        existing = {"source":"HKCU/Run","name":"existing","kind":"registry","status":"ok"}
        state, events = evaluate([section("startup", [missing, existing], "partial")], now=1000)
        self.assertIn("startup", state["baselines"])
        self.assertEqual(events[0]["severity"], "info")
        added = {"source":"HKCU/Run","name":"(legitimate-name)","kind":"registry","status":"ok"}
        state, events = evaluate([section("startup", [missing, existing, added], "partial")], state, now=1120)
        self.assertEqual(events[0]["event_type"], "persistence.changed")
        self.assertEqual(events[0]["severity"], "warning")

    def test_skipped_folder_does_not_complete_baseline(self):
        state, events = evaluate([section("startup", [{"name":"skipped","kind":"folder_skipped","status":"unknown"}], "partial")], now=1000)
        self.assertNotIn("startup", state["baselines"])
        self.assertEqual(events[0]["event_type"], "coverage.degraded")

    def test_partial_or_truncated_startup_is_not_relaxed(self):
        missing = {"source":"HKCU/RunOnce","name":"(key absent)","kind":"registry_missing","status":"not_applicable"}
        supplied = section("startup", [missing], "partial")
        supplied["truncated"] = True
        state, _ = evaluate([supplied], now=1000)
        self.assertNotIn("startup", state["baselines"])
        supplied["truncated"] = False
        supplied["coverage"]["truncated"] = True
        state, _ = evaluate([supplied], now=1000)
        self.assertNotIn("startup", state["baselines"])
        state, _ = evaluate([section("startup", [{"name":"example","status":"ok"}], "partial")], now=1000)
        self.assertNotIn("startup", state["baselines"])

    def test_service_and_task_state_diff(self):
        for source in ("services", "tasks"):
            state, events = evaluate([section(source, [{"name":"demo","state":"Stopped","status":"ok"}])], now=1000)
            self.assertEqual(events[0]["severity"], "info")
            state, events = evaluate([section(source, [{"name":"demo","state":"Running","status":"ok"}])], state, now=1120)
            self.assertEqual(events[0]["severity"], "warning")

    def test_same_named_tasks_in_different_paths_are_distinct(self):
        state, _ = evaluate([section("tasks", [{"name":"demo","task_path":"/first/","state":"Ready","status":"ok"}])], now=1000)
        state, events = evaluate([section("tasks", [{"name":"demo","task_path":"/first/","state":"Ready","status":"ok"},{"name":"demo","task_path":"/second/","state":"Ready","status":"ok"}])], state, now=1120)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["severity"], "warning")

    def test_cooldown_suppresses_flap_but_eventually_reports_persistent_new(self):
        state, original = evaluate([defender(False, True)], now=1000)
        state, _ = evaluate([defender()], state, now=1010)
        state, restored = evaluate([defender()], state, now=1020)
        self.assertEqual(restored[0]["transition"], "resolved")
        state, events = evaluate([defender(False, True)], state, now=1030)
        self.assertEqual(events, [])
        state, events = evaluate([defender(False, True)], state, now=1321)
        self.assertEqual(events[0]["transition"], "new")
        self.assertNotEqual(events[0]["episode_id"], original[0]["episode_id"])

    def test_higher_new_episode_is_not_suppressed_by_cooldown(self):
        state, _ = evaluate([defender(False, True)], now=1000)
        state, _ = evaluate([defender()], state, now=1010)
        state, _ = evaluate([defender()], state, now=1020)
        state, events = evaluate([defender(False, False)], state, now=1030)
        self.assertEqual(events[0]["severity"], "high")

    def test_restart_roundtrip_does_not_reemit(self):
        state, first = evaluate([section("listeners", [endpoint()])], now=1000)
        restored = json.loads(json.dumps(state))
        restored, events = evaluate([section("listeners", [endpoint()])], restored, now=1120)
        self.assertEqual(events, [])
        self.assertEqual(len(first), 1)

    def test_storm_returns_at_most_twenty_and_preserves_all_transition_ids(self):
        sources = [section("listeners", [endpoint(10000+i) for i in range(45)])]
        state, events = evaluate(sources, now=1000)
        seen = list(events)
        self.assertEqual(len(events), 20)
        self.assertGreater(state["metrics"]["suppression_count"], 0)
        for stamp in (1120, 1240, 1360, 1480):
            state = json.loads(json.dumps(state))
            state, events = evaluate(sources, state, now=stamp)
            self.assertLessEqual(len(events), 20)
            seen.extend(events)
        listeners = [e for e in seen if e["event_type"] == "listener.changed"]
        self.assertEqual(len(listeners), 45)
        self.assertEqual(len({e["event_id"] for e in listeners}), 45)
        self.assertEqual(state["deferred"], [])

    def test_capacity_is_explicit_and_input_is_unchanged(self):
        state, _ = evaluate([], now=1000)
        before = copy.deepcopy(state)
        with self.assertRaises(DetectorCapacityError):
            evaluate([section("listeners", [endpoint(i+1) for i in range(1001)])], state, now=1120)
        self.assertEqual(state, before)

    def test_secret_and_arbitrary_history_are_never_persisted(self):
        row = {"source":"Run","name":"PRIVATE-NAME","kind":"registry","status":"ok","command_line":"SECRET-TOKEN"}
        state, events = evaluate([section("startup", [row]), section("threat_history", [{"name":"Trojan:Win32/ClickFix.ZZI!MTB","IsActive":False,"DidThreatExecute":False,"status":"ok"}])], now=1000)
        encoded = json.dumps([state, events])
        self.assertNotIn("SECRET-TOKEN", encoded)
        self.assertNotIn("PRIVATE-NAME", encoded)
        self.assertNotIn("ClickFix", encoded)
        self.assertTrue(all(e["inference"]["compromise_conclusion"] == "undetermined" for e in events))

    def test_invalid_state_and_duplicate_sections_fail_visibly(self):
        with self.assertRaises(StateValidationError):
            evaluate([], {"schema_version":"invalid"}, now=1000)
        with self.assertRaises(ValueError):
            evaluate([section("startup"), section("startup")], now=1000)


class PlaybookTests(unittest.TestCase):
    def setUp(self):
        self.path = BASE / "playbooks" / "default.json"
        self.document = json.loads(self.path.read_text(encoding="utf-8"))
        self.event = {"event_type":"listener.changed","transition":"new","severity":"warning","synthetic":True,"event_id":"evt-test"}

    def test_default_has_four_valid_complete_playbooks(self):
        self.assertEqual(len(self.document["playbooks"]), 4)
        self.assertEqual(validate_playbooks(self.path), [])
        for rule in self.document["playbooks"]:
            self.assertEqual(rule["allowed_actions"], [])
            self.assertTrue(rule["approval_gate"]["required_for_sensitive_actions"])

    def test_dry_run_plans_only_without_granting_authority(self):
        result = simulate(self.event, self.document)
        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["selected_rule"]["rule_id"], "pb-listener-change")
        self.assertFalse(result["authorization_granted"])
        self.assertEqual(result["actions_executed"], [])
        self.assertEqual(result["tools_executed"], [])

    def test_no_rule_is_safe_unknown_not_a_guessed_action(self):
        result = simulate(dict(self.event, event_type="unknown.signal"), self.document)
        self.assertEqual(result["status"], "no_match")
        self.assertEqual(result["actions_executed"], [])

    def test_shell_bad_edges_cycles_and_unknown_schema_are_rejected(self):
        for mutation in ("shell", "edge", "cycle", "schema"):
            document = copy.deepcopy(self.document)
            rule = document["playbooks"][0]
            if mutation == "shell":
                rule["shell"] = "do not execute"
            elif mutation == "edge":
                rule["edges"][0]["to"] = "missing-node"
            elif mutation == "cycle":
                rule["edges"].append({"from":rule["investigation_steps"][-1]["id"],"on":["ok"],"to":rule["investigation_steps"][0]["id"]})
            else:
                document["schema_version"] = "99.0"
            self.assertTrue(validate_playbooks(document), mutation)
            self.assertEqual(simulate(self.event, document)["status"], "invalid_playbooks")

    def test_conflicting_rules_do_not_choose_arbitrarily(self):
        duplicate = copy.deepcopy(self.document["playbooks"][0])
        duplicate["rule_id"] += "-conflict"
        self.document["playbooks"].append(duplicate)
        result = simulate(self.event, self.document)
        self.assertIn(result["status"], ("conflict", "invalid_playbooks"))
        self.assertEqual(result["actions_executed"], [])

    def test_action_list_does_not_grant_authority(self):
        self.document["playbooks"][0]["allowed_actions"] = ["stop_process"]
        result = simulate(self.event, self.document)
        self.assertEqual(result["actions_executed"], [])
        self.assertFalse(result["authorization_granted"])
        self.assertTrue(result["blocked_actions"])


if __name__ == "__main__":
    unittest.main()
