"""Saved synthetic review presentation, without native queries."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from eventguard.diagnostics.review import event_view, review
from eventguard.gui_presenter import diagnosis_summary
from eventguard.synthetic import make_synthetic


def document(status='denied', truncated=False):
    event = make_synthetic('listener')
    api = SimpleNamespace(query=lambda *a: {'source': 'listeners', 'status': status, 'rows': [],
        'coverage': {}, 'truncated': truncated, 'observed_at': event['observed_at']})
    diagnosis = review(event, api, refresh=True)
    diagnosis['namespace'] = 'live'
    return {'event': event_view(event), 'latest_diagnosis': diagnosis, 'latest_diagnosis_is_saved': True}


class DesktopDiagnosisSummaryTests(unittest.TestCase):
    def text(self, value):
        return '\n'.join(diagnosis_summary(value, value['event']['event_id']))

    def test_partial_denied_empty_and_truncated_remain_historical(self):
        value = document(truncated=True)
        before = deepcopy(value)
        text = self.text(value)
        for term in ('歷史觀察', '部分觀察', '監聽端點：拒讀', '保存列數 0', '已截斷', '非來源認證', '查無資料不等於恢復'):
            self.assertIn(term, text)
        self.assertEqual(value, before)
        self.assertIn('非安全判定', self.text(document('ok')))

    def test_missing_unbound_and_oversized_do_not_disclose_other_diagnosis(self):
        for mutate in (lambda v: v.pop('latest_diagnosis_is_saved'),
                       lambda v: v['latest_diagnosis']['event'].update(event_id='another-event'),
                       lambda v: v['latest_diagnosis'].update(observations=[{}]*3)):
            value = document()
            mutate(value)
            self.assertIn('無法核對，保持未知', self.text(value))
            self.assertNotIn('監聽端點：拒讀', self.text(value))
        value = document()
        value['latest_diagnosis'] = None
        self.assertIn('尚無已保存查證', self.text(value))

    def test_untrusted_codes_are_inert_bounded_and_current_only_is_disclosed(self):
        value = document()
        row = value['latest_diagnosis']['observations'][0]
        row.update(error_code='instruction\n\u202e'+'x'*500, coverage={'mode': 'current_only', 'errors_truncated': True})
        text = self.text(value)
        for term in ('不能重建事件發生時', '錯誤紀錄已截斷', '\\u000a', '\\u202e'):
            self.assertIn(term, text)
        self.assertNotIn('\u202e', text)
        self.assertNotIn('x'*100, text)
