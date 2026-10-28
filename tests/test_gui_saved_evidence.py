"""Real own Tk + synthetic SQLite evidence changes; no collector/model/ACK."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.gui import EventGuardWindow
from test_event_investigation import fixture_events, NOW
from test_gui import FixtureController


class SavedEvidenceWidgetTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('standard-library Tk unavailable')
        try:
            self.window = tk.Tk()
        except tk.TclError:
            self.skipTest('own Tk display unavailable; not a successful desktop acceptance')
        self.addCleanup(self.window.destroy)
        self.window.withdraw()
        self.controller = FixtureController()
        self.ui = EventGuardWindow(self.window, self.controller)
        self.addCleanup(self.close_ui)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root/'data/test')
        self.events = fixture_events()[:2]
        for event in self.events:
            self.store.enqueue(event)
        self.catalog = EventCatalog(self.root, 'test')
        self.anchor = self.events[0]['event_id']
        self.member = self.events[1]['event_id']
        self.catalog.investigate(self.anchor, now=NOW)
        self.catalog.investigate(self.anchor, now=(datetime.fromisoformat(NOW)+timedelta(seconds=1)).isoformat())
        self.enterContext(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')))

    def close_ui(self):
        self.ui.dispose()
        self.ui.worker.shutdown(wait=True)
        self.assertFalse(self.ui.worker.thread.is_alive())

    def render_readonly(self):
        before = hashlib.sha256(self.store.path.read_bytes()).hexdigest()
        value = self.catalog.detail(self.anchor)
        self.ui._show_detail(value)
        self.window.update_idletasks()
        self.assertEqual(before, hashlib.sha256(self.store.path.read_bytes()).hexdigest())
        self.assertEqual(value['event']['delivery_status'], 'pending')
        self.assertEqual(self.ui.detail.cget('state'), 'disabled')
        self.assertFalse(any(action != 'snapshot' for action, _ in self.controller.calls))
        return self.ui.detail.get('1.0', 'end')

    def test_member_removed_marks_latest_case_and_prior_case_unknown(self):
        self.assertIn('保存成員相符', self.render_readonly())
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute('DELETE FROM events WHERE event_id=?', (self.member,))
            db.commit()
        text = self.render_readonly()
        for expected in ('成員證據：未知', '原事件缺失，未知', '成員證據未知'):
            self.assertIn(expected, text)
        self.assertNotIn('保存成員相符', text)

    def test_member_payload_change_is_not_presented_as_matching_history(self):
        changed = deepcopy(self.events[1])
        changed['evidence']['port'] += 1
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute('UPDATE events SET payload=?,payload_hash=? WHERE event_id=?',
                       (json.dumps(changed), event_payload_hash(changed), self.member))
            db.commit()
        text = self.render_readonly()
        self.assertIn('事件內容已變更，未知', text)
        self.assertIn('成員證據未知', text)
        self.assertNotIn('保存成員相符', text)
