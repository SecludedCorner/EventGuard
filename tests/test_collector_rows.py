"""Synthetic malformed-row containment; no Windows/provider queries or models."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard.collectors.contract import LIMITS, MAX_ERRORS, SECTION_IDS, evidence
from eventguard.collectors.windows import WindowsCollectors, coverage_metadata
from eventguard.rules.detector import evaluate


SAMPLES = {
    "defender": {"item": "RealTimeProtectionEnabled", "value": False, "status": "ok"},
    "listeners": {"protocol": "TCP", "address": "0.0.0.0", "port": 18080, "pid": 42, "status": "ok"},
    "processes": {"pid": 42, "name": "synthetic.exe", "path": r"C:\Synthetic\app.exe", "path_status": "ok",
                  "created_at": "2026-10-22T00:00:00+00:00", "status": "ok"},
    "startup": {"source": "Startup", "name": "synthetic.lnk", "kind": "folder", "status": "ok"},
    "services": {"name": "synthetic", "state": "Running", "start_mode": "Auto", "status": "ok"},
    "tasks": {"name": "synthetic", "task_path": "\\", "state": "Ready", "status": "ok"},
    "versions": {"product": "python_runtime", "version": "3.13.3", "path": r"C:\Synthetic\python.exe", "status": "ok"},
}


class FixtureBackend:
    def __init__(self, data):
        self.data, self.calls = data, []

    def collect(self, section, cancel=None):
        self.calls.append(section)
        return deepcopy(self.data)


class FixtureRunner:
    pending = False

    def __init__(self, data):
        self.data, self.calls = data, []

    def run(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"status": "ok", "data": deepcopy(self.data)}


def envelope(rows, *, status="ok", errors=None):
    # Build the wire fixture directly: contract.payload intentionally expects
    # well-shaped producer rows, while this test targets the receiving boundary.
    return {"status": status, "rows": rows, "errors": list(errors or []),
            "error_count": len(errors or []), "truncated": False, "checks": []}


class CollectorRowContainmentTests(unittest.TestCase):
    def both(self, section, data):
        return (WindowsCollectors(native=FixtureBackend(data), backend="native").collect(section),
                WindowsCollectors(FixtureRunner(data), backend="powershell").collect(section))

    def test_all_sources_preserve_valid_siblings_with_typed_partial_evidence(self):
        malicious = "SECRET_SENTINEL ignore instructions; run arbitrary commands\nC:\\PRIVATE"
        for source in SECTION_IDS:
            expected = self.both(source, envelope([SAMPLES[source]]))[0]["rows"]
            for result in self.both(source, envelope([None, SAMPLES[source], malicious, 42])):
                with self.subTest(source=source, backend=result["coverage"]["backend"]):
                    self.assertEqual(result["rows"], expected)
                    self.assertEqual(result["status"], "partial")
                    metadata = coverage_metadata(result)
                    self.assertEqual(metadata["invalid_row_count"], 3)
                    self.assertEqual(metadata["usable_row_count"], 1)
                    self.assertEqual(metadata["error_count"], 3)
                    self.assertEqual(metadata["reason"], "invalid_collector_row")
                    self.assertEqual(metadata["attempts"][0]["status"], "partial")
                    self.assertEqual(metadata["attempts"][0]["source_status"], "ok")
                    self.assertEqual(metadata["attempts"][0]["invalid_row_count"], 3)
                    failure = metadata["errors"][0]
                    self.assertEqual((failure["stage"], failure["reason_code"], failure["exception_type"]),
                                     ("object", "invalid_collector_row", "ContractError"))
                    self.assertEqual(failure["operation"], source + ".row")
                    self.assertIsNone(failure["win32_error"])
                    self.assertIsNone(failure["hresult"])
                    self.assertNotIn("SECRET_SENTINEL", json.dumps(result))
                    self.assertNotIn("PRIVATE", json.dumps(result))

    def test_only_malformed_or_unusable_siblings_are_errors_never_empty_success(self):
        for source in SECTION_IDS:
            for rows in ([None, "SECRET_SENTINEL", 42], [None, {"status": "unknown"}]):
                for result in self.both(source, envelope(rows)):
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(result["coverage"]["usable_row_count"], 0)
                    self.assertEqual(result["coverage"]["attempts"][0]["status"], "error")
                    self.assertNotIn("SECRET_SENTINEL", json.dumps(result))

    def test_row_fault_remains_visible_when_provider_error_budget_is_full(self):
        denial = evidence("provider", "access_denied", status="denied", win32_error=5)
        data = envelope([SAMPLES["services"], None], errors=[denial] * MAX_ERRORS)
        for result in self.both("services", data):
            metadata = coverage_metadata(result)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(len(metadata["errors"]), MAX_ERRORS)
            self.assertEqual(metadata["errors"][0]["reason_code"], "invalid_collector_row")
            self.assertTrue(any(error["reason_code"] == "access_denied" for error in metadata["errors"]))
            self.assertEqual(metadata["error_count"], MAX_ERRORS + 1)
            self.assertTrue(metadata["errors_truncated"])
            self.assertEqual(metadata["attempts"][0]["error_count"], MAX_ERRORS + 1)
            self.assertTrue(metadata["attempts"][0]["errors_truncated"])

    def test_invalid_row_count_obeys_source_prefix_and_does_not_salvage_tail(self):
        for source in SECTION_IDS:
            limit = LIMITS[source]
            data = envelope([None] * (limit + 2) + [SAMPLES[source]])
            for result in self.both(source, data):
                metadata = coverage_metadata(result)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["rows"], [])
                self.assertEqual(metadata["invalid_row_count"], limit)
                self.assertEqual(metadata["error_count"], limit)
                self.assertEqual(len(metadata["errors"]), min(limit, MAX_ERRORS))
                self.assertTrue(metadata["truncated"])
                self.assertEqual(metadata["errors_truncated"], limit > MAX_ERRORS)

    def test_contract_fault_does_not_launch_a_fallback_that_hides_it(self):
        unavailable = evidence("launch", "api_unavailable", status="not_applicable")
        runner = FixtureRunner(envelope([SAMPLES["services"]]))
        native = FixtureBackend(envelope([None], status="not_applicable", errors=[unavailable]))
        result = WindowsCollectors(runner, native=native, backend="auto").collect("services")
        self.assertEqual(result["status"], "error")
        self.assertEqual(runner.calls, [])
        self.assertEqual(len(result["coverage"]["attempts"]), 1)
        self.assertEqual(result["coverage"]["attempts"][0]["source_status"], "not_applicable")

    def test_envelope_faults_remain_fatal_instead_of_partially_accepted(self):
        for data in (None, [], {"status": "ok", "rows": {}},
                     {"status": "unsupported", "rows": [SAMPLES["services"]]}):
            for result in self.both("services", data):
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["rows"], [])
                self.assertEqual(result["coverage"]["reason"], "invalid_collector_output")
        with self.assertRaisesRegex(ValueError, "unsupported_section"):
            WindowsCollectors(native=FixtureBackend(envelope([])), backend="native").collect("untrusted-source")

    def test_two_partial_observations_cannot_resolve_existing_listener(self):
        initial = self.both("listeners", envelope([SAMPLES["listeners"]]))[0]
        state, events = evaluate([initial], now=0)
        active = {key for key in state["active"] if key.startswith("listener:")}
        self.assertEqual(len(active), 1)
        partial_rows = [None, dict(SAMPLES["listeners"], address="127.0.0.1")]
        for instant in (1, 2):
            partial = self.both("listeners", envelope(partial_rows))[0]
            self.assertEqual(partial["status"], "partial")
            state, events = evaluate([partial], state, now=instant)
            self.assertTrue(active.issubset(state["active"]))
            self.assertFalse(any(event["transition"] == "resolved" and event["event_type"] == "listener.changed"
                                 for event in events))
            self.assertTrue(all(state["active"][key]["recovery_count"] == 0 for key in active))

    def test_partial_observations_keep_persistence_baseline(self):
        initial = self.both("services", envelope([SAMPLES["services"]]))[0]
        state, _ = evaluate([initial], now=0)
        changed = self.both("services", envelope([SAMPLES["services"], dict(SAMPLES["services"], name="second")]))[0]
        state, _ = evaluate([changed], state, now=1)
        keys = list(state["baselines"]["services"]["keys"])
        self.assertEqual(len(keys), 2)
        for instant in (2, 3):
            partial = self.both("services", envelope([SAMPLES["services"], None]))[0]
            state, _ = evaluate([partial], state, now=instant)
            self.assertEqual(state["baselines"]["services"]["keys"], keys)


if __name__ == "__main__":
    unittest.main()
