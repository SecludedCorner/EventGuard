"""Real ordinary-token Windows jobs + separately labelled gap fixtures. No model."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import json
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from eventguard.processes import spawn, finish, remaining_owned, identity, Job, JobError
from eventguard.collectors.runner import Runner
from eventguard.collectors.worker import NativeWorker
from eventguard.collectors.windows import WindowsCollectors
from eventguard.acceptance_process import capture
from eventguard.runtime import Runtime, InstanceLock, atomic_json
from eventguard.monitor import Monitor
from eventguard.monitor_gap import prepare, persist
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic

ROOT = Path(__file__).resolve().parents[1]


class FixtureRoot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("config/default.json", "tests/fixtures/normal.json"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)


@unittest.skipUnless(os.name == "nt", "real Windows Job Object tests; not Linux support")
class JobTests(FixtureRoot):
    def setUp(self):
        super().setUp()
        self.children = []

    def tearDown(self):
        for child in self.children:
            finish(child, "test_teardown", grace=.1, request_stop=False)
            for pipe in (child.stdin, child.stdout, child.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()
        self.assertEqual(remaining_owned(), 0, "managed test children must not remain")

    def child(self, source, **kwargs):
        child = spawn([sys.executable, "-B", "-c", source], **kwargs)
        self.children.append(child)
        return child

    def assert_identity_exited(self, before):
        self.assertIsInstance(before.get("created_at"), str, "record the owned identity before stopping it")
        until = time.monotonic() + 3
        observations = 0
        while True:
            current = identity(before["pid"])
            observations += 1
            reused = (isinstance(current.get("created_at"), str)
                      and current["created_at"] != before["created_at"])
            if current["state"] in {"missing", "exited"} or reused:
                return {"last_identity": current, "pid_reused": reused, "observations": observations}
            if time.monotonic() >= until:
                self.fail("original owned PID+creation time did not confirm exit within 3 seconds")
            time.sleep(.01)

    def test_exit_check_handles_signalling_lag_and_pid_reuse_without_signals(self):
        before = {"pid": 123, "created_at": "fixture-original", "state": "alive"}
        with patch(__name__ + ".identity", side_effect=[before, {**before, "state": "exited"}]):
            self.assertEqual(self.assert_identity_exited(before)["observations"], 2)
        with patch(__name__ + ".identity", return_value={**before, "created_at": "fixture-reused"}):
            self.assertTrue(self.assert_identity_exited(before)["pid_reused"])

    def test_real_job_normal_stdio_identity_and_natural_exit(self):
        child = self.child('import sys; print("stdout-fixture"); print("stderr-fixture",file=sys.stderr)', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, errors = child.communicate(timeout=5)
        receipt = finish(child, grace=.2)
        self.assertEqual(output.strip(), b"stdout-fixture")
        self.assertEqual(errors.strip(), b"stderr-fixture")
        self.assertTrue(receipt["child_exited"])
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.assertTrue(receipt["created_at"])
        self.evidence = {"scope": "real_windows_job", "case": "natural_exit", "receipt": receipt}

    def test_job_terminates_its_grandchild_and_leaves_other_job_sentinel_alive(self):
        sentinel = self.child("import sys;sys.stdin.read()", stdin=subprocess.PIPE)
        try:
            child = self.child('import subprocess,sys,time;p=subprocess.Popen([sys.executable,"-B","-c","import time;time.sleep(60)"]);print(p.pid,flush=True);time.sleep(60)', stdout=subprocess.PIPE)
            grandchild = int(child.stdout.readline())
            before = identity(grandchild)
            self.assertGreaterEqual(child.job.active(), 2)
            receipt = finish(child, "timeout", grace=.05)
            self.assertTrue(receipt["forcibly_terminated"])
            self.assertTrue(receipt["child_exited"])
            self.assertEqual(receipt["remaining_owned_processes"], 0)
            self.assertIsNone(sentinel.poll(), "terminating our job must not affect the sibling sentinel")
            observed = self.assert_identity_exited(before)
            self.evidence = {"scope": "real_windows_job", "case": "descendant_timeout", "receipt": receipt, "sentinel_outside_target_job_alive": True,
                             "owned_descendant_before": before, "exit_observation": observed}
        finally:
            sentinel.stdin.close()
            sentinel.wait(timeout=5)

    def test_nested_managed_job_is_included_in_ancestor_cleanup(self):
        source = 'import sys,time;sys.path.insert(0,sys.argv[1]);from eventguard.processes import spawn;p=spawn([sys.executable,"-B","-c","import time;time.sleep(60)"]);print(p.pid,flush=True);time.sleep(60)'
        child = spawn([sys.executable, "-B", "-c", source, str(ROOT / "src")], stdout=subprocess.PIPE)
        self.children.append(child)
        pid = int(child.stdout.readline())
        before = identity(pid)
        self.assertGreaterEqual(child.job.active(), 2)
        receipt = finish(child, "timeout", grace=.05)
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.assert_identity_exited(before)

    def test_owner_exit_closes_private_job_and_cleans_descendant(self):
        source = 'import sys,os,json;sys.path.insert(0,sys.argv[1]);from eventguard.processes import spawn;p=spawn([sys.executable,"-B","-c","import time;time.sleep(60)"]);print(json.dumps({"pid":p.pid,"created_at":p.created_at}),flush=True);sys.stdout.flush();os._exit(17)'
        child = spawn([sys.executable, "-B", "-c", source, str(ROOT / "src")], stdout=subprocess.PIPE)
        self.children.append(child)
        before = json.loads(child.stdout.readline())
        self.assertEqual(child.wait(timeout=5), 17)
        until = time.monotonic()+3
        while child.job.active() and time.monotonic() < until:
            time.sleep(.01)
        self.assertEqual(child.job.active(), 0, "Inner owner death must close its noninherited job handle")
        receipt = finish(child, grace=0)
        self.assertFalse(receipt["forcibly_terminated"], "Outer guardian did not need forced cleanup")
        self.assert_identity_exited(before)
        self.evidence = {"scope": "real_windows_job_synthetic_owner_exit_not_live_monitor_crash", "case": "kill_on_job_close", "outer_receipt": receipt, "owned_descendant_exited": True}

    def test_existing_named_job_is_refused_without_modifying_it(self):
        import uuid
        name = "Local\\EventGuard-" + uuid.uuid4().hex
        job = Job(name)
        try:
            with self.assertRaisesRegex(JobError, "already_exists"):
                Job(name)
            self.assertEqual(job.active(), 0)
        finally:
            job.close()

    def test_runner_timeout_is_bounded_and_records_job_exit(self):
        runner = Runner()
        tick = time.monotonic()
        result = runner.run("synthetic-worker", timeout=.05, _argv=[sys.executable, "-B", "-c", "import time;time.sleep(60)"])
        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["process"]["forcibly_terminated"])
        self.assertTrue(result["process"]["child_exited"])
        self.assertFalse(runner.pending)
        self.assertLess(time.monotonic()-tick, 8)
        self.evidence = {"scope": "real_windows_job_synthetic_query", "case": "runner_timeout", "result": result}

    def test_default_native_worker_entry_reads_only_fixed_python_version(self):
        result = WindowsCollectors(backend="native").collect("versions")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["rows"]), 1)
        receipt = result["coverage"]["process"]
        self.assertTrue(receipt["managed"])
        self.assertTrue(receipt["child_exited"])
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.evidence = {"scope": "real_windows_worker_fixed_python_version_only_not_inventory_scan", "case": "native_worker_entry", "coverage": result["coverage"], "row_count": len(result["rows"])}

    def test_monitor_duration_deadline_cancels_hanging_fixture_query(self):
        entry = self.root / "hanging-fixture.py"
        entry.write_text("import time;time.sleep(60)", encoding="utf-8")
        collector = WindowsCollectors(native=NativeWorker(timeout=15, entry=entry), backend="native")
        collector.runner = collector.native.runner
        tick = time.monotonic()
        result = Monitor(self.root, collectors=collector).run(max_seconds=1)
        self.assertEqual(result["stop_reason"], "duration_limit")
        self.assertTrue(result["query_shutdown"]["forcibly_terminated"])
        self.assertEqual(result["query_shutdown"]["remaining_owned_processes"], 0)
        self.assertLess(time.monotonic()-tick, 8)

    def test_cancelled_native_worker_monitor_stops_and_releases_singleton(self):
        entry = self.root / "hanging-fixture.py"
        entry.write_text("import time;time.sleep(60)", encoding="utf-8")
        collector = WindowsCollectors(native=NativeWorker(timeout=15, entry=entry), backend="native")
        # Use the same controlled worker runner for the monitor's cleanup view.
        collector.runner = collector.native.runner
        monitor = Monitor(self.root, collectors=collector)
        results = []
        thread = threading.Thread(target=lambda: results.append(monitor.run(max_cycles=1)))
        thread.start()
        try:
            until = time.monotonic()+5
            while not collector.runner.pending and time.monotonic() < until:
                time.sleep(.01)
            self.assertTrue(collector.runner.pending)
            Runtime(self.root).request_stop()
        finally:
            thread.join(8)
            if thread.is_alive():
                monitor.cancel.set()
                collector.runner.shutdown(.1)
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]["state"], "stopped")
        receipt = results[0]["query_shutdown"]
        self.assertTrue(receipt["forcibly_terminated"])
        self.assertEqual(receipt["reason"], "cancelled")
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        lock = InstanceLock(Runtime(self.root))
        self.assertTrue(lock.acquire(), "Stop must release the singleton only after query exit")
        lock.release()
        self.assertEqual(remaining_owned(), 0)
        self.evidence = {"scope": "real_windows_job_hanging_fixture_not_provider", "case": "monitor_stop", "state": results[0]["state"], "remaining_owned": 0, "query_shutdown": receipt}

    def test_capture_timeout_with_blocked_stdin_has_exit_receipt(self):
        code = capture([sys.executable, "-B", "-c", "import time;time.sleep(60)"], self.root, "c"*32, "x"*262144, timeout_seconds=.1)
        result = json.loads((self.root / "capture-exit.json").read_text())
        self.assertEqual(code, 0, "capture completion is separate from child success")
        self.assertTrue(result["forcibly_terminated"])
        self.assertTrue(result["child_exited"])
        self.assertNotEqual(result["codex_exit_code"], 0)
        self.assertEqual(result["process"]["remaining_owned_processes"], 0)
        self.evidence = {"scope": "real_windows_job_synthetic_python_not_codex", "case": "capture_timeout", "receipt": result}

    def test_launch_job_failure_never_falls_back_to_uncontained_child(self):
        with patch.object(Job, "__init__", side_effect=JobError("synthetic_job_creation_failure")), patch("eventguard.processes.JobPopen._execute_child") as launch:
            with self.assertRaises(JobError):
                spawn([sys.executable, "-B", "-c", "pass"])
        launch.assert_not_called()

    def test_capture_start_receipt_failure_still_cleans_owned_tree(self):
        with patch("eventguard.acceptance_process.write_json", side_effect=OSError("synthetic filesystem failure")):
            self.assertEqual(capture([sys.executable, "-B", "-c", "import time;time.sleep(60)"], self.root, "d"*32, "fixture", timeout_seconds=.1), 2)
        self.assertEqual(remaining_owned(), 0)


class GapTests(FixtureRoot):
    def test_unconfirmed_owned_exit_is_never_reported_stopped(self):
        from types import SimpleNamespace
        for pending in (False, True):
            with self.subTest(pending=pending):
                receipt = {"managed": True, "child_exited": True, "remaining_owned_processes": 1, "forcibly_terminated": True}
                runner = SimpleNamespace(last_process=receipt, pending=pending, shutdown=lambda: receipt)
                monitor = Monitor(self.root, collectors=SimpleNamespace(runner=runner))
                health = {"state": "running", "namespace": "test", "heartbeat_at": datetime.now(timezone.utc).isoformat()}
                monitor._finish(health, 0, "test")
                self.assertEqual(health["state"], "shutdown_unconfirmed")
                self.assertFalse(health["monitoring"])
                self.assertFalse(health["healthy"])

    def checkpoint(self, **changes):
        current = identity()
        value = {"namespace": "test", "state": "running", "pid": current["pid"], "process_created_at": current["created_at"],
                 "instance_id": "a"*32, "heartbeat_at": (datetime.now(timezone.utc)-timedelta(seconds=120)).isoformat()}
        value.update(changes)
        atomic_json(Runtime(self.root).path("data/test/monitor-checkpoint.json"), value)
        return value

    def test_first_start_has_no_invented_gap(self):
        self.assertIsNone(prepare(Runtime(self.root), "test", "synthetic-host"))

    def test_stale_pid_reuse_denial_and_planned_stop_are_distinct(self):
        for reason, changes, owner in (
            ("heartbeat_stale", {}, {"state": "alive", "created_at": "2020-01-01T00:00:00+00:00"}),
            ("owner_identity_changed", {}, {"state": "alive", "created_at": "2021-01-01T00:00:00+00:00"}),
            ("owner_identity_unverifiable", {}, {"state": "denied", "created_at": None}),
            ("planned_monitor_interval", {"state": "stopped"}, {"state": "missing", "created_at": None}),
        ):
            Runtime(self.root).path("data/test/monitor-gap-pending.json").unlink(missing_ok=True)
            self.checkpoint(process_created_at="2020-01-01T00:00:00+00:00", **changes)
            result = prepare(Runtime(self.root), "test", "synthetic-host", inspect=lambda _: owner)
            self.assertEqual(result["evidence"]["reason"], reason)
            self.assertEqual(result["coverage"]["status"], "unknown")
            self.assertTrue(result["synthetic"])

    def test_gap_marker_replays_same_id_and_payload_until_durable_enqueue(self):
        self.checkpoint()
        runtime = Runtime(self.root)
        store = EventStore(runtime.data_dir("test"), max_events=1)
        pending = make_synthetic()
        store.enqueue(pending)
        original = prepare(runtime, "test", "synthetic-host")
        with self.assertRaises(RuntimeError):
            persist(runtime, "test", "synthetic-host", store)
        replay = prepare(runtime, "test", "synthetic-host")
        self.assertEqual(original, replay)
        store.acknowledge(pending["event_id"], {"ack_type": "receiver_persisted", "event_id": pending["event_id"], "receipt_id": "fixture-receipt"})
        receipt = persist(runtime, "test", "synthetic-host", store)
        self.assertEqual(receipt["event_id"], original["event_id"])
        self.assertEqual(store.get_event(original["event_id"])["delivery_status"], "pending")
        self.assertFalse(runtime.path("data/test/monitor-gap-pending.json").exists())
        self.evidence = {"scope": "metadata_and_sqlite_fixture_not_reboot", "case": "gap_full_queue_recovery", "same_event_id": True, "event": original}

    def test_fixture_monitor_emits_durable_gap_before_collection(self):
        self.checkpoint()
        result = Monitor(self.root).run(max_cycles=1, fixture="tests/fixtures/normal.json")
        events = EventStore(self.root / "data/test").list_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "monitor_gap")
        self.assertEqual(result["monitor_gap"]["event_id"], events[0]["event_id"])
        self.assertEqual(events[0]["delivery_status"], "pending")

    def test_invalid_checkpoint_is_unknown_gap_not_empty_success(self):
        runtime = Runtime(self.root)
        path = runtime.path("data/test/monitor-checkpoint.json")
        path.parent.mkdir(parents=True)
        path.write_text("not-json", encoding="utf-8")
        event = prepare(runtime, "test", "synthetic-host")
        self.assertEqual(event["evidence"]["reason"], "checkpoint_unreadable")

    def test_future_clock_and_namespace_mismatch_are_unknown_gaps(self):
        runtime = Runtime(self.root)
        for changes, reason in (({"heartbeat_at": (datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat()}, "heartbeat_clock_anomaly"),
                                ({"namespace": "live"}, "checkpoint_unreadable")):
            with self.subTest(reason=reason):
                runtime.path("data/test/monitor-gap-pending.json").unlink(missing_ok=True)
                self.checkpoint(**changes)
                event = prepare(runtime, "test", "synthetic-host")
                self.assertEqual(event["evidence"]["reason"], reason)
                self.assertEqual(event["coverage"]["status"], "unknown")

    def test_monitor_full_queue_blocks_collection_then_recovers_same_gap(self):
        runtime = Runtime(self.root)
        config = runtime.config()
        config["outbox"]["max_events"] = 1
        atomic_json(self.root / "config/default.json", config)
        self.checkpoint()
        store = EventStore(runtime.data_dir("test"), max_events=1)
        pending = make_synthetic()
        store.enqueue(pending)
        observed = []
        result = Monitor(self.root).run(max_cycles=1, fixture="tests/fixtures/normal.json", on_cycle=observed.append)
        self.assertEqual(result["state"], "blocked_monitor_gap")
        self.assertEqual(observed, [], "No query round may run while gap persistence is blocked")
        marker = json.loads(runtime.path("data/test/monitor-gap-pending.json").read_text())
        expected = marker["event"]["event_id"]
        self.assertEqual(store.get_event(pending["event_id"])["delivery_status"], "pending")
        store.acknowledge(pending["event_id"], {"ack_type": "receiver_persisted", "event_id": pending["event_id"], "receipt_id": "fixture-receipt"})
        recovered = Monitor(self.root).run(max_cycles=1, fixture="tests/fixtures/normal.json")
        self.assertEqual(recovered["monitor_gap"]["event_id"], expected)
        self.assertEqual(store.get_event(expected)["delivery_status"], "pending")
        self.evidence = {"scope": "fixture_monitor_sqlite_not_live_reboot", "case": "blocked_gap_recovery", "event_id": expected, "blocked_state": result["state"], "recovered_same_event_id": True}


class ScheduleTests(unittest.TestCase):
    def test_install_uninstall_only_print_candidate_and_execute_is_refused(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("eventguard_schedule", ROOT / "scripts/eventguard_schedule.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        main = module.main
        for args, code, status in ((["install"], 0, "dry_run"), (["uninstall", "--dry-run"], 0, "dry_run"), (["install", "--execute"], 2, "approval_required")):
            with self.subTest(args=args), redirect_stdout(io.StringIO()) as output, patch("subprocess.Popen") as launch:
                self.assertEqual(main(args), code)
                value = json.loads(output.getvalue())
                self.assertEqual(value["status"], status)
                self.assertFalse(value["executed"])
                launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
