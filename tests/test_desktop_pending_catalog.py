"""101 synthetic events prove discovery beyond the unchanged recent-100 list."""
from pathlib import Path
import json
import tempfile
import unittest

from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.events.schema import validate_event
from eventguard.synthetic import make_synthetic


class DesktopPendingCatalogTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = EventStore(self.root/'data/test')
        self.events = [dict(make_synthetic('listener'), event_id=f'synthetic-pending-{i:03}') for i in range(101)]
        self.store.commit_evaluation({'synthetic_fixture': True}, self.events)
        with self.store._connect() as db:
            db.execute('UPDATE events SET created_at=0 WHERE event_id=?', (self.events[0]['event_id'],))
        self.catalog = EventCatalog(self.root, 'test')

    def prepare(self, index, status='handled'):
        event_id = self.events[index]['event_id']
        value = {'namespace': 'test', 'event_id': event_id, 'status': status,
                 'operation_id': f'pending-{index}-{status}',
                 'payload_hash': event_payload_hash(validate_event(self.store.get_event(event_id)))}
        self.store._prepare_desktop_request(value, namespace='test')

    def test_old_anchor_outside_recent_100_is_discoverable_with_requests_coalesced(self):
        self.prepare(0)
        self.prepare(0, 'ignored')
        event_id = self.events[0]['event_id']
        self.assertNotIn(event_id, {e['event_id'] for e in self.store.list_events(limit=100)})
        before = self.store.path.read_bytes()
        result = self.catalog.pending_requests()
        self.assertEqual((result['state'], result['total'], result['request_total']), ('available', 1, 2))
        self.assertEqual(result['events'][0]['event_id'], event_id)
        self.assertEqual(result['events'][0]['pending_request_count'], 2)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (101, 0))

    def test_stable_two_pages_validate_off_page_binding_in_the_same_snapshot(self):
        for index in range(101):
            self.prepare(index)
        first = self.catalog.pending_requests()
        second = self.catalog.pending_requests(offset=100)
        self.assertEqual((len(first['events']), len(second['events']), first['total']), (100, 1, 101))
        self.assertTrue(first['has_more'])
        self.assertFalse(second['has_more'])
        ids = [e['event_id'] for e in first['events']+second['events']]
        self.assertEqual(ids, sorted(e['event_id'] for e in self.events))
        with self.store._connect() as db:
            db.execute("UPDATE desktop_status_requests SET payload_hash=? WHERE event_id=?", ('0'*64, ids[-1]))
        before = self.store.path.read_bytes()
        unknown = self.catalog.pending_requests()
        self.assertEqual((unknown['state'], unknown['total'], unknown['events']), ('unknown', None, []))
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_missing_source_and_invalid_pages_are_not_an_available_empty_list(self):
        self.assertEqual(EventCatalog(self.root/'missing', 'test').pending_requests()['state'], 'unknown')
        self.assertFalse((self.root/'missing').exists())
        for query in ({'limit': 101}, {'limit': True}, {'offset': -1}, {'offset': 129}):
            with self.assertRaisesRegex(ValueError, 'desktop_request_page_invalid'):
                self.catalog.pending_requests(**query)

    def test_hash_valid_payload_with_a_different_row_identity_is_unknown(self):
        self.prepare(0)
        identity = self.events[0]['event_id']
        changed = validate_event(self.store.get_event(identity))
        changed['event_id'] = 'synthetic-foreign-payload'
        digest = event_payload_hash(changed)
        with self.store._connect() as db:
            db.execute('UPDATE events SET payload=?,payload_hash=? WHERE event_id=?', (json.dumps(changed), digest, identity))
            db.execute('UPDATE desktop_status_requests SET payload_hash=?', (digest,))
        before = self.store.path.read_bytes()
        self.assertEqual(self.catalog.pending_requests()['state'], 'unknown')
        self.assertEqual(self.store.path.read_bytes(), before)
