"""Own real Tk + saved synthetic SQLite review, never a live query."""
from contextlib import closing
import sqlite3
import unittest
from unittest.mock import patch

from eventguard.desktop import DesktopController
from eventguard.diagnostics.review import review, validate_saved_review
from eventguard.gui_presenter import event_summary
import test_desktop_investigation_widgets as fixture
from test_investigation_diagnostics import FixtureAPI


class DesktopDiagnosisWidgetTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def save_diagnosis(self, *, status='denied', truncated=True):
        api = FixtureAPI(empty=True, status=status)
        original = api.query
        def query(*args):
            result = original(*args)
            result.update(truncated=truncated, coverage={'mode': 'current_only', 'errors_truncated': True})
            return result
        api.query = query
        event = self.store.get_event(self.anchor)
        result = dict(review(event, api, refresh=True, now=fixture.NOW), namespace='live')
        validate_saved_review(result, event)
        self.store.save_review(self.anchor, result['payload_hash'], result)
        return result

    def guard_queries(self):
        self.enterContext(patch('eventguard.diagnostics.api.DiagnosticAPI.query', side_effect=AssertionError('no implicit query')))

    def assert_pending(self):
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_real_widget_reads_saved_partial_denied_truncated_and_reopens_identically(self):
        self.save_diagnosis()
        self.guard_queries()
        before = self.store.path.read_bytes()
        self.select(self.anchor)
        text = self.ui.detail.get('1.0', 'end')
        for term in ('另存的查證結果（歷史觀察）', '部分觀察', '監聽端點：拒讀', '程序：拒讀',
                     '保存列數 0', '已截斷', '不能重建事件發生時', '查無資料不等於恢復'):
            self.assertIn(term, text)
        self.assertFalse(self.ui.show_raw.get())
        reopened = DesktopController(self.root).inspect(self.anchor)
        self.assertEqual(event_summary(reopened).strip(), text.strip())
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assert_pending()

    def test_missing_saved_diagnosis_does_not_copy_another_events_result(self):
        self.save_diagnosis(status='ok', truncated=False)
        self.guard_queries()
        self.select(self.anchor)
        self.assertIn('監聽端點：可讀', self.ui.detail.get('1.0', 'end'))
        before = self.store.path.read_bytes()
        self.select(self.member)
        text = self.ui.detail.get('1.0', 'end')
        self.assertIn('尚無已保存查證', text)
        self.assertNotIn('監聽端點：可讀', text)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assert_pending()

    def test_saved_hash_conflict_clears_stale_summary_then_recovers_by_read(self):
        result = self.save_diagnosis()
        self.guard_queries()
        self.select(self.anchor)
        self.select(self.member)
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('UPDATE event_reviews SET payload_hash=? WHERE event_id=?', ('0'*64, self.anchor))
        before = self.store.path.read_bytes()
        self.ui.events.selection_set(self.anchor)
        self.ui.select_event()
        self.wait_for(lambda: self.ui._detail_document.get('state') == 'error')
        text = self.ui.detail.get('1.0', 'end')
        self.assertIn('詳情讀取失敗', text)
        self.assertNotIn('監聽端點：拒讀', text)
        self.assertTrue(all(b.instate(['disabled']) for b in self.ui.handling_buttons.values()))
        self.assertEqual(self.store.path.read_bytes(), before)
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('UPDATE event_reviews SET payload_hash=? WHERE event_id=?', (result['payload_hash'], self.anchor))
        self.select(self.anchor)
        self.assertIn('監聽端點：拒讀', self.ui.detail.get('1.0', 'end'))
        self.assert_pending()
