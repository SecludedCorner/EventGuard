"""Only injected identity calls and synthetic envelopes; no native query."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_windows_listener_validation as fixtures
from eventguard.collectors.contract import MAX_ERRORS, payload
from eventguard.collectors.native import NativeBackend
from eventguard.collectors.winapi import NativeError
from eventguard.collectors.windows import WindowsCollectors

validation = fixtures.validation


class Backend:
    def __init__(self, value):
        self.value = value

    def collect(self, source, cancel=None):
        return self.value


class ListenerErrorSummaryTests(unittest.TestCase):
    def test_existing_native_codes_survive_envelope_and_projection_without_new_lookup(self):
        captured = {pid: datetime(2026, 10, 28, tzinfo=timezone.utc) for pid in range(10, 17)}
        errors = []
        responses = [NativeError("ListenerOpenProcess", 5, "object"),
                     NativeError("ListenerOpenProcess", 5, "object"),
                     NativeError("ListenerOpenProcess", 87, "object"),
                     "2026-10-28T00:00:01Z", ValueError("PRIVATE_ERROR_TEXT"),
                     NativeError("OpenProcess", 127, "launch"),
                     NativeError("ListenerGetProcessTimes", 999, "field")]
        with patch("eventguard.collectors.native.process_created_at", side_effect=responses) as lookup:
            identities = NativeBackend()._listener_identities(captured, None, errors)
        self.assertEqual(lookup.call_count, 7)
        rows = [{"protocol": "TCP", "address": "192.0.2.1", "port": 12345,
                 "pid": pid, "status": "ok", "created_at": identity["created_at"],
                 "process_identity_status": identity["status"]} for pid, identity in identities.items()]
        # A second endpoint for one owner is not a second error record.
        rows.append(dict(rows[0], port=12346))
        section = WindowsCollectors(native=Backend(payload(rows, errors)), backend="native").collect("listeners")
        result = validation.project_baseline(section)
        summary = result["error_summary"]
        self.assertFalse(result["complete"])
        self.assertEqual(result["process_identity_missing_count"], 8)
        self.assertEqual((summary["reported_count"], summary["retained_count"],
                          summary["classified_count"], summary["unknown_count"], summary["unretained_count"]),
                         (7, 7, 7, 0, 0))
        groups = {(g["stage"], g["operation"], g["reason_code"], g["status"]): g["count"]
                  for g in summary["groups"]}
        self.assertEqual(groups[("object", "ListenerOpenProcess", "access_denied", "denied")], 2)
        self.assertEqual(groups[("object", "ListenerOpenProcess", "object_unavailable", "unknown")], 1)
        self.assertEqual(groups[("object", "ListenerProcessIdentity", "listener_pid_reused", "unknown")], 1)
        self.assertEqual(groups[("launch", "OpenProcess", "api_unavailable", "not_applicable")], 1)
        self.assertEqual(sum(groups.values()), 7)
        saved = json.dumps(result)
        for private in ("PRIVATE_ERROR_TEXT", "192.0.2.1", "12345", '"pid"', '"created_at"'):
            self.assertNotIn(private, saved)

    def test_unknown_dimensions_and_malformed_records_never_copy_hostile_text(self):
        hostile = "PRIVATE_NAME_OR_PATH"
        records = [{"stage": hostile, "operation": hostile, "reason_code": hostile,
                    "status": hostile, "pid": 456, "exception_type": hostile},
                   None, {"stage": "object", "operation": "ListenerOpenProcess",
                          "reason_code": "query_failed", "status": []}]
        summary = validation.summarize_errors({"errors": records, "error_count": 3})
        self.assertEqual(summary["unknown_count"], 3)
        self.assertEqual(sum(g["count"] for g in summary["groups"]), 3)
        self.assertFalse(summary["complete"])
        self.assertNotIn(hostile, json.dumps(summary))
        self.assertNotIn("456", json.dumps(summary))

    def test_retained_prefix_and_unretained_errors_conserve_counts(self):
        record = {"stage": "object", "operation": "ListenerOpenProcess",
                  "reason_code": "access_denied", "status": "denied"}
        summary = validation.summarize_errors({"errors": [record] * MAX_ERRORS,
                                               "error_count": 80, "errors_truncated": True})
        self.assertEqual(validation.MAX_ERROR_RECORDS, MAX_ERRORS)
        self.assertEqual((summary["retained_count"], summary["unretained_count"]), (64, 16))
        self.assertEqual(summary["reported_count"], summary["retained_count"] + summary["unretained_count"])
        self.assertTrue(summary["truncated"])
        self.assertFalse(summary["complete"])
        oversized = validation.summarize_errors({"errors": [record] * 70, "error_count": 70})
        self.assertEqual((oversized["retained_count"], oversized["unretained_count"]), (64, 6))
        self.assertTrue(oversized["truncated"])

    def test_missing_or_contradictory_error_counts_stay_unknown(self):
        for coverage in ({}, {"errors": None, "error_count": 1},
                         {"errors": [], "error_count": True}, {"errors": [], "error_count": -1},
                         {"errors": [None], "error_count": 0}):
            with self.subTest(coverage=coverage):
                summary = validation.summarize_errors(coverage)
                self.assertFalse(summary["count_consistent"])
                self.assertIsNone(summary["unretained_count"])
                self.assertFalse(summary["complete"])

    def test_summary_is_not_a_completeness_or_acceptance_override(self):
        section = fixtures.complete_section()
        section["status"] = section["coverage"]["status"] = "partial"
        section["coverage"]["process_identity_missing_count"] = 1
        section["coverage"]["error_summary"] = {"complete": True, "groups": []}
        result = validation.project_baseline(section)
        self.assertTrue(result["error_summary"]["complete"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["status"], "partial")

    def test_fixture_execution_saves_summary_without_private_error_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            (project / "reports").mkdir()
            for name in validation.SOURCE_FILES:
                source = project / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("fixture only\n", encoding="utf-8")
            root = project / "reports/windows-listener-summary-fixture"
            validation.prepare(root, project, now=fixtures.NOW)
            approval = validation._read(root / "human-approval.template.json")
            approval.update(approved=True, approved_at=validation.stamp(fixtures.NOW),
                            expires_at=validation.stamp(fixtures.NOW + timedelta(minutes=5)),
                            authorization_text="Fixture only; not native authorization")
            validation._write(root / "human-approval.json", approval)
            section = fixtures.complete_section()
            section["status"] = section["coverage"]["status"] = "partial"
            section["coverage"].update(error_count=1, errors=[{
                "stage": "object", "operation": "ListenerOpenProcess", "reason_code": "access_denied",
                "status": "denied", "message": "PRIVATE_SECRET", "pid": 777777}])
            collector = fixtures.FixtureCollector(section)
            result = validation.execute(root, project, now=fixtures.NOW,
                                        collector_factory=lambda project: collector)
            self.assertEqual(collector.calls, ["listeners"])
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason"], "baseline_incomplete")
            self.assertEqual(result["baseline"]["error_summary"]["groups"][0]["count"], 1)
            saved = (root / "result.json").read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE_", saved)
            self.assertNotIn("777777", saved)


if __name__ == "__main__":
    unittest.main()
