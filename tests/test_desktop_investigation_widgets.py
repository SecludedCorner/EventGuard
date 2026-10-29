"""Real own Tk button -> DesktopController -> synthetic Catalog/SQLite."""
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from eventguard.desktop import DesktopController
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import CapacityError, EventStore
from eventguard.gui import EventGuardWindow
from test_event_investigation import fixture_events, NOW


class DesktopInvestigationWidgetTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('standard-library Tk unavailable')
        try:
            self.window = tk.Tk()
        except tk.TclError:
            self.skipTest('own Tk unavailable; not desktop acceptance')
        self.window.withdraw()
        self.addCleanup(self.window.destroy)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root/'data/live')
        self.events = fixture_events()[:2]
        for event in self.events:
            self.store.enqueue(event)
        self.anchor, self.member = (event['event_id'] for event in self.events)
        self.catalog = EventCatalog(self.root, 'live')
        self.controller = DesktopController(self.root)
        self.controller.api = Mock()
        self.controller.api.call.side_effect = lambda *a, **k: {
            'event_storage': {'state': 'available', 'counts': self.store.stats()},
            'event_list': {'events': self.store.list_events(), 'total': 2, 'truncated': False}}
        self.as_of = NOW
        original = EventCatalog.investigate
        self.enterContext(patch.object(EventCatalog, 'investigate', lambda c, event_id: original(c, event_id, now=self.as_of)))
        self.enterContext(patch('eventguard.processes.spawn', side_effect=AssertionError('no child/model')))
        self.enterContext(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')))
        self.enterContext(patch.object(EventStore, 'acknowledge', side_effect=AssertionError('no ACK')))
        self.ui = EventGuardWindow(self.window, self.controller, refresh_ms=60000)
        self.addCleanup(self.close_ui)
        self.wait_for(lambda: self.ui.events.exists(self.anchor))

    def close_ui(self):
        self.ui.dispose()
        self.ui.worker.shutdown(wait=True)
        self.assertFalse(self.ui.worker.thread.is_alive())

    def wait_for(self, condition):
        deadline = time.monotonic()+4
        while time.monotonic() < deadline:
            self.window.update()
            if condition():
                return
            time.sleep(.005)
        self.fail('own Tk integration did not reach expected state')

    def select(self, event_id):
        self.ui.events.selection_set(event_id)
        self.ui.select_event()
        self.wait_for(lambda: self.ui.investigate_button.instate(['!disabled']))

    def save(self):
        self.ui.investigate_button.invoke()
        self.wait_for(lambda: '已保存調查' in self.ui.message.get())
        self.wait_for(lambda: self.ui.investigate_button.instate(['!disabled']))

    def test_button_save_update_and_reopen_preserve_real_versions_and_pending(self):
        self.select(self.anchor)
        self.assertIsNone(self.catalog.detail(self.anchor)['investigation'])
        self.save()
        first = self.catalog.detail(self.anchor)['investigation']['case']
        self.assertIn('成員與保存雜湊相符（非來源認證）', self.ui.detail.get('1.0', 'end'))
        self.as_of = (datetime.fromisoformat(NOW)+timedelta(seconds=1)).isoformat()
        self.save()
        detail = self.catalog.detail(self.anchor)
        self.assertEqual(len(detail['investigation_revisions']['revisions']), 1)
        self.assertEqual(detail['investigation_revisions']['revisions'][0]['case'], first)
        self.ui._last_event = None
        self.select(self.anchor)
        self.assertIn('保存前版 1', self.ui.detail.get('1.0', 'end'))
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_real_capacity_failure_keeps_old_database_and_pending(self):
        self.select(self.anchor)
        self.save()
        before = self.store.path.read_bytes()
        with patch.object(EventStore, 'save_investigation', side_effect=CapacityError('synthetic capacity')):
            self.ui.investigate_button.invoke()
            self.wait_for(lambda: '容量不足' in self.ui.message.get())
            self.wait_for(lambda: self.ui.investigate_button.instate(['!disabled']))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertIn('成員與保存雜湊相符（非來源認證）', self.ui.detail.get('1.0', 'end'))
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_selection_change_during_save_does_not_display_the_old_case(self):
        self.select(self.anchor)
        entered, release = threading.Event(), threading.Event()
        original = self.controller.investigate
        def save(event_id):
            entered.set()
            release.wait(timeout=2)
            return original(event_id)
        with patch.object(self.controller, 'investigate', side_effect=save):
            try:
                self.ui.investigate_button.invoke()
                self.wait_for(entered.is_set)
                self.ui.events.selection_set(self.member)
                self.ui.select_event()
                release.set()
                self.wait_for(lambda: not self.ui.worker.pending and self.ui._detail_document.get('event', {}).get('event_id') == self.member)
            finally:
                release.set()
        self.assertIsNone(self.ui._detail_document['investigation'])
        self.assertIsNotNone(self.catalog.detail(self.anchor)['investigation'])
        self.assertIsNone(self.catalog.detail(self.member)['investigation'])
        self.assertIn(self.anchor, self.ui.message.get())
