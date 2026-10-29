"""Real controller/SQLite ordering; activity completion is outside the write."""
import unittest
from unittest.mock import patch

import test_desktop_handling as fixture
from eventguard import activity
from eventguard.desktop import DesktopController
from eventguard.events.store import CapacityError, EventStore


class DesktopRequestControlTests(unittest.TestCase):
    setUp = fixture.DesktopHandlingTests.setUp

    def view(self):
        return self.catalog.detail(self.event_id)['pending_handling_requests']

    def test_intent_is_committed_before_operation_and_cleared_after_outer_receipt(self):
        original, seen = self.controller._set_status_bound, []
        def check(*args):
            seen.extend(self.view()['requests'])
            return original(*args)
        with patch.object(self.controller, '_set_status_bound', side_effect=check):
            result = self.controller.set_status_durable(self.event_id, 'handled', 'durable-first')
        self.assertEqual(seen[0]['operation_id'], 'durable-first')
        self.assertTrue(result['request_pending'])
        self.assertTrue(self.view()['requests'])
        self.assertFalse(self.controller.confirm_status_receipt(self.event_id, 'handled', 'durable-first')['request_pending'])
        self.assertEqual(self.view()['requests'], [])
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_activity_completion_failure_preserves_id_for_explicit_reopen_retry(self):
        with patch('eventguard.activity.complete', side_effect=activity.ActivityError('activity_storage_unavailable')):
            result = self.controller.set_status_durable(self.event_id, 'handled', 'uncertain-op')
        self.assertTrue(result['request_pending'])
        self.assertNotEqual(result.get('state'), 'event_status_updated')
        self.assertEqual(self.view()['requests'][0]['operation_id'], 'uncertain-op')
        self.catalog.set_status(self.event_id, 'read', source='cli', operation_id='later-decision')
        reopened = DesktopController(self.root)
        result = reopened.set_status_durable(self.event_id, 'handled', 'uncertain-op')
        self.assertEqual(result['status'], 'read')
        self.assertTrue(result['history_replayed'])
        self.assertTrue(result['request_pending'])
        reopened.confirm_status_receipt(self.event_id, 'handled', 'uncertain-op')
        self.assertEqual(self.view()['requests'], [])
        self.assertEqual(len(self.catalog.detail(self.event_id)['handling_history']['entries']), 2)

    def test_resolution_failure_is_uncertain_and_prepare_failure_never_dispatches(self):
        with patch.object(EventStore, '_prepare_desktop_request', side_effect=CapacityError('synthetic capacity')), patch.object(
                self.controller, '_set_status_bound', side_effect=AssertionError('no dispatch')):
            result = self.controller.set_status_durable(self.event_id, 'handled', 'prepare-fail')
        self.assertFalse(result['operation_started'])
        self.assertEqual(self.view()['requests'], [])
        self.controller.set_status_durable(self.event_id, 'handled', 'finish-fail')
        with patch.object(EventStore, '_complete_desktop_request', side_effect=OSError('synthetic fs error')):
            result = self.controller.confirm_status_receipt(self.event_id, 'handled', 'finish-fail')
        self.assertEqual(result['reason'], 'desktop_request_completion_unconfirmed')
        self.assertTrue(result['request_pending'])
        self.assertEqual(self.view()['requests'][0]['operation_id'], 'finish-fail')
        self.assertFalse(self.controller.confirm_status_receipt(self.event_id, 'handled', 'finish-fail')['request_pending'])

    def test_lost_success_reply_keeps_id_until_new_consumer_explicitly_confirms(self):
        self.controller.set_status_durable(self.event_id, 'handled', 'reply-lost-after-success')
        reopened = DesktopController(self.root)
        with patch.object(reopened, '_set_status_bound', side_effect=AssertionError('read never dispatches')):
            self.assertEqual(reopened.inspect(self.event_id)['pending_handling_requests']['requests'][0]['operation_id'],
                             'reply-lost-after-success')
        before = self.store.path.read_bytes()
        wrong = reopened.confirm_status_receipt(self.event_id, 'ignored', 'reply-lost-after-success')
        self.assertTrue(wrong['request_pending'])
        self.assertEqual(self.store.path.read_bytes(), before)
        self.catalog.set_status(self.event_id, 'read', source='cli', operation_id='later-decision')
        result = reopened.set_status_durable(self.event_id, 'handled', 'reply-lost-after-success')
        self.assertEqual(result['status'], 'read')
        reopened.confirm_status_receipt(self.event_id, 'handled', 'reply-lost-after-success')
        self.assertEqual(self.view()['requests'], [])
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))
