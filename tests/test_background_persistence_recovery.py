"""Supervisor persistence recovery fixtures; no processes, inventory, model or reboot."""
import copy
from pathlib import Path
import json
import shutil
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from eventguard import background as bg
from eventguard.runtime import Runtime

ROOT = Path(__file__).resolve().parents[1]
CREATED = "2026-10-23T00:00:00.000000+00:00"
PID = 4242


class FixtureKeeper:
    def __init__(self, name):
        self.name = name

    def receipt(self):
        return {"kind": "eventguard-private-job-keeper-v1", "job_name": self.name,
                "pid": PID, "created_at": CREATED, "session_id": 1, "keeper_handle": 123,
                "parent_job_present": True, "lifetime_owner": "scheduler_or_foreground_host"}


class BackgroundPersistenceRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default.json", self.root / "config/default.json")
        self.runtime = Runtime(self.root)
        self.write = bg._write
        self.control = bg._control
        self.records = []
        self.enterContext(patch.object(bg, "_KEEPERS", []))
        self.enterContext(patch.object(bg, "RESTART_DELAYS", (.01, .02, .03)))
        self.enterContext(patch.object(bg, "HEARTBEAT_SECONDS", .01))
        self.enterContext(patch.object(bg.processes, "process_session", return_value=1))
        self.enterContext(patch.object(bg.processes, "identity", return_value={"pid": PID,
            "created_at": CREATED, "state": "alive"}))
        self.enterContext(patch.object(bg.processes, "current_job_active", return_value=0))
        self.enterContext(patch.object(bg.processes, "standalone_host_job", side_effect=FixtureKeeper))
        for name in ("spawn", "spawn_persistent", "spawn_application_host", "finish", "stop_persistent"):
            self.enterContext(patch.object(bg.processes, name, side_effect=AssertionError("process forbidden in fixture")))
        self.enterContext(patch.object(bg.subprocess, "Popen", side_effect=AssertionError("Popen forbidden in fixture")))
        self.addCleanup(self.assert_control_thread_exited)
        self.write(self.runtime, "control.json", {"kind": bg.CONTROL_KIND, "enabled": True,
            "generation": "a" * 32, "namespace": "live", "fixture": None, "max_cycles": None,
            "updated_at": bg._stamp(), "reason": "explicit_fixture"})

    def assert_control_thread_exited(self):
        self.assertFalse(any(thread.name == "eventguard-background-control" and thread.is_alive()
                             for thread in threading.enumerate()))

    def disable(self):
        value = self.control(self.runtime)
        value.update(enabled=False, updated_at=bg._stamp(), reason="explicit_fixture_stop")
        self.write(self.runtime, "control.json", value)

    def record_write(self, runtime, name, value):
        if name == "run.json":
            self.records.append(copy.deepcopy(value))
        return self.write(runtime, name, value)

    def assert_no_model_or_exit_claim(self, result):
        self.assertEqual(result["model_calls"], 0)
        self.assertTrue(result["host_exit_pending"])
        self.assertNotIn("child_exited", result)
        self.assertNotIn("PRIVATE", json.dumps(result))

    def evidence_for(self, result, **extra):
        return {"scope": "fake Keeper/Monitor and isolated metadata fault injection, no OS child/live source/model",
                "machine_scan_executed": False, "model_calls": 0, "real_agent_woken": False,
                "run_records": self.records, "result": result, **extra}

    def test_control_thread_heartbeat_fault_cancels_only_monitor_then_retries(self):
        attempts, failed, running, observed_cancel = [], threading.Event(), threading.Event(), []
        test = self
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
                attempts.append(self)

            def run(self, **kwargs):
                if len(attempts) == 1:
                    running.set()
                    observed_cancel.append(self.cancel.wait(3))
                else:
                    test.disable()
                    self.cancel.wait(2)
                return {"state": "stopped", "healthy": False}

        def fault(runtime, name, value):
            if (name == "run.json" and threading.current_thread().name == "eventguard-background-control"
                    and running.is_set() and not failed.is_set()):
                failed.set()
                raise PermissionError("PRIVATE synthetic heartbeat write failure")
            return self.record_write(runtime, name, value)

        with patch.object(bg, "Monitor", FakeMonitor), patch.object(bg, "_write", side_effect=fault):
            result = bg.serve(self.root)
        self.assertTrue(failed.is_set())
        self.assertEqual(observed_cancel, [True])
        self.assertEqual(len(attempts), 2)
        backoff = [row for row in self.records if row.get("state") == "backoff"]
        self.assertTrue(backoff)
        self.assertEqual(backoff[0]["reason"], "background_state_persistence_failed")
        self.assertEqual(backoff[0]["backoff_seconds"], .01)
        self.assertFalse(self.control(self.runtime)["enabled"])
        self.assertFalse(result["desired_enabled"])
        self.assert_no_model_or_exit_claim(result)
        self.evidence = self.evidence_for(result, monitor_attempts=len(attempts),
                                           cancelled_first_monitor=observed_cancel[0])

    def test_persistent_heartbeat_fault_wait_remains_interruptible_by_manual_stop(self):
        attempts, failed, running, waits = [], threading.Event(), threading.Event(), []
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
                attempts.append(self)

            def run(self, **kwargs):
                running.set()
                self.cancel.wait(3)
                return {"state": "stopped", "healthy": False}

        def fault(runtime, name, value):
            if (name == "run.json" and (failed.is_set() or
                    threading.current_thread().name == "eventguard-background-control" and running.is_set())):
                failed.set()
                raise PermissionError("PRIVATE persistent heartbeat failure")
            return self.record_write(runtime, name, value)

        def waiting(cancelled, delay):
            waits.append(delay)
            self.disable()
            return cancelled.wait(.01)

        with patch.object(bg, "Monitor", FakeMonitor), patch.object(bg, "_write", side_effect=fault), \
                patch.object(bg, "_wait_retry", side_effect=waiting):
            result = bg.serve(self.root)
        self.assertTrue(failed.is_set())
        self.assertEqual(len(attempts), 1)
        self.assertEqual(waits, [.01])
        self.assertFalse(self.control(self.runtime)["enabled"])
        self.assertFalse(result["desired_enabled"])
        self.assertTrue(result["evidence_write_failed"])
        self.assert_no_model_or_exit_claim(result)
        self.evidence = self.evidence_for(result, retry_delays=waits, monitor_attempts=len(attempts))

    def test_monitor_starting_write_fault_is_retried_before_constructing_monitor(self):
        failed, attempts, waits, order = [], [], [], []
        test = self
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
                attempts.append(self)
                order.append("construct_monitor")

            def run(self, **kwargs):
                test.disable()
                self.cancel.wait(2)
                return {"state": "stopped"}

        def fault(runtime, name, value):
            if name == "run.json" and value.get("reason") == "monitor_starting":
                if not failed:
                    failed.append(True)
                    order.append("start_publish_failed")
                    raise PermissionError("PRIVATE first starting write failure")
                order.append("start_publish_saved")
            return self.record_write(runtime, name, value)

        def waiting(cancelled, delay):
            waits.append(delay)
            self.assertEqual(attempts, [])
            order.append("backoff_wait")
            return False

        with patch.object(bg, "Monitor", FakeMonitor), patch.object(bg, "_write", side_effect=fault), \
                patch.object(bg, "_wait_retry", side_effect=waiting):
            result = bg.serve(self.root)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(waits, [.01])
        self.assertLess(order.index("start_publish_failed"), order.index("backoff_wait"))
        self.assertLess(order.index("backoff_wait"), order.index("start_publish_saved"))
        self.assertLess(order.index("start_publish_saved"), order.index("construct_monitor"))
        self.assert_no_model_or_exit_claim(result)
        self.evidence = self.evidence_for(result, order=order, retry_delays=waits)

    def test_persistent_starting_write_failure_uses_bounded_backoff_without_collecting(self):
        failed, waits, failed_writes = threading.Event(), [], []
        def fault(runtime, name, value):
            if name == "run.json" and (failed.is_set() or value.get("reason") == "monitor_starting"):
                failed.set()
                failed_writes.append(value.get("state"))
                raise PermissionError("PRIVATE persistent starting failure")
            return self.record_write(runtime, name, value)

        def waiting(cancelled, delay):
            waits.append(delay)
            if len(waits) == 3:
                self.disable()
            return False

        with patch.object(bg, "Monitor", side_effect=AssertionError("must not construct collector")) as monitor, \
                patch.object(bg, "_write", side_effect=fault), patch.object(bg, "_wait_retry", side_effect=waiting):
            result = bg.serve(self.root)
        monitor.assert_not_called()
        self.assertEqual(waits, [.01, .02, .03])
        self.assertLessEqual(len(failed_writes), 10, "each failed admission must wait rather than spin")
        self.assertFalse(self.control(self.runtime)["enabled"])
        self.assertTrue(result["evidence_write_failed"])
        self.assert_no_model_or_exit_claim(result)
        self.evidence = self.evidence_for(result, retry_delays=waits, failed_write_count=len(failed_writes))

    def test_replaced_generation_during_fault_backoff_keeps_new_enabled_intent(self):
        failed, replacement_bytes, waits = [], [], []
        def fault(runtime, name, value):
            if name == "run.json" and value.get("reason") == "monitor_starting" and not failed:
                failed.append(True)
                raise PermissionError("PRIVATE first starting failure")
            return self.record_write(runtime, name, value)

        def waiting(cancelled, delay):
            waits.append(delay)
            control = self.control(self.runtime)
            control.update(enabled=True, generation="b" * 32, updated_at=bg._stamp(), reason="replacement_fixture_start")
            self.write(self.runtime, "control.json", control)
            replacement_bytes.append(bg._path(self.runtime, "control.json").read_bytes())
            return False

        with patch.object(bg, "Monitor", side_effect=AssertionError("no old-generation collection")) as monitor, \
                patch.object(bg, "_write", side_effect=fault), patch.object(bg, "_wait_retry", side_effect=waiting):
            result = bg.serve(self.root)
        monitor.assert_not_called()
        self.assertEqual(waits, [.01])
        self.assertEqual(bg._path(self.runtime, "control.json").read_bytes(), replacement_bytes[0])
        self.assertEqual(self.control(self.runtime)["generation"], "b" * 32)
        self.assertTrue(self.control(self.runtime)["enabled"])
        self.assertTrue(result["desired_enabled"])
        self.assert_no_model_or_exit_claim(result)
        self.evidence = self.evidence_for(result, replacement_generation_preserved=True)

    def test_unreadable_control_blocks_collection_without_rewriting_intent_then_recovers(self):
        unreadable, attempts, waits = threading.Event(), [], []
        before = bg._path(self.runtime, "control.json").read_bytes()
        test = self
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
                attempts.append(self)

            def run(self, **kwargs):
                test.disable()
                self.cancel.wait(2)
                return {"state": "stopped"}

        def record(runtime, name, value):
            saved = self.record_write(runtime, name, value)
            if name == "ready.json":
                unreadable.set()
            return saved

        def control(runtime):
            if unreadable.is_set():
                raise PermissionError("PRIVATE temporary control read failure")
            return self.control(runtime)

        def waiting(cancelled, delay):
            waits.append(delay)
            self.assertEqual(attempts, [])
            self.assertEqual(bg._path(self.runtime, "control.json").read_bytes(), before)
            unreadable.clear()
            return False

        with patch.object(bg, "Monitor", FakeMonitor), patch.object(bg, "_write", side_effect=record), \
                patch.object(bg, "_control", side_effect=control), patch.object(bg, "_wait_retry", side_effect=waiting):
            result = bg.serve(self.root)
        self.assertEqual(waits, [.01])
        self.assertEqual(len(attempts), 1)
        self.assertTrue(any(row.get("reason") == "background_control_unverifiable" for row in self.records))
        self.assert_no_model_or_exit_claim(result)
        self.evidence = self.evidence_for(result, unreadable_control_was_not_rewritten=True, retry_delays=waits)

    def test_state_fault_between_start_publish_and_monitor_assignment_prevents_first_run(self):
        constructing, failed, instances, runs = threading.Event(), threading.Event(), [], []
        test = self
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
                instances.append(self)
                if len(instances) == 1:
                    constructing.set()
                    if not failed.wait(3):
                        raise AssertionError("control thread did not reach the injected heartbeat failure")

            def run(self, **kwargs):
                runs.append(instances.index(self))
                test.disable()
                self.cancel.wait(2)
                return {"state": "stopped"}

        def fault(runtime, name, value):
            if (name == "run.json" and threading.current_thread().name == "eventguard-background-control"
                    and constructing.is_set() and not failed.is_set()):
                failed.set()
                raise PermissionError("PRIVATE admission-race heartbeat failure")
            return self.record_write(runtime, name, value)

        with patch.object(bg, "Monitor", FakeMonitor), patch.object(bg, "_write", side_effect=fault):
            result = bg.serve(self.root)
        self.assertTrue(failed.is_set())
        self.assertEqual(len(instances), 2)
        self.assertEqual(runs, [1], "the instance admitted before the persistence fault must not collect")
        self.assertTrue(instances[0].cancel.is_set())
        self.assertTrue(any(row.get("state") == "backoff" for row in self.records))
        self.assert_no_model_or_exit_claim(result)
        self.evidence = self.evidence_for(result, monitor_instances=len(instances), monitor_runs=runs)

    def test_failed_shutdown_gate_write_retains_unconfirmed_runner_until_exact_job_recovers(self):
        from eventguard import runtime as runtime_module
        job_name = "Global\\EventGuard-" + "d" * 32
        receipt = {"managed": True, "pid": 4343, "created_at": CREATED, "job_name": job_name,
                   "child_exited": False, "remaining_owned_processes": 1, "forcibly_terminated": False}
        instances, waits, gate_writes, job_queries, shutdown_calls = [], [], [], [], []
        empty, zero_observed, active_observed = threading.Event(), threading.Event(), threading.Event()
        atomic = runtime_module.atomic_json
        test = self

        class FakeRunner:
            pending = True
            last_process = copy.deepcopy(receipt)

            def shutdown(self, *, grace):
                shutdown_calls.append({"grace": grace, "zero_job_proof_observed": zero_observed.is_set()})
                return dict(receipt, child_exited=True, remaining_owned_processes=0) if zero_observed.is_set() else copy.deepcopy(receipt)

        class FakeMonitor:
            def __init__(self, root):
                self.runtime = Runtime(root)
                self.cancel = threading.Event()
                self.collectors = SimpleNamespace(runner=FakeRunner() if not instances else None)
                instances.append(self)

            def run(self, **kwargs):
                if len(instances) == 1:
                    self.runtime.block_monitor_shutdown({"state": "shutdown_unconfirmed", "namespace": "live",
                        "instance_id": "c" * 32, "pid": PID, "process_created_at": CREATED,
                        "query_shutdown": copy.deepcopy(receipt)})
                    return {"state": "shutdown_unconfirmed", "healthy": False}
                if zero_observed.is_set():
                    test.disable()
                    self.cancel.wait(2)
                # An unsafe second admission is asserted from the next outer
                # backoff, outside serve's monitor-exception swallowing scope.
                return {"state": "stopped", "healthy": False}

        def fail_gate_twice(path, value, limit=65536):
            if Path(path).name == "monitor-shutdown-gate.json":
                gate_writes.append(copy.deepcopy(value))
                if len(gate_writes) <= 2:
                    raise PermissionError("PRIVATE shutdown gate storage failure")
            return atomic(path, value, limit)

        def exact_job_active(name):
            self.assertEqual(name, job_name, "only the recorded unconfirmed query Job may be inspected")
            count = 0 if empty.is_set() else 1
            job_queries.append({"job_name": name, "remaining_owned_processes": count})
            if count:
                active_observed.set()
            else:
                zero_observed.set()
            return count

        def waiting(cancelled, delay):
            waits.append(delay)
            if not zero_observed.is_set():
                self.assertEqual(len(instances), 1,
                    "gate persistence failure must not discard the old unconfirmed runner and admit another Monitor")
            if active_observed.is_set():
                empty.set()
            if len(waits) >= 8:
                self.fail("the in-memory fence did not restore and verify its durable gate within bounded fixture retries")
            return False

        with patch.object(bg, "Monitor", FakeMonitor), patch.object(bg, "_write", side_effect=self.record_write), \
                patch.object(runtime_module, "atomic_json", side_effect=fail_gate_twice), \
                patch.object(bg.processes, "current_job_active", side_effect=exact_job_active), \
                patch.object(bg, "_wait_retry", side_effect=waiting):
            result = bg.serve(self.root)
        self.assertEqual(len(instances), 2)
        self.assertGreaterEqual(len(gate_writes), 3)
        self.assertTrue(active_observed.is_set())
        self.assertTrue(zero_observed.is_set())
        self.assertEqual(job_queries[-1]["remaining_owned_processes"], 0)
        self.assertEqual(shutdown_calls, [{"grace": 0, "zero_job_proof_observed": True}])
        recovered = json.loads((self.root / "data/monitor-shutdown-recovered.json").read_text(encoding="utf-8"))
        self.assertEqual(recovered["previous"]["process"]["job_name"], job_name)
        self.assertEqual(recovered["verification"]["remaining_owned_processes"], 0)
        self.assertFalse((self.root / "data/monitor-shutdown-gate.json").exists())
        self.assertFalse(self.control(self.runtime)["enabled"])
        self.assert_no_model_or_exit_claim(result)
        self.evidence = self.evidence_for(result, monitor_instances=len(instances), retry_delays=waits,
            gate_write_attempts=len(gate_writes), exact_job_queries=job_queries,
            recovered_job_name=recovered["previous"]["process"]["job_name"], runner_shutdown_calls=shutdown_calls)

    def test_keyboard_interrupt_during_unknown_query_backoff_preserves_shutdown_uncertainty(self):
        receipt = {"managed": True, "pid": 4343, "created_at": CREATED,
                   "job_name": "Global\\EventGuard-" + "e" * 32,
                   "child_exited": False, "remaining_owned_processes": 1, "forcibly_terminated": False}
        instances = []
        class FakeMonitor:
            def __init__(self, root):
                self.runtime = Runtime(root)
                self.cancel = threading.Event()
                self.collectors = SimpleNamespace(runner=SimpleNamespace(pending=True,
                    last_process=copy.deepcopy(receipt)))
                instances.append(self)

            def run(self, **kwargs):
                return {"state": "shutdown_unconfirmed", "healthy": False}

        with patch.object(bg, "Monitor", FakeMonitor), patch.object(bg, "_write", side_effect=self.record_write), \
                patch.object(bg, "_wait_retry", side_effect=KeyboardInterrupt) as wait:
            result = bg.serve(self.root)
        self.assertEqual(len(instances), 1)
        self.assertEqual(wait.call_count, 1)
        self.assertFalse(self.control(self.runtime)["enabled"])
        self.assertTrue(result["disabled_persisted"])
        self.assertFalse(result["desired_enabled"])
        self.assertEqual(result["state"], "shutdown_unconfirmed")
        self.assertEqual(result["reason"], "monitor_query_exit_unconfirmed")
        self.assertEqual(self.records[-1]["state"], "shutdown_unconfirmed")
        self.assert_no_model_or_exit_claim(result)
        self.evidence = self.evidence_for(result, monitor_instances=len(instances),
            keyboard_interrupt_is_fixture=True, unresolved_query_job_name=receipt["job_name"])


if __name__ == "__main__":
    unittest.main()
