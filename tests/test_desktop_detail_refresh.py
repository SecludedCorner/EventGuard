"""Real Tk refresh must not leave an externally changed human status stale."""
import threading
import unittest
from unittest.mock import patch

import test_desktop_investigation_widgets as fixture


class DesktopDetailRefreshTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def test_refresh_reloads_selected_detail_and_buttons_after_external_change(self):
        self.select(self.anchor)
        self.assertEqual(self.ui._detail_document['status'], 'new')
        self.catalog.set_status(self.anchor, 'handled', source='cli', operation_id='external-refresh')
        self.ui.refresh_button.invoke()
        self.wait_for(lambda: self.ui.events.item(self.anchor, 'values')[-1] == '已處理')
        self.wait_for(lambda: (self.ui._detail_document or {}).get('status') == 'handled')
        self.assertEqual(self.ui.events.selection(), (self.anchor,))
        self.assertTrue(self.ui.handling_buttons['handled'].instate(['disabled']))
        self.assertTrue(self.ui.handling_buttons['new'].instate(['!disabled']))
        self.assertIn('人工處置狀態：已處理', self.ui.detail.get('1.0', 'end'))
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_periodic_snapshot_notices_external_status_without_writing(self):
        self.select(self.anchor)
        self.catalog.set_status(self.anchor, 'ignored', source='cli', operation_id='external-periodic')
        self.ui._refresh()
        self.wait_for(lambda: (self.ui._detail_document or {}).get('status') == 'ignored')
        self.assertEqual(len(self.catalog.detail(self.anchor)['handling_history']['entries']), 1)
        self.assertEqual(self.store.stats()['receipt_count'], 0)

    def test_malformed_detail_status_does_not_crash_refresh_or_enable_writes(self):
        self.select(self.anchor)
        self.ui._detail_document['status'] = []
        self.ui._apply_snapshot(self.ui._recent_document)
        self.assertTrue(all(button.instate(['disabled']) for button in self.ui.handling_buttons.values()))

    def test_explicit_refresh_reads_new_investigation_even_if_status_unchanged(self):
        self.select(self.anchor)
        self.catalog.investigate(self.anchor)
        self.ui.refresh_button.invoke()
        self.wait_for(lambda: (self.ui._detail_document or {}).get('investigation') is not None)
        self.assertEqual(self.ui._detail_document['status'], 'new')
        self.assertEqual(self.store.stats()['receipt_count'], 0)

    def test_switch_during_refresh_keeps_new_selection_and_error_disables_writes(self):
        self.select(self.anchor)
        entered, release = threading.Event(), threading.Event()
        original = self.controller.snapshot
        def snapshot():
            entered.set()
            release.wait(timeout=3)
            return original()
        with patch.object(self.controller, 'snapshot', side_effect=snapshot):
            try:
                self.ui.refresh_button.invoke()
                self.wait_for(entered.is_set)
                self.assertTrue(all(button.instate(['disabled']) for button in self.ui.handling_buttons.values()))
                self.ui.events.selection_set(self.member)
                self.ui.select_event()
            finally:
                release.set()
            self.wait_for(lambda: (self.ui._detail_document or {}).get('event', {}).get('event_id') == self.member)
        with patch.object(self.controller, 'inspect', side_effect=OSError('synthetic unreadable')):
            self.ui.refresh_button.invoke()
            self.wait_for(lambda: (self.ui._detail_document or {}).get('state') == 'error')
        self.assertEqual(self.ui.events.selection(), (self.member,))
        self.assertTrue(all(button.instate(['disabled']) for button in self.ui.handling_buttons.values()))
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))
