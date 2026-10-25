"""Finite synthetic harness contracts; no model, network or native collection."""
import tempfile
from pathlib import Path
import unittest

from eventguard.acceptance_control import read_json
from eventguard.soak import SoakError, exercise, options, verify_sets


class SoakTests(unittest.TestCase):
    def test_missing_hash_changed_and_duplicate_ack_never_pass_conservation(self):
        hashes = {"one": "a", "two": "b"}
        ack = {"event_id": "one", "payload_hash": "a", "query_id": "q", "result_id": "r",
               "receipt": {"ack_type": "receiver_persisted", "event_id": "one", "receiver_receipt_id": "r"}}
        self.assertTrue(verify_sets(hashes, ["one", "two"], [ack], {"two": "b"})["passed"])
        for accepted, receipts, pending in ((["one", "two"], [ack], {}),
                (["one", "two"], [ack], {"two": "changed"}),
                (["one"], [ack, ack], {})):
            with self.subTest(accepted=accepted, pending=pending):
                self.assertFalse(verify_sets(hashes, accepted, receipts, pending)["passed"])

    def test_finite_exercise_recovers_same_producer_and_query_without_losing_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/"new-exercise"
            result = exercise(root, options(duration_seconds=20, max_events=12))
            self.assertTrue(result["passed"], result)
            self.assertEqual((result["accepted_count"], result["unique_ack_count"]), (12, 12))
            self.assertEqual(result["outbox"]["pending"], 0)
            self.assertEqual(result["completion_fault_count"], 1)
            progress = read_json(root/"progress.json")
            self.assertTrue(progress["recovery"]["same_query_after_restart"])
            self.assertTrue(progress["recovery"]["pinned_receipt_maintained"])
            self.assertIn(progress["rejected"][0]["event_id"], progress["accepted"])
            self.assertEqual(progress["backpressure"]["pending_before"], progress["backpressure"]["pending_after"])
            self.assertEqual(progress["readmission"]["original_payload_hash"],
                             progress["readmission"]["recovered_payload_hash"])
            self.assertTrue(result["synthetic_harness"])
            self.assertEqual(result["model_calls"], 0)
            self.assertFalse(result["twenty_four_hour_proof"])

    def test_existing_directory_refused_and_bounds_cannot_disable_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root/"preserve.txt"
            marker.write_text("original", encoding="utf-8")
            with self.assertRaisesRegex(SoakError, "existing_soak_directory_refused"):
                exercise(root, options())
            self.assertEqual(marker.read_text(encoding="utf-8"), "original")
        for supplied in ({"duration_seconds": 0}, {"duration_seconds": float("inf")},
                         {"max_events": True}, {"max_events": 0}, {"max_report_bytes": 0}):
            with self.subTest(supplied=supplied), self.assertRaises(SoakError):
                options(**supplied)
