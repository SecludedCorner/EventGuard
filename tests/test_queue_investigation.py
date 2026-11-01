"""Durable agent-authored report must precede ACK; no real model execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.store import EventStore, StoreError
from eventguard.queue_inbox import QueueInbox, QueueInboxError
from eventguard.synthetic import make_synthetic


class QueueInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.event = make_synthetic('listener')
        self.identity = self.event['event_id']
        self.store = EventStore(self.root/'source')
        self.store.enqueue(self.event)
        self.inbox = self.open()
        self.inbox.receive_event()
        self.query = self.inbox.query_evidence(self.identity)
        self.report = dict(summary='Synthetic listener metadata requires follow-up; current host is unverified.',
            finding='metadata_requires_followup', fact_keys=['coverage_status'],
            limitations=self.query['saved_evidence']['limitations'], next_step='request_authorized_evidence')

    def open(self):
        return QueueInbox(self.root/'source', self.root/'inbox', self.identity, investigation=True)

    def save(self, **changes):
        return self.inbox.save_investigation(self.identity, self.query['query_id'], dict(self.report, **changes))

    def ack(self):
        return self.inbox.ack_event(self.identity, self.query['query_id'], 'needs_more_evidence')

    def test_large_legal_classification_fits_reserved_investigation_stages(self):
        from eventguard.rules.configured import ENUM_FIELDS
        from eventguard.rules.decisions import classify
        rule = dict(id='wide-classifier', name='inert bounded fixture', enabled=True, severity='critical',
            conditions=[dict(field='coverage_status', op='in', value=sorted(ENUM_FIELDS['coverage_status'])) for _ in range(12)])
        event = classify([self.event], [rule])[0]
        source = self.root/'large-source'
        store = EventStore(source)
        store.enqueue(event)
        inbox = QueueInbox(source, self.root/'large-inbox', self.identity, investigation=True)
        inbox.receive_event()
        query = inbox.query_evidence(self.identity)
        value = dict(self.report, fact_keys=['classification'], limitations=query['saved_evidence']['limitations'])
        try:
            inbox.save_investigation(self.identity, query['query_id'], value)
        except QueueInboxError:
            self.assertEqual((store.stats()['pending'], store.stats()['receipt_count']), (1, 0))
            raise
        inbox.ack_event(self.identity, query['query_id'], 'needs_more_evidence')
        self.assertEqual((store.stats()['pending'], store.stats()['receipt_count']), (0, 1))

    def test_separate_save_restart_and_ack_preserve_traceable_report(self):
        with self.assertRaisesRegex(QueueInboxError, 'saved_investigation_required'):
            self.ack()
        saved = self.save()
        self.assertFalse(saved['outbox_acknowledged'])
        self.assertEqual(self.store.stats()['pending'], 1)
        self.assertEqual(self.save(), saved)
        with self.assertRaisesRegex(QueueInboxError, 'immutable_record_conflict'):
            self.save(summary='Changed analysis')
        self.inbox = self.open()
        completed = self.ack()
        self.assertTrue(completed['outbox_acknowledged'])
        self.assertEqual(self.store.stats()['pending'], 0)
        self.assertEqual(completed['investigation'], saved['investigation'])
        audit = QueueInbox.open_readonly(self.root/'source', self.root/'inbox', self.identity, investigation=True)
        self.assertEqual(audit.evidence(self.identity)['result']['result_id'], saved['result_id'])

    def test_failed_save_foreign_query_and_incomplete_report_never_ack(self):
        with patch.object(self.inbox, '_immutable', side_effect=QueueInboxError('injected_save_failure')):
            with self.assertRaisesRegex(QueueInboxError, 'injected_save_failure'):
                self.save()
        for query, value in [('query-foreign', self.report), (self.query['query_id'], dict(self.report, limitations=[]))]:
            with self.assertRaises(QueueInboxError):
                self.inbox.save_investigation(self.identity, query, value)
        self.assertEqual(self.store.stats()['pending'], 1)
        self.assertFalse(self.inbox.acknowledged(self.identity))

    def test_evidence_tampering_and_profile_switch_are_rejected(self):
        with self.assertRaisesRegex(QueueInboxError, 'profile_conflict'):
            QueueInbox(self.root/'source', self.root/'inbox', self.identity)
        path = self.inbox._path('query', self.identity)
        value = json.loads(path.read_text())
        value['saved_evidence']['facts']['coverage_status'] = 'denied'
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(QueueInboxError, 'evidence_identity_conflict'):
            self.save()
        self.assertEqual(self.store.stats()['pending'], 1)

    def test_oversized_completion_is_rejected_before_source_ack(self):
        with patch('eventguard.queue_inbox.INVESTIGATION_STAGE_RESERVE', 100):
            with self.assertRaisesRegex(QueueInboxError, 'stage_reserve_exceeded'):
                self.save()
        self.assertEqual(self.store.stats()['pending'], 1)

    def test_investigation_receive_reserves_all_stages_before_disclosing_second_event(self):
        second = dict(self.event, event_id=self.identity+'-second')
        self.store.enqueue(second)
        state = self.root/'bounded-inbox'
        limits = dict(max_events=3, max_bytes=65536)
        first = QueueInbox(self.root/'source', state, self.identity, investigation=True, limits=limits)
        first.receive_event()
        self.assertEqual(first.maintain()['reserved_bytes'], 3*16384)
        other = QueueInbox(self.root/'source', state, second['event_id'], investigation=True, limits=limits)
        with self.assertRaisesRegex(QueueInboxError, 'capacity'):
            other.receive_event()
        self.assertEqual(len(list(state.glob('snapshot-*.json'))), 1)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_large_classification_and_unicode_report_survive_save_and_finalization_failures(self):
        from eventguard.rules.configured import ENUM_FIELDS
        from eventguard.rules.decisions import classify
        rule = dict(id='recovery-classifier', name='inert fixture', enabled=True, severity='high',
            conditions=[dict(field='coverage_status', op='in', value=sorted(ENUM_FIELDS['coverage_status'])) for _ in range(12)])
        event = classify([self.event], [rule])[0]
        results = []
        for failure in ('completion', 'finalize'):
            with self.subTest(failure=failure):
                source, state = self.root/failure/'source', self.root/failure/'inbox'
                store = EventStore(source, acked_retention_seconds=0, receipt_retention_seconds=0)
                store.enqueue(event)
                inbox = QueueInbox(source, state, self.identity, investigation=True)
                inbox.receive_event()
                query = inbox.query_evidence(self.identity)
                report = dict(self.report, summary='\U0001f9ea'*400, fact_keys=['classification'],
                              limitations=query['saved_evidence']['limitations'])
                with patch.object(inbox, '_immutable', side_effect=QueueInboxError('synthetic_save_failure')):
                    with self.assertRaisesRegex(QueueInboxError, 'synthetic_save_failure'):
                        inbox.save_investigation(self.identity, query['query_id'], report)
                self.assertEqual((store.stats()['pending'], store.stats()['receipt_count']), (1, 0))
                self.assertNotIn('result', inbox.evidence(self.identity))
                inbox = QueueInbox(source, state, self.identity, investigation=True)
                self.assertEqual(inbox.query_evidence(self.identity), query)
                saved = inbox.save_investigation(self.identity, query['query_id'], report)
                expected = saved['investigation']
                self.assertEqual(expected['observations']['classification'], event['classification'])
                original = inbox._immutable
                def fail_completion(path, value):
                    if path.name.startswith('completed-'):
                        raise QueueInboxError('synthetic_completion_failure')
                    return original(path, value)
                target = inbox if failure == 'completion' else inbox.store
                method = '_immutable' if failure == 'completion' else 'finalize_receiver'
                injected = fail_completion if failure == 'completion' else StoreError('synthetic_finalize_failure')
                with patch.object(target, method, side_effect=injected), self.assertRaises(QueueInboxError):
                    inbox.ack_event(self.identity, query['query_id'], 'needs_more_evidence')
                self.assertEqual((store.stats()['pending'], store.stats()['receipt_count'],
                                  store.stats()['pending_receiver_finalizations']), (0, 1, 1))
                self.assertEqual(inbox._path('completed', self.identity).exists(), failure == 'finalize')
                store.maintain()
                self.assertIsNone(store.get_event(self.identity))
                self.assertEqual(store.stats()['receipt_count'], 1)
                restarted = QueueInbox(source, state, self.identity, investigation=True)
                with patch.object(EventStore, 'acknowledge', side_effect=AssertionError('must not ACK twice')):
                    restarted.maintain()
                    self.assertEqual(restarted.query_evidence(self.identity), query)
                    completed = restarted.ack_event(self.identity, query['query_id'], 'needs_more_evidence')
                    self.assertEqual(completed['investigation'], expected)
                    self.assertTrue(completed['outbox_acknowledged'])
                    self.assertEqual(restarted.ack_event(self.identity, query['query_id'], 'needs_more_evidence'), completed)
                self.assertEqual(store.stats()['pending_receiver_finalizations'], 0)
                for stage in ('snapshot', 'query', 'result'):
                    self.assertFalse(restarted._path(stage, self.identity).exists())
                audit = QueueInbox.open_readonly(source, state, self.identity, investigation=True).evidence(self.identity)
                self.assertEqual(audit['saved_evidence']['facts']['classification'], event['classification'])
                self.assertEqual(audit['result']['investigation'], expected)
                results.append(dict(failure=failure, classification_preserved=True, pending=0,
                                    finalization_pins=0, repeated_source_ack=False, model_calls=0))
        self.evidence = dict(scope='synthetic SQLite/files; fault injection, zero TTL, actual reopen; no model', cases=results)
