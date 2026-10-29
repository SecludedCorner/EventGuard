"""Actual Tk list columns backed by synthetic SQLite human decisions."""
from copy import deepcopy
import unittest

import test_desktop_investigation_widgets as fixture


class DesktopHandlingListTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def refresh_list(self, expected):
        self.ui.refresh()
        self.wait_for(lambda: self.ui.events.set(self.anchor, 'handling') == expected)
        self.assertEqual(self.ui.events.set(self.anchor, 'delivery'), '待接手')

    def test_columns_show_saved_human_decision_without_ack_or_read_side_effect(self):
        self.assertEqual(self.ui.events.heading('handling')['text'], '人工處置')
        self.assertEqual(self.ui.events.heading('delivery')['text'], '接收狀態')
        self.assertEqual(self.ui.events.set(self.anchor, 'handling'), '新增')
        self.assertIn('人工處置不等於接收 ACK 或修復', self.ui.events_note.get())
        for state, label in (('read', '已讀'), ('handled', '已處理'), ('ignored', '忽略')):
            self.catalog.set_status(self.anchor, state, source='cli')
            before = self.store.path.read_bytes()
            self.refresh_list(label)
            self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_changed_loaded_payload_and_missing_annotation_render_unknown(self):
        self.catalog.set_status(self.anchor, 'handled', source='cli')
        self.refresh_list('已處理')
        changed = deepcopy(self.store.list_events())
        next(e for e in changed if e['event_id'] == self.anchor)['evidence']['port'] += 1
        self.controller.api.call.side_effect = lambda *a, **k: {'event_list': {'events': changed, 'total': 2}}
        before = self.store.path.read_bytes()
        self.refresh_list('未知')
        self.assertEqual(self.store.path.read_bytes(), before)
        self.ui._apply_snapshot({'events': self.store.list_events(), 'events_total': 2})
        self.assertEqual(self.ui.events.set(self.anchor, 'handling'), '未知')

    def test_button_save_updates_list_and_keeps_selection(self):
        self.select(self.anchor)
        self.ui.handling_buttons['handled'].invoke()
        self.wait_for(lambda: '人工狀態已核對' in self.ui.message.get())
        self.wait_for(lambda: self.ui.events.set(self.anchor, 'handling') == '已處理')
        self.assertEqual(self.ui.events.selection(), (self.anchor,))
        self.assertEqual(self.ui.events.set(self.anchor, 'delivery'), '待接手')
        self.assertEqual(self.catalog.detail(self.anchor)['status'], 'handled')
