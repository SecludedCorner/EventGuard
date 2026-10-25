"""Finite synthetic harness contracts; no model, network or native collection."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from eventguard.acceptance_control import read_json
from eventguard import soak
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

    def test_guardian_start_write_fault_requests_stop_before_grace_and_preserves_data(self):
        with tempfile.TemporaryDirectory(dir=soak.PROJECT/"reports") as directory:
            root = Path(directory)/"run"
            sequence = []
            original_write = soak.write_json
            child = Mock(pid=12345, created_at="2026-10-26T00:00:00+00:00")
            child.poll.return_value = None
            def spawn_owned(arguments):
                sequence.append("spawn")
                original_write(root/"pending-proof.json", {"event_id": "synthetic-pending", "hash": "preserve"})
                return child
            def write(path, value):
                if path.name == "guardian-start.json":
                    sequence.append("start_write_failed")
                    raise OSError("private exception must be omitted")
                if path.name == "stop.request":
                    sequence.append("stop_requested")
                original_write(path, value)
            def finish_owned(observed, reason, *, grace, request_stop):
                self.assertIs(observed, child)
                self.assertTrue((root/"stop.request").exists())
                self.assertGreater(grace, 0)
                sequence.append("finish")
                return {"managed": True, "child_exited": True, "exit_code": 2,
                    "remaining_owned_processes": 0, "forcibly_terminated": False, "reason": "natural_exit"}
            with patch.object(soak, "spawn", side_effect=spawn_owned), \
                    patch.object(soak, "write_json", side_effect=write), \
                    patch.object(soak, "finish", side_effect=finish_owned):
                self.assertEqual(soak.main(["--root", str(root)]), 2)
            self.assertEqual(sequence, ["spawn", "start_write_failed", "stop_requested", "finish"])
            receipt = read_json(root/"guardian-exit.json")
            self.assertTrue(receipt["guardian_operation_failed"])
            self.assertEqual(receipt["cooperative_stop"]["state"], "requested")
            self.assertEqual(read_json(root/"pending-proof.json"),
                             {"event_id": "synthetic-pending", "hash": "preserve"})

    def test_stop_write_failure_stays_explicit_and_cleanup_uses_only_original_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root/"pending.txt"
            marker.write_text("preserved", encoding="utf-8")
            child = Mock(pid=12345, created_at="2026-10-26T00:00:00+00:00")
            child.poll.return_value = None
            sequence = []
            def failed_write(path, value):
                self.assertEqual(path, root/"stop.request")
                sequence.append("stop_write_failed")
                raise OSError("private failure sentinel")
            def finish_owned(observed, reason, *, grace, request_stop):
                self.assertIs(observed, child)
                self.assertGreater(grace, 0)
                sequence.append("finish")
                return {"child_exited": True, "exit_code": 1460, "remaining_owned_processes": 0,
                        "forcibly_terminated": True, "reason": "owner_exception"}
            with patch.object(soak, "write_json", side_effect=failed_write), \
                    patch.object(soak, "finish", side_effect=finish_owned):
                receipt = soak._shutdown_owned(child, root, "owner_exception")
            self.assertEqual(sequence, ["stop_write_failed", "finish"])
            self.assertIn("cooperative_stop_persist_failed", receipt["cleanup_errors"])
            self.assertEqual(receipt["cooperative_stop"]["state"], "unconfirmed")
            self.assertTrue(receipt["forcibly_terminated"])
            self.assertNotIn("private failure sentinel", json.dumps(receipt))
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserved")

    def test_explicit_minimum_and_pacing_leave_idle_window_and_preserve_workload(self):
        class Clock:
            value = 0.0
            def now(self):
                return self.value
            def sleep(self, seconds):
                self.value += max(seconds, .000001)
        clock = Clock()
        metrics = {"cpu_seconds": 1.0, "private_bytes": 100, "working_set_bytes": 200,
                   "handles": 4, "status": "measured", "error_codes": []}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/"exercise"
            with patch.object(soak.time, "monotonic", side_effect=clock.now), \
                    patch.object(soak.time, "sleep", side_effect=clock.sleep), \
                    patch.object(soak, "_self_resources", return_value=metrics):
                result = exercise(root, options(duration_seconds=3, max_events=4,
                    min_wall_seconds=1, pacing_seconds=.1))
            self.assertTrue(result["passed"], result)
            self.assertGreaterEqual(result["elapsed_seconds"], 1)
            self.assertEqual(result["unique_ack_count"], 4)
            samples = [json.loads(line) for line in (root/"resource-samples.jsonl").read_text().splitlines()]
            self.assertEqual({row["phase"] for row in samples}, {"idle_before", "work", "idle_after"})
            self.assertGreaterEqual(result["resource_sampling"]["phase_windows"][-1]["ended_elapsed_seconds"], 1)
            self.assertGreaterEqual(clock.value, 1)

    def test_unavailable_self_resources_remain_null_without_private_exception_text(self):
        with patch.object(soak, "_self_api", side_effect=OSError("private failure sentinel")):
            sample = soak._self_resources()
        self.assertEqual(sample["status"], "unknown")
        for field in soak.RESOURCE_FIELDS:
            self.assertIsNone(sample[field])
        self.assertNotIn("private failure sentinel", json.dumps(sample))

    def test_idle_wait_uses_bounded_chunks_and_stop_preserves_completed_work(self):
        class Clock:
            value = 0.0
            chunks = None
            def __init__(self):
                self.chunks = []
            def now(self):
                return self.value
            def sleep(self, seconds):
                self.chunks.append(seconds)
                self.value += max(seconds, .000001)
        clock = Clock()
        unknown = {**{field: None for field in soak.RESOURCE_FIELDS},
                   "status": "unknown", "error_codes": ["synthetic_resource_unavailable"]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/"exercise"
            with patch.object(soak.time, "monotonic", side_effect=clock.now), \
                    patch.object(soak.time, "sleep", side_effect=clock.sleep), \
                    patch.object(soak, "_self_resources", return_value=unknown):
                result = exercise(root, options(duration_seconds=5, max_events=4, min_wall_seconds=2),
                    stop_requested=lambda: clock.value >= .2)
            self.assertFalse(result["passed"])
            self.assertEqual(result["reason"], "soak_cooperative_stop_requested")
            self.assertLessEqual(max(clock.chunks), .25)
            self.assertGreaterEqual(max(clock.chunks), .249)
            self.assertLessEqual(len(clock.chunks), 2, "idle control need not wake at 20 Hz")
            self.assertLessEqual(clock.value-.2, .25)
            self.assertEqual(result["accepted_count"], 4)
            self.assertEqual(result["unique_ack_count"], 4)
            progress = read_json(root/"progress.json")
            self.assertEqual(len(progress["accepted"]), len(progress["acknowledgments"]))
            self.assertEqual(len(read_json(root/"producer-manifest.json")["events"]), 4)

    def test_resource_jsonl_byte_bound_is_explicit_and_minimum_cannot_exceed_deadline(self):
        unknown = {**{field: None for field in soak.RESOURCE_FIELDS}, "status": "unknown", "error_codes": []}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(soak, "RESOURCE_MAX_BYTES", 64), \
                patch.object(soak, "_self_resources", return_value=unknown):
            root = Path(directory)
            samples = soak._ResourceLog(root, 0, options())
            samples.record("idle_before", force=True)
            self.assertTrue(samples.status()["truncated"])
            self.assertLessEqual(samples.path.stat().st_size, 64)
        for supplied in ({"duration_seconds": 3, "min_wall_seconds": 3},
                         {"min_wall_seconds": True}, {"pacing_seconds": float("nan")},
                         {"duration_seconds": 2, "max_events": 4, "pacing_seconds": 1}):
            with self.subTest(supplied=supplied), self.assertRaises(SoakError):
                options(**supplied)
