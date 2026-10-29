"""Explicitly synthetic CLI traces; never claim a model has executed."""
from copy import deepcopy
import unittest

from eventguard.investigation_evidence import assess
import test_queue_investigation as fixture


class InvestigationEvidenceTests(unittest.TestCase):
    setUp = fixture.QueueInvestigationTests.setUp
    open = fixture.QueueInvestigationTests.open
    save = fixture.QueueInvestigationTests.save
    ack = fixture.QueueInvestigationTests.ack

    def fixture(self):
        received = self.inbox.receive_event()
        saved = self.save()
        ack = self.ack()
        record = self.inbox.evidence(self.identity)
        args = [{}, dict(event_id=self.identity),
            dict(event_id=self.identity, query_id=self.query['query_id'], report=self.report),
            dict(event_id=self.identity, query_id=self.query['query_id'], decision='needs_more_evidence')]
        trace = [dict(type='thread.started', thread_id='synthetic-trace-not-a-model')]
        for index, (tool, value, reply) in enumerate(zip(
                ('receive_event', 'query_evidence', 'save_investigation', 'ack_event'), args,
                (received, self.query, saved, ack))):
            item = dict(type='mcp_tool_call', id=str(index), server='eventguard_inbox', tool=tool, arguments=value)
            trace.append(dict(type='item.started', item=item))
            trace.append(dict(type='item.completed', item=dict(item, status='completed', result={'structuredContent': reply})))
        trace.append(dict(type='turn.completed'))
        return trace, record

    def test_synthetic_four_step_trace_matches_durable_report(self):
        trace, record = self.fixture()
        self.assertTrue(assess(trace, record, self.identity, 0, True)['passed'])

    def test_omitted_save_foreign_content_reordered_calls_or_shell_are_not_proof(self):
        trace, record = self.fixture()
        for change in ('omit_save', 'changed_summary', 'foreign_hash', 'shell', 'duplicate', 'bad_exit', 'not_acked'):
            rows, saved = deepcopy(trace), deepcopy(record)
            code, acked = 0, True
            if change == 'omit_save': del rows[5:7]
            if change == 'changed_summary': rows[6]['item']['arguments']['report']['summary'] = 'Different'
            if change == 'foreign_hash': saved['saved_evidence']['payload_hash'] = '0'*64
            if change == 'shell': rows.insert(-1, dict(type='item.completed', item=dict(type='command_execution')))
            if change == 'duplicate': rows.insert(-1, deepcopy(rows[6]))
            if change == 'bad_exit': code = 1
            if change == 'not_acked': acked = False
            with self.subTest(change=change):
                self.assertFalse(assess(rows, saved, self.identity, code, acked)['passed'])
