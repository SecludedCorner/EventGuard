"""Synthetic revision contracts; no persistence or previous-version invention."""
from copy import deepcopy
import unittest

from eventguard.events.investigation import build, diagnostic_summary, project
from eventguard.events.investigation_revision import (
    MAX_REVISIONS, MAX_REVISIONS_PER_EVENT, encode_case, has_revision_capacity,
    make_revision, validate_revision,
)
from eventguard.synthetic import make_synthetic


class InvestigationRevisionTests(unittest.TestCase):
    def setUp(self):
        self.event = make_synthetic("listener")
        self.event["event_id"] = "evt-revision-fixture"
        anchor = project(self.event, "listeners")
        self.case = build(anchor, [], as_of=self.event["observed_at"])

    def test_saved_case_is_bound_and_revalidates(self):
        value = make_revision(self.case, self.event, saved_at=1.25)
        self.assertEqual(validate_revision(value, self.event), value)
        self.assertEqual(value["event_id"], self.event["event_id"])
        self.assertEqual(value["payload_hash"], self.case["anchor_payload_hash"])
        self.assertEqual(value["case"], self.case)

    def test_diagnostic_schema_is_compatible_without_inventing_history(self):
        anchor = project(self.event, "listeners")
        case = build(anchor, [], as_of=self.event["observed_at"], diagnosis=diagnostic_summary(None))
        self.assertEqual(case["schema_version"], "1.1")
        value = make_revision(case, self.event, saved_at=1.25)
        self.assertEqual(validate_revision(value, self.event)["case"], case)
        self.assertIn("diagnostic_not_saved", [gap["reason"] for gap in case["gaps"]])

    def test_bad_identity_hash_or_body_never_passes(self):
        value = make_revision(self.case, self.event, saved_at=1.25)
        for field, replacement in (("event_id", "evt-other"), ("payload_hash", "0" * 64),
                                   ("case_hash", "0" * 64), ("schema_version", "2.0"),
                                   ("saved_at", float("nan"))):
            with self.subTest(field=field), self.assertRaises(ValueError):
                altered = deepcopy(value)
                altered[field] = replacement
                validate_revision(altered, self.event)
        altered = deepcopy(value)
        altered["case"]["incident_conclusion"] = "safe"
        with self.assertRaises(ValueError):
            validate_revision(altered, self.event)
        other = deepcopy(self.event)
        other["event_id"] = "evt-other"
        with self.assertRaises(ValueError):
            validate_revision(value, other)

    def test_bounded_capacity_and_case_size(self):
        self.assertTrue(has_revision_capacity(15, 15))
        self.assertFalse(has_revision_capacity(MAX_REVISIONS_PER_EVENT, MAX_REVISIONS_PER_EVENT))
        self.assertFalse(has_revision_capacity(MAX_REVISIONS, 0))
        for total, per_event in ((-1, 0), (1, 2), (True, 0)):
            with self.subTest(total=total, per_event=per_event), self.assertRaises(ValueError):
                has_revision_capacity(total, per_event)
        with self.assertRaisesRegex(ValueError, "case_limit"):
            encode_case({"value": "x" * 65536})

    def test_synthetic_saved_times_are_not_guessed(self):
        for invalid in (None, True, -1, float("inf"), 253402300800):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                make_revision(self.case, self.event, saved_at=invalid)
