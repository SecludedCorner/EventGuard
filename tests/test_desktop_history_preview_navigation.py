"""Own Tk tab/focus targets, not native keyboard or human acceptance."""
import threading
import unittest
from unittest.mock import patch

import test_desktop_investigation_widgets as base
import test_desktop_history_preview_widgets as fixture


class DesktopHistoryPreviewNavigationTests(unittest.TestCase):
    setUp = base.DesktopInvestigationWidgetTests.setUp
    close_ui = base.DesktopInvestigationWidgetTests.close_ui
    wait_for = base.DesktopInvestigationWidgetTests.wait_for
    select = base.DesktopInvestigationWidgetTests.select
    backup = fixture.DesktopHistoryPreviewWidgetTests.backup
    preview = fixture.DesktopHistoryPreviewWidgetTests.preview

    def prepare(self):
        self.select(self.anchor)
        self.ui.delivery_filter.set('待接手')
        self.ui.filter_events()
        self.backup()
        self.window.deiconify()
        self.window.update()

    def test_return_restores_event_context_and_focus_without_another_read(self):
        self.prepare()
        before = self.store.path.read_bytes()
        with patch.object(self.controller, 'preview_history_backup', wraps=self.controller.preview_history_backup) as calls:
            self.preview('身分衝突 0')
            notebook = self.ui.history_preview_frame.master
            self.assertEqual(str(self.window.tk.call('focus', '-lastfor', self.window)), str(self.ui.history_preview))
            self.assertTrue(self.ui.history_preview_scroll.winfo_ismapped())
            self.ui.history_return_button.invoke()
            self.window.update()
            self.assertEqual(notebook.select(), str(self.ui.events.master))
            self.assertEqual(str(self.window.tk.call('focus', '-lastfor', self.window)), str(self.ui.history_preview_button))
            self.assertEqual(self.ui.events.selection(), (self.anchor,))
            self.assertEqual(self.ui.delivery_filter.get(), '待接手')
            self.assertEqual(self.ui._detail_document['event']['event_id'], self.anchor)
            self.assertEqual(calls.call_count, 1)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_return_while_pending_keeps_event_tab_when_result_arrives(self):
        self.prepare()
        original, entered, release = self.controller.preview_history_backup, threading.Event(), threading.Event()
        def delayed(name):
            entered.set()
            release.wait(timeout=2)
            return original(name)
        with patch.object(self.controller, 'preview_history_backup', side_effect=delayed):
            try:
                self.ui.history_preview_button.invoke()
                self.wait_for(entered.is_set)
                self.ui.history_return_button.invoke()
                self.assertEqual(str(self.window.tk.call('focus', '-lastfor', self.window)), str(self.ui.events))
                release.set()
                self.wait_for(lambda: '身分衝突 0' in self.ui.history_preview.get('1.0', 'end'))
                self.assertEqual(self.ui.events.master.master.select(), str(self.ui.events.master))
                self.assertEqual(self.ui.events.selection(), (self.anchor,))
            finally:
                release.set()
