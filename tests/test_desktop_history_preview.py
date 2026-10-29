"""Only known own backups; synthetic SQLite and files, no user paths."""
from unittest.mock import patch
import os
import unittest

from eventguard.desktop import DesktopController
from eventguard.events.disposition_history_backup_file import read_known_backup
import test_desktop_history_backup as fixture


class DesktopHistoryPreviewTests(unittest.TestCase):
    setUp = fixture.DesktopHistoryBackupTests.setUp
    def backup(self):
        self.name = 'history-backup-preview.json'
        self.controller.backup_history(self.name)
        self.path = self.root/'reports'/self.name

    def test_known_backup_comparison_is_read_only_and_not_a_restore(self):
        self.backup()
        before = self.store.path.read_bytes()
        result = self.controller.preview_history_backup(self.name)
        self.assertEqual(result['counts']['already_present'], 1)
        self.assertEqual(result['identity_conflicts'], 0)
        self.assertEqual(result['history_order'], 'exact_prefix')
        self.assertEqual(result['recoverability_status'], 'unknown')
        self.assertFalse(result['restore_performed'])
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_unknown_and_reopened_controller_never_open_arbitrary_file(self):
        self.backup()
        for controller, name in ((self.controller, 'history-backup-other.json'), (DesktopController(self.root), self.name)):
            with self.assertRaisesRegex(ValueError, 'history_backup_not_known'), patch('pathlib.Path.open', side_effect=AssertionError('no read')):
                controller.preview_history_backup(name)

    def test_changed_missing_and_changed_during_preview_reject_without_source_writes(self):
        self.backup()
        before = self.store.path.read_bytes()
        original = self.catalog.preview_handling_history
        def change(value):
            result = original(value)
            self.path.write_bytes(b'changed synthetic file')
            return result
        with patch('eventguard.events.catalog.EventCatalog.preview_handling_history', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'history_backup_file_changed'):
                self.controller.preview_history_backup(self.name)
        with self.assertRaisesRegex(ValueError, 'history_backup_file_changed'):
            self.controller.preview_history_backup(self.name)
        self.path.unlink()  # This test's own temporary fixture only.
        with self.assertRaises(FileNotFoundError):
            self.controller.preview_history_backup(self.name)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_metadata_mismatch_rejects_before_read_and_hash_rejects_same_metadata(self):
        self.backup()
        identity = self.controller._history_backup[1]
        expected, digest = identity
        opened = self.path.open('rb')
        self.addCleanup(opened.close)
        with patch('pathlib.Path.open', return_value=opened), patch.object(opened, 'read', side_effect=AssertionError('no content read')):
            with self.assertRaisesRegex(ValueError, 'history_backup_file_changed'):
                read_known_backup(self.root, self.name, ((expected[0], expected[1]+1, *expected[2:]), digest))
        self.path.write_bytes(b'x'*expected[2])
        os.utime(self.path, ns=(self.path.stat().st_atime_ns, expected[3]))
        with self.assertRaisesRegex(ValueError, 'history_backup_file_changed'):
            self.controller.preview_history_backup(self.name)
