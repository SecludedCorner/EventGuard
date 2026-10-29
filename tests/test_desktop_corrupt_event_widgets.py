"""Real Tk + corrupt synthetic SQLite: unknown must never become another case."""
import json
import unittest

from eventguard.events.schema import validate_event
from eventguard.events.store import event_payload_hash
import test_desktop_investigation_widgets as fixture


class DesktopCorruptEventWidgetTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def corrupt(self):
        event = validate_event(self.store.get_event(self.anchor))
        event['event_id'] = 'foreign-case-never-shown'
        with self.store._connect() as db:
            db.execute('UPDATE events SET payload=?,payload_hash=? WHERE event_id=?',
                       (json.dumps(event), event_payload_hash(event), self.anchor))
        return self.store.path.read_bytes()

    def assert_write_controls_disabled(self):
        self.assertTrue(self.ui.investigate_button.instate(['disabled']))
        self.assertTrue(all(button.instate(['disabled']) for button in self.ui.handling_buttons.values()))

    def test_bad_detail_clears_previous_case_disables_writes_and_healthy_case_still_opens(self):
        self.select(self.member)
        before = self.corrupt()
        self.ui.events.selection_set(self.anchor)
        self.ui.select_event()
        self.wait_for(lambda: self.ui._detail_document.get('state') == 'error')
        self.assert_write_controls_disabled()
        text = self.ui.detail.get('1.0', 'end')
        self.assertNotIn('foreign-case-never-shown', text)
        self.assertNotIn(self.member, text)
        self.assertEqual(self.ui._detail_document, {'state': 'error'})
        self.assertFalse(self.ui._request_journal_known)
        self.select(self.member)
        self.assertEqual(self.ui._detail_document['event']['event_id'], self.member)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_stale_loaded_detail_cannot_save_after_source_corruption(self):
        self.select(self.anchor)
        before = self.corrupt()
        self.ui.handling_buttons['handled'].invoke()
        self.wait_for(lambda: not self.ui._busy and not self.ui.worker.pending
                      and not self.ui._snapshot_due)
        self.wait_for(lambda: not self.ui.events.get_children())
        self.assert_write_controls_disabled()
        self.assertIn('未知', self.ui.events_note.get())
        self.assertIn('不代表沒有事件或主機安全', self.ui.events_note.get())
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_refresh_failure_shows_unknown_total_without_safe_empty_claim(self):
        self.select(self.anchor)
        before = self.corrupt()
        self.ui.refresh_button.invoke()
        self.wait_for(lambda: '狀態讀取失敗' in self.ui.message.get())
        self.assertEqual(self.ui.events.get_children(), ())
        self.assertIn('儲存總數 未知', self.ui.events_note.get())
        self.assertIn('不代表沒有事件或主機安全', self.ui.events_note.get())
        self.assert_write_controls_disabled()
        self.assertEqual(self.store.path.read_bytes(), before)
