"""Saved synthetic validation never repairs a database or reads installation data."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from eventguard.desktop_fixture import DesktopFixtureController
from eventguard.desktop_fixture_read import SavedFixtureStore
from eventguard.events.schema import validate_event
from eventguard.events.store import event_payload_hash


class SavedFixtureReadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.fixture = DesktopFixtureController(self.project, 'desktop-ux-saved')
        self.addCleanup(self.fixture.close)

    def test_existing_states_and_cases_read_without_database_changes(self):
        self.fixture.set_status('synthetic-ux-listener', 'handled', 'fixture-saved')
        self.fixture.investigate('synthetic-ux-listener')
        before = self.fixture.store.path.read_bytes()
        saved = SavedFixtureStore(self.fixture.root)
        self.assertEqual(len(saved.list_events()), 4)
        self.assertEqual(saved.stats()['pending'], 4)
        detail = saved.catalog.detail('synthetic-ux-listener')
        self.assertEqual(detail['status'], 'handled')
        self.assertIsNotNone(detail['investigation'])
        self.assertEqual(self.fixture.store.path.read_bytes(), before)

    def test_missing_schema_and_invalid_marker_are_not_repaired(self):
        marker = self.fixture.root/'fixture.json'
        document = json.loads(marker.read_bytes())
        document['synthetic'] = False
        marker.write_text(json.dumps(document), encoding='utf-8')
        before = self.fixture.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_scope_invalid'):
            SavedFixtureStore(self.fixture.root)
        self.assertEqual(self.fixture.store.path.read_bytes(), before)
        document['synthetic'] = True
        marker.write_text(json.dumps(document), encoding='utf-8')
        with closing(sqlite3.connect(self.fixture.store.path)) as db, db:
            db.execute('DROP TABLE receipts')
        broken = self.fixture.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_scope_invalid'):
            SavedFixtureStore(self.fixture.root)
        self.assertEqual(self.fixture.store.path.read_bytes(), broken)

    def test_missing_store_and_hash_valid_non_synthetic_event_are_refused(self):
        absent = self.project/'reports/desktop-ux-absent'
        absent.mkdir()
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_scope_invalid'):
            SavedFixtureStore(absent)
        self.assertFalse((absent/'data').exists())
        event = validate_event(self.fixture.store.get_event('synthetic-ux-listener'))
        event['synthetic'] = False
        with closing(sqlite3.connect(self.fixture.store.path)) as db, db:
            db.execute('UPDATE events SET payload=?,payload_hash=? WHERE event_id=?',
                       (json.dumps(event), event_payload_hash(event), event['event_id']))
        before = self.fixture.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_scope_invalid'):
            SavedFixtureStore(self.fixture.root)
        self.assertEqual(self.fixture.store.path.read_bytes(), before)
