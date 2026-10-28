"""Pure synthetic history contracts; no event, DB, collector or model writes."""
import math
import unittest

from eventguard.events.disposition_history import MAX_HISTORY_ENTRIES, MAX_HISTORY_PER_EVENT, has_capacity, validate_record


class DispositionHistoryContractTests(unittest.TestCase):
    def setUp(self):
        self.record = {"event_id": "evt-synthetic", "operation_id": "op-synthetic", "previous_status": "new",
                       "status": "handled", "source": "gui", "at": 1000}

    def test_valid_record_is_copied_and_source_is_not_user_identity(self):
        result = validate_record(self.record)
        self.assertEqual(result, self.record)
        self.assertIsNot(result, self.record)
        self.assertNotIn("actor", result)
        self.assertNotIn("ack", result)

    def test_noop_and_invalid_states_are_not_transitions(self):
        for change in ({"status": "new"}, {"status": "safe"}, {"previous_status": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_record({**self.record, **change})

    def test_untrusted_identifiers_and_unexpected_fields_are_rejected(self):
        for change in ({"event_id": "../secret"}, {"operation_id": "x" * 129},
                       {"source": "administrator"}, {"private_message": "not allowed"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_record({**self.record, **change})

    def test_time_is_finite_bounded_and_not_boolean(self):
        for value in (True, -1, math.inf, math.nan, 253402300800, "1000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_record({**self.record, "at": value})

    def test_capacity_never_goes_unbounded_or_treats_bad_counts_as_empty(self):
        self.assertTrue(has_capacity(0, 0))
        self.assertTrue(has_capacity(MAX_HISTORY_ENTRIES - 1, MAX_HISTORY_PER_EVENT - 1))
        self.assertFalse(has_capacity(MAX_HISTORY_ENTRIES, 0))
        self.assertFalse(has_capacity(MAX_HISTORY_PER_EVENT, MAX_HISTORY_PER_EVENT))
        for total, per_event in ((True, 0), (-1, 0), (0, 1), (1, -1)):
            with self.subTest(total=total, per_event=per_event), self.assertRaises(ValueError):
                has_capacity(total, per_event)


if __name__ == "__main__":
    unittest.main()
