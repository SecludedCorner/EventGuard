"""Actual Tk decisions -> real synthetic Catalog, history and pending outbox."""
import threading
import unittest
from unittest.mock import patch

from eventguard import activity
from eventguard.desktop import DesktopController
from eventguard.events.store import event_payload_hash
import test_desktop_investigation_widgets as fixture


class DesktopHandlingWidgetTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def decide(self, status):
        self.ui.handling_buttons[status].invoke()
        self.wait_for(lambda: '人工狀態已核對' in self.ui.message.get())
        self.wait_for(lambda: not self.ui._busy and self.ui._detail_document.get('status') == status)

    def assert_pending(self):
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_four_states_reopen_and_history_leave_delivery_and_payload_unchanged(self):
        before = event_payload_hash(self.store.get_event(self.anchor))
        self.select(self.anchor)
        self.assertTrue(self.ui.handling_buttons['new'].instate(['disabled']))
        for status in ('read', 'handled', 'ignored', 'new'):
            self.decide(status)
            self.assertEqual(self.ui._detail_document['event']['delivery_status'], 'pending')
            self.assert_pending()
        reopened = DesktopController(self.root).inspect(self.anchor)
        self.assertEqual(reopened['status'], 'new')
        self.assertEqual([x['status'] for x in reopened['handling_history']['entries']], ['read', 'handled', 'ignored', 'new'])
        self.assertTrue(all(x['source'] == 'gui' for x in reopened['handling_history']['entries']))
        self.select(self.member)
        self.select(self.anchor)
        self.assertIn('人工處置狀態：新增', self.ui.detail.get('1.0', 'end'))
        self.assertIn('不是投遞 ACK', self.ui.detail.get('1.0', 'end'))
        self.assertEqual(event_payload_hash(self.store.get_event(self.anchor)), before)

    def test_lost_reply_retry_replays_original_key_without_reverting_later_human_state(self):
        self.select(self.anchor)
        original, keys = self.controller.set_status, []
        def save(event_id, status, operation_id):
            keys.append(operation_id)
            value = original(event_id, status, operation_id)
            if len(keys) == 1:
                raise OSError('synthetic lost reply after commit')
            return value
        with patch.object(self.controller, 'set_status', side_effect=save):
            self.ui.handling_buttons['handled'].invoke()
            self.wait_for(lambda: '結果未確認' in self.ui.message.get())
            self.wait_for(lambda: self.ui.handling_buttons['handled'].instate(['!disabled']))
            self.assertEqual(len(keys), 1)
            self.catalog.set_status(self.anchor, 'read', source='cli', operation_id='op-later-human')
            self.ui._last_event = None
            self.select(self.anchor)
            self.ui.handling_buttons['handled'].invoke()
            self.wait_for(lambda: '人工狀態已核對' in self.ui.message.get())
            self.wait_for(lambda: not self.ui._busy and self.ui._detail_document.get('status') == 'read')
        self.assertEqual(keys[0], keys[1])
        entries = self.catalog.detail(self.anchor)['handling_history']['entries']
        self.assertEqual([x['status'] for x in entries], ['handled', 'read'])
        self.assertEqual(self.ui._pending_status, {})
        self.assert_pending()

    def test_capacity_and_activity_failure_preserve_database_then_allow_read_recovery(self):
        self.select(self.anchor)
        self.decide('read')
        before = self.store.path.read_bytes()
        with patch('eventguard.events.disposition_history.MAX_HISTORY_PER_EVENT', 1):
            self.ui.handling_buttons['handled'].invoke()
            self.wait_for(lambda: '人工狀態未保存' in self.ui.message.get())
            self.wait_for(lambda: self.ui.handling_buttons['handled'].instate(['!disabled']))
        self.assertEqual(self.store.path.read_bytes(), before)
        with patch('eventguard.activity.begin', side_effect=activity.ActivityError('activity_storage_unavailable')):
            self.ui.handling_buttons['handled'].invoke()
            self.wait_for(lambda: '人工狀態未保存' in self.ui.message.get())
            self.wait_for(lambda: self.ui._detail_document.get('state') == 'error')
        self.assertEqual(self.store.path.read_bytes(), before)
        self.select(self.anchor)
        self.assertEqual(self.ui._detail_document['status'], 'read')
        self.assertEqual(len(self.catalog.detail(self.anchor)['handling_history']['entries']), 1)
        self.assert_pending()

    def test_switching_selection_during_save_keeps_decisions_bound_to_requested_event(self):
        self.select(self.anchor)
        original, entered, release = self.controller.set_status, threading.Event(), threading.Event()
        def save(*args):
            entered.set()
            release.wait(timeout=2)
            return original(*args)
        with patch.object(self.controller, 'set_status', side_effect=save):
            try:
                self.ui.handling_buttons['handled'].invoke()
                self.wait_for(entered.is_set)
                self.assertTrue(all(b.instate(['disabled']) for b in self.ui.handling_buttons.values()))
                self.ui.handling_buttons['handled'].invoke()
                self.ui.events.selection_set(self.member)
                self.ui.select_event()
                release.set()
                self.wait_for(lambda: not self.ui.worker.pending and self.ui._detail_document.get('event', {}).get('event_id') == self.member)
            finally:
                release.set()
        self.assertEqual(self.ui._detail_document['status'], 'new')
        self.assertEqual(self.catalog.detail(self.anchor)['status'], 'handled')
        self.assertEqual(len(self.catalog.detail(self.anchor)['handling_history']['entries']), 1)
        self.assertIn(self.anchor, self.ui.message.get())
        self.assert_pending()
