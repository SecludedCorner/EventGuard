"""Saved synthetic observations only. No collectors, OS queries or processes."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from eventguard.collectors.contract import SECTION_IDS
from eventguard.monitor import Monitor
from eventguard.runtime import Runtime, atomic_json, read_json
from eventguard.source_status import source_status

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 24, 4, 0, tzinfo=timezone.utc)


def stamp(seconds=0):
    return (NOW + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def sample(source="defender", status="ok", *, at=None, coverage=None, rows=None):
    return {"id": source, "status": status, "rows": [] if rows is None else rows,
            "observed_at": stamp(-10) if at is None else at,
            "coverage": {"status": status, "errors": []} if coverage is None else coverage}


class SourceSuccessHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default.json", self.root / "config/default.json")
        self.runtime = Runtime(self.root)
        self.enterContext(patch("eventguard.runtime.utc_now", return_value=stamp()))
        self.enterContext(patch("eventguard.source_status._now", return_value=NOW))
        self.enterContext(patch("eventguard.collectors.windows.WindowsCollectors.collect",
                                side_effect=AssertionError("saved-source reads cannot query the OS")))

    def rows(self, namespace="test"):
        return {row["source_id"]: row for row in source_status(self.root, namespace)["sources"]}

    def path(self, source="defender", namespace="test"):
        return self.root / "data" / namespace / "observations" / (source + ".json")

    def test_no_history_read_is_unknown_and_creates_no_data(self):
        rows = self.rows()
        self.assertEqual(set(rows), set(SECTION_IDS))
        self.assertTrue(all(row["last_success_at"] is None for row in rows.values()))
        self.assertTrue(all(row["last_success_state"] == "unknown" for row in rows.values()))
        self.assertFalse((self.root / "data").exists())

    def test_seven_successes_survive_failures_and_new_runtime_monitor_instances(self):
        for source in SECTION_IDS:
            self.runtime.save_observation(sample(source, at=stamp(-50)), "test")
            self.runtime.save_observation(sample(source, "denied" if source == "defender" else "error", at=stamp(-5)), "test")
        # Fresh objects model a process reopening only persisted JSON; no old
        # health or in-memory coverage is supplied to the new monitor.
        reopened = Runtime(self.root)
        monitor = Monitor(self.root)
        monitor._restore_success_history("test")
        for source, row in self.rows().items():
            self.assertEqual(row["last_collected_at"], stamp(-5))
            self.assertEqual(row["last_success_at"], stamp(-50))
            self.assertEqual(row["last_success_state"], "known")
            self.assertFalse(row["success"])
            self.assertEqual(reopened.observation(source, "test")["last_success_at"], stamp(-50))
            self.assertEqual(monitor.coverage[source]["last_success"], stamp(-50))
        health = {}
        monitor._record(sample("defender", "denied", at=stamp(-1)), health, "test", "a" * 32)
        self.assertEqual(monitor.coverage["defender"]["last_success"], stamp(-50))
        self.assertEqual(self.rows()["defender"]["last_collected_at"], stamp(-1))

    def test_partial_denied_unknown_and_inapplicable_never_advance_success(self):
        self.runtime.save_observation(sample(at=stamp(-50)), "test")
        for status in ("partial", "denied", "unknown", "error", "not_applicable", "timeout", "cancelled", "busy", "not_requested"):
            with self.subTest(status=status):
                result = self.runtime.save_observation(sample(status=status, at=stamp(-1)), "test")
                self.assertEqual(result["last_success_at"], stamp(-50))
                self.assertEqual(self.rows()["defender"]["last_success_at"], stamp(-50))

    def test_incomplete_ok_envelopes_cannot_advance_success(self):
        self.runtime.save_observation(sample(at=stamp(-50)), "test")
        cases = (
            ({"status": "partial"}, []),
            ({"status": "ok", "truncated": True}, []),
            ({"status": "ok", "errors_truncated": True}, []),
            ({"status": "ok", "error_count": 1}, []),
            ({"status": "ok", "errors": [{"stage": "provider", "reason_code": "access_denied", "status": "denied"}]}, []),
            ({"status": "ok"}, [{"pid": 42, "status": "partial"}]),
        )
        for coverage, rows in cases:
            with self.subTest(coverage=coverage, rows=rows):
                saved = self.runtime.save_observation(sample(at=stamp(-1), coverage=coverage, rows=rows), "test")
                self.assertEqual(saved["last_success_at"], stamp(-50))

    def test_complete_zero_rows_and_missing_optional_registry_key_are_success(self):
        self.runtime.save_observation(sample("listeners", at=stamp(-5)), "test")
        self.runtime.save_observation(sample("startup", at=stamp(-5), rows=[
            {"status": "not_applicable", "kind": "registry_missing"}]), "test")
        self.runtime.save_observation(sample("processes", at=stamp(-5), rows=[
            {"pid": index, "status": "ok"} for index in range(250)]), "test")
        self.assertEqual(self.rows()["listeners"]["last_success_at"], stamp(-5))
        self.assertEqual(self.rows()["startup"]["last_success_at"], stamp(-5))
        # Local row projection limits do not change the collector's complete
        # success. A collector coverage.truncated flag does (separate test).
        self.assertTrue(self.runtime.observation("processes", "test")["truncated"])
        self.assertEqual(self.rows()["processes"]["last_success_at"], stamp(-5))

    def test_later_success_advances_and_older_replayed_sample_does_not_rewind(self):
        for at, status in ((-50, "ok"), (-10, "denied"), (-5, "ok"), (-40, "ok")):
            self.runtime.save_observation(sample(status=status, at=stamp(at)), "test")
        row = self.rows()["defender"]
        self.assertEqual(row["last_collected_at"], stamp(-40))
        self.assertEqual(row["last_success_at"], stamp(-5))

    def test_invalid_or_future_collection_time_cannot_become_success_time(self):
        for at in ("not-time", "2026-10-24T04:00:00", stamp(1)):
            with self.subTest(at=at):
                self.runtime.save_observation(sample(at=at), "test")
                row = self.rows()["defender"]
                self.assertIsNone(row["last_success_at"])
                self.assertEqual(row["last_success_state"], "unknown")

    def test_malformed_future_or_after_save_history_is_unknown_and_reads_do_not_repair(self):
        self.runtime.save_observation(sample(), "test")
        path = self.path()
        for value in ("not-time", "2026-10-24T04:00:00", stamp(1), ["unsafe"]):
            with self.subTest(value=value):
                document = read_json(path)
                document["last_success_at"] = value
                atomic_json(path, document)
                before = path.read_bytes()
                row = self.rows()["defender"]
                self.assertIsNone(row["last_success_at"])
                self.assertEqual(row["last_success_state"], "unknown")
                self.assertIn("source_success_timestamp_invalid", [reason["reason_code"] for reason in row["reasons"]])
                self.assertEqual(path.read_bytes(), before)
        document = read_json(path)
        document.update(last_success_at=stamp(-1), saved_at=stamp(-2))
        atomic_json(path, document)
        self.assertIsNone(self.rows()["defender"]["last_success_at"])

    def test_legacy_success_uses_its_collection_time_and_never_saved_or_health_time(self):
        self.runtime.save_observation(sample(at=stamp(-50)), "test")
        path = self.path()
        document = read_json(path)
        document.pop("last_success_at")
        atomic_json(path, document)
        before = path.read_bytes()
        self.assertEqual(self.rows()["defender"]["last_success_at"], stamp(-50))
        self.assertEqual(path.read_bytes(), before)
        document["section"].update(status="denied", observed_at=stamp(-5))
        document["section"]["coverage"] = {"status": "denied"}
        atomic_json(path, document)
        self.runtime.save_health({"namespace": "test", "coverage": {
            "defender": {"status": "denied", "last_success": stamp(-1), "observed_at": stamp(-5)}}})
        self.assertIsNone(self.rows()["defender"]["last_success_at"])

    def test_success_history_is_bound_to_source_and_namespace(self):
        self.runtime.save_observation(sample("listeners", at=stamp(-30)), "live")
        self.runtime.save_observation(sample("defender", at=stamp(-50)), "test")
        self.assertIsNone(self.rows("live")["defender"]["last_success_at"])
        self.assertIsNone(self.rows("test")["listeners"]["last_success_at"])
        monitor = Monitor(self.root)
        monitor._restore_success_history("live")
        self.assertEqual(monitor.coverage["listeners"]["last_success"], stamp(-30))
        self.assertIsNone(monitor.coverage["defender"]["last_success"])

    def test_failed_atomic_save_never_advances_durable_or_monitor_success(self):
        self.runtime.save_observation(sample(at=stamp(-50)), "test")
        path = self.path()
        before = path.read_bytes()
        monitor = Monitor(self.root)
        monitor._restore_success_history("test")
        health = {}
        with patch("eventguard.runtime.atomic_json", side_effect=OSError("synthetic write failure")):
            monitor._record(sample(at=stamp(-1)), health, "test", "b" * 32)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(monitor.coverage["defender"]["last_success"], stamp(-50))
        self.assertEqual(health["last_error"], "observation_persistence_failed")
        self.assertEqual(self.rows()["defender"]["last_success_at"], stamp(-50))

    def test_repeated_page_reads_do_not_write_observations_health_or_sqlite(self):
        self.runtime.save_observation(sample(at=stamp(-50)), "test")
        self.runtime.save_observation(sample(status="denied", at=stamp(-5)), "test")
        files = {path: path.read_bytes() for path in (self.root / "data").rglob("*") if path.is_file()}
        with patch("eventguard.runtime.atomic_json", side_effect=AssertionError("page cannot write")):
            for _ in range(3):
                self.assertEqual(self.rows()["defender"]["last_success_at"], stamp(-50))
        self.assertEqual(files, {path: path.read_bytes() for path in (self.root / "data").rglob("*") if path.is_file()})
        self.assertFalse(list((self.root / "data").rglob("*.sqlite3")))
        self.assertNotIn("unsafe", json.dumps(self.rows()))


if __name__ == "__main__":
    unittest.main()
