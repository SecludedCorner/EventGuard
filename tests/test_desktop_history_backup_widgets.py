"""Own real Tk backup button -> real synthetic history and local file."""
import json
import threading
import unittest
from unittest.mock import patch

from eventguard.events.disposition_history_backup import verify_snapshot
import test_desktop_investigation_widgets as fixture


class DesktopHistoryBackupWidgetTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for

    def test_explicit_button_creates_one_verified_file_without_changing_source(self):
        self.catalog.set_status(self.anchor, 'read', source='cli', operation_id='op-widget-backup')
        self.wait_for(lambda: not self.ui.worker.pending)
        self.assertFalse((self.root/'reports').exists())
        before = self.store.path.read_bytes()
        original, entered, release, names = self.controller.backup_history, threading.Event(), threading.Event(), []
        def save(name):
            names.append(name)
            entered.set()
            release.wait(timeout=2)
            return original(name)
        with patch.object(self.controller, 'backup_history', side_effect=save):
            try:
                self.ui.history_backup_button.invoke()
                self.wait_for(entered.is_set)
                self.assertTrue(self.ui.history_backup_button.instate(['disabled']))
                self.ui.history_backup_button.invoke()
                release.set()
                self.wait_for(lambda: '歷程備份已核對' in self.ui.message.get())
            finally:
                release.set()
        self.assertEqual(len(names), 1)
        files = list((self.root/'reports').iterdir())
        self.assertEqual([p.name for p in files], names)
        saved = json.loads(files[0].read_bytes())
        self.assertEqual((verify_snapshot(saved)['records'], saved['data']['namespace']), (1, 'live'))
        self.assertIn('目錄項耐久性未驗', self.ui.message.get())
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_existing_destination_failure_is_visible_without_overwrite_or_auto_retry(self):
        self.wait_for(lambda: not self.ui.worker.pending)
        original, paths = self.controller.backup_history, []
        def collide(name):
            path = self.root/'reports'/name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'synthetic existing backup')
            paths.append(path)
            return original(name)
        before = self.store.path.read_bytes()
        with patch.object(self.controller, 'backup_history', side_effect=collide):
            self.ui.history_backup_button.invoke()
            self.wait_for(lambda: '歷程備份結果未確認' in self.ui.message.get())
            self.wait_for(lambda: not self.ui.worker.pending)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].read_bytes(), b'synthetic existing backup')
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_unrelated_receipt_cannot_claim_success(self):
        self.wait_for(lambda: not self.ui.worker.pending)
        with patch.object(self.controller, 'backup_history', return_value={
            'state': 'history_backup_saved', 'path': 'reports/history-backup-other.json',
            'namespace': 'live', 'file_fsynced': True, 'source_history_removed': False, 'ack_performed': False}):
            self.ui.history_backup_button.invoke()
            self.wait_for(lambda: '歷程備份結果未確認' in self.ui.message.get())
        self.assertFalse((self.root/'reports').exists())
