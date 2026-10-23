"""Reject syntactically valid cached observations for another event target.

All observations come from in-memory fixtures. No native query or subprocess.
"""
import copy
import unittest

from eventguard.diagnostics.api import DiagnosticAPI
from eventguard.diagnostics.review import review, validate_saved_review
from eventguard.rules.detector import evaluate
from eventguard.synthetic import make_synthetic


STAMP = "2026-10-23T01:00:00Z"
REF = "proc-" + "a" * 24


class Fixtures:
    def __init__(self, sections):
        self.sections = sections

    def collect(self, source, cancel=None):
        return {"id": source, "status": "ok", "coverage": {}, "observed_at": STAMP,
                "rows": copy.deepcopy(self.sections[source])}


def saved(event, sections):
    return dict(review(event, DiagnosticAPI(Fixtures(sections)), refresh=True), namespace="test")


def endpoint(**fields):
    return dict({"protocol": "TCP", "port": 18080, "pid": 42, "address": "0.0.0.0", "status": "ok"}, **fields)


def listener():
    return dict(make_synthetic("listener"), delivery_status="pending", attempts=0)


class SavedReviewBindingTests(unittest.TestCase):
    def assertRejected(self, result, event):
        with self.assertRaisesRegex(ValueError, "saved_review_invalid"):
            validate_saved_review(result, event)

    def test_current_exact_listener_review_is_accepted(self):
        event = listener()
        result = saved(event, {"listeners": [endpoint()]})
        self.assertIs(validate_saved_review(result, event), result)

    def test_synthetic_saved_review_cannot_claim_a_real_system_query(self):
        event = listener()
        result = saved(event, {"listeners": [endpoint()]})
        self.assertTrue(result["fixture_queries_executed"])
        self.assertFalse(result["system_query_executed"])
        result["system_query_executed"] = True
        self.assertRejected(result, event)

    def test_wrong_port_and_protocol_are_rejected_even_when_well_formed(self):
        event = listener()
        original = saved(event, {"listeners": [endpoint()]})
        for field, value in (("port", 443), ("protocol", "UDP")):
            with self.subTest(field=field):
                result = copy.deepcopy(original)
                result["observations"][0]["rows"][0][field] = value
                self.assertRejected(result, event)

    def test_wrong_source_operation_duplicate_or_missing_observation_rejected(self):
        event = listener()
        original = saved(event, {"listeners": [endpoint()]})
        for field, value in (("source", "processes"), ("operation", "query_process")):
            result = copy.deepcopy(original)
            result["observations"][0][field] = value
            self.assertRejected(result, event)
        result = copy.deepcopy(original)
        result["observations"] *= 2
        self.assertRejected(result, event)
        result = copy.deepcopy(original)
        result["observations"] = []
        self.assertRejected(result, event)

    def test_process_reference_binding_rejects_a_different_process(self):
        event = listener()
        event["evidence"]["process_instance_ref"] = REF
        result = saved(event, {"listeners": [endpoint()], "processes": [
            {"pid": 42, "process_instance_ref": REF, "name": "Safe.exe", "status": "ok"},
        ]})
        self.assertIs(validate_saved_review(result, event), result)
        result["observations"][1]["rows"][0]["process_instance_ref"] = "proc-" + "b" * 24
        self.assertRejected(result, event)

    def test_pid_creation_time_binding_rejects_reused_pid_or_other_pid(self):
        event = listener()
        event["evidence"].update(pid=42, process_created_at=STAMP)
        original = saved(event, {"listeners": [endpoint()], "processes": [
            {"pid": 42, "created_at": STAMP, "name": "Safe.exe", "status": "ok"},
        ]})
        self.assertIs(validate_saved_review(original, event), original)
        for field, value in (("pid", 43), ("created_at", "2026-10-23T02:00:00+00:00")):
            result = copy.deepcopy(original)
            result["observations"][1]["rows"][0][field] = value
            self.assertRejected(result, event)

    def test_operation_order_is_bound_to_plan(self):
        event = listener()
        event["evidence"]["process_instance_ref"] = REF
        result = saved(event, {"listeners": [endpoint()], "processes": [
            {"pid": 42, "process_instance_ref": REF, "status": "ok"},
        ]})
        result["observations"].reverse()
        self.assertRejected(result, event)

    def test_persistence_reference_binding_rejects_other_reference_and_redacts_legacy(self):
        row = {"name": "TargetService", "state": "Running", "start_mode": "Auto", "status": "ok"}
        source = lambda rows: {"id": "services", "status": "ok", "rows": rows, "coverage": {}, "observed_at": STAMP}
        state, _ = evaluate([source([])], now=1000)
        _, events = evaluate([source([row])], state, now=1120)
        event = dict(events[0], synthetic=True, delivery_status="pending", attempts=0)
        original = saved(event, {"services": [row]})
        self.assertIs(validate_saved_review(original, event), original)
        result = copy.deepcopy(original)
        result["observations"][0]["rows"][0]["entry_ref"] = "0" * 32
        self.assertRejected(result, event)
        result = copy.deepcopy(original)
        del result["observations"][0]["rows"][0]["entry_ref"]
        validated = validate_saved_review(result, event)
        self.assertEqual(validated["status"], "partial")
        self.assertEqual(validated["observations"][0]["rows"], [])
        self.assertIn("saved_diagnosis_binding_unverifiable", validated["uncertainties"])

    def test_denied_observation_cannot_smuggle_a_row_for_another_target(self):
        event = listener()
        result = saved(event, {"listeners": [endpoint()]})
        observation = result["observations"][0]
        observation["status"] = "denied"
        observation["rows"][0]["port"] = 443
        self.assertRejected(result, event)

    def test_empty_bound_observation_preserves_unknown_without_claiming_recovery(self):
        event = listener()
        result = saved(event, {"listeners": []})
        self.assertIs(validate_saved_review(result, event), result)
        self.assertIn("not_observed_is_not_recovery", result["uncertainties"])
        self.assertEqual(result["incident_conclusion"], "not_assessed")
        self.assertFalse(result["ack_performed"])

    def test_new_review_rejects_mismatched_provider_result_before_saving(self):
        event = listener()
        good = saved(event, {"listeners": [endpoint()]})["observations"][0]

        class UnboundAPI:
            def __init__(self, result):
                self.result = result

            def query(self, operation, args):
                return copy.deepcopy(self.result)

        for field, value in (("source", "processes"), ("port", 443), ("protocol", "UDP")):
            with self.subTest(field=field):
                raw = copy.deepcopy(good)
                if field == "source":
                    raw[field] = value
                else:
                    raw["rows"][0][field] = value
                result = review(event, UnboundAPI(raw), refresh=True)
                observation = result["observations"][0]
                self.assertEqual(observation["status"], "error")
                self.assertEqual(observation["rows"], [])
                self.assertEqual(observation["error_code"], "diagnostic_binding_mismatch")
                self.assertEqual(result["incident_conclusion"], "not_assessed")

    def test_new_review_rejects_mismatched_process_reference(self):
        event = listener()
        event["evidence"]["process_instance_ref"] = REF
        api = DiagnosticAPI(Fixtures({"listeners": [endpoint()], "processes": [
            {"pid": 42, "process_instance_ref": REF, "status": "ok"},
        ]}))

        class IncorrectProcess:
            def query(self, operation, args):
                raw = api.query(operation, args)
                if operation == "query_process":
                    raw["rows"][0]["process_instance_ref"] = "proc-" + "b" * 24
                return raw

        result = review(event, IncorrectProcess(), refresh=True)
        observation = result["observations"][1]
        self.assertEqual(observation["rows"], [])
        self.assertEqual(observation["error_code"], "diagnostic_binding_mismatch")


if __name__ == "__main__":
    unittest.main()
