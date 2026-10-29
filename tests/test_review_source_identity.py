"""Saved diagnosis must bind the current source inside its write transaction."""
import json
import unittest

from eventguard.diagnostics.review import review
from eventguard.events.schema import validate_event
from eventguard.events.store import StoreError, event_payload_hash
import test_investigation_diagnostics as fixture
from test_investigation_diagnostics import FixtureAPI, NOW


class ReviewSourceIdentityTests(unittest.TestCase):
    setUp = fixture.InvestigationDiagnosticTests.setUp

    def result(self, event=None):
        return dict(review(self.event if event is None else event, FixtureAPI(),
                           refresh=True, now=NOW), namespace='test')

    def corrupt(self, *, replace_hash=False):
        event = validate_event(self.event)
        event['event_id'] = 'foreign-payload-id'
        digest = event_payload_hash(event) if replace_hash else event_payload_hash(validate_event(self.event))
        with self.store._connect() as db:
            db.execute('UPDATE events SET payload=?,payload_hash=? WHERE event_id=?',
                       (json.dumps(event), digest, 'evt-anchor'))
        return event

    def assert_save_refused(self, result):
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(StoreError, 'stored_event_identity_mismatch'):
            self.store.save_review('evt-anchor', result['payload_hash'], result)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_payload_changed_after_review_read_refuses_before_table_creation(self):
        result = self.result()
        self.corrupt()
        self.assert_save_refused(result)

    def test_valid_foreign_payload_and_hash_cannot_receive_anchor_review(self):
        foreign = self.corrupt(replace_hash=True)
        self.assert_save_refused(self.result(foreign))

    def test_existing_saved_review_survives_corrupt_source_overwrite_attempt(self):
        result = self.result()
        self.store.save_review('evt-anchor', result['payload_hash'], result)
        self.corrupt()
        self.assert_save_refused(result)

    def test_catalog_never_returns_foreign_event_as_requested_anchor(self):
        self.corrupt(replace_hash=True)
        before = self.store.path.read_bytes()
        for action in (lambda: self.catalog.detail('evt-anchor'), self.catalog.list,
                       lambda: self.catalog.investigate('evt-anchor', now=NOW)):
            with self.subTest(action=action):
                with self.assertRaisesRegex(StoreError, 'stored_event_identity_mismatch'):
                    action()
        self.assertEqual(self.store.path.read_bytes(), before)
