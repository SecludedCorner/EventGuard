"""Actual own Tk controls and real synthetic backup identity comparison."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from eventguard.gui_presenter import history_preview_text
import test_desktop_investigation_widgets as fixture


class DesktopHistoryPreviewWidgetTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for

    def backup(self):
        self.wait_for(lambda: not self.ui.worker.pending)
        self.ui.history_backup_button.invoke()
        self.wait_for(lambda: self.ui.history_preview_button.instate(['!disabled']))
        return self.ui._confirmed_backup_name

    def preview(self, term):
        self.wait_for(lambda: not self.ui.worker.pending and self.ui.history_preview_button.instate(['!disabled']))
        self.ui.history_preview_button.invoke()
        self.wait_for(lambda: term in self.ui.history_preview.get('1.0', 'end'))

    def test_explicit_preview_counts_are_inert_private_and_not_restore_evidence(self):
        self.assertTrue(self.ui.history_preview_button.instate(['disabled']))
        self.catalog.set_status(self.anchor, 'read', source='cli', operation_id='op-preview-widget')
        name = self.backup()
        before = self.store.path.read_bytes()
        with patch.object(self.controller, 'preview_history_backup', wraps=self.controller.preview_history_backup) as calls:
            self.ui.history_preview_frame.master.select(self.ui.history_preview_frame)
            self.window.update()
            calls.assert_not_called()
            self.preview('身分衝突 0')
            self.assertEqual(calls.call_count, 1)
        text = self.ui.history_preview.get('1.0', 'end')
        for term in ('已存在操作 1', '可恢復性均未知', '零衝突不等於可信', '未執行還原'):
            self.assertIn(term, text)
        self.assertNotIn(self.anchor, text)
        self.assertNotIn('op-preview-widget', text)
        self.assertEqual(self.ui.history_preview.cget('state'), 'disabled')
        self.assertEqual(self.store.path.read_bytes(), before)
        self.catalog.set_status(self.anchor, 'handled', source='cli', operation_id='op-after-backup')
        before = self.store.path.read_bytes()
        self.preview('順序已分歧')
        self.assertIn('備份 1 筆；目前 2 筆', self.ui.history_preview.get('1.0', 'end'))
        self.assertEqual(self.store.path.read_bytes(), before)
        result = self.controller.preview_history_backup(name)
        result['counts']['already_present'] = True
        self.assertIsNone(history_preview_text(result))
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_changed_file_clears_previous_success_and_rejects_unrelated_receipt(self):
        name = self.backup()
        self.preview('身分衝突 0')
        valid = self.controller.preview_history_backup(name)
        before = self.store.path.read_bytes()
        (self.root/'reports'/name).write_bytes(b'synthetic changed backup')
        self.preview('核對結果未確認')
        self.assertNotIn('身分衝突 0', self.ui.history_preview.get('1.0', 'end'))
        self.wait_for(lambda: not self.ui.worker.pending)
        with patch.object(self.controller, 'preview_history_backup', return_value=dict(valid, path='reports/history-backup-other.json')):
            self.preview('核對結果未確認')
        self.assertEqual(self.store.path.read_bytes(), before)
        self.wait_for(lambda: not self.ui.worker.pending)
        with patch.object(self.controller, 'backup_history', return_value={'operation_started': False}):
            self.ui.history_backup_button.invoke()
            self.wait_for(lambda: '歷程備份結果未確認' in self.ui.message.get())
        self.assertTrue(self.ui.history_preview_button.instate(['disabled']))
        self.assertIn('先前核對不能代表本次', self.ui.history_preview.get('1.0', 'end'))

    def test_real_widget_discloses_controlled_interval_and_missing_time_is_not_filled(self):
        name = self.backup()
        original = self.controller.preview_history_backup
        start, end = (datetime(2026, 10, 26, 0, 0, s, tzinfo=timezone.utc) for s in (0, 1))
        def timed(filename):
            with patch('eventguard.desktop.datetime') as clock:
                clock.now.side_effect = (start, end)
                return original(filename)
        before = self.store.path.read_bytes()
        with patch.object(self.controller, 'preview_history_backup', side_effect=timed):
            self.preview('2026-10-26T00:00:00+00:00 → 2026-10-26T00:00:01+00:00')
        self.assertIn('不能證明之後狀態', self.ui.history_preview.get('1.0', 'end'))
        value = dict(original(name), read_started_at=None, read_finished_at=None)
        with patch.object(self.controller, 'preview_history_backup', return_value=value):
            self.preview('核對讀取區間：未知')
        self.assertNotIn('2026-10-26', self.ui.history_preview.get('1.0', 'end'))
        self.assertEqual(self.store.path.read_bytes(), before)
