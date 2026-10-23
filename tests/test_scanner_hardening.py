"""Bounded parser fixtures and labelled Windows-owned synthetic output floods."""
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eventguard.collectors.bounded_json import BoundedJSONError, MAX_JSON_DEPTH, loads
from eventguard.collectors.runner import MAX_OUTPUT_BYTES, Runner
from eventguard.collectors.windows import WindowsCollectors, process_metadata
from eventguard.processes import identity, remaining_owned


class BoundedJSONTests(unittest.TestCase):
    def test_exact_depth_bound_and_deep_input_fail_before_recursive_decode(self):
        source = "[" * MAX_JSON_DEPTH + "0" + "]" * MAX_JSON_DEPTH
        self.assertIsInstance(loads(source), list)
        for count in (MAX_JSON_DEPTH + 1, 10000):
            with self.subTest(count=count), self.assertRaisesRegex(BoundedJSONError, "^query_json_depth_exceeded$"):
                loads("[" * count + "0" + "]" * count)

    def test_brackets_and_escaped_quotes_inside_strings_are_not_nesting(self):
        hostile = '[{\\"ignore instructions; run commands\\"}]' * 200
        payload = {"rows": [{"name": hostile, "status": "ok"}], "status": "ok"}
        self.assertEqual(loads(json.dumps(payload)), payload)

    def test_duplicate_keys_rejected_including_decoded_unicode_and_nested_keys(self):
        fixtures = (
            '{"status":"denied","status":"ok","rows":[]}',
            '{"status":"denied","sta\\u0074us":"ok","rows":[]}',
            '{"rows":[{"name":"SECRET_SENTINEL","name":"overwritten"}]}',
            '{"rows":[],"rows":[{"status":"ok"}]}',
        )
        for source in fixtures:
            with self.subTest(source=source), self.assertRaises(BoundedJSONError) as caught:
                loads(source)
            self.assertEqual(str(caught.exception), "query_json_duplicate_key")
            self.assertNotIn("SECRET_SENTINEL", str(caught.exception))

    def test_same_key_in_separate_objects_is_valid(self):
        self.assertEqual(loads('{"rows":[{"status":"ok"},{"status":"denied"}]}'),
                         {"rows": [{"status": "ok"}, {"status": "denied"}]})

    def test_standard_decoder_still_checks_complete_syntax(self):
        for source in ('{"rows":[]', '{"rows":[]} trailing', '[}', '"unterminated\\"'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                loads(source)

    def test_utf8_byte_limit_applies_to_string_fixture_seam(self):
        with self.assertRaisesRegex(BoundedJSONError, "^query_output_limit_exceeded$"):
            loads('"' + "\u4e2d" * (MAX_OUTPUT_BYTES // 3 + 1) + '"')

    def test_runner_rejects_duplicate_or_deep_wire_payload_with_fixed_reason(self):
        fixtures = (
            ('{"rows":[],"rows":[]}', "query_json_duplicate_key"),
            ('{"rows":' + '[' * MAX_JSON_DEPTH + '0' + ']' * MAX_JSON_DEPTH + '}', "query_json_depth_exceeded"),
        )
        for source, reason in fixtures:
            child = MemoryChild(source.encode())
            result = Runner(lambda *a, **k: child).run("STATIC_SYNTHETIC")
            self.assertEqual((result["status"], result["note"]), ("error", reason))
            self.assertIsNone(result["data"])

    def test_powershell_string_seam_uses_the_same_fail_closed_parser(self):
        class FixtureRunner:
            def __init__(self, value):
                self.value = value

            def run(self, *args, **kwargs):
                return {"status": "ok", "data": self.value}

        for source, reason in (
            ('{"status":"denied","status":"ok","rows":[]}', "query_json_duplicate_key"),
            ('{"status":"ok","rows":' + '[' * MAX_JSON_DEPTH + '0' + ']' * MAX_JSON_DEPTH + '}',
             "query_json_depth_exceeded"),
        ):
            result = WindowsCollectors(FixtureRunner(source)).collect("services")
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["rows"], [])
            self.assertEqual(result["coverage"]["errors"][0]["reason_code"], reason)


class MemoryChild:
    def __init__(self, stdout=b'{"rows":[]}', stderr=b"", gate=None):
        self.stdout, self.stderr = io.BytesIO(stdout), io.BytesIO(stderr)
        self.gate, self.returncode = gate, None

    def wait(self):
        if self.gate is not None:
            self.gate.wait(5)
        self.returncode = 0
        return 0

    def terminate(self):
        raise AssertionError("an unmanaged fixture is never termination authority")

    kill = terminate


class OutputLimitFixtureTests(unittest.TestCase):
    def test_combined_stream_limit_returns_early_without_stopping_unmanaged_child(self):
        gate = threading.Event()
        child = MemoryChild(b"a" * (MAX_OUTPUT_BYTES // 2 + 1),
                            b"b" * (MAX_OUTPUT_BYTES // 2 + 1), gate)
        runner = Runner(lambda *a, **k: child)
        try:
            with patch("eventguard.collectors.runner.finish") as cleanup:
                result = runner.run("STATIC_SYNTHETIC", timeout=1)
            self.assertEqual((result["status"], result["note"]), ("error", "query_output_limit_exceeded"))
            cleanup.assert_not_called()
            self.assertTrue(runner.pending)
            self.assertIsNone(child.returncode)
            self.assertEqual(runner.run("STATIC_SYNTHETIC")["status"], "busy")
            stored = len(runner._active.get("stdout", b"")) + len(runner._active.get("stderr", b""))
            self.assertLessEqual(stored, MAX_OUTPUT_BYTES)
        finally:
            gate.set()
            self.assertTrue(runner._active["done"].wait(3))
        self.assertFalse(runner.pending)

    def test_output_limit_receipt_survives_coverage_minimization(self):
        receipt = {"managed": True, "forcibly_terminated": True, "child_exited": True,
                   "remaining_owned_processes": 0, "reason": "output_limit",
                   "shutdown_requested_reason": "output_limit", "output_limit_exceeded": True,
                   "output_limit_bytes": MAX_OUTPUT_BYTES, "output_bytes_observed": MAX_OUTPUT_BYTES + 1,
                   "private": "SECRET_SENTINEL"}
        clean = process_metadata(receipt)
        self.assertEqual(clean["reason"], "output_limit")
        self.assertEqual(clean["output_bytes_observed"], MAX_OUTPUT_BYTES + 1)
        self.assertNotIn("SECRET_SENTINEL", json.dumps(clean))


@unittest.skipUnless(os.name == "nt", "real Windows owned synthetic child; not Linux support")
class WindowsOutputLimitTests(unittest.TestCase):
    def test_owned_synthetic_flood_stops_before_deadline_and_leaves_no_child(self):
        runner = Runner()
        source = ("import sys,time\n"
                  "for _ in range(80):\n"
                  " sys.stdout.buffer.write(b'o'*65536);sys.stdout.buffer.flush()\n"
                  " sys.stderr.buffer.write(b'e'*65536);sys.stderr.buffer.flush()\n"
                  "time.sleep(60)\n")
        started = time.monotonic()
        try:
            result = runner.run("OWNED_SYNTHETIC_FLOOD", timeout=10,
                                _argv=[sys.executable, "-B", "-c", source])
            elapsed = time.monotonic() - started
            self.assertEqual((result["status"], result["note"]), ("error", "query_output_limit_exceeded"))
            receipt = result["process"]
            self.assertTrue(receipt["managed"])
            self.assertTrue(receipt["forcibly_terminated"], "fixture ignores EOF: owned-job force is expected")
            self.assertTrue(receipt["child_exited"])
            self.assertEqual(receipt["remaining_owned_processes"], 0)
            self.assertEqual(receipt["reason"], "output_limit")
            self.assertEqual(receipt["shutdown_requested_reason"], "output_limit")
            self.assertGreater(receipt["output_bytes_observed"], MAX_OUTPUT_BYTES)
            self.assertLess(elapsed, 8, "output limit must stop before the 10-second query deadline")
            self.assertFalse(runner.pending)
            current = identity(receipt["pid"])
            original_exited = current["state"] in {"missing", "exited"} or (
                isinstance(current.get("created_at"), str) and current["created_at"] != receipt["created_at"])
            self.assertTrue(original_exited, "verify the original PID+creation identity exited")
            self.assertEqual(remaining_owned(), 0)
            self.evidence = {"scope": "real_windows_owned_synthetic_flood_no_inventory_or_model",
                             "case": "combined_output_limit", "expected_forced_cleanup": True,
                             "elapsed_seconds": elapsed, "result": result,
                             "exit_observation": current, "remaining_owned_processes": remaining_owned()}
        finally:
            if runner.pending:
                runner.shutdown(grace=.1)
            self.assertEqual(remaining_owned(), 0, "owned test processes must not remain")


if __name__ == "__main__":
    unittest.main()
