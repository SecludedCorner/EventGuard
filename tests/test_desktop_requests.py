"""Synthetic SQLite only; pending intents must never become a dispatch queue."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.desktop_requests import begin, pending
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.synthetic import make_synthetic


class DesktopRequestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = EventStore(Path(temp.name)/'test')
        event = make_synthetic('listener')
        self.store.enqueue(event)
        self.value = {'event_id': event['event_id'], 'status': 'handled', 'operation_id': 'pending-op',
                      'payload_hash': event_payload_hash(self.store.get_event(event['event_id']))}

    def connect(self):
        db = sqlite3.connect(self.store.path)
        db.row_factory = sqlite3.Row
        return db

    def test_read_does_not_initialize_and_committed_id_survives_reopen_without_dispatch(self):
        before = self.store.path.read_bytes()
        with closing(self.connect()) as db:
            db.execute('PRAGMA query_only=ON')
            self.assertEqual(pending(db), [])
        self.assertEqual(self.store.path.read_bytes(), before)
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            self.assertFalse(begin(db, self.value, available_bytes=100000)['replayed'])
            db.commit()
        with closing(self.connect()) as db:
            self.assertEqual(pending(db), [self.value])
            db.execute('BEGIN IMMEDIATE')
            with patch('eventguard.desktop_requests.MAX_PENDING', 1):
                self.assertTrue(begin(db, self.value, available_bytes=0)['replayed'])
            db.rollback()
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_capacity_and_wrong_hash_never_create_journal(self):
        before = self.store.path.read_bytes()
        for value, available in ((self.value, 0), (dict(self.value, payload_hash='0'*64), 100000)):
            with closing(self.connect()) as db:
                db.execute('BEGIN IMMEDIATE')
                with self.assertRaises(ValueError):
                    begin(db, value, available_bytes=available)
                db.rollback()
            self.assertEqual(self.store.path.read_bytes(), before)

    def test_conflicting_id_and_corrupt_schema_are_not_reset(self):
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            begin(db, self.value, available_bytes=100000)
            db.commit()
            before = self.store.path.read_bytes()
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaisesRegex(ValueError, 'desktop_request_pending_conflict'):
                begin(db, dict(self.value, operation_id='different-op'), available_bytes=100000)
            db.rollback()
            self.assertEqual(self.store.path.read_bytes(), before)
            db.execute('ALTER TABLE desktop_status_requests ADD COLUMN unexpected TEXT')
            db.commit()
            before = self.store.path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'desktop_request_schema_invalid'):
                pending(db)
            self.assertEqual(self.store.path.read_bytes(), before)
