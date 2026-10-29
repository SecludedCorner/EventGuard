"""Real synthetic SQLite with capability fences; never installation data."""
from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.desktop_fixture import BLOCKED, DesktopFixtureController
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class DesktopFixtureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)
        self.enterContext(patch('eventguard.processes.spawn', side_effect=AssertionError('no process/model')))
        self.enterContext(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no collector')))
        self.enterContext(patch('eventguard.diagnostics.api.DiagnosticAPI.query', side_effect=AssertionError('no native query')))
        self.enterContext(patch('eventguard.operations.OperatorAPI.call', side_effect=AssertionError('no native API')))
        self.enterContext(patch.object(EventStore, 'acknowledge', side_effect=AssertionError('no ACK')))

    def test_fresh_scope_real_catalog_and_blocked_capabilities(self):
        fixture = DesktopFixtureController(self.project, 'desktop-ux-test')
        self.addCleanup(fixture.close)
        before = fixture.store.path.read_bytes()
        snapshot = fixture.snapshot()
        self.assertTrue(snapshot['synthetic_fixture'])
        self.assertEqual(len(snapshot['sources']), 7)
        self.assertTrue(all(e['synthetic'] for e in snapshot['events']))
        self.assertEqual(snapshot['counts']['pending'], 4)
        for name in BLOCKED:
            self.assertEqual(getattr(fixture, name)(True)['state'], 'blocked')
        self.assertEqual(fixture.store.path.read_bytes(), before)

        event_id = 'synthetic-ux-listener'
        fixture.set_status(event_id, 'handled', 'fixture-human-1')
        self.assertEqual(fixture.inspect(event_id)['status'], 'handled')
        self.assertEqual(fixture.inspect(event_id)['latest_diagnosis']['observations'][0]['status'], 'denied')
        self.assertEqual((fixture.store.stats()['pending'], fixture.store.stats()['receipt_count']), (4, 0))
        self.assertTrue(fixture.close()['can_close'])
        self.assertEqual(fixture.inspect(event_id)['state'], 'blocked')

    def test_existing_scope_and_unsafe_name_refused_without_touching_installation(self):
        sentinel = self.project/'data/live'
        sentinel.mkdir(parents=True)
        (sentinel/'eventguard.sqlite3').write_bytes(b'not synthetic: must not open')
        fixture = DesktopFixtureController(self.project, 'desktop-ux-existing')
        self.addCleanup(fixture.close)
        before = fixture.store.path.read_bytes()
        with self.assertRaises(FileExistsError):
            DesktopFixtureController(self.project, 'desktop-ux-existing')
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_name_invalid'):
            DesktopFixtureController(self.project, '../data/live')
        self.assertEqual(fixture.store.path.read_bytes(), before)
        self.assertEqual((sentinel/'eventguard.sqlite3').read_bytes(), b'not synthetic: must not open')

    def test_extra_or_non_synthetic_content_refused_before_ui_operations(self):
        fixture = DesktopFixtureController(self.project, 'desktop-ux-changed')
        self.addCleanup(fixture.close)
        event = make_synthetic('listener')
        event['synthetic'] = False
        fixture.store.enqueue(event)
        before = fixture.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_data_scope_changed'):
            fixture.snapshot()
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_data_scope_changed'):
            fixture.set_status('synthetic-ux-listener', 'handled', 'fixture-rejected')
        self.assertEqual(fixture.store.path.read_bytes(), before)
        with closing(sqlite3.connect(fixture.store.path)) as db, db:
            db.execute("DELETE FROM events WHERE event_id='synthetic-ux-coverage'")
        self.assertEqual(len(fixture.store.list_events()), 4)
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_data_scope_changed'):
            fixture.snapshot()
