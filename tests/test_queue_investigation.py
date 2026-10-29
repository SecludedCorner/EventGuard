"""Durable agent-authored report must precede ACK; no real model execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.store import EventStore
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
        with patch('eventguard.queue_inbox.STAGE_RESERVE', 100):
            with self.assertRaisesRegex(QueueInboxError, 'stage_reserve_exceeded'):
                self.save()
        self.assertEqual(self.store.stats()['pending'], 1)
