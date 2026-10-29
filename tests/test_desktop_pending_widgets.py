"""Real Tk + 101 synthetic SQLite events; hidden requests remain reachable."""
import threading
import unittest
from unittest.mock import patch

import test_desktop_pending_control as data
import test_desktop_investigation_widgets as ui_fixture
from eventguard.gui import EventGuardWindow
from eventguard.gui_presenter import SEVERITY_FILTERS, DELIVERY_FILTERS, HANDLING_FILTERS
from eventguard.events.store import event_payload_hash
from eventguard.events.schema import validate_event


class DesktopPendingWidgetTests(unittest.TestCase):
    wait_for = ui_fixture.DesktopInvestigationWidgetTests.wait_for
    close_ui = ui_fixture.DesktopInvestigationWidgetTests.close_ui
    select = ui_fixture.DesktopInvestigationWidgetTests.select

    def setUp(self):
        data.DesktopPendingControlTests.setUp(self)
        import tkinter as tk
        self.controller.set_status_durable(self.anchor, 'handled', self.intent['operation_id'])
        self.window = tk.Tk()
        self.window.withdraw()
        self.addCleanup(self.window.destroy)
        self.ui = EventGuardWindow(self.window, self.controller, refresh_ms=60000)
        self.addCleanup(self.close_ui)
        self.wait_for(lambda: len(self.ui.events.get_children()) == 100 and self.ui.pending_button.instate(['!disabled']))

    def open_page(self):
        self.ui.pending_button.invoke()
        self.wait_for(lambda: self.ui._pending_page is not None and self.ui.pending_button.instate(['!disabled']))

    def test_hidden_anchor_original_key_explicit_retry_refresh_and_filtered_return(self):
        recent = self.store.list_events(limit=100)[0]
        for variable, choices, selected in ((self.ui.severity_filter, SEVERITY_FILTERS, recent['severity']),
                (self.ui.delivery_filter, DELIVERY_FILTERS, 'pending'), (self.ui.handling_filter, HANDLING_FILTERS, 'new')):
            variable.set(next(label for label, value in choices.items() if value == selected))
        self.ui.filter_events()
        self.select(recent['event_id'])
        filters = tuple(v.get() for v in (self.ui.severity_filter, self.ui.delivery_filter, self.ui.handling_filter))
        before = self.store.path.read_bytes()
        with patch.object(self.controller, 'set_status_durable', wraps=self.controller.set_status_durable) as save:
            self.open_page()
            self.assertEqual(self.ui.events.get_children(), (self.anchor,))
            self.select(self.anchor)
            self.assertEqual(self.ui._pending_status[(self.anchor, 'handled')], self.intent['operation_id'])
            self.assertEqual(save.call_count, 0)
            self.assertEqual(self.store.path.read_bytes(), before)
            self.ui._apply_snapshot(self.controller.snapshot())
            self.assertTrue(self.ui.events.exists(self.anchor))
            self.controller.set_status(self.anchor, 'read', 'later-pending-view-decision')
            self.ui.handling_buttons['handled'].invoke()
            self.wait_for(lambda: '人工狀態已核對' in self.ui.message.get())
            self.wait_for(lambda: self.ui.pending_button.instate(['!disabled']) and self.ui._detail_document.get('status') == 'read')
            self.assertEqual(save.call_args.args[2], self.intent['operation_id'])
            self.assertEqual(save.call_count, 1)
        self.assertEqual(len(self.controller.inspect(self.anchor)['handling_history']['entries']), 2)
        self.ui.refresh_button.invoke()
        self.wait_for(lambda: self.ui._pending_page is not None and self.ui._pending_page['total'] == 0)
        self.assertEqual(self.ui.events.get_children(), ())
        self.ui.pending_back.invoke()
        self.wait_for(lambda: not self.ui.worker.pending and self.ui._detail_document.get('event', {}).get('event_id') == recent['event_id'])
        self.assertEqual(tuple(v.get() for v in (self.ui.severity_filter, self.ui.delivery_filter, self.ui.handling_filter)), filters)
        self.assertEqual(self.ui.events.selection(), (recent['event_id'],))
        self.assertEqual(self.ui.events.focus(), recent['event_id'])
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (101, 0))

    def prepare_all_pending(self):
        for event in self.store.list_events(limit=100):
            value = {'namespace': 'live', 'event_id': event['event_id'], 'status': 'handled',
                     'operation_id': 'page-'+event['event_id'], 'payload_hash': event_payload_hash(validate_event(event))}
            self.store._prepare_desktop_request(value, namespace='live')

    def test_actual_next_previous_buttons_cover_101_pending_anchors(self):
        self.prepare_all_pending()
        before = self.store.path.read_bytes()
        self.open_page()
        first = set(self.ui.events.get_children())
        self.assertEqual(len(first), 100)
        self.ui.pending_next.invoke()
        self.wait_for(lambda: self.ui._pending_offset == 100 and self.ui._pending_page is not None and self.ui.pending_previous.instate(['!disabled']))
        second = set(self.ui.events.get_children())
        self.assertEqual(len(second), 1)
        self.assertFalse(first & second)
        self.assertEqual(len(first | second), 101)
        self.assertTrue(self.ui.pending_next.instate(['disabled']))
        self.ui.pending_previous.invoke()
        self.wait_for(lambda: self.ui._pending_offset == 0 and self.ui._pending_page is not None)
        self.assertEqual(set(self.ui.events.get_children()), first)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_wrong_context_page_is_unknown_not_empty_and_explicit_retry_recovers(self):
        original = self.controller.pending_requests
        def wrong(offset=0):
            result = original(offset)
            result[fault] = 'test' if fault == 'namespace' else 100
            return result
        before = self.store.path.read_bytes()
        for fault in ('namespace', 'offset'):
            with patch.object(self.controller, 'pending_requests', side_effect=wrong), patch.object(
                    self.controller, 'set_status_durable', side_effect=AssertionError('no automatic replay')):
                self.ui.pending_button.invoke()
                self.wait_for(lambda: self.ui._pending_expected is None and self.ui.pending_button.instate(['!disabled']))
                self.assertIsNone(self.ui._pending_page)
                self.assertEqual(self.ui.events.get_children(), ())
                self.assertIn('未知', self.ui.events_note.get())
                self.assertTrue(all(b.instate(['disabled']) for b in self.ui.handling_buttons.values()))
                self.assertTrue(self.ui.pending_next.instate(['disabled']))
            self.open_page()
            self.assertEqual(self.ui.events.get_children(), (self.anchor,))
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_snapshot_read_does_not_eat_a_pending_refresh_click(self):
        self.open_page()
        entered, release = threading.Event(), threading.Event()
        original = self.controller.snapshot
        def slow():
            entered.set()
            release.wait(timeout=2)
            return original()
        with patch.object(self.controller, 'snapshot', side_effect=slow):
            try:
                self.wait_for(lambda: not self.ui.worker.pending)
                self.ui._request('snapshot')
                self.wait_for(lambda: entered.is_set() and self.ui.refresh_button.instate(['disabled']))
                self.assertEqual(self.ui.events.get_children(), (self.anchor,))
                release.set()
                self.wait_for(lambda: self.ui.refresh_button.instate(['!disabled']))
            finally:
                release.set()

    def test_last_page_can_become_empty_after_confirmation_then_return_to_previous(self):
        self.prepare_all_pending()
        self.open_page()
        self.wait_for(lambda: self.ui.pending_next.instate(['!disabled']))
        self.ui.pending_next.invoke()
        self.wait_for(lambda: self.ui._pending_offset == 100 and self.ui._pending_page is not None and self.ui.pending_button.instate(['!disabled']))
        identity = self.ui.events.get_children()[0]
        self.select(identity)
        original = self.ui._pending_status[(identity, 'handled')]
        with patch.object(self.controller, 'set_status_durable', wraps=self.controller.set_status_durable) as save:
            self.ui.handling_buttons['handled'].invoke()
            self.wait_for(lambda: '人工狀態已核對' in self.ui.message.get() and self.ui.pending_button.instate(['!disabled']))
            self.assertEqual(save.call_args.args[2], original)
        self.ui.refresh_button.invoke()
        self.wait_for(lambda: self.ui._pending_page is not None and self.ui._pending_page['total'] == 100 and self.ui.pending_previous.instate(['!disabled']))
        self.assertEqual(self.ui.events.get_children(), ())
        self.assertIn('本頁無事件', self.ui.events_note.get())
        self.ui.pending_previous.invoke()
        self.wait_for(lambda: self.ui._pending_offset == 0 and self.ui._pending_page is not None)
        self.assertEqual(len(self.ui.events.get_children()), 100)
        self.assertFalse(self.ui.events.exists(identity))
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (101, 0))

    def test_return_during_read_discards_late_page_without_automatic_state_calls(self):
        recent = self.store.list_events(limit=100)[0]['event_id']
        self.select(recent)
        entered, release = threading.Event(), threading.Event()
        original = self.controller.pending_requests
        def slow(offset=0):
            entered.set()
            release.wait(timeout=2)
            return original(offset)
        before = self.store.path.read_bytes()
        with patch.object(self.controller, 'pending_requests', side_effect=slow), patch.object(
                self.controller, 'set_status_durable', side_effect=AssertionError('no automatic replay')):
            try:
                self.ui.pending_button.invoke()
                self.wait_for(lambda: entered.is_set() and self.ui.pending_back.instate(['!disabled']))
                self.ui.pending_back.invoke()
                release.set()
                self.wait_for(lambda: not self.ui.worker.pending and self.ui._detail_document.get('event', {}).get('event_id') == recent)
            finally:
                release.set()
        self.assertFalse(self.ui._pending_mode)
        self.assertFalse(self.ui.events.exists(self.anchor))
        self.assertEqual(self.ui.events.selection(), (recent,))
        self.assertEqual(self.store.path.read_bytes(), before)
