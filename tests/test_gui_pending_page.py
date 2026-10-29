"""Actual controller/worker reply contract; malformed pages never mean zero."""
import copy
import unittest

import test_desktop_pending_control as fixture
from eventguard.gui import ControllerWorker
from eventguard.gui_pending import page


class GuiPendingPageTests(unittest.TestCase):
    setUp = fixture.DesktopPendingControlTests.setUp

    def reply(self):
        worker = ControllerWorker(self.controller)
        try:
            worker.submit('pending_requests', 0)
            return worker.results.get(timeout=4)[1]
        finally:
            worker.shutdown(wait=True)

    def test_real_worker_page_has_old_anchor_and_is_read_only(self):
        before = self.store.path.read_bytes()
        result = page(self.reply(), namespace='live', offset=0)
        self.assertEqual(result['events'][0]['event_id'], self.anchor)
        self.assertEqual(result['total'], 1)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_wrong_context_counts_identity_and_duplicate_rows_are_unknown(self):
        original = self.reply()
        for key, bad in (('state', 'unknown'), ('namespace', 'test'), ('offset', 100), ('requested_offset', 100),
                         ('limit', 101), ('total', True), ('total', 129), ('request_total', 0), ('has_more', True),
                         ('events', []), ('events', [None]), ('ack_performed', True)):
            value = copy.deepcopy(original)
            value[key] = bad
            self.assertIsNone(page(value, namespace='live', offset=0), key)
        for key, bad in (('event_id', 'different'), ('payload_hash', 'invalid'), ('pending_request_count', True),
                         ('handling_status', 'ignored'), ('status', 'safe')):
            value = copy.deepcopy(original)
            value['events'][0][key] = bad
            self.assertIsNone(page(value, namespace='live', offset=0), key)
        value = copy.deepcopy(original)
        value.update(total=2, request_total=2, events=value['events']*2)
        self.assertIsNone(page(value, namespace='live', offset=0))
