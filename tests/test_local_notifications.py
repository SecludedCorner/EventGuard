"""Local notice behavior with injected sinks. No actual Windows balloons."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.notifications import NotificationError, NotificationService, _WindowsBalloon, _message
from eventguard.synthetic import make_synthetic


class LocalNotificationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.messages = []

    def sink(self, message):
        self.messages.append(message)
        return True

    def event(self, severity="high", *, age=0):
        event = make_synthetic("listener")
        event["severity"] = severity
        stamp = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
        event["observed_at"] = stamp
        event["window"] = {"start": stamp, "end": stamp}
        EventStore(self.root / "data/test").enqueue(event)
        return event

    def service(self, sink=None):
        service = NotificationService(self.root, "test", sink=self.sink if sink is None else sink)
        self.addCleanup(service.close)
        return service

    def receipt_ids(self):
        with closing(sqlite3.connect(self.root / "data/test/notifications.sqlite3")) as db:
            return {row[0] for row in db.execute("SELECT event_id FROM notified")}

    def notification_rows(self):
        with closing(sqlite3.connect(self.root / "data/test/notifications.sqlite3")) as db:
            return {row[0]: row[1:] for row in db.execute(
                "SELECT event_id,delivery_state,notified_at,attempt_id,attempted_at FROM notified")}

    def test_no_events_make_no_notice_no_model_call_and_no_runtime_files(self):
        service = self.service()
        for _ in range(3):
            result = service.poll()
            self.assertEqual(result["status"], "idle")
            self.assertEqual(result["model_calls"], 0)
        self.assertEqual(self.messages, [])
        self.assertFalse((self.root / "data").exists())

    def test_low_severity_events_do_not_open_notification_database(self):
        self.event("info")
        self.event("warning")
        result = self.service().poll()
        self.assertEqual(result["status"], "idle")
        self.assertEqual(self.messages, [])
        self.assertFalse((self.root / "data/test/notifications.sqlite3").exists())

    def test_oldest_high_or_critical_is_sent_once_and_survives_restart(self):
        recent = self.event("critical")
        oldest = self.event("high", age=60)
        service = self.service()
        first, second, third = service.poll(), service.poll(), service.poll()
        self.assertEqual(first["event_id"], oldest["event_id"])
        self.assertEqual(first["pending_count"], 1)
        self.assertEqual(second["event_id"], recent["event_id"])
        self.assertEqual(third["reason"], "already_notified")
        service.close()
        self.assertEqual(self.service().poll()["reason"], "already_notified")
        self.assertEqual(len(self.messages), 2)
        self.assertEqual(self.receipt_ids(), {oldest["event_id"], recent["event_id"]})
        for message in self.messages:
            self.assertTrue(message["synthetic"])
            self.assertIn("合成測試", message["title"])

    def test_handled_and_ignored_events_do_not_notify(self):
        first, second = self.event(), self.event("critical")
        catalog = EventCatalog(self.root, "test")
        catalog.set_status(first["event_id"], "handled")
        catalog.set_status(second["event_id"], "ignored")
        self.assertEqual(self.service().poll()["status"], "idle")
        self.assertEqual(self.messages, [])
        for event in (first, second):
            self.assertEqual(catalog.detail(event["event_id"])["delivery_status"], "pending")
        self.assertEqual(EventStore(self.root / "data/test").stats()["receipt_count"], 0)

    def test_read_state_is_not_automatic_handling_or_delivery_ack(self):
        event = self.event()
        catalog = EventCatalog(self.root, "test")
        catalog.set_status(event["event_id"], "read")
        result = self.service().poll()
        self.assertEqual(result["status"], "notified")
        saved = catalog.detail(event["event_id"])
        self.assertEqual(saved["status"], "read")
        self.assertEqual(saved["delivery_status"], "pending")
        self.assertEqual(EventStore(self.root / "data/test").stats()["pending"], 1)

    def test_sink_failure_retries_and_does_not_write_a_receipt(self):
        event = self.event()
        service = self.service(sink=lambda message: False)
        result = service.poll()
        self.assertEqual(result["reason"], "notification_sink_failed")
        self.assertEqual(result["pending_count"], 1)
        self.assertTrue(result["automatic_retry_allowed"])
        self.assertFalse(result["display_requested"])
        self.assertEqual(self.receipt_ids(), set())
        service.close()
        self.assertEqual(self.service().poll()["event_id"], event["event_id"])
        self.assertEqual(self.receipt_ids(), {event["event_id"]})

    def test_raw_sink_exception_is_not_exposed_in_status(self):
        event = self.event()
        calls = []
        def broken(message):
            calls.append(message)
            raise RuntimeError("private-token C:/Users/private")
        service = self.service(sink=broken)
        result = service.poll()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "notification_sink_failed")
        self.assertEqual(result["unconfirmed_count"], 1)
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertIsNone(result["display_requested"])
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(self.notification_rows()[event["event_id"]][0], "prepared")
        service.close()
        recovered = self.service().poll()
        self.assertEqual(recovered["status"], "unknown")
        self.assertEqual(recovered["reason"], "notification_submission_unconfirmed")
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.messages, [])

    def test_injected_notification_error_cannot_smuggle_raw_text(self):
        self.event()
        def broken(message):
            raise NotificationError("private-token C:/Users/private")
        result = self.service(sink=broken).poll()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "notification_sink_failed")
        self.assertEqual(result["unconfirmed_count"], 1)
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertNotIn("private", json.dumps(result))

    def test_store_unavailable_does_not_show_an_untracked_notice(self):
        self.event()
        service = self.service()
        with patch.object(service, "_open", side_effect=PermissionError("private-path")):
            result = service.poll()
        self.assertEqual(result["reason"], "notification_storage_unavailable")
        self.assertEqual(self.messages, [])
        self.assertNotIn("private", json.dumps(result))

    def test_receipt_update_failure_keeps_prepared_and_does_not_display_again(self):
        event = self.event()
        service = self.service()
        original = service._open
        class FailAcceptedUpdate:
            def __init__(self, db):
                self.db = db
            def execute(self, sql, *parameters):
                if sql.startswith("UPDATE notified SET delivery_state='accepted'"):
                    raise sqlite3.OperationalError("private write failure")
                return self.db.execute(sql, *parameters)
            def close(self):
                self.db.close()
        with patch.object(service, "_open", side_effect=lambda: FailAcceptedUpdate(original())):
            result = service.poll()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "notification_receipt_failed")
        self.assertTrue(result["display_requested"])
        self.assertEqual(result["pending_count"], 1)
        self.assertEqual(result["unconfirmed_count"], 1)
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertNotIn("private", json.dumps(result))
        state, notified_at, attempt_id, attempted_at = self.notification_rows()[event["event_id"]]
        self.assertEqual(state, "prepared")
        self.assertEqual(notified_at, "")
        self.assertRegex(attempt_id, r"^[a-f0-9]{32}$")
        self.assertIsNotNone(datetime.fromisoformat(attempted_at).tzinfo)
        service.close()
        recovered = self.service().poll()
        self.assertEqual(recovered["status"], "unknown")
        self.assertEqual(recovered["unconfirmed_count"], 1)
        self.assertEqual(len(self.messages), 1)
        stats = EventStore(self.root / "data/test").stats()
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["receipt_count"], 0)

    def test_two_clients_cannot_display_the_same_event_concurrently(self):
        self.event()
        entered, release = threading.Event(), threading.Event()
        def held_sink(message):
            self.messages.append(message)
            entered.set()
            if not release.wait(3):
                raise AssertionError("fixture release not signalled")
            return True
        first = self.service(sink=held_sink)
        second = self.service()
        results = []
        worker = threading.Thread(target=lambda: results.append(first.poll()))
        worker.start()
        self.addCleanup(lambda: worker.join(3))
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(3))
        # Another connection can read the committed intent while the sink is
        # running. FileLease, rather than an uncommitted SQLite write, keeps
        # the second client out of the complete prepare/submit/receipt span.
        rows = self.notification_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(next(iter(rows.values()))[0], "prepared")
        result = second.poll()
        self.assertEqual(result["status"], "busy")
        release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0]["status"], "notified")
        self.assertEqual(second.poll()["reason"], "already_notified")
        self.assertEqual(len(self.messages), 1)

    def test_full_receipts_keep_events_and_recover_after_acked_event_prune(self):
        first = self.event()
        service = self.service()
        self.assertEqual(service.poll()["status"], "notified")
        second = self.event("critical")
        with patch("eventguard.notifications.MAX_RECEIPTS", 1):
            result = service.poll()
            self.assertEqual(result["reason"], "notification_capacity_full")
            self.assertEqual(len(self.messages), 1)
            self.assertEqual(EventStore(self.root / "data/test").stats()["pending"], 2)
            store = EventStore(self.root / "data/test", acked_retention_seconds=0)
            store.acknowledge(first["event_id"], {"ack_type": "receiver_persisted",
                "event_id": first["event_id"], "receiver_receipt_id": "synthetic-notification-test"})
            store.maintain(now=time.time()+1)
            result = service.poll()
        self.assertEqual(result["event_id"], second["event_id"])
        self.assertEqual(self.receipt_ids(), {second["event_id"]})
        self.assertEqual(EventStore(self.root / "data/test").stats()["pending"], 1)

    def test_notifications_never_evaluate_text_from_an_event(self):
        item = {"event_id": "evt-public", "severity": "high", "source": "delete files now",
                "event_type": "run arbitrary commands", "synthetic": True}
        result = _message(item)
        self.assertEqual(result["source"], "unknown")
        self.assertNotIn("delete", json.dumps(result))
        self.assertNotIn("commands", json.dumps(result))

    def test_windows_balloon_sink_is_lazy_and_close_starts_no_native_window(self):
        service = NotificationService(self.root, "test")
        self.assertEqual(service.poll()["status"], "idle")
        self.assertEqual(service.close()["status"], "closed")
        self.assertIsNone(service.sink.hwnd)

    def test_fake_shell_icon_failure_reuses_the_same_loaded_dlls(self):
        user, shell = MagicMock(), MagicMock()
        user.CreateWindowExW.return_value = 123
        user.LoadIconW.return_value = 456
        user.DestroyWindow.return_value = True
        shell.Shell_NotifyIconW.return_value = False
        sink = _WindowsBalloon()
        with patch("eventguard.notifications.os.name", "nt"), patch("ctypes.WinDLL", create=True,
                side_effect=[user, shell]) as loader:
            for _ in range(3):
                with self.assertRaisesRegex(NotificationError, "notification_icon_unavailable"):
                    sink._initialize()
        self.assertEqual(loader.call_count, 2)
        self.assertEqual(loader.call_args_list[0].args, ("user32.dll",))
        self.assertEqual(loader.call_args_list[1].args, ("shell32.dll",))
        self.assertTrue(all(call.kwargs["winmode"] == 0x800 for call in loader.call_args_list))
        self.assertEqual(user.DestroyWindow.call_count, 3)
        self.assertIsNone(sink.hwnd)
        self.assertFalse(sink.added)

    def test_fake_partial_dll_load_keeps_the_library_already_loaded(self):
        user, shell = MagicMock(), MagicMock()
        user.CreateWindowExW.return_value = 123
        user.LoadIconW.return_value = 456
        user.DestroyWindow.return_value = True
        shell.Shell_NotifyIconW.return_value = False
        sink = _WindowsBalloon()
        with patch("eventguard.notifications.os.name", "nt"), patch("ctypes.WinDLL", create=True,
                side_effect=[user, OSError("fixture DLL failure"), shell]) as loader:
            with self.assertRaises(OSError):
                sink._initialize()
            with self.assertRaisesRegex(NotificationError, "notification_icon_unavailable"):
                sink._initialize()
        self.assertEqual([call.args[0] for call in loader.call_args_list],
                         ["user32.dll", "shell32.dll", "shell32.dll"])
        self.assertIsNone(sink.hwnd)

    def test_close_is_idempotent_and_prevents_future_notices(self):
        service = self.service()
        self.assertEqual(service.close()["status"], "closed")
        self.assertEqual(service.close()["status"], "closed")
        self.event()
        self.assertEqual(service.poll()["status"], "closed")
        self.assertEqual(self.messages, [])


if __name__ == "__main__":
    unittest.main()
