"""Product Tk over isolated synthetic controller; no human results implied."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from eventguard.desktop_fixture import DesktopFixtureController
from eventguard.events.store import EventStore
from eventguard.gui import EventGuardWindow


class DesktopFixtureWidgetTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
            self.window = tk.Tk()
        except (ImportError, RuntimeError) as error:
            self.skipTest(type(error).__name__)
        except Exception as error:
            if type(error).__name__ == 'TclError':
                self.skipTest('own Tk unavailable')
            raise
        self.window.withdraw()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        for target in ('eventguard.processes.spawn', 'eventguard.collectors.windows.WindowsCollectors.collect',
                       'eventguard.diagnostics.api.DiagnosticAPI.query', 'eventguard.operations.OperatorAPI.call'):
            self.enterContext(patch(target, side_effect=AssertionError('fixture must not use native capability')))
        self.enterContext(patch.object(EventStore, 'acknowledge', side_effect=AssertionError('no ACK')))
        self.controller = DesktopFixtureController(self.project, 'desktop-ux-widget')
        self.ui = EventGuardWindow(self.window, self.controller, refresh_ms=60000)
        self.addCleanup(self.close)
        self.wait_for(lambda: self.ui.events.exists('synthetic-ux-listener'))

    def close(self):
        self.ui.dispose()
        self.ui.worker.shutdown(wait=True)
        self.assertFalse(self.ui.worker.thread.is_alive())
        try:
            self.window.destroy()
        except self.ui.tk.TclError:
            pass

    def wait_for(self, condition):
        deadline = time.monotonic()+4
        while time.monotonic() < deadline:
            self.window.update()
            if condition():
                return
            time.sleep(.005)
        self.fail('synthetic Tk did not reach expected state')

    def assert_fence(self):
        for widget in (self.ui.start_button, self.ui.pause_button, self.ui.agent_check,
                       self.ui.automatic_check, self.ui.automatic_path, self.ui.automatic_browse):
            self.assertTrue(widget.instate(['disabled']))
        self.assertIn('非主機實測', self.window.title())
        self.assertIn('合成驗收', self.ui.headline.get())
        self.assertIn('情境準備時間', self.ui.updated.get())

    def test_real_handling_and_backup_stay_synthetic_and_do_not_ack(self):
        self.assert_fence()
        self.assertIn('合成固定情境', self.ui.message.get())
        self.ui.events.selection_set('synthetic-ux-listener')
        self.ui.select_event()
        self.wait_for(lambda: self.ui.handling_buttons['handled'].instate(['!disabled']))
        self.ui.handling_buttons['handled'].invoke()
        self.wait_for(lambda: '人工狀態已核對' in self.ui.message.get())
        self.wait_for(lambda: not self.ui.worker.pending)
        self.assert_fence()
        self.ui.history_backup_button.invoke()
        self.wait_for(lambda: self.ui.history_preview_button.instate(['!disabled']))
        self.ui.history_preview_button.invoke()
        self.wait_for(lambda: '身分衝突 0' in self.ui.history_preview.get('1.0', 'end'))
        self.assertEqual((self.controller.store.stats()['pending'], self.controller.store.stats()['receipt_count']), (4, 0))

    def test_error_or_reopened_view_cannot_remove_marker_or_reset_saved_status(self):
        self.controller.set_status('synthetic-ux-listener', 'read', 'fixture-reopen')
        self.ui._apply_snapshot({})
        self.assert_fence()
        self.ui.dispose()
        self.ui.worker.shutdown(wait=True)
        for widget in self.window.winfo_children():
            widget.destroy()
        self.ui = EventGuardWindow(self.window, self.controller, refresh_ms=60000)
        self.wait_for(lambda: self.ui.events.exists('synthetic-ux-listener'))
        self.assertEqual(self.ui.events.set('synthetic-ux-listener', 'handling'), '已讀')
        self.assert_fence()
