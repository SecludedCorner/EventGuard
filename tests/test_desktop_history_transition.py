"""Actual Tk preserves known transition conflicts even with identity match."""
from contextlib import closing
import sqlite3
import unittest

from eventguard.gui_presenter import history_transition_text
import test_desktop_history_preview_widgets as fixture


class HistoryTransitionPresenterTests(unittest.TestCase):
    def test_missing_malformed_and_impossible_counts_are_unknown(self):
        for value in (None, [], {}, {'state': 'consistent', 'checked_pairs': 0, 'conflicts': 0},
                      {'state': 'conflict', 'checked_pairs': 1, 'conflicts': 2},
                      {'state': 'conflict', 'checked_pairs': True, 'conflicts': 1},
                      {'state': 'safe', 'checked_pairs': 1, 'conflicts': 0}):
            with self.subTest(value=value):
                self.assertIn('未知，格式或計數無法核對', history_transition_text(value))


class DesktopHistoryTransitionTests(unittest.TestCase):
    setUp = fixture.DesktopHistoryPreviewWidgetTests.setUp
    close_ui = fixture.DesktopHistoryPreviewWidgetTests.close_ui
    wait_for = fixture.DesktopHistoryPreviewWidgetTests.wait_for
    backup = fixture.DesktopHistoryPreviewWidgetTests.backup
    preview = fixture.DesktopHistoryPreviewWidgetTests.preview

    def test_known_conflict_survives_matching_hashes_and_prefix_in_real_widget(self):
        self.catalog.set_status(self.anchor, 'read', source='cli', operation_id='op-first')
        self.catalog.set_status(self.anchor, 'handled', source='cli', operation_id='op-second')
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("UPDATE event_disposition_operations SET previous_status='ignored' WHERE operation_id='op-second'")
        self.backup()
        before = self.store.path.read_bytes()
        self.preview('備份內部轉換：已知衝突')
        text = self.ui.history_preview.get('1.0', 'end')
        for term in ('身分衝突 0', '目前歷程是備份前綴', '檢查 1 對／衝突 1 對', '首筆前狀態與缺失歷程仍未知'):
            self.assertIn(term, text)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_single_record_is_unobserved_and_consistency_does_not_prove_completeness(self):
        self.catalog.set_status(self.anchor, 'read', source='cli', operation_id='op-one')
        self.backup()
        self.preview('尚無可比較相鄰轉換')
        self.catalog.set_status(self.anchor, 'handled', source='cli', operation_id='op-two')
        self.backup()
        before = self.store.path.read_bytes()
        self.preview('已檢查相鄰轉換一致（非完整性證明）')
        self.assertEqual(self.store.path.read_bytes(), before)
