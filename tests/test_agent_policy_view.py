"""Default-condition explanations match real selector exclusions, without launch."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard.agent_policy_view import snapshot
from eventguard.dispatch_policy import select_pending
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.queue_inbox import QueueInbox
from test_dispatch_policy import event


class AgentPolicyViewTests(unittest.TestCase):
    def test_severity_and_human_status_reasons_match_real_sqlite_selector(self):
        for severity, status, reason in (('high', 'new', None), ('warning', 'new', 'severity_not_selected'),
                                        ('high', 'handled', 'human_status_not_selected')):
            with self.subTest(severity=severity, status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                store = EventStore(root / 'data/test')
                store.enqueue(event(severity=severity))
                if status != 'new':
                    store.set_disposition('evt-one', status)
                before = store.path.read_bytes()
                view = EventCatalog(root, 'test').detail('evt-one')['default_agent_policy']
                selected = select_pending(QueueInbox(store.directory, root / 'inbox'))
                self.assertEqual(view['state'], 'conditions_met' if selected else 'conditions_not_met')
                self.assertEqual(view['reasons'], [] if reason is None else [reason])
                self.assertEqual(store.path.read_bytes(), before)
                self.assertEqual((store.stats()['pending'], store.stats()['receipt_count']), (1, 0))

    def test_ack_and_unknown_metadata_never_claim_conditions_met(self):
        value = event()
        value['delivery_status'] = 'ack'
        self.assertEqual(snapshot(value, 'read')['reasons'], ['delivery_not_pending'])
        for bad in ({}, dict(value, delivery_status='unknown')):
            self.assertEqual(snapshot(bad, 'new')['state'], 'unknown')
        self.assertEqual(snapshot(value, 'unknown')['state'], 'unknown')
        with patch('eventguard.agent_policy_view.load_policy', side_effect=ValueError('unavailable')):
            self.assertEqual(snapshot(value, 'new')['state'], 'unknown')
