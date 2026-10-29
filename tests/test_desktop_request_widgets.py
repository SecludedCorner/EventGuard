"""Real Tk windows recover saved keys; reads and malformed journals never write."""
import unittest
import threading
from unittest.mock import patch

import test_desktop_investigation_widgets as fixture
from eventguard.desktop import DesktopController
from eventguard.gui import EventGuardWindow


class DesktopRequestWidgetTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def test_confirmation_failure_before_or_after_cleanup_keeps_key_without_replay(self):
        for index, stage in enumerate(('before', 'after')):
            with self.subTest(stage=stage):
                self.select(self.anchor)
                original, confirms = self.controller.confirm_status_receipt, []
                def fail(*args):
                    confirms.append(args)
                    if stage == 'after':
                        original(*args)
                    raise OSError('synthetic confirmation reply failure')
                with patch.object(self.controller, 'confirm_status_receipt', side_effect=fail), patch.object(
                        self.controller, 'set_status_durable', wraps=self.controller.set_status_durable) as save:
                    self.ui.handling_buttons['handled'].invoke()
                    self.wait_for(lambda: '清理結果未確認' in self.ui.message.get() and not self.ui._busy)
                    self.assertIn('保存回條已收到', self.ui.message.get())
                    self.assertNotIn('未保存', self.ui.message.get())
                    self.assertNotIn('人工狀態已核對', self.ui.message.get())
                    op = self.ui._pending_status[(self.anchor, 'handled')]
                    self.assertEqual((save.call_count, len(confirms)), (1, 1))
                    self.assertEqual(len(self.catalog.detail(self.anchor)['pending_handling_requests']['requests']),
                                     1 if stage == 'before' else 0)
                self.catalog.set_status(self.anchor, 'read', source='cli', operation_id='later-confirm-'+stage)
                self.ui._last_event = None
                self.select(self.anchor)
                with patch.object(self.controller, 'set_status_durable', wraps=self.controller.set_status_durable) as retry:
                    self.ui.handling_buttons['handled'].invoke()
                    self.wait_for(lambda: '人工狀態已核對' in self.ui.message.get())
                    self.wait_for(lambda: not self.ui._busy and self.ui._detail_document.get('status') == 'read')
                    self.assertEqual(retry.call_args.args[2], op)
                self.assertEqual(len(self.catalog.detail(self.anchor)['handling_history']['entries']), 2*(index+1))
                self.assertEqual(self.ui._pending_status, {})
                self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_confirmation_failure_after_selection_change_stays_bound_to_original_event(self):
        self.select(self.anchor)
        entered, release = threading.Event(), threading.Event()
        def fail(*args):
            entered.set()
            release.wait(timeout=2)
            raise OSError('synthetic confirmation unavailable')
        with patch.object(self.controller, 'confirm_status_receipt', side_effect=fail):
            try:
                self.ui.handling_buttons['handled'].invoke()
                self.wait_for(entered.is_set)
                self.ui.events.selection_set(self.member)
                self.ui.select_event()
                release.set()
                self.wait_for(lambda: not self.ui.worker.pending and self.ui._detail_document.get('event', {}).get('event_id') == self.member)
            finally:
                release.set()
        self.assertIn(self.anchor, self.ui.message.get())
        self.assertEqual(self.ui._detail_document['status'], 'new')
        self.assertNotIn('未確認要求：', self.ui.handling_status.get())
        self.assertEqual(self.catalog.detail(self.anchor)['status'], 'handled')
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_new_tk_window_recovers_lost_success_key_without_automatic_replay(self):
        self.select(self.anchor)
        original = self.controller.set_status_durable
        def lose(*args):
            original(*args)
            raise OSError('synthetic lost success reply')
        with patch.object(self.controller, 'set_status_durable', side_effect=lose):
            self.ui.handling_buttons['handled'].invoke()
            self.wait_for(lambda: '結果未確認' in self.ui.message.get() and not self.ui._busy)
        op = self.catalog.detail(self.anchor)['pending_handling_requests']['requests'][0]['operation_id']
        self.close_ui()
        controller = DesktopController(self.root)
        controller.api = self.controller.api
        window = self.ui.tk.Toplevel(self.window)
        second = EventGuardWindow(window, controller, refresh_ms=60000)
        try:
            with patch.object(controller, 'set_status_durable', wraps=controller.set_status_durable) as save, patch.object(
                    controller, 'confirm_status_receipt', wraps=controller.confirm_status_receipt) as confirm:
                self.wait_for(lambda: second.events.exists(self.anchor))
                before = self.store.path.read_bytes()
                second.events.selection_set(self.anchor)
                second.select_event()
                self.wait_for(lambda: second._request_journal_known and (self.anchor, 'handled') in second._pending_status)
                self.assertEqual(second._pending_status[(self.anchor, 'handled')], op)
                self.assertIn('未確認要求：已處理', second.handling_status.get())
                self.assertEqual((save.call_count, confirm.call_count), (0, 0))
                self.assertEqual(self.store.path.read_bytes(), before)
                self.catalog.set_status(self.anchor, 'read', source='cli', operation_id='newer-window-decision')
                second.handling_buttons['handled'].invoke()
                self.wait_for(lambda: '人工狀態已核對' in second.message.get())
                self.wait_for(lambda: not second._busy and second._detail_document.get('status') == 'read')
                self.assertEqual(save.call_args.args[2], op)
                self.assertEqual((save.call_count, confirm.call_count), (1, 1))
                self.assertEqual(self.catalog.detail(self.anchor)['pending_handling_requests']['requests'], [])
                self.assertEqual(len(self.catalog.detail(self.anchor)['handling_history']['entries']), 2)
                self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))
        finally:
            second.dispose()
            second.worker.shutdown(wait=True)
            window.destroy()

    def test_malformed_journal_keeps_detail_readable_and_disables_human_writes(self):
        self.controller.set_status_durable(self.anchor, 'handled', 'corrupt-journal-op')
        with self.store._connect() as db:
            db.execute('ALTER TABLE desktop_status_requests ADD COLUMN unexpected TEXT')
        self.select(self.anchor)
        self.assertIn('人工處置狀態：已處理', self.ui.detail.get('1.0', 'end'))
        self.assertIn('日誌未知，人工寫入停用', self.ui.handling_status.get())
        self.assertTrue(all(b.instate(['disabled']) for b in self.ui.handling_buttons.values()))
        before = self.store.path.read_bytes()
        with patch.object(self.controller, 'set_status_durable', side_effect=AssertionError('no write')):
            self.ui.set_status('ignored')
            self.ui.handling_buttons['ignored'].invoke()
        self.assertEqual(self.store.path.read_bytes(), before)
