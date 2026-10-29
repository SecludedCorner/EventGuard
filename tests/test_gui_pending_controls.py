"""Actual Tk controls over synthetic SQLite; no browser/native input claim."""
import unittest

import test_desktop_investigation_widgets as fixture


class GuiPendingControlTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def test_view_snapshot_refresh_and_return_preserve_context_without_ack(self):
        self.select(self.member)
        self.controller.set_status_durable(self.anchor, 'handled', 'pending-control-op')
        self.wait_for(lambda: self.ui.pending_button.instate(['!disabled']))
        before = self.store.path.read_bytes()
        self.ui.pending_button.invoke()
        self.wait_for(lambda: self.ui._pending_page is not None)
        self.assertEqual(self.ui.events.get_children(), (self.anchor,))
        self.assertIn('待確認清單快照', self.ui.events_note.get())
        self.assertTrue(self.ui.pending_next.instate(['disabled']))
        self.ui._apply_snapshot(self.controller.snapshot())
        self.assertEqual(self.ui.events.get_children(), (self.anchor,))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.ui.pending_back.invoke()
        self.wait_for(lambda: not self.ui.worker.pending and self.ui._detail_document.get('event', {}).get('event_id') == self.member)
        self.assertEqual(self.ui.events.selection(), (self.member,))
        self.assertFalse(self.ui._pending_mode)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))
