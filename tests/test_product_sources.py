"""Saved-source product views. Fixture files only; no Windows collection."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from eventguard.collectors.contract import SECTION_IDS, evidence
from eventguard.runtime import Runtime, atomic_json
from eventguard.source_status import source_status

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


class ProductSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default.json", self.root / "config/default.json")
        self.runtime = Runtime(self.root)
        self.enterContext(patch("eventguard.source_status._now", return_value=NOW))
        self.enterContext(patch("eventguard.collectors.windows.WindowsCollectors.collect",
                                side_effect=AssertionError("a status view must not collect")))

    def save(self, source="defender", status="ok", *, age=0, errors=None, namespace="test"):
        self.runtime.save_observation({"id": source, "status": status, "rows": [],
            "observed_at": (NOW - timedelta(seconds=age)).isoformat(),
            "coverage": {"errors": errors or []}}, namespace)

    def rows(self, namespace="test"):
        return {item["source_id"]: item for item in source_status(self.root, namespace)["sources"]}

    def test_empty_view_has_seven_unknown_sources_and_creates_no_data(self):
        result = source_status(self.root, "test")
        self.assertEqual(len(result["sources"]), 7)
        self.assertEqual({row["source_id"] for row in result["sources"]}, set(SECTION_IDS))
        self.assertTrue(all(row["success"] is None and row["status"] == "not_collected" for row in result["sources"]))
        self.assertFalse((self.root / "data").exists())
        self.assertFalse(result["system_query_executed"])

    def test_each_source_reports_a_fresh_success_without_reading_rows(self):
        for source in SECTION_IDS:
            self.save(source)
        rows = self.rows()
        self.assertTrue(all(row["status"] == "ok" and row["success"] is True for row in rows.values()))
        self.assertTrue(all(row["last_collected_at"] == NOW.isoformat(timespec="seconds") for row in rows.values()))
        self.assertTrue(all(row["row_count"] == 0 for row in rows.values()))

    def test_defender_denied_has_actual_provider_codes_and_a_safe_action(self):
        error = evidence("provider", "access_denied", exception_type="CimException",
                         hresult=-2146233088, provider_code="AccessDenied", category="PermissionDenied", status="denied")
        error["message"] = "private user and path: C:/Users/private"
        self.save(status="denied", errors=[error])
        row = self.rows()["defender"]
        self.assertFalse(row["success"])
        self.assertEqual(row["reasons"][0]["stage"], "provider")
        self.assertEqual(row["reasons"][0]["provider_code"], "AccessDenied")
        self.assertEqual(row["reasons"][0]["hresult_hex"], "0x80131500")
        self.assertIn("Windows 安全性", row["suggestion"])
        self.assertIn("組織管理", row["suggestion"])
        self.assertNotIn("private", json.dumps(row))
        self.assertNotIn("系統管理員身分執行", row["suggestion"])

    def test_tasks_unknown_folder_error_is_not_access_denied(self):
        error = evidence("provider", "task_get_folder_failed", exception_type="COMError",
                         hresult=-2147024893, operation="TaskGetFolder", status="unknown")
        self.save("tasks", "unknown", errors=[error])
        row = self.rows()["tasks"]
        self.assertIsNone(row["success"])
        self.assertEqual(row["status"], "unknown")
        self.assertEqual(row["reasons"][0]["hresult_hex"], "0x80070003")
        self.assertIn("工作排程器", row["suggestion"])
        self.assertIn("路徑不存在", row["suggestion"])
        self.assertIn("不能判為拒絕存取", row["suggestion"])

    def test_stale_success_is_not_current_success(self):
        self.save("listeners", age=136)
        row = self.rows()["listeners"]
        self.assertEqual(row["saved_status"], "ok")
        self.assertEqual(row["status"], "stale")
        self.assertIsNone(row["success"])
        self.assertIn("過期", row["suggestion"])

    def test_stale_denied_keeps_the_specific_self_check(self):
        self.save(status="denied", age=136)
        row = self.rows()["defender"]
        self.assertEqual(row["status"], "stale")
        self.assertIn("Windows 安全性", row["suggestion"])
        self.assertIn("過期", row["suggestion"])

    def test_partial_and_not_applicable_are_not_safe_or_success(self):
        self.save("processes", "partial")
        self.save("tasks", "not_applicable")
        rows = self.rows()
        self.assertIsNone(rows["processes"]["success"])
        self.assertIsNone(rows["tasks"]["success"])
        self.assertEqual(rows["tasks"]["status"], "not_applicable")

    def test_health_from_another_namespace_cannot_supply_an_attempt(self):
        self.runtime.save_health({"namespace": "live", "coverage": {
            "defender": {"status": "ok", "observed_at": NOW.isoformat()}}})
        self.assertEqual(self.rows()["defender"]["status"], "not_collected")

    def test_newer_persistence_failure_is_not_hidden_by_old_success(self):
        self.save(age=20)
        self.runtime.save_health({"namespace": "test", "coverage": {
            "defender": {"status": "ok", "observed_at": NOW.isoformat(),
                         "observation_error": "observation_persistence_failed", "row_count": 2}}})
        row = self.rows()["defender"]
        self.assertEqual(row["last_collected_at"], NOW.isoformat(timespec="seconds"))
        self.assertEqual(row["status"], "error")
        self.assertFalse(row["success"])
        self.assertIn("observation_persistence_failed", [item["reason_code"] for item in row["reasons"]])

    def test_one_corrupt_observation_does_not_hide_other_sources(self):
        self.save("listeners")
        target = self.root / "data/test/observations/defender.json"
        target.write_text("{broken", encoding="utf-8")
        before = target.read_bytes()
        rows = self.rows()
        self.assertEqual(rows["listeners"]["status"], "ok")
        self.assertEqual(rows["defender"]["status"], "unknown")
        self.assertEqual(rows["defender"]["reasons"][0]["reason_code"], "saved_observation_unreadable")
        self.assertEqual(target.read_bytes(), before)

    def test_future_or_invalid_collection_time_cannot_report_success(self):
        self.save(age=-60)
        row = self.rows()["defender"]
        self.assertIsNone(row["success"])
        self.assertEqual(row["freshness"], "unknown")

    def test_invalid_namespace_is_rejected_without_creating_runtime(self):
        with self.assertRaisesRegex(ValueError, "invalid_namespace"):
            source_status(self.root, "../private")
        self.assertFalse((self.root / "data").exists())

    def test_saved_files_are_unchanged_after_repeated_status_reads(self):
        self.save("defender", "denied")
        paths = list((self.root / "data").rglob("*.json"))
        before = {path: path.read_bytes() for path in paths}
        self.rows()
        self.rows()
        self.assertEqual(before, {path: path.read_bytes() for path in paths})


if __name__ == "__main__":
    unittest.main()
