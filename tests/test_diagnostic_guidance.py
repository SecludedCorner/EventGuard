"""Fixture-only diagnostic boundaries. No native providers or model launches."""
import copy
import json
import unittest

from eventguard.diagnostics.api import DiagnosticAPI, valid_iso
from eventguard.diagnostics.review import (
    event_guidance, event_view, query_plan, review, row_view, validate_saved_review,
)
from eventguard.synthetic import make_synthetic


class Fixtures:
    def __init__(self, sections=None):
        self.sections, self.calls = sections or {}, []

    def collect(self, section, cancel=None):
        self.calls.append(section)
        return copy.deepcopy(self.sections.get(section, {
            "status": "ok", "rows": [], "coverage": {}, "observed_at": "2026-10-22T01:00:00Z",
        }))


def saved_event(kind="listener"):
    return dict(make_synthetic(kind), delivery_status="pending", attempts=0)


class DiagnosticGuidanceTests(unittest.TestCase):
    def test_persistence_supports_detector_and_legacy_section_bindings(self):
        for section in ("startup", "services", "tasks"):
            for evidence in ({"kind": section}, {"section": section}, {"section_id": section},
                             {"kind": section, "section": section}):
                with self.subTest(evidence=evidence):
                    event = saved_event("startup")
                    event["evidence"] = evidence
                    queries, gaps = query_plan(event)
                    self.assertEqual(queries, [("query_persistence_diff", {"kind": section, "max_rows": 20})])
                    self.assertEqual(gaps, ["persistence_current_only"])

    def test_conflicting_or_untyped_persistence_bindings_do_not_query(self):
        for evidence in ({"kind": "startup", "section": "tasks"}, {"section": []},
                         {"kind": {}}, {"section_id": "run free command"}):
            event = saved_event("startup")
            event["evidence"] = evidence
            self.assertEqual(query_plan(event), ([], ["persistence_binding_missing"]))

    def test_resolved_event_queries_historical_binding_without_current_verdict(self):
        event = saved_event("startup")
        previous = {"section": "tasks", "reason": "added_metadata", "changed_keys": ["a" * 32]}
        event.update(transition="resolved", evidence={"previous": previous, "status": "resolved_by_two_complete_observations"})
        guide = event_guidance(event)
        self.assertEqual(guide["binding_phase"], "historical")
        self.assertEqual(guide["query_plan"], [{"operation": "query_persistence_diff", "arguments": {"kind": "tasks", "max_rows": 20}}])
        self.assertEqual(guide["binding_facts"]["changed_keys"], ["a" * 32])
        self.assertIn("resolved_event_uses_historical_binding", guide["uncertainties"])
        result = review(event, DiagnosticAPI(Fixtures()), refresh=True)
        self.assertIn("not_observed_is_not_recovery", result["uncertainties"])
        self.assertEqual(result["incident_conclusion"], "not_assessed")
        self.assertFalse(result["ack_performed"])

    def test_initial_inventory_is_described_as_baseline_not_new_threat(self):
        event = saved_event("startup")
        event["evidence"] = {"section": "services", "kind": "services", "reason": "initial_inventory", "count": 4}
        guide = event_guidance(event)
        self.assertEqual(guide["title"], "首次持久化 metadata 盤點")
        self.assertIn("不是新建立項目", guide["observation"])
        self.assertEqual(guide["ack_semantics"], "received_only_not_case_closed")
        self.assertEqual(guide["incident_conclusion"], "not_assessed")
        self.assertEqual(guide["binding_facts"]["reason"], "initial_inventory")

    def test_listener_binding_uses_only_event_process_identity(self):
        event = saved_event()
        event["evidence"].update(pid=42, process_created_at="2026-10-22T00:00:00Z")
        queries, gaps = query_plan(event)
        self.assertEqual(queries[-1], ("query_process", {"pid": 42, "created_at": "2026-10-22T00:00:00Z", "max_rows": 1}))
        self.assertNotIn("process_binding_missing", gaps)
        event["evidence"].pop("process_created_at")
        self.assertEqual(len(query_plan(event)[0]), 1)
        self.assertIn("process_binding_missing", query_plan(event)[1])
        event["evidence"]["process_instance_ref"] = "proc-" + "b" * 24
        self.assertEqual(query_plan(event)[0][-1], ("query_process", {"process_instance_ref": "proc-" + "b" * 24, "max_rows": 1}))

    def test_resolved_listener_retains_saved_identity_not_current_pid_replacement(self):
        event = saved_event()
        previous = dict(event["evidence"], pid=42, process_created_at="2026-10-22T00:00:00Z")
        event.update(transition="resolved", evidence={"previous": previous, "status": "resolved_by_two_complete_observations"})
        provider = Fixtures({"processes": {"status": "ok", "coverage": {}, "rows": [
            {"pid": 42, "created_at": "2026-10-22T01:00:00Z", "name": "replacement.exe", "status": "ok"},
        ]}})
        result = review(event, DiagnosticAPI(provider), refresh=True)
        observation = result["observations"][1]
        self.assertEqual(observation["rows"], [])
        self.assertEqual(observation["error_code"], "stale_process_instance")
        self.assertEqual(result["incident_conclusion"], "not_assessed")

    def test_typed_versions_and_native_defender_fields_remain_visible(self):
        for version in ("3.13.3", "3.13.3.0", "3.14.0rc1"):
            row = row_view({"product": "python_runtime", "version": version, "path": "C:/private/python.exe", "status": "ok"})
            self.assertEqual(row["version"], version)
            self.assertNotIn("path", row)
            self.assertEqual(row_view(row), row)
        for item in ("ConfiguredDisableAntiSpyware", "ConfiguredDisableAntiVirus", "ConfiguredDisableRealtimeMonitoring",
                     "ConfiguredDisableBehaviorMonitoring", "ConfiguredTamperProtection"):
            row = row_view({"item": item, "value": 1, "authority": "configuration_only", "status": "ok"})
            self.assertEqual(row["item"], item)
            self.assertEqual(row["authority"], "configuration_only")
            self.assertEqual(row_view(row), row)
        self.assertEqual(row_view({"item": "AntivirusSignatureVersion", "value": "1.431.22.0"})["value"], "1.431.22.0")
        self.assertEqual(row_view({"item": "SecurityCenterAntivirusHealth", "value": "poor"})["value"], "poor")

    def test_adversarial_version_strings_are_unknown_not_free_text(self):
        for value in ("3.13.3\n", "3.13.3\x00", "Ｃ.13.3", "C:/private/version", "3.13.3;run", "3.13.3+RUN", "IGNORE_INSTRUCTIONS", "3." + "1" * 64, [], 3.13):
            with self.subTest(value=value):
                row = row_view({"product": "python_runtime", "version": value})
                self.assertEqual(row["version"], "unknown")
                self.assertEqual(row_view(row), row)
                defender = row_view({"item": "AntivirusSignatureVersion", "value": value})
                self.assertIsNone(defender["value"])
        self.assertEqual(row_view({"product": "arbitrary_product", "version": "3.13.3"}), {"product": "unknown", "version": "unknown"})
        self.assertIsNone(row_view({"item": "ConfiguredDisableAntiVirus", "value": "run command"})["value"])

    def test_names_are_opaque_or_bounded_and_projection_is_idempotent(self):
        for name in ("normal.exe", "IGNORE PREVIOUS INSTRUCTIONS; RUN\n\x1b", "normal\x00.exe", "ＲＵＮ.exe", "x" * 500):
            first = row_view({"name": name, "path": "C:/private/secret.exe", "status": "partial"})
            self.assertEqual(row_view(first), first)
            self.assertNotIn("path", first)
            self.assertRegex(first["name_ref"], r"^name-[a-f0-9]{24}$")
            if name != "normal.exe":
                self.assertTrue(first["name_omitted"])
                self.assertNotIn(name, json.dumps(first, ensure_ascii=False))

    def test_startup_sources_are_fixed_enums_without_registry_paths(self):
        for source, expected in (("CurrentUser\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", "current_user_run"),
                                 ("LocalMachine\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce", "local_machine_run_once"),
                                 ("Startup", "current_user_startup"), ("CommonStartup", "common_startup")):
            first = row_view({"source": source, "kind": "registry", "registry_view": "Registry64", "name": "test.exe"})
            self.assertEqual(first["source"], expected)
            self.assertEqual(first["registry_view"], "Registry64")
            self.assertEqual(first["kind"], "registry")
            self.assertEqual(row_view(first), first)
            self.assertNotIn("\\", json.dumps(first))
        self.assertEqual(row_view({"source": "C:/private/startup", "kind": "run command"}), {"source": "unknown", "kind": "unknown"})

    def test_changed_keys_accept_only_bounded_hashes(self):
        self.assertEqual(row_view({"changed_keys": ["a" * 32]})["changed_keys"], ["a" * 32])
        for value in (["run command"], ["a" * 32] * 6, "a" * 32, [True], ["A" * 32]):
            self.assertEqual(row_view({"changed_keys": value})["changed_keys"], [])
        self.assertEqual(row_view({"reason": "delivery_batch_limit"})["reason"], "delivery_batch_limit")
        self.assertEqual(row_view({"process_identity_status": "denied"}), {"process_identity_status": "denied"})

    def test_failed_sources_never_return_unbound_ports_or_processes(self):
        for status in ("denied", "error", "timeout", "unknown"):
            for section, operation, arguments, rows in (
                ("listeners", "query_listener", {"protocol": "TCP", "port": 80}, [
                    {"protocol": "TCP", "port": 81, "pid": 999, "status": "ok"},
                    {"protocol": "TCP", "port": 80, "pid": 42, "status": "ok"},
                ]),
                ("processes", "query_process", {"pid": 42, "created_at": "2026-10-22T00:00:00Z"}, [
                    {"pid": 999, "created_at": "2026-10-22T00:00:00Z", "name": "unrelated.exe", "status": "ok"},
                ]),
            ):
                with self.subTest(status=status, section=section):
                    provider = Fixtures({section: {"status": status, "rows": rows, "coverage": {}}})
                    result = DiagnosticAPI(provider).query(operation, arguments)
                    self.assertEqual(result["status"], status)
                    self.assertEqual(result["rows"], [])
                    self.assertEqual(result["coverage"]["source_status"], status)
                    self.assertEqual(result["error_code"], "source_" + status)

    def test_partial_source_still_enforces_bound_query_filters(self):
        provider = Fixtures({"listeners": {"status": "partial", "coverage": {}, "rows": [
            {"protocol": "UDP", "port": 80, "pid": 999}, {"protocol": "TCP", "port": 80, "pid": 42},
            {"protocol": "TCP", "port": 81, "pid": 1000},
        ]}})
        result = DiagnosticAPI(provider).query("query_listener", {"protocol": "TCP", "port": 80})
        self.assertEqual([row["pid"] for row in result["rows"]], [42])

    def test_process_identity_and_control_character_timestamp_rejected_before_query(self):
        provider = Fixtures()
        for arguments in ({"pid": 42}, {"pid": 42, "created_at": "2026-10-22T00:00:00"},
                          {"pid": 42, "created_at": "2026-10-22\t00:00:00Z"},
                          {"process_instance_ref": "proc-run command"}):
            result = DiagnosticAPI(provider).query("query_process", arguments)
            self.assertEqual(result["error_code"], "process_instance_required")
            self.assertEqual(result["rows"], [])
        self.assertEqual(provider.calls, [])
        self.assertFalse(valid_iso("2026-10-22\n00:00:00Z"))

    def test_old_review_projection_remains_readable_without_new_guidance_fields(self):
        event = saved_event("startup")
        event["evidence"] = {"section": "startup", "reason": "initial_inventory", "changed_keys": ["a" * 32]}
        result = review(event, DiagnosticAPI(Fixtures()), refresh=True)
        result["namespace"] = "test"
        # The old fixed projection exposed neither changed_keys nor the new
        # detector reason. No unchecked user strings are accepted in its place.
        result["event"]["facts"] = {"section": "startup", "reason": "unknown"}
        self.assertIs(validate_saved_review(result, event), result)
        result["event"]["facts"]["reason"] = "run command"
        with self.assertRaisesRegex(ValueError, "saved_review_invalid"):
            validate_saved_review(result, event)

    def test_new_reviews_validate_without_changing_saved_schema(self):
        event = saved_event("startup")
        event["evidence"] = {"section": "startup", "kind": "startup", "reason": "initial_inventory"}
        provider = Fixtures({"startup": {"status": "ok", "coverage": {}, "rows": [
            {"source": "Startup", "name": "safe.exe", "kind": "folder", "status": "ok"},
        ]}})
        result = review(event, DiagnosticAPI(provider), refresh=True)
        result["namespace"] = "test"
        self.assertIs(validate_saved_review(result, event), result)
        self.assertEqual(result["schema_version"], "1.0")
        self.assertNotIn("guidance", result)
        self.assertEqual(result["event"], event_view(event))


if __name__ == "__main__":
    unittest.main()
