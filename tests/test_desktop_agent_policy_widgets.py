"""Actual Tk policy explanations never activate agent, collection or ACK."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from eventguard.events.schema import validate_event
import test_desktop_investigation_widgets as fixture


class DesktopAgentPolicyWidgetTests(unittest.TestCase):
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def setUp(self):
        fixture.DesktopInvestigationWidgetTests.setUp(self)
        event = validate_event(self.store.get_event(self.anchor))
        event.update(event_id='high-policy-fixture', severity='high')
        self.high = event['event_id']
        self.store.enqueue(event)
        self.controller.api.call.side_effect = lambda *a, **k: {
            'event_storage': {'state': 'available', 'counts': self.store.stats()},
            'event_list': {'events': self.store.list_events(), 'total': 3, 'truncated': False}}
        self.ui.refresh_button.invoke()
        self.wait_for(lambda: self.ui.events.exists(self.high))

    def test_warning_and_high_text_are_distinct_and_read_only(self):
        before = self.store.path.read_bytes()
        self.select(self.anchor)
        self.assertIn('嚴重度未被預設政策選中', self.ui.detail.get('1.0', 'end'))
        self.select(self.high)
        text = self.ui.detail.get('1.0', 'end')
        self.assertIn('Agent 預設政策條件：符合', text)
        self.assertIn('不是啟動授權或喚醒證據', text)
        self.assertIn('自訂 dispatcher、重試時間／lease', text)
        self.assertIn('不代表 agent 已喚醒、ACK 或防守成功', text)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_human_handled_refreshes_reason_but_does_not_ack(self):
        self.select(self.high)
        self.ui.handling_buttons['handled'].invoke()
        self.wait_for(lambda: self.ui._detail_document.get('status') == 'handled')
        text = self.ui.detail.get('1.0', 'end')
        self.assertIn('人工狀態未被預設政策選中', text)
        self.assertIn('Agent 預設政策條件：不符合', text)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (3, 0))

    def test_wrong_event_and_unknown_policy_never_render_conditions_met(self):
        original = self.controller.inspect
        def wrong(event_id):
            value = deepcopy(original(event_id))
            value['default_agent_policy']['event_id'] = 'other-case'
            return value
        before = self.store.path.read_bytes()
        with patch.object(self.controller, 'inspect', side_effect=wrong):
            self.select(self.high)
            self.assertIn('Agent 預設政策條件：未知', self.ui.detail.get('1.0', 'end'))
        self.select(self.member)
        with patch('eventguard.agent_policy_view.load_policy', side_effect=ValueError('unavailable')):
            self.select(self.high)
            self.assertIn('Agent 預設政策條件：未知', self.ui.detail.get('1.0', 'end'))
            self.assertNotIn('Agent 預設政策條件：符合', self.ui.detail.get('1.0', 'end'))
        self.assertEqual(self.store.path.read_bytes(), before)
