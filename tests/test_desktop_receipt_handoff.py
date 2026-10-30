"""Force the receipt publication boundary with real Tk and synthetic SQLite."""
import threading
import unittest
from unittest.mock import patch

import test_desktop_investigation_widgets as fixture


class DesktopReceiptHandoffTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def test_published_receipt_before_worker_idle_defers_confirmation_without_resending(self):
        self.select(self.anchor)
        published, release = threading.Event(), threading.Event()
        original = self.ui.worker.results.put
        def put(item, *args, **kwargs):
            original(item, *args, **kwargs)
            if item[0] == 'set_status':
                published.set()
                release.wait(timeout=3)
        with patch.object(self.ui.worker.results, 'put', side_effect=put), patch.object(
                self.controller, 'set_status_durable', wraps=self.controller.set_status_durable) as save, patch.object(
                self.controller, 'confirm_status_receipt', wraps=self.controller.confirm_status_receipt) as confirm:
            try:
                self.ui.handling_buttons['handled'].invoke()
                self.wait_for(published.is_set)
                self.wait_for(lambda: self.ui._deferred_request is not None)
                self.assertEqual(self.ui._deferred_request[0], 'confirm_status_receipt')
                self.assertEqual(confirm.call_count, 0)
                self.assertTrue(self.catalog.detail(self.anchor)['pending_handling_requests']['requests'])
                self.assertNotIn('人工狀態已核對', self.ui.message.get())
            finally:
                release.set()
            self.wait_for(lambda: '人工狀態已核對' in self.ui.message.get())
            self.wait_for(lambda: (self.ui._detail_document or {}).get('status') == 'handled')
            self.assertEqual((save.call_count, confirm.call_count), (1, 1))
        self.assertEqual(self.catalog.detail(self.anchor)['pending_handling_requests']['requests'], [])
        self.assertEqual(len(self.catalog.detail(self.anchor)['handling_history']['entries']), 1)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_published_confirm_receipt_can_be_consumed_before_worker_idle(self):
        self.select(self.anchor)
        published, release = threading.Event(), threading.Event()
        original = self.ui.worker.results.put
        def put(item, *args, **kwargs):
            original(item, *args, **kwargs)
            if item[0] == 'confirm_status_receipt':
                published.set()
                release.wait(timeout=3)
        with patch.object(self.ui.worker.results, 'put', side_effect=put):
            try:
                self.ui.handling_buttons['read'].invoke()
                self.wait_for(published.is_set)
                self.wait_for(lambda: '人工狀態已核對' in self.ui.message.get())
                self.assertTrue(self.ui.worker.pending)
                self.assertFalse(self.ui._pending_status)
            finally:
                release.set()
            self.wait_for(lambda: (self.ui._detail_document or {}).get('status') == 'read')
        self.assertEqual(self.catalog.detail(self.anchor)['pending_handling_requests']['requests'], [])
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))
