"""Admission fixtures and labelled finite Windows lease-owner child; no provider/model."""
import copy
from contextlib import contextmanager, nullcontext
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from eventguard import processes
from eventguard import runtime as runtime_module
from eventguard.collectors import runner as runner_module
from eventguard.collectors.runner import Runner
from eventguard.events.store import EventStore
from eventguard.monitor import Monitor
from eventguard.rules.detector import evaluate
from eventguard.runtime import InstanceLock, Runtime

ROOT = Path(__file__).resolve().parents[1]
CREATED = "2026-10-23T00:00:00.000000+00:00"
JOB_NAME = "Global\\EventGuard-" + "d" * 32


class MonitorAdmissionBarrierTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default.json", self.root / "config/default.json")
        self.runtime = Runtime(self.root)
        self.atomic = runtime_module.atomic_json
        self.enterContext(patch.object(Monitor, "_own_low_priority", return_value="fixture"))
        self.enterContext(patch.object(processes, "identity", side_effect=lambda pid=None: {
            "pid": pid or os.getpid(), "created_at": CREATED, "state": "alive"}))
        self.enterContext(patch.object(processes, "process_session", return_value=1))
        self.enterContext(patch.object(processes, "spawn", side_effect=AssertionError("child process forbidden")))
        self.enterContext(patch.object(processes, "finish", side_effect=AssertionError("owned process cleanup forbidden")))
        self.enterContext(patch.object(subprocess, "Popen", side_effect=AssertionError("Popen forbidden")))

    @staticmethod
    def section(source):
        return {"id": source, "status": "ok", "rows": [], "observed_at": "2026-10-23T00:00:00+00:00",
                "coverage": {"status": "ok"}}

    def safe_collector(self, calls):
        test = self
        class FixtureCollector:
            runner = None

            def collect(self, source, cancel=None):
                calls.append(source)
                return test.section(source)
        return FixtureCollector()

    def test_failed_finish_gate_write_blocks_independent_monitor_until_same_job_is_empty(self):
        first_calls, second_calls, recovery_calls, admissions, job_queries, shutdown_calls = [], [], [], [], [], []
        active, launched, recover = [0], threading.Event(), threading.Event()
        zero_proof, finish_write_fault = threading.Event(), threading.Event()
        finish_write_fault.set()
        receipt = {"managed": True, "pid": 4343, "created_at": CREATED, "job_name": JOB_NAME,
                   "child_exited": False, "remaining_owned_processes": 1, "forcibly_terminated": False}
        test = self

        class FakeOwnedRunner(Runner):
            def __init__(self):
                super().__init__(popen_factory=lambda *args, **kwargs: test.fail("fake Runner cannot spawn"))
                self.launched, self.confirmed = False, False

            @property
            def pending(self):
                return self.launched and not self.confirmed

            @property
            def last_process(self):
                if not self.launched:
                    return {}
                return dict(receipt, child_exited=True, remaining_owned_processes=0) if self.confirmed else dict(receipt)

            def shutdown(self, grace=2):
                shutdown_calls.append({"grace": grace, "zero_job_proof_observed": zero_proof.is_set()})
                if recover.is_set() and zero_proof.is_set():
                    self.confirmed = True
                return self.last_process

        class FirstCollector:
            def __init__(self):
                self.runner, self.monitor = FakeOwnedRunner(), None

            def collect(self, source, cancel=None):
                first_calls.append(source)
                admission = getattr(self.runner, "admission", None)
                admissions.append(callable(admission))
                with admission(JOB_NAME) if callable(admission) else nullcontext():
                    self.runner.launched = True
                    launched.set()
                    active[0] = 1
                self.monitor.cancel.set()
                return test.section(source)

        def fail_finish_write(path, value, limit=65536):
            if (Path(path).name == "monitor-shutdown-gate.json" and finish_write_fault.is_set()
                    and value.get("phase") != "launch_intent"):
                raise PermissionError("synthetic post-launch gate write failure")
            return self.atomic(path, value, limit)

        def query_exact_job(name):
            self.assertEqual(name, JOB_NAME)
            job_queries.append({"job_name": name, "remaining_owned_processes": active[0]})
            if launched.is_set() and recover.is_set() and active[0] == 0:
                zero_proof.set()
            return active[0]

        collector = FirstCollector()
        first = Monitor(self.root, collectors=collector)
        collector.monitor = first
        first_error, first_result, second_result, recovery_result = None, None, None, None
        with patch.object(runtime_module, "atomic_json", side_effect=fail_finish_write), \
                patch.object(processes, "current_job_active", side_effect=query_exact_job):
            try:
                try:
                    first_result = first.run(max_cycles=1)
                except (OSError, ValueError, RuntimeError) as error:
                    first_error = type(error).__name__
                second_result = Monitor(self.root, collectors=self.safe_collector(second_calls)).run(max_cycles=1)
            finally:
                # Resolve only the fake recorded Job, then use the normal
                # independent entry point to release any retained real lease.
                recover.set()
                active[0] = 0
                finish_write_fault.clear()
                recovery_result = Monitor(self.root, collectors=self.safe_collector(recovery_calls)).run(max_cycles=1)
                # The original client retains responsibility for its Runner
                # handles; another client must not adopt that Runner.
                collector.runner.shutdown(grace=0)
        probe = InstanceLock(self.runtime)
        try:
            acquired = probe.acquire()
        finally:
            probe.release()
        self.assertEqual(admissions, [True], "Monitor must bind the actual Runner subclass to durable launch admission")
        self.assertTrue(launched.is_set())
        self.assertEqual(second_calls, [], "a second client cannot collect while the original query exit is unknown")
        self.assertTrue(any(row["remaining_owned_processes"] == 1 for row in job_queries))
        self.assertTrue(zero_proof.is_set())
        self.assertTrue(any(row["grace"] == 0 and row["zero_job_proof_observed"] for row in shutdown_calls))
        self.assertEqual(len(recovery_calls), 7)
        self.assertEqual(recovery_result["state"], "stopped")
        self.assertTrue(acquired, "fixture teardown must not leave a retained monitor lease")
        self.evidence = {"scope": "real Monitor and OS file leases, fake recorded query Job; not real child or inventory",
            "first_result": first_result, "first_error": first_error, "second_result": second_result,
            "first_fixture_sources": first_calls, "second_fixture_sources": second_calls,
            "recovery_fixture_sources": recovery_calls, "job_queries": job_queries,
            "runner_shutdown_calls": shutdown_calls, "final_lease_available": acquired,
            "children_started": 0, "model_calls": 0, "machine_scan_executed": False}

    def test_launch_intent_write_failure_prevents_query_body(self):
        calls, admissions, bodies = [], [], []
        test = self
        class FakeOwnedRunner(Runner):
            def __init__(self):
                super().__init__(popen_factory=lambda *args, **kwargs: test.fail("fake Runner cannot spawn"))

            @property
            def pending(self):
                return False

            @property
            def last_process(self):
                return {}

        class Collector:
            def __init__(self):
                self.runner = FakeOwnedRunner()

            def collect(self, source, cancel=None):
                calls.append(source)
                admission = getattr(self.runner, "admission", None)
                admissions.append(callable(admission))
                with admission(JOB_NAME) if callable(admission) else nullcontext():
                    bodies.append(source)
                return test.section(source)

        def reject_launch(path, value, limit=65536):
            if Path(path).name == "monitor-shutdown-gate.json":
                raise PermissionError("synthetic launch intent storage failure")
            return self.atomic(path, value, limit)

        with patch.object(runtime_module, "atomic_json", side_effect=reject_launch):
            result = Monitor(self.root, collectors=Collector()).run(max_cycles=1)
        self.assertTrue(calls)
        self.assertTrue(all(admissions), "each managed-query collector needs the same admission hook")
        self.assertEqual(bodies, [], "a failed durable launch plan cannot enter the query body")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["model_calls"], 0)
        self.evidence = {"scope": "Monitor/OS file lease and failing launch-plan file with fake Runner body",
            "source_calls": calls, "query_bodies_entered": bodies, "result": result,
            "children_started": 0, "model_calls": 0, "machine_scan_executed": False}

    @unittest.skipUnless(os.name == "nt", "Windows managed Runner launch contract")
    def test_managed_runner_admission_failure_occurs_before_spawn(self):
        # Construct before patching Popen so the production managed-factory
        # identity is retained; spawn itself is forbidden and independently spied.
        managed = Runner(popen_factory=runner_module.ORIGINAL_POPEN)
        admissions = []
        def admission(job_name):
            admissions.append(job_name)
            return self.runtime.query_launch(job_name, namespace="live")
        managed.admission = admission

        def reject_launch(path, value, limit=65536):
            if Path(path).name == "monitor-shutdown-gate.json":
                raise PermissionError("synthetic launch plan failure")
            return self.atomic(path, value, limit)

        with patch.object(runtime_module, "atomic_json", side_effect=reject_launch), \
                patch.object(runner_module, "spawn", side_effect=AssertionError("spawn must not precede durable admission")) as spawn:
            result = managed.run("STATIC FIXTURE", timeout=.1, source_id="defender")
        self.assertEqual(len(admissions), 1)
        spawn.assert_not_called()
        self.assertNotEqual(result["status"], "ok")
        self.assertFalse(managed.pending)
        self.evidence = {"scope": "real managed Runner with failed durable launch admission; no spawn",
            "admission_job_names": admissions, "result": result, "children_started": 0,
            "model_calls": 0, "machine_scan_executed": False}

    @unittest.skipUnless(os.name == "nt", "Windows managed Runner launch contract")
    def test_failed_spawn_preserves_intent_until_missing_job_recovery_is_durable(self):
        managed = Runner(popen_factory=runner_module.ORIGINAL_POPEN,
                         admission=lambda name: self.runtime.query_launch(name, namespace="live"))
        with patch.object(runner_module, "spawn", side_effect=FileNotFoundError("synthetic missing query executable")) as spawn:
            result = managed.run("STATIC FIXTURE", timeout=.1, source_id="defender")
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(result["status"], "not_applicable")
        self.assertFalse(managed.pending)
        marker = self.root / "data/monitor-shutdown-gate.json"
        planned = json.loads(marker.read_text(encoding="utf-8"))
        self.assertEqual(planned["phase"], "launch_intent")
        self.assertEqual(planned["process"]["job_name"], spawn.call_args.kwargs["job_name"])
        missing = FileNotFoundError("synthetic planned private Job missing")
        missing.winerror = 2
        with patch.object(processes, "current_job_active", side_effect=missing) as query:
            recovered = self.runtime.monitor_shutdown_gate(recover=True)
        query.assert_called_once_with(planned["process"]["job_name"])
        self.assertEqual(recovered["state"], "clear")
        self.assertFalse(marker.exists())
        saved = json.loads((self.root / "data/monitor-shutdown-recovered.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["previous"], planned)
        self.assertEqual(saved["verification"]["remaining_owned_processes"], 0)
        self.evidence = {"scope": "managed Runner failed-spawn mock and fake missing-Job recovery; no child",
            "result": result, "planned": planned, "recovery": recovered, "children_started": 0,
            "model_calls": 0, "machine_scan_executed": False}

    @unittest.skipUnless(os.name == "nt", "Windows managed Runner bookkeeping contract")
    def test_admission_release_failure_after_spawn_retains_owned_child_for_same_runner_cleanup(self):
        spawned, admissions, reported = [], [], []
        class FakeManagedChild:
            pid = 4343
            created_at = CREATED

            def __init__(self):
                self.job = SimpleNamespace(name=None)

        class InlineWatcher:
            def __init__(self, *, target, args, daemon):
                self.target, self.args = target, args

            def start(self):
                self.target(*self.args)

        @contextmanager
        def failed_release(name):
            admissions.append(name)
            yield
            raise runtime_module.QueryAdmissionError("query_admission_release_unconfirmed")

        child = FakeManagedChild()
        def fake_spawn(argv, **kwargs):
            child.job.name = kwargs["job_name"]
            spawned.append({"pid": child.pid, "job_name": child.job.name})
            return child

        managed = Runner(popen_factory=runner_module.ORIGINAL_POPEN, admission=failed_release,
                         evidence_sink=reported.append)
        confirmed = {"managed": True, "child_exited": True, "remaining_owned_processes": 0,
                     "exit_code": 0, "forcibly_terminated": False, "reason": "fixture_owned_child_exit"}
        with patch.object(runner_module, "JobPopen", FakeManagedChild), \
                patch.object(runner_module, "spawn", side_effect=fake_spawn), \
                patch.object(runner_module.threading, "Thread", InlineWatcher), \
                patch.object(Runner, "_watch", side_effect=lambda job: job["done"].set()), \
                patch.object(runner_module, "finish", return_value=confirmed) as finish:
            result = managed.run("STATIC FIXTURE", timeout=.1, source_id="defender")
            self.assertEqual(result["note"], "query_admission_release_unconfirmed")
            self.assertEqual(len(spawned), 1)
            self.assertEqual(admissions, [child.job.name])
            self.assertTrue(reported[0]["process_started"])
            self.assertEqual(reported[0]["pid"], child.pid)
            self.assertTrue(result["process"]["managed"])
            self.assertEqual(result["process"]["pid"], child.pid)
            self.assertIs(managed._active["child"], child)
            self.assertTrue(managed.pending, "release failure cannot discard the child that already spawned")
            receipt = managed.shutdown(grace=0)
            self.assertFalse(managed.pending)
        finish.assert_called_once_with(child, "cancelled", grace=0)
        self.assertTrue(receipt["child_exited"])
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.evidence = {"scope": "actual Runner with fake managed spawn callback/child and inline watcher; no OS child",
            "spawn_callback_executed": spawned, "process_started_as_reported": reported[0]["process_started"],
            "launch_result": result, "same_runner_shutdown_receipt": receipt,
            "actual_os_children_started": 0, "model_calls": 0, "machine_scan_executed": False}

    def test_long_interval_admission_rejection_does_not_charge_interval_or_clear_baseline(self):
        class VirtualClock:
            def __init__(self):
                self.now = 21600.0

            def __call__(self):
                return self.now

            def wait(self, seconds):
                self.now += seconds

        seed = self.section("services")
        seed["rows"] = [{"name": "fixture.service", "state": "Stopped", "start_mode": "Manual", "status": "ok"}]
        state, events = evaluate([seed], host_id=self.runtime.identity(), now=1000)
        store = EventStore(self.root / "data/live")
        store.commit_evaluation(state, events)
        baseline = copy.deepcopy(state["baselines"])
        initial_ids = {event["event_id"] for event in events}
        attempts, actual_fixture_reads = [], []
        blocked, clock, test = [True], VirtualClock(), self
        class Collector:
            runner = None

            def collect(self, source, cancel=None):
                attempts.append({"source": source, "at": clock(), "admission_blocked": blocked[0]})
                if blocked[0]:
                    return {"id": source, "status": "busy", "rows": [],
                        "observed_at": "2026-10-23T00:00:00+00:00", "coverage": {"status": "busy",
                            "errors": [{"stage": "policy", "reason_code": "query_admission_busy"}]}}
                actual_fixture_reads.append(source)
                return test.section(source)

        first = Monitor(self.root, collectors=Collector(), clock=clock, wait=clock.wait)
        first.last = {name: clock() for name in ("defender", "listeners", "processes", "startup", "services", "tasks")}
        first.last["versions"] = 0.0
        rejected = first.run(max_cycles=1)
        self.assertEqual(attempts, [{"source": "versions", "at": 21600.0, "admission_blocked": True}])
        self.assertEqual(first.last["versions"], 0.0)
        self.assertEqual(first.not_before["versions"], 21605.0)
        self.assertEqual(rejected["stop_reason"], "persistence_backpressure")
        self.assertEqual(rejected["last_error"], "query_admission_blocked")
        self.assertEqual(store.load_detector_state()["baselines"], baseline)
        blocked[0] = False
        clock.wait(5)
        second = Monitor(self.root, collectors=Collector(), clock=clock, wait=clock.wait)
        second.last, second.not_before = dict(first.last), dict(first.not_before)
        recovered = second.run(max_cycles=1)
        self.assertEqual(actual_fixture_reads, ["versions"])
        self.assertEqual(second.last["versions"], 21605.0)
        self.assertEqual(self.runtime.config()["interval_seconds"]["versions"], 21600)
        self.assertEqual(store.load_detector_state()["baselines"], baseline)
        self.assertTrue(initial_ids <= {event["event_id"] for event in store.list_events()})
        self.assertEqual(recovered["model_calls"], 0)
        self.evidence = {"scope": "virtual-clock/injected source fixtures and real SQLite; no provider or elapsed-day claim",
            "source_attempts": attempts, "actual_fixture_reads": actual_fixture_reads,
            "configured_versions_interval": 21600, "retry_elapsed_seconds": 5,
            "baseline_preserved": True, "original_events_preserved": sorted(initial_ids),
            "rejected": rejected, "recovered": recovered, "children_started": 0,
            "model_calls": 0, "machine_scan_executed": False}

    def test_fallback_admission_rejection_after_native_attempt_keeps_actual_attempt_interval(self):
        seed = self.section("services")
        seed["rows"] = [{"name": "fixture.service", "state": "Stopped", "start_mode": "Manual", "status": "ok"}]
        state, events = evaluate([seed], host_id=self.runtime.identity(), now=1000)
        store = EventStore(self.root / "data/live")
        store.commit_evaluation(state, events)
        baseline = copy.deepcopy(state["baselines"])
        initial_ids, calls = {event["event_id"] for event in events}, []
        native_process = {"managed": True, "pid": 4343, "created_at": CREATED,
            "job_name": JOB_NAME, "child_exited": True, "remaining_owned_processes": 0,
            "forcibly_terminated": False}
        class Collector:
            runner = None

            def collect(self, source, cancel=None):
                calls.append(source)
                return {"id": source, "status": "busy", "rows": [],
                    "observed_at": "2026-10-23T00:00:00+00:00", "coverage": {"status": "busy", "process": {},
                        "errors": [{"stage": "policy", "reason_code": "query_admission_busy"}],
                        "attempts": [{"backend": "native", "status": "not_applicable", "process": native_process,
                                      "errors": [{"stage": "launch", "reason_code": "api_unavailable"}]},
                                     {"backend": "powershell", "status": "busy", "process": {},
                                      "errors": [{"stage": "policy", "reason_code": "query_admission_busy"}]}]}}

        monitor = Monitor(self.root, collectors=Collector(), clock=lambda: 21600.0)
        monitor.last = {name: 21600.0 for name in ("defender", "listeners", "processes", "startup", "services", "tasks")}
        monitor.last["versions"] = 0.0
        result = monitor.run(max_cycles=1)
        self.assertEqual(calls, ["versions"])
        self.assertEqual(monitor.last["versions"], 21600.0,
                         "an earlier native attempt cannot disappear when fallback admission is rejected")
        self.assertNotIn("versions", monitor.not_before)
        self.assertNotEqual(result.get("stop_reason"), "persistence_backpressure")
        self.assertNotEqual(result.get("last_error"), "query_admission_blocked")
        self.assertEqual(result["coverage"]["versions"]["attempts"][0]["process"]["pid"], 4343)
        self.assertEqual(store.load_detector_state()["baselines"], baseline)
        self.assertTrue(initial_ids <= {event["event_id"] for event in store.list_events()})
        self.evidence = {"scope": "injected multi-attempt source metadata/virtual clock and real SQLite; no actual OS child",
            "source_fixture_calls": calls, "recorded_attempt_started_at": monitor.last["versions"],
            "baseline_preserved": True, "original_event_ids_preserved": sorted(initial_ids),
            "result": result, "actual_os_children_started": 0, "model_calls": 0,
            "machine_scan_executed": False}

    @unittest.skipUnless(os.name == "nt", "Windows default managed-Runner admission wiring")
    def test_default_monitor_collectors_and_runner_reach_durable_admission_before_spawn(self):
        from eventguard.collectors.windows import WindowsCollectors
        from eventguard.collectors.worker import NativeWorker
        admissions, backend_calls, rejected_plans = [], [], []
        original_launch = Runtime.query_launch
        def record_launch(runtime, job_name, **kwargs):
            admissions.append({"job_name": job_name, "namespace": kwargs.get("namespace"),
                               "instance_id": kwargs.get("instance_id")})
            return original_launch(runtime, job_name, **kwargs)

        def fixture_backend(worker, source, cancel=None, progress=None):
            backend_calls.append(source)
            raw = worker.runner.run("STATIC SYNTHETIC WORKER", timeout=.1, cancel=cancel,
                progress=progress, source_id=source, _argv=[sys.executable, "-B", "-c", "print('{}')"])
            return {"status": raw["status"], "rows": [], "errors": raw.get("errors", []),
                    "process": raw.get("process", {})}

        def reject_plan(path, value, limit=65536):
            if Path(path).name == "monitor-shutdown-gate.json" and value.get("phase") == "launch_intent":
                rejected_plans.append(copy.deepcopy(value))
                raise PermissionError("synthetic production-wiring launch plan failure")
            return self.atomic(path, value, limit)

        # Use the production constructor and its default Runner factory. The
        # sole backend body is fixed synthetic code, and spawn is forbidden.
        monitor = Monitor(self.root, clock=lambda: 21600.0)
        monitor.last = {source: 21600.0 for source in ("defender", "listeners", "processes", "startup", "services", "tasks")}
        monitor.last["versions"] = 0.0
        with patch.object(subprocess, "Popen", runner_module.ORIGINAL_POPEN), \
                patch.object(Runtime, "query_launch", record_launch), \
                patch.object(NativeWorker, "collect", fixture_backend), \
                patch.object(runtime_module, "atomic_json", side_effect=reject_plan), \
                patch.object(runner_module, "spawn", side_effect=AssertionError("no provider or fixture process may spawn")) as spawn:
            result = monitor.run(max_cycles=1)
        self.assertIs(type(monitor.collectors), WindowsCollectors)
        self.assertIs(type(monitor.collectors.native), NativeWorker)
        self.assertIs(type(monitor.collectors.runner), Runner)
        self.assertEqual(backend_calls, ["versions"])
        self.assertEqual(len(admissions), 1)
        self.assertEqual(admissions[0]["namespace"], "live")
        self.assertRegex(admissions[0]["instance_id"], r"^[a-f0-9]{32}$")
        self.assertEqual(len(rejected_plans), 1)
        self.assertEqual(rejected_plans[0]["process"]["job_name"], admissions[0]["job_name"])
        spawn.assert_not_called()
        self.assertEqual(monitor.last["versions"], 0.0)
        self.assertEqual(monitor.not_before["versions"], 21605.0)
        self.assertEqual(result["stop_reason"], "persistence_backpressure")
        self.assertEqual(result["last_error"], "query_admission_blocked")
        self.evidence = {"scope": "production Monitor/WindowsCollectors/Runner constructors and Runtime hook with fixed backend body; no native provider",
            "backend_fixture_calls": backend_calls, "runtime_launch_admissions": admissions,
            "rejected_launch_plans": rejected_plans, "result": result, "children_started": 0,
            "model_calls": 0, "machine_scan_executed": False}

    def test_plan_lease_prevents_other_client_recovery_and_recovery_write_failure_keeps_gate(self):
        active, job_queries = [0], []
        other = Runtime(self.root)
        gate_path = self.root / "data/monitor-shutdown-gate.json"
        recovery_path = self.root / "data/monitor-shutdown-recovered.json"

        def exact_job_active(name):
            self.assertEqual(name, JOB_NAME)
            job_queries.append({"job_name": name, "remaining_owned_processes": active[0]})
            return active[0]

        def reject_recovery(path, value, limit=65536):
            if Path(path).name == "monitor-shutdown-recovered.json":
                raise PermissionError("synthetic recovery evidence write failure")
            return self.atomic(path, value, limit)

        with patch.object(processes, "current_job_active", side_effect=exact_job_active):
            with self.runtime.query_launch(JOB_NAME, namespace="live"):
                planned = gate_path.read_bytes()
                self.assertEqual(json.loads(planned)["phase"], "launch_intent")
                blocked_during_plan = other.monitor_shutdown_gate(recover=True)
                self.assertNotEqual(blocked_during_plan["state"], "clear")
                self.assertEqual(gate_path.read_bytes(), planned,
                                 "a second client cannot clear a planned Job before the first client spawns it")
                self.assertEqual(job_queries, [], "the live admission lease must serialize recovery before probing the planned Job")
                try:
                    replacement_during_plan = other.block_monitor_shutdown({"namespace": "live",
                        "query_shutdown": {"managed": True, "job_name": "Global\\EventGuard-" + "e" * 32,
                            "child_exited": False, "remaining_owned_processes": 1}})
                except (OSError, ValueError, RuntimeError) as error:
                    replacement_during_plan = {"error_type": type(error).__name__}
                self.assertEqual(gate_path.read_bytes(), planned,
                                 "another client cannot replace a live launch intent")
                active[0] = 1
            blocked_active = other.monitor_shutdown_gate(recover=True)
            self.assertNotEqual(blocked_active["state"], "clear")
            self.assertEqual(job_queries[-1]["remaining_owned_processes"], 1)
            self.assertTrue(gate_path.exists())
            active[0] = 0
            with patch.object(runtime_module, "atomic_json", side_effect=reject_recovery):
                failed_recovery = other.monitor_shutdown_gate(recover=True)
            self.assertNotEqual(failed_recovery["state"], "clear")
            self.assertTrue(gate_path.exists(), "an empty Job without durable recovery evidence cannot clear admission")
            self.assertFalse(recovery_path.exists())
            recovered = other.monitor_shutdown_gate(recover=True)
        self.assertEqual(recovered["state"], "clear")
        self.assertFalse(gate_path.exists())
        saved = json.loads(recovery_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["previous"]["process"]["job_name"], JOB_NAME)
        self.assertEqual(saved["verification"]["remaining_owned_processes"], 0)
        self.evidence = {"scope": "real shared admission file lease with fake Job state; no process launch",
            "blocked_during_plan": blocked_during_plan, "replacement_during_plan": replacement_during_plan,
            "blocked_while_job_active": blocked_active, "failed_recovery": failed_recovery,
            "recovered": recovered, "job_queries": job_queries, "children_started": 0,
            "model_calls": 0, "machine_scan_executed": False}


@unittest.skipUnless(os.name == "nt", "Windows owned helper Job and cross-process file lease")
class QueryAdmissionOwnerExitTests(unittest.TestCase):
    """Finite private-Job helpers, with fixed synthetic code only."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.child, self.stderr = None, None
        self.addCleanup(self.cleanup_child)

    def cleanup_child(self):
        try:
            if self.child is not None:
                if self.child.stdin is not None and not self.child.stdin.closed:
                    self.child.stdin.close()
                receipt = processes.finish(self.child, "test_teardown", grace=10)
                self.assertFalse(receipt["forcibly_terminated"], receipt)
                self.assertEqual(receipt["remaining_owned_processes"], 0)
        finally:
            if self.stderr is not None:
                self.stderr.close()

    def test_owner_exit_releases_lease_but_keeps_launch_intent_until_missing_job_proof(self):
        planned_job = "Global\\EventGuard-" + uuid.uuid4().hex
        ready = self.root / "plan-ready.json"
        entry = self.root / "plan-owner.py"
        entry.write_text("import os,sys\nfrom pathlib import Path\n"
            + "sys.path.insert(0," + repr(str(ROOT / "src")) + ")\n"
            + "from eventguard.runtime import Runtime,atomic_json\n"
            + "root=Path(sys.argv[1])\n"
            + "with Runtime(root).query_launch(sys.argv[2],namespace='live'):\n"
            + " atomic_json(root/'plan-ready.json',{'phase':'holding_launch_lease','pid':os.getpid(),'query_children_started':0})\n"
            + " sys.stdin.buffer.read(1)\n"
            + " os._exit(0)\n", encoding="utf-8")
        self.stderr = (self.root / "owner.stderr.txt").open("xb")
        self.child = processes.spawn([sys.executable, "-B", str(entry), str(self.root), planned_job],
            job_name="Global\\EventGuard-" + uuid.uuid4().hex,
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.stderr)
        until = time.monotonic() + 15
        while not ready.is_file() and self.child.poll() is None and time.monotonic() < until:
            time.sleep(.02)
        self.assertTrue(ready.is_file(), "one exact helper must publish readiness; observation expiry never starts another")
        ready_value = json.loads(ready.read_text(encoding="utf-8"))
        self.assertEqual(ready_value["pid"], self.child.pid)
        marker = self.root / "data/monitor-shutdown-gate.json"
        before = marker.read_bytes()
        runtime = Runtime(self.root)
        held = runtime.monitor_shutdown_gate(recover=True)
        self.assertNotEqual(held["state"], "clear")
        self.assertEqual(marker.read_bytes(), before)
        self.child.stdin.close()
        self.assertEqual(self.child.wait(timeout=15), 0)
        receipt = processes.finish(self.child, "descendants_remaining", grace=1)
        self.assertTrue(receipt["child_exited"])
        self.assertEqual(receipt["exit_code"], 0)
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.assertEqual(marker.read_bytes(), before, "the owner's OS exit must not erase its launch intent")
        probe_job, observations = processes.current_job_active, []
        def observe_missing(name):
            self.assertEqual(name, planned_job)
            try:
                count = probe_job(name)
            except OSError as error:
                observations.append({"job_name": name, "win32_error": getattr(error, "winerror", None)})
                raise
            observations.append({"job_name": name, "remaining_owned_processes": count})
            return count
        with patch.object(processes, "current_job_active", side_effect=observe_missing):
            recovered = runtime.monitor_shutdown_gate(recover=True)
        self.assertEqual(observations, [{"job_name": planned_job, "win32_error": 2}])
        self.assertEqual(recovered["state"], "clear")
        self.assertFalse(marker.exists())
        saved = json.loads((self.root / "data/monitor-shutdown-recovered.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["previous"]["phase"], "launch_intent")
        self.assertEqual(saved["previous"]["process"]["job_name"], planned_job)
        self.assertEqual(saved["verification"]["remaining_owned_processes"], 0)
        self.evidence = {"scope": "finite real Windows helper/private Job and cross-process file lease; no query/provider/model",
            "helper_ready": ready_value, "blocked_while_owner_alive": held, "helper_exit": receipt,
            "intent_sha256_before_and_after_owner_exit": hashlib.sha256(before).hexdigest(),
            "planned_job_missing_observations": observations, "recovery": recovered,
            "helper_children_started": 1, "query_children_started": 0,
            "machine_scan_executed": False, "model_calls": 0, "real_agent_woken": False}

    def test_other_runtime_recovery_reaps_exact_exited_owned_query_handle(self):
        runtime = Runtime(self.root)
        entry = self.root / "synthetic-query.py"
        entry.write_text("print('{\"status\":\"ok\",\"rows\":[]}')\n", encoding="utf-8")
        managed = Runner(admission=lambda name: runtime.query_launch(name, namespace="live"))
        spawn_real, unknown_finishes = runner_module.spawn, []

        def capture_spawn(*args, **kwargs):
            self.child = spawn_real(*args, **kwargs)
            return self.child

        def preserve_unknown(child, reason, grace=2, **kwargs):
            unknown_finishes.append({"pid": child.pid, "job_name": child.job.name,
                                     "actual_returncode": child.poll(), "reason": reason})
            return {"managed": True, "child_exited": None, "remaining_owned_processes": 0,
                    "forcibly_terminated": False, "reason": "synthetic_missing_exit_receipt"}

        with patch.object(runner_module, "spawn", side_effect=capture_spawn), \
                patch.object(runner_module, "finish", side_effect=preserve_unknown):
            result = managed.run("STATIC SYNTHETIC QUERY", timeout=10,
                                 _argv=[sys.executable, "-B", str(entry)], source_id="versions")
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(len(unknown_finishes), 1)
        self.assertEqual(self.child.poll(), 0)
        empty_started = time.monotonic()
        empty_deadline = empty_started + 3
        active = self.child.job.active()
        first_active, observations = active, 1
        while active != 0:
            remaining = empty_deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(.01, remaining))
            active = self.child.job.active()
            observations += 1
        empty_wait = {"configured_timeout_seconds": 3, "observation_count": observations,
            "elapsed_ms": round((time.monotonic() - empty_started) * 1000, 3),
            "initial_active_processes": first_active, "final_active_processes": active,
            "finish_or_force_used_during_observation": False}
        self.assertEqual(active, 0, empty_wait)
        self.assertIsNone(self.child.receipt, "the fixture must leave the original owned handle unreaped")
        self.assertTrue(managed.pending)
        self.assertIsNotNone(self.child.job.handle)
        recovered = Runtime(self.root).monitor_shutdown_gate(recover=True)
        self.assertEqual(recovered["state"], "clear")
        self.assertEqual(recovered["owned_handles_reaped"], 1)
        self.assertIsNone(self.child.job.handle)
        self.assertFalse(managed.pending)
        self.assertTrue(managed.last_process["child_exited"])
        self.assertEqual(managed.last_process["remaining_owned_processes"], 0)
        self.assertTrue(self.child.receipt["child_exited"])
        self.assertEqual(self.child.receipt["exit_code"], 0)
        self.assertFalse(self.child.receipt["forcibly_terminated"])
        self.assertEqual(self.child.receipt["remaining_owned_processes"], 0)
        self.evidence = {"scope": "one real Windows synthetic Python query/private Job; injected missing receipt, no inventory/model",
            "query_result_before_recovery": result, "injected_unknown_finish": unknown_finishes,
            "natural_job_empty_observation": empty_wait,
            "other_runtime_recovery": recovered, "original_child_exit_receipt": self.child.receipt,
            "runner_pending_after_recovery": managed.pending, "last_process_after_recovery": managed.last_process,
            "synthetic_query_children_started": 1, "machine_scan_executed": False,
            "model_calls": 0, "real_agent_woken": False}


if __name__ == "__main__":
    unittest.main()
