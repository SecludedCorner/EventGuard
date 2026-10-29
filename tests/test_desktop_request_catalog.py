"""Real RO Catalog snapshot binds pending intent to namespace and event hash."""
from contextlib import closing
import unittest

import test_desktop_requests as fixture
from eventguard.events.catalog import EventCatalog


class DesktopRequestCatalogTests(unittest.TestCase):
    setUp = fixture.DesktopRequestTests.setUp
    connect = fixture.DesktopRequestTests.connect

    def detail(self):
        return EventCatalog(self.store.directory.parent, 'test', directory=self.store.directory).detail(self.value['event_id'])

    def test_missing_then_saved_journal_is_read_only_and_never_dispatches(self):
        before = self.store.path.read_bytes()
        self.assertEqual(self.detail()['pending_handling_requests']['requests'], [])
        self.assertEqual(self.store.path.read_bytes(), before)
        self.store._prepare_desktop_request(self.value, namespace='test')
        before = self.store.path.read_bytes()
        view = self.detail()['pending_handling_requests']
        self.assertEqual(view['state'], 'available')
        self.assertEqual(view['requests'], [self.value])
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_foreign_namespace_and_changed_payload_binding_are_unknown_without_reset(self):
        self.store._prepare_desktop_request(self.value, namespace='test')
        for field, value in (('namespace', 'live'), ('payload_hash', '0'*64)):
            with closing(self.connect()) as db:
                db.execute('UPDATE desktop_status_requests SET '+field+'=?', (value,))
                db.commit()
            before = self.store.path.read_bytes()
            self.assertEqual(self.detail()['pending_handling_requests']['state'], 'unknown')
            self.assertEqual(self.store.path.read_bytes(), before)
            with closing(self.connect()) as db:
                db.execute('UPDATE desktop_status_requests SET '+field+'=?', (self.value[field],))
                db.commit()

    def test_store_refuses_namespace_mismatch_before_opening_transaction(self):
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'desktop_request_namespace_mismatch'):
            self.store._prepare_desktop_request(self.value, namespace='live')
        self.assertEqual(self.store.path.read_bytes(), before)
