"""Synthetic progress/contract tests; no provider query or real child process."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eventguard.collectors.contract import evidence, payload
from eventguard.collectors.progress import Progress, invoke_with_progress
from eventguard.collectors.runner import Runner
from eventguard.collectors.windows import WindowsCollectors, coverage_metadata
from eventguard.collectors.worker import NativeWorker


class LegacyBackend:
    def __init__(self, result):
        self.result, self.calls = result, 0

    def collect(self, section_id, cancel=None):
        self.calls += 1
        return deepcopy(self.result)


class LegacyRunner:
    def __init__(self):
        self.calls = 0

    def run(self, script, timeout=15, cancel=None, _argv=None):
        self.calls += 1
        return {"status": "ok", "data": payload()}


class MemoryChild:
    def __init__(self):
        self.stdout = io.BytesIO(b'{"status":"ok","rows":[]}')
        self.stderr = io.BytesIO()

    def wait(self):
        return 0


class CollectorProgressTests(unittest.TestCase):
    def test_waiting_ticks_are_limited_to_one_per_second_and_minimal(self):
        events = []
        with patch("eventguard.collectors.progress.time.monotonic", side_effect=[0, 0, .2, .9, 1, 1.2, 2, 2.1]):
            reporter = Progress(events.append, "tasks", "native")
            for phase in ("launch", "waiting", "waiting", "waiting", "waiting", "waiting", "completed"):
                reporter.emit(phase)
        self.assertEqual([e["phase"] for e in events], ["launch", "waiting", "waiting", "completed"])
        self.assertEqual([e["elapsed_ms"] for e in events], [0, 1000, 2000, 2100])
        self.assertTrue(all(set(e) == {"phase", "source_id", "backend", "elapsed_ms"} for e in events))

    def test_forward_discards_untrusted_event_fields_and_rebinds_source(self):
        events = []
        reporter = Progress(events.append, "listeners", "native")
        reporter.forward({"phase": "launch", "source_id": "PRIVATE", "backend": "PRIVATE", "argv": "PRIVATE"})
        reporter.forward({"phase": "run arbitrary command"})
        reporter.forward({"phase": "completed", "path": "PRIVATE"})
        self.assertNotIn("PRIVATE", json.dumps(events))
        self.assertEqual([e["source_id"] for e in events], ["listeners", "listeners"])

    def test_observer_failure_does_not_replace_source_facts(self):
        def broken(value):
            raise OSError("PRIVATE display failure")
        backend = LegacyBackend(payload())
        result = WindowsCollectors(native=backend, backend="native").collect("tasks", progress=broken)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(backend.calls, 1)

    def test_legacy_backend_without_new_keyword_is_called_once(self):
        events = []
        backend = LegacyBackend(payload())
        result = WindowsCollectors(native=backend, backend="native").collect("tasks", progress=events.append)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(backend.calls, 1)
        self.assertEqual([e["phase"] for e in events], ["launch", "completed"])

    def test_provider_type_error_does_not_retry(self):
        calls = []
        def collect(section_id, cancel=None, progress=None):
            calls.append(section_id)
            raise TypeError("PRIVATE internal provider failure")
        backend = type("Backend", (), {"collect": staticmethod(collect)})()
        result = WindowsCollectors(native=backend, backend="native").collect("tasks", progress=lambda e: None)
        self.assertEqual(result["status"], "error")
        self.assertEqual(calls, ["tasks"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_legacy_runner_remains_compatible_in_both_backends(self):
        for factory in (lambda r: WindowsCollectors(r), lambda r: NativeWorker(runner=r)):
            runner = LegacyRunner()
            result = factory(runner).collect("versions", progress=lambda e: None)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(runner.calls, 1)

    def test_signature_probe_failure_still_invokes_once_without_new_keywords(self):
        calls = []
        def legacy(value):
            calls.append(value)
            return 42
        with patch("eventguard.collectors.progress.inspect.signature", side_effect=ValueError()):
            self.assertEqual(invoke_with_progress(legacy, "fixture", progress=lambda e: None), 42)
        self.assertEqual(calls, ["fixture"])

    def test_runner_progress_callback_may_read_runner_state_without_deadlock(self):
        events = []
        runner = Runner(lambda *a, **k: MemoryChild())
        def observe(event):
            events.append((event, runner.pending, runner.last_process))
        result = runner.run("STATIC", progress=observe, source_id="versions")
        self.assertEqual(result["status"], "ok")
        self.assertEqual([e[0]["phase"] for e in events], ["launch", "completed"])

    def test_runner_launch_denial_is_completed_and_private_text_not_in_progress(self):
        events = []
        def denied(*args, **kwargs):
            raise PermissionError("PRIVATE path and account")
        result = Runner(denied).run("STATIC PRIVATE", progress=events.append, source_id="tasks")
        self.assertEqual(result["status"], "denied")
        self.assertEqual([e["phase"] for e in events], ["launch", "completed"])
        self.assertNotIn("PRIVATE", json.dumps(events))

    def test_fallback_has_two_distinct_progress_attempts_and_retains_duration(self):
        events = []
        absent = payload(errors=[evidence("launch", "api_unavailable", status="not_applicable")])
        collector = WindowsCollectors(LegacyRunner(), native=LegacyBackend(absent), backend="auto")
        result = collector.collect("versions", progress=events.append)
        self.assertEqual([(e["backend"], e["phase"]) for e in events], [
            ("native", "launch"), ("native", "completed"), ("powershell", "launch"), ("powershell", "completed")])
        attempts = coverage_metadata(result)["attempts"]
        self.assertEqual(len(attempts), 2)
        self.assertTrue(all(type(attempt["elapsed_ms"]) is int for attempt in attempts))

    def test_summary_distinguishes_received_rows_from_usable_metadata(self):
        denial = evidence("field", "access_denied", status="denied", win32_error=5)
        rows = [{"name": "fixture", "state": "Running", "status": "ok"},
                {"name": "partial fixture", "status": "partial"}, {"status": "denied"}]
        result = WindowsCollectors(native=LegacyBackend(payload(rows, [denial])), backend="native").collect("services")
        coverage = coverage_metadata(result)
        self.assertEqual((coverage["row_count"], coverage["usable_row_count"], coverage["error_count"]), (3, 2, 1))
        self.assertEqual(coverage["reason"], "access_denied")
        self.assertNotIn("fixture", json.dumps(coverage))

    def test_empty_success_remains_an_empty_observation_not_a_denial(self):
        result = WindowsCollectors(native=LegacyBackend(payload()), backend="native").collect("listeners")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["coverage"]["row_count"], 0)
        self.assertEqual(result["coverage"]["usable_row_count"], 0)
        self.assertEqual(result["coverage"]["error_count"], 0)
        self.assertNotIn("reason", result["coverage"])


if __name__ == "__main__":
    unittest.main()
