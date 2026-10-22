"""Pure JSON proof validation; no processes, SDK, model, files or native query."""
from copy import deepcopy
import unittest

from eventguard.capture_receipt import validate_receipt


TOKEN = "a" * 32
CREATED = "2026-10-23T01:02:03.123456+00:00"


def fixture():
    started = {"attempt_id": TOKEN, "codex_pid": 1234, "created_at": CREATED}
    receipt = {"attempt_id": TOKEN, "codex_pid": 1234, "codex_exit_code": 0,
               "capture_complete": True, "child_exited": True,
               "stdout_truncated": False, "stderr_truncated": False,
               "forcibly_terminated": False, "stop_reason": "descendants_remaining",
               "process": {"managed": True, "pid": 1234, "created_at": CREATED,
                           "child_exited": True, "exit_code": 0, "remaining_owned_processes": 0,
                           "forcibly_terminated": False, "reason": "natural_exit",
                           "shutdown_requested_reason": "descendants_remaining"}}
    return receipt, started


class CaptureReceiptTests(unittest.TestCase):
    def test_exact_writer_schema_proves_exit_and_natural_success(self):
        receipt, started = fixture()
        self.assertEqual(validate_receipt(receipt, started, TOKEN), [])
        self.assertEqual(validate_receipt(receipt, started, TOKEN, require_success=True), [])

    def test_preflight_counterexample_cannot_be_promoted_to_child_exited(self):
        receipt, started = fixture()
        receipt.update(child_exited=False, capture_complete=True)
        receipt["process"]["remaining_owned_processes"] = 7
        for success in (False, True):
            errors = validate_receipt(receipt, started, TOKEN, require_success=success)
            self.assertIn("owned_child_exit_unconfirmed", errors)
            self.assertIn("owned_tree_exit_unconfirmed", errors)

    def test_known_nonzero_exit_is_terminal_but_not_success(self):
        for code in (-9, 1, 7, 1460, 0xFFFFFFFF):
            with self.subTest(code=code):
                receipt, started = fixture()
                receipt["codex_exit_code"] = receipt["process"]["exit_code"] = code
                self.assertEqual(validate_receipt(receipt, started, TOKEN), [])
                self.assertIn("cli_not_completed_successfully", validate_receipt(receipt, started, TOKEN, require_success=True))

    def test_known_forced_exit_releases_gate_without_passing_delivery(self):
        receipt, started = fixture()
        receipt.update(forcibly_terminated=True, stop_reason="timeout")
        receipt["process"].update(forcibly_terminated=True, reason="timeout", shutdown_requested_reason="timeout")
        self.assertEqual(validate_receipt(receipt, started, TOKEN), [])
        self.assertIn("owned_tree_forced_or_unknown", validate_receipt(receipt, started, TOKEN, require_success=True))

    def test_incomplete_or_truncated_capture_is_known_exit_only(self):
        for key, value in (("capture_complete", False), ("stdout_truncated", True), ("stderr_truncated", True)):
            with self.subTest(key=key):
                receipt, started = fixture()
                receipt[key] = value
                self.assertEqual(validate_receipt(receipt, started, TOKEN), [])
                self.assertTrue(validate_receipt(receipt, started, TOKEN, require_success=True))

    def test_timeout_without_force_is_known_exit_but_not_natural_success(self):
        receipt, started = fixture()
        receipt["stop_reason"] = receipt["process"]["shutdown_requested_reason"] = "timeout"
        self.assertEqual(validate_receipt(receipt, started, TOKEN), [])
        self.assertIn("natural_capture_exit_not_verified", validate_receipt(receipt, started, TOKEN, require_success=True))

    def test_attempt_identity_is_required_in_both_records(self):
        for expected in (None, True, 1, "", "a" * 31, "A" * 32, "a" * 32 + "\n"):
            self.assertTrue(validate_receipt(*fixture(), expected))
        for record in ("receipt", "started"):
            for value in (None, True, "b" * 32):
                receipt, started = fixture()
                (receipt if record == "receipt" else started)["attempt_id"] = value
                self.assertIn("capture_attempt_mismatch", validate_receipt(receipt, started, TOKEN))

    def test_pid_requires_exact_integer_and_matching_all_three_positions(self):
        for location in ("receipt", "started", "process"):
            for value in (None, True, False, 0, -1, 2**32, 1234.0, "1234", 4321):
                with self.subTest(location=location, value=value):
                    receipt, started = fixture()
                    target = started if location == "started" else receipt["process"] if location == "process" else receipt
                    target["pid" if location == "process" else "codex_pid"] = value
                    self.assertTrue(validate_receipt(receipt, started, TOKEN))

    def test_creation_time_requires_valid_aware_timestamp_and_exact_match(self):
        for value in (None, True, "", "2026-10-23", "2026-10-23T01:02:03", "2026-13-23T01:02:03Z",
                      CREATED + "\n", "X" * 65, "2026-10-23T01:02:04.123456+00:00"):
            for location in ("started", "process"):
                with self.subTest(location=location, value=value):
                    receipt, started = fixture()
                    (started if location == "started" else receipt["process"])["created_at"] = value
                    self.assertTrue(validate_receipt(receipt, started, TOKEN))

    def test_all_core_exit_proof_fields_are_required(self):
        for location, fields in (("receipt", ("attempt_id", "codex_pid", "codex_exit_code", "child_exited", "process")),
                                 ("started", ("attempt_id", "codex_pid", "created_at")),
                                 ("process", ("managed", "pid", "created_at", "child_exited", "exit_code", "remaining_owned_processes"))):
            for field in fields:
                with self.subTest(location=location, field=field):
                    receipt, started = fixture()
                    target = started if location == "started" else receipt["process"] if location == "process" else receipt
                    del target[field]
                    self.assertTrue(validate_receipt(receipt, started, TOKEN))

    def test_bool_cannot_stand_in_for_process_count_or_exit_code(self):
        for value in (None, True, False, "0", 0.0, -1, 1):
            receipt, started = fixture()
            receipt["process"]["remaining_owned_processes"] = value
            self.assertIn("owned_tree_exit_unconfirmed", validate_receipt(receipt, started, TOKEN))
        for location in ("receipt", "process"):
            for value in (None, True, False, "0", 0.0, -(2**31)-1, 2**32):
                receipt, started = fixture()
                (receipt if location == "receipt" else receipt["process"])["codex_exit_code" if location == "receipt" else "exit_code"] = value
                self.assertIn("owned_root_exit_code_unconfirmed", validate_receipt(receipt, started, TOKEN))

    def test_root_codes_must_match_even_when_both_are_valid_integers(self):
        receipt, started = fixture()
        receipt["process"]["exit_code"] = 7
        self.assertIn("owned_root_exit_code_unconfirmed", validate_receipt(receipt, started, TOKEN))

    def test_managed_and_exited_flags_require_literal_true(self):
        for field, location in (("managed", "process"), ("child_exited", "process"), ("child_exited", "receipt")):
            for value in (None, False, 1, "true", [], {}):
                receipt, started = fixture()
                (receipt if location == "receipt" else receipt["process"])[field] = value
                self.assertTrue(validate_receipt(receipt, started, TOKEN))

    def test_natural_capture_flags_and_reasons_cannot_be_missing_or_coerced(self):
        pairs = (("receipt", "capture_complete", True), ("receipt", "stdout_truncated", False),
                 ("receipt", "stderr_truncated", False), ("receipt", "forcibly_terminated", False),
                 ("process", "forcibly_terminated", False), ("receipt", "stop_reason", "descendants_remaining"),
                 ("process", "reason", "natural_exit"), ("process", "shutdown_requested_reason", "descendants_remaining"))
        for location, field, expected in pairs:
            for value in (None, 0, 1, "unknown", not expected if type(expected) is bool else "timeout"):
                with self.subTest(location=location, field=field, value=value):
                    receipt, started = fixture()
                    (receipt if location == "receipt" else receipt["process"])[field] = value
                    self.assertTrue(validate_receipt(receipt, started, TOKEN, require_success=True))

    def test_missing_capture_quality_does_not_erase_known_exit(self):
        receipt, started = fixture()
        for field in ("capture_complete", "stdout_truncated", "stderr_truncated", "forcibly_terminated", "stop_reason"):
            del receipt[field]
        self.assertEqual(validate_receipt(receipt, started, TOKEN), [])
        self.assertTrue(validate_receipt(receipt, started, TOKEN, require_success=True))

    def test_malformed_json_shapes_and_policy_fail_closed_without_exceptions(self):
        for value in (None, True, 0, "unknown", [], [1]):
            self.assertTrue(validate_receipt(value, fixture()[1], TOKEN))
            self.assertTrue(validate_receipt(fixture()[0], value, TOKEN))
            receipt, started = fixture()
            receipt["process"] = value
            self.assertTrue(validate_receipt(receipt, started, TOKEN))
        for value in (None, 0, 1, "unknown", [], {}):
            self.assertEqual(validate_receipt(*fixture(), TOKEN, require_success=value), ["invalid_capture_receipt_policy"])

    def test_validation_is_deterministic_and_does_not_mutate_input(self):
        receipt, started = fixture()
        before = deepcopy((receipt, started))
        self.assertEqual(validate_receipt(receipt, started, TOKEN), validate_receipt(receipt, started, TOKEN))
        self.assertEqual((receipt, started), before)


if __name__ == "__main__":
    unittest.main()
