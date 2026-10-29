"""Catalog-backed retry projection; malformed views never become empty/safe."""
import copy
import unittest
from unittest.mock import patch

import test_desktop_handling as fixture
from eventguard.gui_requests import recover


class GuiRequestTests(unittest.TestCase):
    setUp = fixture.DesktopHandlingTests.setUp

    def document(self):
        return self.catalog.detail(self.event_id)

    def test_real_catalog_empty_and_uncertain_views_are_inert(self):
        self.assertEqual(recover(self.document()), {})
        from eventguard import activity
        with patch('eventguard.activity.complete', side_effect=activity.ActivityError('activity_storage_unavailable')):
            self.controller.set_status_durable(self.event_id, 'handled', 'saved-uncertain')
        before = self.store.path.read_bytes()
        self.assertEqual(recover(self.document()), {(self.event_id, 'handled'): 'saved-uncertain'})
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_wrong_identity_namespace_hash_shape_and_duplicate_id_are_unknown(self):
        from eventguard import activity
        with patch('eventguard.activity.complete', side_effect=activity.ActivityError('activity_storage_unavailable')):
            self.controller.set_status_durable(self.event_id, 'handled', 'uncertain-op')
        original = self.document()
        for key, bad in (('event_id', 'different'), ('namespace', 'test'), ('payload_hash', '0'*64),
                         ('state', 'unknown'), ('requests', None), ('requests', [None])):
            value = copy.deepcopy(original)
            value['pending_handling_requests'][key] = bad
            self.assertIsNone(recover(value), key)
        value = copy.deepcopy(original)
        value['pending_handling_requests']['requests'] *= 2
        self.assertIsNone(recover(value))
        for value in ({}, None, {'event': None}):
            self.assertIsNone(recover(value))
