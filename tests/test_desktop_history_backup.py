"""Synthetic desktop backup controller; no native activity or user data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard import activity
from eventguard.desktop import DesktopController
from eventguard.events.catalog import EventCatalog
from eventguard.events.disposition_history_backup import verify_snapshot
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class DesktopHistoryBackupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root/'data/live')
        self.event = make_synthetic('listener')
        self.store.enqueue(self.event)
        self.catalog = EventCatalog(self.root, 'live')
        self.catalog.set_status(self.event['event_id'], 'read', source='gui', operation_id='op-backup')
        self.controller = DesktopController(self.root)
        self.enterContext(patch('eventguard.processes.spawn', side_effect=AssertionError('no child/model')))
        self.enterContext(patch('eventguard.diagnostics.api.DiagnosticAPI.query', side_effect=AssertionError('no query')))
        self.enterContext(patch.object(EventStore, 'acknowledge', side_effect=AssertionError('no ACK')))

    def test_backup_matches_source_and_has_no_capacity_or_ack_side_effect(self):
        before = self.store.path.read_bytes()
        result = self.controller.backup_history('history-backup-desktop.json')
        value = json.loads((self.root/result['path']).read_bytes())
        self.assertEqual(verify_snapshot(value)['records'], 1)
        self.assertEqual(value, self.catalog.handling_history_snapshot())
        self.assertEqual(result['state'], 'history_backup_saved')
        self.assertTrue(result['file_fsynced'])
        self.assertEqual(result['directory_entry_durability'], 'not_verified')
        self.assertFalse(result['source_history_removed'])
        self.assertFalse(result['ack_performed'])
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_existing_name_and_invalid_path_never_overwrite_or_change_source(self):
        self.controller.backup_history('history-backup-desktop.json')
        path = self.root/'reports/history-backup-desktop.json'
        before, content = self.store.path.read_bytes(), path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.controller.backup_history(path.name)
        with self.assertRaisesRegex(ValueError, 'history_backup_filename_invalid'):
            self.controller.backup_history('../outside.json')
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_activity_failure_prevents_file_write_and_missing_store_is_not_initialized(self):
        with patch('eventguard.activity.begin', side_effect=activity.ActivityError('activity_storage_unavailable')):
            result = self.controller.backup_history('history-backup-blocked.json')
        self.assertFalse(result['operation_started'])
        self.assertFalse((self.root/'reports').exists())
        other = self.root/'empty'
        other.mkdir()
        with self.assertRaisesRegex(ValueError, 'history_store_not_found'):
            DesktopController(other).backup_history('history-backup-empty.json')
        self.assertFalse((other/'data/live').exists())
        self.assertFalse((other/'reports').exists())
