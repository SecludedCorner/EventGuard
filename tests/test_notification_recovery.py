"""Synthetic notification durability faults. Never display a Windows notice.

The Windows-only child test exits itself with code 23 after its injected sink
writes a public marker. That is an intentional crash fault, not a successful
application exit or evidence that a person saw a notification.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eventguard import processes
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.notifications import NotificationError, NotificationService
from eventguard.synthetic import make_synthetic


ROOT = Path(__file__).resolve().parents[1]


class FaultConnection:
    """Raise before the selected SQL operation; use real SQLite otherwise."""
    def __init__(self, db, *, fail_insert=False, fail_commit=None):
        self.db = db
        self.fail_insert = fail_insert
        self.fail_commit = fail_commit
        self.commits = 0

    def execute(self, sql, *parameters):
        if self.fail_insert and sql.startswith("INSERT INTO notified"):
            raise sqlite3.OperationalError("fixture intent insert failure")
        if sql == "COMMIT":
            self.commits += 1
            if self.commits == self.fail_commit:
                raise sqlite3.OperationalError("fixture commit failure")
        return self.db.execute(sql, *parameters)

    def __getattr__(self, name):
        return getattr(self.db, name)


class NotificationRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.messages = []

    def event(self, *, age=0):
        event = make_synthetic("listener")
        event["severity"] = "high"
        stamp = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
        event["observed_at"] = stamp
        event["window"] = {"start": stamp, "end": stamp}
        EventStore(self.root / "data/test").enqueue(event)
        return event

    def sink(self, message):
        self.messages.append(message)
        return True

    def service(self, sink=None):
        service = NotificationService(self.root, "test", sink=self.sink if sink is None else sink)
        self.addCleanup(service.close)
        return service

    def rows(self):
        with closing(sqlite3.connect(self.root / "data/test/notifications.sqlite3")) as db:
            return {row[0]: row[1:] for row in db.execute(
                "SELECT event_id,delivery_state,notified_at,attempt_id,attempted_at FROM notified")}

    def assert_pending_without_ack(self, count):
        stats = EventStore(self.root / "data/test").stats()
        self.assertEqual(stats["pending"], count)
        self.assertEqual(stats["ack"], 0)
        self.assertEqual(stats["receipt_count"], 0)

    def test_intent_insert_or_commit_failure_never_calls_sink(self):
        self.event()
        service = self.service()
        original = service._open
        for fault in ({"fail_insert": True}, {"fail_commit": 1}):
            with self.subTest(fault=fault), patch.object(service, "_open",
                    side_effect=lambda: FaultConnection(original(), **fault)):
                result = service.poll()
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["reason"], "notification_intent_not_saved")
            self.assertFalse(result["display_requested"])
            self.assertEqual(self.messages, [])
            self.assertEqual(self.rows(), {})
            self.assert_pending_without_ack(1)
        self.assertEqual(self.service().poll()["status"], "notified")
        self.assertEqual(len(self.messages), 1)

    def test_accepted_commit_failure_leaves_only_durable_prepared_intent(self):
        event = self.event()
        service = self.service()
        original = service._open
        # COMMIT 1 saves intent. COMMIT 2 would save the acceptance receipt.
        with patch.object(service, "_open", side_effect=lambda: FaultConnection(original(), fail_commit=2)):
            result = service.poll()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "notification_receipt_failed")
        self.assertTrue(result["display_requested"])
        self.assertFalse(result["automatic_retry_allowed"])
        row = self.rows()[event["event_id"]]
        self.assertEqual(row[:2], ("prepared", ""))
        self.assertRegex(row[2], r"^[a-f0-9]{32}$")
        self.assertIsNotNone(datetime.fromisoformat(row[3]).tzinfo)
        service.close()
        restarted = self.service().poll()
        self.assertEqual(restarted["status"], "unknown")
        self.assertEqual(restarted["unconfirmed_count"], 1)
        self.assertEqual(len(self.messages), 1)
        self.assert_pending_without_ack(1)

    def test_legacy_two_column_receipt_migrates_without_resending(self):
        event = self.event()
        stamp = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.root / "data/test/notifications.sqlite3")) as db:
            db.execute("CREATE TABLE notified(event_id TEXT PRIMARY KEY,notified_at TEXT NOT NULL)")
            db.execute("INSERT INTO notified VALUES(?,?)", (event["event_id"], stamp))
            db.commit()
        result = self.service().poll()
        self.assertEqual(result["status"], "idle")
        self.assertEqual(result["reason"], "already_notified")
        self.assertEqual(result["unconfirmed_count"], 0)
        self.assertEqual(self.rows()[event["event_id"]], ("accepted", stamp, None, None))
        self.assertEqual(self.messages, [])
        self.assert_pending_without_ack(1)

    def test_unconfirmed_attempt_does_not_block_another_new_event(self):
        first, second = self.event(age=60), self.event()
        attempts = []
        def uncertain(message):
            attempts.append(message)
            raise RuntimeError("private sink state")
        service = self.service(sink=uncertain)
        unknown = service.poll()
        self.assertEqual(unknown["status"], "unknown")
        service.close()
        restarted = self.service()
        result = restarted.poll()
        self.assertEqual(result["status"], "notified")
        self.assertEqual(result["event_id"], second["event_id"])
        self.assertEqual(result["unconfirmed_count"], 1)
        self.assertEqual(result["pending_count"], 1)
        rows = self.rows()
        self.assertEqual(rows[first["event_id"]][0], "prepared")
        self.assertEqual(rows[second["event_id"]][0], "accepted")
        self.assertEqual(restarted.poll()["status"], "unknown")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(len(self.messages), 1)
        self.assert_pending_without_ack(2)

    def test_known_os_rejection_can_retry_without_marking_acceptance(self):
        event = self.event()
        def rejected(message):
            raise NotificationError("notification_display_failed")
        service = self.service(sink=rejected)
        result = service.poll()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "notification_display_failed")
        self.assertFalse(result["display_requested"])
        self.assertTrue(result["automatic_retry_allowed"])
        self.assertEqual(self.rows(), {})
        service.close()
        self.assertEqual(self.service().poll()["event_id"], event["event_id"])
        self.assertEqual(len(self.messages), 1)
        self.assert_pending_without_ack(1)

    def test_unknown_sink_return_retains_prepared_intent(self):
        event = self.event()
        service = self.service(sink=lambda message: None)
        result = service.poll()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "notification_sink_failed")
        self.assertIsNone(result["display_requested"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(self.rows()[event["event_id"]][0], "prepared")
        service.close()
        self.assertEqual(self.service().poll()["unconfirmed_count"], 1)
        self.assertEqual(self.messages, [])
        self.assert_pending_without_ack(1)

    def test_capacity_preserves_unconfirmed_intent_and_pending_source_events(self):
        first = self.event(age=60)
        calls = []
        def uncertain(message):
            calls.append(message)
            return None
        service = self.service(sink=uncertain)
        self.assertEqual(service.poll()["status"], "unknown")
        second = self.event()
        before = self.rows()
        with patch("eventguard.notifications.MAX_RECEIPTS", 1):
            full = service.poll()
        self.assertEqual(full["status"], "failed")
        self.assertEqual(full["reason"], "notification_capacity_full")
        self.assertEqual(full["pending_count"], 2)
        self.assertEqual(self.rows(), before)
        self.assertEqual(set(before), {first["event_id"]})
        self.assertEqual(len(calls), 1)
        self.assert_pending_without_ack(2)
        service.close()
        # A larger capacity can admit a new event, without erasing uncertainty.
        recovered = self.service().poll()
        self.assertEqual(recovered["event_id"], second["event_id"])
        self.assertEqual(recovered["unconfirmed_count"], 1)
        self.assertEqual(self.rows()[first["event_id"]], before[first["event_id"]])
        self.assert_pending_without_ack(2)

    def test_handled_case_keeps_prepared_and_never_creates_delivery_ack(self):
        event = self.event()
        service = self.service(sink=lambda message: None)
        self.assertEqual(service.poll()["status"], "unknown")
        before = self.rows()
        catalog = EventCatalog(self.root, "test")
        catalog.set_status(event["event_id"], "handled")
        service.close()
        self.assertEqual(self.service().poll()["status"], "idle")
        self.assertEqual(self.rows(), before)
        self.assertEqual(catalog.detail(event["event_id"])["delivery_status"], "pending")
        self.assertEqual(self.messages, [])
        self.assert_pending_without_ack(1)

    @unittest.skipUnless(os.name == "nt", "real owned Windows Job required; synthetic sink only")
    def test_owned_child_self_exit_after_sink_keeps_intent_without_repeat(self):
        event = self.event()
        marker = self.root / "synthetic-sink-entered.txt"
        # The only sink action is writing a fixed fixture marker. It never
        # loads user32/shell32 or starts native collection, models or services.
        entry = (
            "import os,sys;from pathlib import Path;"
            "sys.path.insert(0," + repr(str(ROOT / "src")) + ");"
            "from eventguard.notifications import NotificationService\n"
            "def sink(message):\n"
            "    with open(" + repr(str(marker)) + ", 'xb') as handle:\n"
            "        handle.write(b'synthetic sink reached\\n');handle.flush();os.fsync(handle.fileno())\n"
            "    os._exit(23)\n"
            "NotificationService(Path(" + repr(str(self.root)) + "), 'test', sink=sink).poll()\n"
            "raise SystemExit(99)\n"
        )
        child = processes.spawn([sys.executable, "-B", "-c", entry], cwd=str(ROOT),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        receipt = None
        try:
            output, errors = child.communicate(timeout=20)
        finally:
            try:
                receipt = processes.finish(child, "test_teardown", grace=2, request_stop=False)
            finally:
                for stream in (child.stdout, child.stderr):
                    if stream is not None:
                        stream.close()
                self.evidence = {"scope": "synthetic_notification_crash_fault",
                    "expected_child_exit": 23, "child_exit_is_application_success": False,
                    "process": receipt, "native_notification_calls": 0, "model_calls": 0}
        self.assertEqual(child.returncode, 23, self.evidence)
        self.assertEqual(output, b"", self.evidence)
        self.assertEqual(errors, b"", self.evidence)
        self.assertTrue(receipt["managed"], self.evidence)
        self.assertTrue(receipt["child_exited"], self.evidence)
        self.assertEqual(receipt["exit_code"], 23, self.evidence)
        self.assertEqual(receipt["remaining_owned_processes"], 0, self.evidence)
        self.assertFalse(receipt["forcibly_terminated"], self.evidence)
        self.assertEqual(marker.read_bytes(), b"synthetic sink reached\n")
        row = self.rows()[event["event_id"]]
        self.assertEqual(row[:2], ("prepared", ""))
        self.assertRegex(row[2], r"^[a-f0-9]{32}$")
        self.assertIsNotNone(datetime.fromisoformat(row[3]).tzinfo)
        result = self.service().poll()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "notification_submission_unconfirmed")
        self.assertEqual(result["unconfirmed_count"], 1)
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(self.messages, [])
        self.assertEqual(self.rows()[event["event_id"]], row)
        self.assert_pending_without_ack(1)
        self.evidence.update(pending_retained=True, source_receipt_count=0,
                             prepared_intent_retained=True, duplicate_sink_calls=0)


if __name__ == "__main__":
    unittest.main()
