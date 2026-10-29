"""Read-only human status binding for loaded synthetic event payloads."""
from copy import deepcopy
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.desktop import DesktopController
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class HandlingProjectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root/'data/live')
        self.store.enqueue(make_synthetic('listener'))
        self.events = self.store.list_events()
        self.event_id = self.events[0]['event_id']
        self.catalog = EventCatalog(self.root, 'live')

    def read(self, events=None):
        before = self.store.path.read_bytes()
        result = self.catalog.handling_states(self.events if events is None else events)
        self.assertEqual(self.store.path.read_bytes(), before)
        return result.get(self.event_id)

    def test_implicit_new_and_saved_decision_require_matching_payload_and_delivery(self):
        self.assertEqual(self.read(), 'new')
        self.catalog.set_status(self.event_id, 'handled', source='gui', operation_id='op-fixture')
        self.assertEqual(self.read(), 'handled')
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_changed_payload_delivery_and_duplicate_ids_stay_unknown(self):
        self.catalog.set_status(self.event_id, 'handled', source='gui')
        changed = deepcopy(self.events)
        changed[0]['evidence']['port'] += 1
        self.assertEqual(self.read(changed), 'unknown')
        changed = deepcopy(self.events)
        changed[0]['delivery_status'] = 'ack'
        self.assertEqual(self.read(changed), 'unknown')
        self.assertEqual(self.read(self.events*2), 'unknown')

    def test_missing_or_corrupt_current_event_never_supplies_old_human_state(self):
        self.catalog.set_status(self.event_id, 'handled', source='gui')
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("UPDATE events SET payload='{}' WHERE event_id=?", (self.event_id,))
        self.assertEqual(self.read(), 'unknown')
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('DELETE FROM events WHERE event_id=?', (self.event_id,))
        self.assertEqual(self.read(), 'unknown')

    def test_invalid_identity_does_not_hide_other_loaded_rows(self):
        malformed = [{'event_id': []}, {'event_id': None}, None]
        self.assertEqual(self.read(malformed+self.events), 'new')
        controller = DesktopController(self.root)
        with patch.object(controller.api, 'call', return_value={'event_list': {'events': malformed+self.events}}):
            value = controller.snapshot()
        self.assertEqual(value['events'][0]['handling_status'], 'unknown')
        self.assertEqual(value['events'][3]['handling_status'], 'new')

    def test_missing_database_is_not_created_and_input_bound_is_enforced(self):
        root = self.root/'not-created'
        self.assertEqual(EventCatalog(root, 'live').handling_states(self.events)[self.event_id], 'unknown')
        self.assertFalse(root.exists())
        with self.assertRaisesRegex(ValueError, 'handling_projection_limit'):
            self.catalog.handling_states(self.events*101)

    def test_controller_projection_does_not_mutate_saved_overview(self):
        self.catalog.set_status(self.event_id, 'read', source='gui')
        controller = DesktopController(self.root)
        overview = {'event_list': {'events': deepcopy(self.events), 'total': 1, 'truncated': False}}
        with patch.object(controller.api, 'call', return_value=overview):
            before = deepcopy(overview)
            value = controller.snapshot()
        self.assertEqual(value['events'][0]['handling_status'], 'read')
        self.assertEqual(value['events'][0]['delivery_status'], 'pending')
        self.assertEqual(overview, before)
