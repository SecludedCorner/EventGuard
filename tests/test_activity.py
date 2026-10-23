"""Bounded real SQLite operation history; no monitor, model or system changes."""
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from unittest.mock import Mock, patch

from eventguard import activity
from eventguard.gui import view_snapshot


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.enterContext(patch.object(activity, "_owner", return_value=(1234, "2026-10-23T00:00:00+00:00")))
        self.enterContext(patch.object(activity, "_gone", return_value=False))

    def test_empty_read_never_creates_files(self):
        self.assertEqual(activity.snapshot(self.root)["state"], "not_created")
        self.assertFalse((self.root / "data").exists())

    def test_running_is_visible_before_completion_and_same_record_finishes(self):
        entered, release = threading.Event(), threading.Event()
        result = []
        def work():
            entered.set()
            release.wait(3)
            return {"status": "review_recorded", "private": "DO_NOT_STORE"}
        worker = threading.Thread(target=lambda: result.append(activity.call(self.root, "agent_mcp", "ack_event", "test", work, "private target")))
        worker.start()
        try:
            self.assertTrue(entered.wait(3))
            before = activity.snapshot(self.root, "test")
            self.assertEqual(before["active"], 1)
            self.assertEqual(before["entries"][0]["state"], "running")
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        after = activity.snapshot(self.root, "test")
        self.assertEqual(after["total"], 1)
        self.assertEqual(after["active"], 0)
        self.assertEqual(after["entries"][0]["id"], before["entries"][0]["id"])
        self.assertEqual(after["entries"][0]["state"], "completed")
        self.assertEqual(result[0]["status"], "review_recorded")
        raw = (self.root / "data/activity.sqlite3").read_bytes()
        self.assertNotIn(b"DO_NOT_STORE", raw)
        self.assertNotIn(b"private target", raw)

    def test_namespace_is_fixed_and_history_read_does_not_rewrite_database(self):
        activity.call(self.root, "agent_mcp", "overview", "test", lambda: {"state": "ready"})
        path = self.root / "data/activity.sqlite3"
        before = path.read_bytes()
        self.assertEqual(activity.snapshot(self.root, "live")["total"], 0)
        self.assertEqual(activity.snapshot(self.root, "test")["total"], 1)
        self.assertEqual(path.read_bytes(), before)

    def test_completed_rows_rotate_without_dropping_running_work(self):
        with patch.object(activity, "MAX_ROWS", 3):
            token = activity.begin(self.root, "agent_mcp", "monitor", "test")
            for _ in range(5):
                activity.call(self.root, "human_gui", "gui_inspect", "test", lambda: {"status": "stored"})
            value = activity.snapshot(self.root, "test", limit=3)
            self.assertEqual(value["total"], 3)
            self.assertTrue(any(row["id"] == token and row["state"] == "running" for row in value["entries"]))
            self.assertEqual(value["active"], 1)

    def test_capacity_refuses_work_but_never_prevents_stop(self):
        with patch.object(activity, "MAX_ACTIVE", 1):
            activity.begin(self.root, "agent_mcp", "monitor", "test")
            work = Mock(return_value={"state": "stopped"})
            result = activity.call(self.root, "agent_mcp", "diagnose_event", "test", work)
            self.assertFalse(result["operation_started"])
            work.assert_not_called()
            stopped = activity.call(self.root, "human_gui", "gui_pause", "test", work)
            self.assertEqual(stopped["state"], "stopped")
            self.assertEqual(stopped["activity_warning"], "activity_active_capacity")
            work.assert_called_once()

    def test_failed_completion_does_not_claim_success_or_retry_operation(self):
        work = Mock(return_value={"status": "review_recorded"})
        with patch.object(activity, "complete", side_effect=activity.ActivityError("fixture")):
            value = activity.call(self.root, "agent_mcp", "ack_event", "test", work)
        self.assertTrue(value["operation_may_have_completed"])
        self.assertFalse(value["automatic_retry_allowed"])
        work.assert_called_once()
        self.assertEqual(activity.snapshot(self.root, "test")["entries"][0]["state"], "running")

    def test_explicit_safety_disable_can_proceed_when_history_is_unavailable(self):
        work = Mock(return_value={"state": "disabled"})
        with patch.object(activity, "begin", side_effect=activity.ActivityError("activity_storage_unavailable")):
            value = activity.call(self.root, "human_gui", "gui_receive_permission", "live", work,
                                  allow_unrecorded_stop=True)
        work.assert_called_once()
        self.assertEqual(value["state"], "disabled")
        self.assertEqual(value["activity_warning"], "activity_storage_unavailable")

    def test_exception_records_failure_without_raw_exception(self):
        def work():
            raise ValueError("PRIVATE_EXCEPTION")
        with self.assertRaisesRegex(ValueError, "PRIVATE_EXCEPTION"):
            activity.call(self.root, "agent_mcp", "diagnose_event", "test", work)
        row = activity.snapshot(self.root, "test")["entries"][0]
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["reason_code"], "operation_raised")
        self.assertNotIn(b"PRIVATE_EXCEPTION", (self.root / "data/activity.sqlite3").read_bytes())

    def test_owner_exit_is_interrupted_never_completed(self):
        token = activity.begin(self.root, "agent_mcp", "diagnose_event", "test")
        with patch.object(activity, "_gone", return_value=True):
            row = activity.snapshot(self.root, "test")["entries"][0]
            self.assertEqual(row["state"], "interrupted")
            activity.begin(self.root, "agent_mcp", "overview", "test")
        row = next(r for r in activity.snapshot(self.root, "test")["entries"] if r["id"] == token)
        self.assertEqual(row["state"], "interrupted")

    def test_foreign_database_is_not_repurposed(self):
        path = self.root / "data/activity.sqlite3"
        path.parent.mkdir()
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE private(value TEXT)")
            db.commit()
        before = path.read_bytes()
        work = Mock()
        result = activity.call(self.root, "agent_mcp", "overview", "test", work)
        self.assertFalse(result["operation_started"])
        work.assert_not_called()
        self.assertEqual(path.read_bytes(), before)

    def test_gui_projects_running_and_completed_activity_without_executing_content(self):
        token = activity.begin(self.root, "agent_mcp", "diagnose_event", "live")
        view = view_snapshot({"activity": activity.snapshot(self.root)})
        self.assertEqual(view["activity_rows"][0][0], token)
        self.assertEqual(view["activity_rows"][0][1][1:4], ("Agent 工具", "唯讀查證", "執行中／待結果"))
        self.assertIn("執行中 1", view["activity_status"])
        broken = view_snapshot({"activity": {"entries": [{"operation": []}, {"operation": "monitor", "actor": [], "state": []}]}})
        self.assertEqual(len(broken["activity_rows"]), 1)

    def test_path_failure_never_prevents_stop_or_crashes_history_view(self):
        for error in (ValueError("PRIVATE_PATH"), PermissionError("PRIVATE_PATH")):
            with self.subTest(error=type(error).__name__), patch.object(activity, "_path", side_effect=error):
                stop = Mock(return_value={"state": "stopped"})
                result = activity.call(self.root, "human_gui", "gui_pause", "live", stop)
                stop.assert_called_once()
                self.assertEqual(result["activity_warning"], "activity_storage_unavailable")
                self.assertEqual(activity.snapshot(self.root)["state"], "unavailable")
                self.assertNotIn("PRIVATE_PATH", str(result))

    def test_tampered_saved_fields_are_not_returned_to_agent_or_gui(self):
        activity.call(self.root, "agent_mcp", "overview", "test", lambda: {"state": "ready"})
        path = self.root / "data/activity.sqlite3"
        changes = {"reason_code": "PRIVATE/PATH", "target_ref": "PRIVATE_TARGET",
                   "started_at": "PRIVATE_TIME", "elapsed_ms": -1, "owner_created_at": "PRIVATE_TIME"}
        for field, invalid in changes.items():
            with self.subTest(field=field), closing(sqlite3.connect(path)) as db:
                original = db.execute("SELECT " + field + " FROM activity").fetchone()[0]
                db.execute("UPDATE activity SET " + field + "=?", (invalid,))
                db.commit()
                result = activity.snapshot(self.root, "test")
                self.assertEqual(result["state"], "unavailable")
                self.assertNotIn("PRIVATE", str(result))
                db.execute("UPDATE activity SET " + field + "=?", (original,))
                db.commit()


if __name__ == "__main__":
    unittest.main()
