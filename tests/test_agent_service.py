"""Isolated host/control fixtures. No real Codex, model, scheduler or service."""
from contextlib import closing
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from eventguard import agent_service as service
from eventguard.events.store import EventStore
from eventguard.runtime import atomic_json
from eventguard.synthetic import make_synthetic
from budget_fixtures import isolated_launch

_ADMISSION_BARRIER = service._admission_barrier


def _stop_test_hosts(root, children, evidence):
    """Even a failed control write must reap only the test's proven jobs."""
    evidence["teardown"] = []
    try:
        return service.stop(root, grace_seconds=5)
    finally:
        for child, job_name in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                receipt = service.processes.stop_persistent(job_name, pid=child.pid,
                    created_at=child.created_at, reason="test_teardown", grace=2)
                evidence["teardown"].append(receipt)
                child.wait(timeout=5)
            if isinstance(child, service.processes.JobPopen) and not child.detached:
                evidence.setdefault("retained_handle_exits", []).append(
                    service.processes.finish(child, "cancelled", grace=0, request_stop=False))
        evidence["child_exit_codes"] = [child.returncode for child, _ in children]


class AgentServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "data/test"
        self.source.mkdir(parents=True)
        self.store = EventStore(self.source)
        self.executable = self.root / "fixture-provider.exe"
        self.executable.write_bytes(b"mock: never execute")
        self.run_id = "a" * 32
        self.job = "Global\\EventGuard-" + "b" * 32
        self.created = "2026-10-24T00:00:00.000000+00:00"
        # The service has no daily quota. Reading the historical budget fails.
        self.enterContext(patch("eventguard.agent_budget.public_status",
                                side_effect=AssertionError("historical budget read")))
        self.enterContext(patch.object(service, "_admission_barrier", return_value={
            "admission_barrier": "unconfirmed", "admission_barrier_reason": "fixture_gate_not_exercised"}))

    def control(self, **changes):
        value = {"kind": service.KIND, "run_id": self.run_id, "job_name": self.job,
                 "enabled": True, "paused": False, "allow_live": False,
                 "updated_at": service._stamp(), "source_dir": str(self.source),
                 "state_dir": str(self.root / "data/agent-delivery-test"),
                 "codex_executable": str(self.executable)}
        value.update(changes)
        service._write(self.root, "control.json", value)
        return value

    def owner(self, **changes):
        value = {"kind": service.OWNER_KIND, "run_id": self.run_id, "job_name": self.job,
                 "pid": 1234, "created_at": self.created, "session_id": 1}
        value.update(changes)
        service._write(self.root, "owner.json", value)
        return value

    def start(self, **kwargs):
        with patch.object(service.importlib.util, "find_spec", return_value=object()):
            return service.start(self.root, self.executable, **kwargs)

    def test_absent_status_does_not_create_service_or_budget(self):
        result = service.status(self.root)
        self.assertEqual(result["state"], "not_started")
        self.assertFalse(result["desired_enabled"])
        self.assertEqual(result["model_calls"], 0)
        self.assertNotIn("budget", result)
        self.assertFalse((self.root / "data/agent-service").exists())
        self.assertFalse((self.root / "data/agent-budget").exists())

    def test_preflight_does_not_start_or_save_enabled(self):
        with patch.object(service.processes, "spawn_persistent") as spawn:
            result = self.start()
        self.assertEqual(result["state"], "preflight_ready")
        self.assertTrue(result["execute_required"])
        self.assertEqual(Path(result["source_dir"]), self.source)
        self.assertTrue(result["state_dir"].endswith("agent-delivery-test"))
        spawn.assert_not_called()
        self.assertFalse((self.root / "data/agent-service").exists())

    def test_preflight_missing_source_wrapper_and_live_test_root_are_refused(self):
        with patch.object(service.processes, "spawn_persistent") as spawn:
            result = self.start(source_dir=self.root / "not-an-event-source")
            self.assertEqual(result["reason"], "existing_event_source_required")
            wrapper = self.root / "codex.cmd"
            wrapper.write_text("never run", encoding="utf-8")
            result = service.start(self.root, wrapper)
            self.assertEqual(result["reason"], "native_codex_executable_required")
            result = self.start(allow_live=True)
            self.assertEqual(result["reason"], "agent_service_live_root_refused")
        spawn.assert_not_called()

    def test_separate_owned_state_required(self):
        self.assertEqual(self.start(state_dir=self.source)["reason"], "agent_service_scope_invalid")
        self.assertEqual(self.start(state_dir=self.source / "nested")["reason"], "agent_service_scope_invalid")
        self.assertEqual(self.start(state_dir=self.root.parent / "outside")["reason"], "agent_service_scope_invalid")

    def test_missing_sdk_blocks_execute_without_creating_host(self):
        with patch.object(service.processes, "spawn_persistent") as spawn, \
             patch.object(service.importlib.util, "find_spec", return_value=None):
            result = service.start(self.root, self.executable, execute=True)
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["capability_reasons"], ["missing_existing_mcp_sdk"])
        self.assertNotIn("budget", result)
        self.assertFalse((self.root / "data/agent-service").exists())
        spawn.assert_not_called()

    def test_preflight_has_no_daily_quota_wait_and_validates_run_task_bound(self):
        with patch.object(service.processes, "spawn_persistent") as spawn:
            result = self.start(max_tasks=1)
            self.assertEqual(result["state"], "preflight_ready")
            self.assertEqual(result["blocked_reasons"], [])
            self.assertEqual(result["capability_reasons"], [])
            self.assertIsNone(result["reason"])
            self.assertEqual(result["max_tasks"], 1)
            self.assertNotIn("budget", result)
            self.assertIsNone(self.start()["max_tasks"], "No bound means no daily cap")
            for limit in (0, 6, True, "1"):
                with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, "agent_service_task_limit_invalid"):
                    self.start(max_tasks=limit)
        spawn.assert_not_called()
        self.assertFalse((self.root / "data/agent-service").exists())

    def test_status_pending_includes_failed_attention_without_changing_events(self):
        self.control()
        events = [make_synthetic("listener") for _ in range(2)]
        for event in events:
            self.store.enqueue(event)
        with self.store._connect() as db:
            db.execute("UPDATE events SET delivery_status='failed' WHERE event_id=?", (events[0]["event_id"],))
        result = service.status(self.root)
        self.assertEqual(result["pending_events"], 2)
        self.assertEqual(result["ready_count"], 1)
        self.assertEqual(result["attention_count"], 1)

    def test_pause_and_resume_persist_without_cancelling_or_replacing_queue(self):
        self.control()
        event = make_synthetic("listener")
        self.store.enqueue(event)
        ledger = self.root / "data/agent-delivery-test/dispatcher-attempts.json"
        atomic_json(ledger, {"fixture": "existing ledger must remain"})
        before = ledger.read_bytes()
        with patch.object(service.agent_dispatch, "stop") as cancel, patch.object(service.processes, "stop_persistent") as terminate, \
             patch.object(service, "status", return_value={"host_liveness": "alive_verified", "state": "paused"}):
            self.assertEqual(service.pause(self.root)["state"], "pause_requested")
            self.assertTrue(service._control(self.root)["paused"])
            self.assertEqual(service.resume(self.root)["state"], "preflight_ready")
            self.assertTrue(service._control(self.root)["paused"])
            self.assertEqual(service.resume(self.root, execute=True)["state"], "resume_requested")
        cancel.assert_not_called()
        terminate.assert_not_called()
        self.assertFalse(service._control(self.root)["paused"])
        self.assertEqual(ledger.read_bytes(), before)
        self.assertEqual(self.store.get_event(event["event_id"])["delivery_status"], "pending")

    def test_resume_never_enables_stopped_or_missing_host(self):
        self.assertEqual(service.resume(self.root, execute=True)["reason"], "agent_service_explicit_start_required")
        self.control(enabled=False, paused=True)
        self.assertEqual(service.resume(self.root, execute=True)["reason"], "agent_service_explicit_start_required")
        self.assertFalse(service._control(self.root)["enabled"])

    def test_resume_refuses_enabled_control_without_a_live_host(self):
        self.control(paused=True)
        with patch.object(service.processes, "spawn_persistent") as spawn:
            result = service.resume(self.root, execute=True)
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reason"], "agent_service_host_not_running")
        self.assertTrue(service._control(self.root)["paused"])
        spawn.assert_not_called()

    def test_preflight_checks_original_channel_before_enabling(self):
        atomic_json(self.source / "agent-channel.json", {"kind": service.agent_dispatch.KIND,
                                                       "state_dir_sha256": "0" * 64})
        with patch.object(service.processes, "spawn_persistent") as spawn:
            result = self.start(execute=True)
        self.assertEqual(result["reason"], "dispatch_source_already_bound_to_other_state")
        self.assertFalse(service._path(self.root, "control.json").exists())
        spawn.assert_not_called()

    def test_preflight_checks_sqlite_and_existing_inbox_without_repairing(self):
        from eventguard.queue_inbox import QueueInbox
        state = self.root / "data/agent-delivery-test"
        QueueInbox(self.source, state)
        self.assertEqual(self.start()["state"], "preflight_ready")
        marker = state / "inbox-state.json"
        before = marker.read_bytes()
        marker.write_text("{}", encoding="utf-8")
        broken = marker.read_bytes()
        self.assertEqual(self.start()["state"], "blocked")
        self.assertEqual(marker.read_bytes(), broken)
        marker.write_bytes(before)
        source = self.source / "eventguard.sqlite3"
        source.write_bytes(b"not a SQLite database")
        self.assertEqual(self.start()["reason"], "event_source_unreadable")
        self.assertEqual(source.read_bytes(), b"not a SQLite database")

    def test_pause_is_saved_before_barrier_even_when_busy(self):
        self.control()
        def busy_barrier():
            self.assertTrue(service._control(self.root)["paused"])
            return {"admission_barrier": "unconfirmed", "admission_barrier_reason": "launch_gate_busy"}
        with patch.object(service, "_admission_barrier", side_effect=busy_barrier):
            result = service.pause(self.root)
        self.assertTrue(service._control(self.root)["paused"])
        self.assertEqual(result["admission_barrier"], "unconfirmed")
        self.assertEqual(result["admission_barrier_reason"], "launch_gate_busy")
        self.assertFalse(result["active_task_cancelled"])
        saved = service._read(self.root, "pause-receipt.json")
        self.assertEqual(saved["admission_barrier"], "unconfirmed")
        self.assertEqual(saved["run_id"], self.run_id)

    def test_pause_barrier_serializes_on_launch_gate_without_quota(self):
        with isolated_launch(self.root) as launch:
            result = _ADMISSION_BARRIER(wait_seconds=0)
            self.assertTrue(launch.gate_entered())
        self.assertEqual(result, {"admission_barrier": "confirmed",
                                  "admission_barrier_reason": "launch_gate_serialized"})

    def test_pause_barrier_keeps_busy_or_unavailable_gate_visible(self):
        from eventguard.acceptance_control import FileLease
        from eventguard.acceptance_process import LaunchGateError
        with isolated_launch(self.root) as launch:
            lease = FileLease(launch.lock)
            self.assertTrue(lease.acquire())
            try:
                busy = _ADMISSION_BARRIER(wait_seconds=0)
            finally:
                lease.release()
            for code, expected in (("launch_gate_unavailable", "launch_gate_unavailable"),
                                   ("fixture_unexpected", "launch_gate_unavailable")):
                with self.subTest(code=code), patch("eventguard.acceptance_process.launch_gate",
                                                    side_effect=LaunchGateError(code)):
                    result = _ADMISSION_BARRIER(wait_seconds=0)
                self.assertEqual(result, {"admission_barrier": "unconfirmed", "admission_barrier_reason": expected})
        self.assertEqual(busy, {"admission_barrier": "unconfirmed", "admission_barrier_reason": "launch_gate_busy"})

    def test_active_owner_is_not_restarted(self):
        self.control()
        self.owner()
        service._write(self.root, "run.json", {"run_id": self.run_id, "state": "waiting",
                        "heartbeat_at": service._stamp(), "model_calls": 0})
        with patch.object(service.processes, "identity", return_value={"state": "alive", "created_at": self.created}), \
             patch.object(service.processes, "process_session", return_value=1), \
             patch.object(service.processes, "spawn_persistent") as spawn:
            result = self.start(execute=True)
        self.assertEqual(result["reason"], "agent_service_already_running")
        spawn.assert_not_called()

    def test_unconfirmed_old_job_blocks_new_start(self):
        self.control()
        self.owner()
        with patch.object(service.processes, "identity", return_value={"state": "missing"}), \
             patch.object(service.processes, "current_job_active", return_value=1), \
             patch.object(service.processes, "spawn_persistent") as spawn:
            result = self.start(execute=True)
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reason"], "previous_agent_host_exit_unconfirmed")
        spawn.assert_not_called()

    def test_explicit_restart_after_blocked_host_exit_preserves_pending_and_ledger(self):
        from eventguard.queue_inbox import QueueInbox
        self.control()
        self.owner()
        event = make_synthetic("listener")
        self.store.enqueue(event)
        inbox = QueueInbox(self.source, self.root / "data/agent-delivery-test")
        ledger = inbox.state_dir / "dispatcher-attempts.json"
        ledger.write_bytes(b'{"kind":"retained-synthetic-ledger","events":{}}')
        before = ledger.read_bytes()
        service._write(self.root, "run.json", {"run_id": self.run_id, "state": "blocked",
            "reason": "dispatch_pending_payload_malformed", "model_calls": 0})
        child = Mock(pid=5678, created_at=service._stamp(), detached=False)
        child.poll.return_value = None
        original_write = service._write
        def write(root, name, value):
            original_write(root, name, value)
            if name == "owner.json":
                original_write(root, "ready.json", {"run_id": value["run_id"], "pid": child.pid,
                    "created_at": child.created_at, "job_keeper": {"fixture": "no-process-started"}})
        with patch.object(service.processes, "identity", return_value={"state": "missing"}), \
             patch.object(service.processes, "current_job_active", return_value=0), \
             patch.object(service.processes, "process_session", return_value=1), \
             patch.object(service, "_write", side_effect=write), \
             patch.object(service.processes, "spawn_persistent", return_value=child) as spawn, \
             patch.object(service.processes, "detach_owned", return_value={"ownership_transferred": True}):
            result = self.start(execute=True)
        self.assertEqual(result["state"], "started")
        spawn.assert_called_once()
        self.assertNotEqual(result["run_id"], self.run_id)
        self.assertEqual(ledger.read_bytes(), before)
        self.assertEqual(self.store.get_event(event["event_id"])["delivery_status"], "pending")

    def test_launch_without_owner_must_prove_empty_job(self):
        self.control()
        service._write(self.root, "launch.json", {"state": "launch_intent", "run_id": self.run_id, "job_name": self.job})
        with patch.object(service.processes, "current_job_active", return_value=2), \
             patch.object(service.processes, "spawn_persistent") as spawn:
            result = self.start(execute=True)
        self.assertEqual(result["reason"], "previous_agent_host_exit_unconfirmed")
        spawn.assert_not_called()

    def test_status_records_unknown_model_usage_and_drops_historical_budget(self):
        self.control()
        self.owner()
        service._write(self.root, "run.json", {"run_id": self.run_id, "state": "waiting",
            "heartbeat_at": service._stamp(), "last_progress": "waiting_attention", "model_calls": None,
            "dispatcher": {"tasks_started": 1, "tasks_passed": 0,
                           "budget": {"state": "blocked", "reason": "budget_exhausted"}},
            "reason": "delivery_evidence_failed_no_automatic_retry"})
        with patch.object(service.processes, "identity", return_value={"state": "alive", "created_at": self.created}), \
             patch.object(service.processes, "process_session", return_value=1):
            result = service.status(self.root)
        self.assertIsNone(result["model_calls"])
        self.assertFalse(result["execution_verified"])
        self.assertEqual(result["queue"]["pending"], 0)
        self.assertEqual(result["reason"], "delivery_evidence_failed_no_automatic_retry")
        self.assertEqual(result["dispatcher"], {"tasks_started": 1, "tasks_passed": 0})
        self.assertNotIn("budget", result)

    def test_stale_heartbeat_does_not_claim_running(self):
        self.control()
        self.owner()
        service._write(self.root, "run.json", {"run_id": self.run_id, "heartbeat_at": "2000-01-01T00:00:00+00:00"})
        with patch.object(service.processes, "identity", return_value={"state": "alive", "created_at": self.created}), \
             patch.object(service.processes, "process_session", return_value=1):
            result = service.status(self.root)
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["host_liveness"], "alive_unverified")

    def test_stop_persists_disable_then_uses_only_recorded_private_job(self):
        self.control()
        owner = self.owner()
        receipt = {"child_exited": True, "remaining_owned_processes": 0, "forcibly_terminated": True,
                   "reason": "cancelled"}
        def stop_job(job, **kwargs):
            self.assertFalse(service._control(self.root)["enabled"])
            self.assertEqual(job, owner["job_name"])
            self.assertEqual(kwargs["created_at"], owner["created_at"])
            self.assertEqual(kwargs["pid"], owner["pid"])
            self.assertEqual(kwargs["session_id"], owner["session_id"])
            return receipt
        with patch.object(service.processes, "stop_persistent", side_effect=stop_job):
            result = service.stop(self.root, grace_seconds=5)
        self.assertEqual(result["state"], "stopped")
        self.assertTrue(result["process"]["forcibly_terminated"])

    def test_stop_unknown_owner_never_signals_by_pid_or_job_name(self):
        self.control()
        self.owner(created_at="invalid")
        with patch.object(service.processes, "current_job_active", return_value=1), \
             patch.object(service.processes, "stop_persistent") as terminate:
            result = service.stop(self.root)
        self.assertEqual(result["state"], "shutdown_unconfirmed")
        self.assertFalse(result["process_signal_sent"])
        terminate.assert_not_called()
        self.assertFalse(service._control(self.root)["enabled"])

    def test_disabled_serve_never_adopts_or_starts_dispatch(self):
        with patch.object(service.processes, "adopt_current_job") as adopt, patch.object(service.agent_dispatch, "run") as run:
            result = service.serve(self.root, self.run_id, self.job)
        self.assertEqual(result["state"], "disabled")
        adopt.assert_not_called()
        run.assert_not_called()

    def keeper(self):
        keeper = Mock()
        keeper.receipt.return_value = {"pid": 1234, "created_at": self.created, "session_id": 1,
                                      "job_name": self.job, "keeper_handle": 9}
        return keeper

    def test_serve_uses_existing_dispatch_with_durable_admission_and_no_restart(self):
        self.control()
        event = make_synthetic("listener")
        self.store.enqueue(event)
        def dispatch(directory, source, state_dir, **kwargs):
            self.assertEqual(source, str(self.source))
            self.assertEqual(kwargs["root"], self.root)
            self.assertTrue(kwargs["continuous"])
            self.assertTrue(kwargs["execute"])
            self.assertEqual(kwargs["admission_path"], service._path(self.root, "control.json"))
            self.assertEqual(kwargs["admission_run_id"], self.run_id)
            self.assertTrue(kwargs["dispatch_enabled"]())
            service.pause(self.root)
            self.assertFalse(kwargs["dispatch_enabled"]())
            self.assertFalse(kwargs["cancel"].is_set())
            with patch.object(service, "status", return_value={"host_liveness": "alive_verified", "state": "paused"}):
                service.resume(self.root, execute=True)
            self.assertTrue(kwargs["dispatch_enabled"]())
            kwargs["cancel"].set()
            return 0
        with patch.object(service.processes, "adopt_current_job", return_value=self.keeper()), \
             patch.object(service.agent_dispatch, "run", side_effect=dispatch) as run, \
             patch.object(service.agent_dispatch, "status", return_value={"state": "stopped", "tasks_started": 0}):
            result = service.serve(self.root, self.run_id, self.job)
        run.assert_called_once()
        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(self.store.get_event(event["event_id"])["delivery_status"], "pending")
        self.assertEqual(service._read(self.root, "exit.json")["state"], "stopped")

    def test_failed_dispatch_waits_for_human_not_automatic_restart(self):
        self.control()
        with patch.object(service.processes, "adopt_current_job", return_value=self.keeper()), \
             patch.object(service.agent_dispatch, "run", return_value=3) as run, \
             patch.object(service.agent_dispatch, "status", return_value={"state": "blocked", "tasks_started": 1,
                       "reason": "prior_child_exit_unconfirmed"}):
            result = service.serve(self.root, self.run_id, self.job)
        run.assert_called_once()
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reason"], "prior_child_exit_unconfirmed")
        self.assertIsNone(result["model_calls"])

    def test_corrupt_low_pending_reaches_host_status_without_launch(self):
        # Real local dispatcher/selector/SQLite integration. Only the kernel
        # owner and launch gate are fixtures. No provider is launched.
        self.control()
        self.owner()
        event = make_synthetic("listener")
        event["severity"] = "info"
        self.store.enqueue(event)
        config = self.root / "config/default.json"
        config.parent.mkdir()
        shutil.copyfile(service.ROOT / "config/default.json", config)
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE events SET payload=?", ("{ invalid private-instruction",))
            db.commit()
        source_before = self.store.path.read_bytes()
        with isolated_launch(self.root) as launch, \
             patch.object(service.processes, "adopt_current_job", return_value=self.keeper()), \
             patch.object(service.agent_dispatch, "spawn", side_effect=AssertionError("No child permitted")) as spawn:
            result = service.serve(self.root, self.run_id, self.job)
            self.assertEqual(result["state"], "blocked")
            self.assertEqual(result["reason"], "dispatch_pending_payload_malformed")
            self.assertEqual(result["model_calls"], 0)
            self.assertEqual(result["dispatcher"]["tasks_started"], 0)
            self.assertFalse(launch.gate_entered())
            spawn.assert_not_called()
        with patch.object(service.processes, "identity", return_value={"state": "alive", "created_at": self.created}), \
             patch.object(service.processes, "process_session", return_value=1):
            visible = service.status(self.root)
        self.assertEqual(visible["state"], "blocked")
        self.assertEqual(visible["reason"], "dispatch_pending_payload_malformed")
        self.assertEqual(visible["pending_events"], 1)
        self.assertNotIn("private-instruction", str(visible))
        self.assertEqual(self.store.path.read_bytes(), source_before)
        self.assertEqual(service._read(self.root, "exit.json")["state"], "blocked")

    def test_start_handoff_requires_verified_same_child_receipt(self):
        child = Mock(pid=1234, created_at=self.created, detached=False)
        child.poll.return_value = None
        original_write = service._write
        def write(root, name, value):
            original_write(root, name, value)
            if name == "owner.json":
                original_write(root, "ready.json", {"run_id": value["run_id"], "pid": 1234,
                               "created_at": self.created, "job_keeper": {"fixture": "kernel-verifier-stub"}})
        with patch.object(service, "_write", side_effect=write), \
             patch.object(service.processes, "spawn_persistent", return_value=child) as spawn, \
             patch.object(service.processes, "process_session", return_value=1), \
             patch.object(service.processes, "detach_owned", return_value={"ownership_transferred": True}) as detach:
            result = self.start(execute=True)
        self.assertEqual(result["state"], "started")
        self.assertTrue(service._control(self.root)["enabled"])
        self.assertIn("eventguard.agent_service", spawn.call_args.args[0])
        self.assertFalse(spawn.call_args.kwargs.get("allow_parent_job", False))
        detach.assert_called_once()

    def test_ready_failure_disables_and_cleans_only_owned_child(self):
        child = Mock(pid=1234, created_at=self.created, detached=False)
        child.poll.return_value = 2
        receipt = {"child_exited": True, "remaining_owned_processes": 0, "forcibly_terminated": False}
        with patch.object(service.processes, "spawn_persistent", return_value=child), \
             patch.object(service.processes, "process_session", return_value=1), \
             patch.object(service.processes, "finish", return_value=receipt) as finish:
            result = self.start(execute=True)
        self.assertEqual(result["state"], "startup_failed")
        self.assertFalse(service._control(self.root)["enabled"])
        self.assertEqual(finish.call_args.args[0], child)

    def test_owner_write_failure_still_cleans_owned_child(self):
        child = Mock(pid=1234, created_at=self.created, detached=False)
        original_write = service._write
        def write(root, name, value):
            if name == "owner.json":
                raise OSError("fixture failure must not escape into status")
            return original_write(root, name, value)
        with patch.object(service, "_write", side_effect=write), \
             patch.object(service.processes, "spawn_persistent", return_value=child), \
             patch.object(service.processes, "process_session", return_value=1), \
             patch.object(service.processes, "finish", return_value={"child_exited": True}) as finish:
            with self.assertRaises(OSError):
                self.start(execute=True)
        self.assertFalse(service._control(self.root)["enabled"])
        self.assertEqual(finish.call_args.args[0], child)

    def test_application_lifetime_requires_owner_callback_and_finite_bound(self):
        with patch.object(service.processes, "spawn_application_host") as spawn:
            for arguments in ({"lifetime_owner": "application"},
                              {"child_owner": lambda child: None},
                              {"deadline_monotonic": time.monotonic()+10},
                              {"lifetime_owner": "application", "child_owner": lambda child: None,
                               "deadline_monotonic": float("inf")}):
                with self.subTest(arguments=list(arguments)), self.assertRaisesRegex(ValueError, "lifetime_invalid"):
                    self.start(execute=True, **arguments)
        spawn.assert_not_called()

    def test_application_start_refuses_unknown_parent_or_expired_deadline(self):
        for observed, deadline, reason in (({"state": "unknown"}, time.monotonic()+30, "application_owner_identity_unverifiable"),
                ({"state": "alive", "pid": 9876, "created_at": self.created}, time.monotonic()-1, "agent_service_deadline_elapsed")):
            with self.subTest(reason=reason), patch.object(service.processes, "identity", return_value=observed), \
                 patch.object(service.processes, "spawn_application_host") as spawn:
                result = self.start(execute=True, lifetime_owner="application", child_owner=lambda child: None,
                                    deadline_monotonic=deadline)
            self.assertEqual(result["state"], "blocked")
            self.assertEqual(result["reason"], reason)
            spawn.assert_not_called()
        self.assertFalse(service._path(self.root, "control.json").exists())

    def test_application_handoff_retains_real_child_before_metadata(self):
        child = Mock(pid=1234, created_at=self.created, detached=False)
        child.poll.return_value = None
        held = []
        original_write = service._write
        parent = {"state": "alive", "pid": 9876, "created_at": self.created}
        def write(root, name, value):
            if name == "owner.json":
                self.assertEqual(held, [child])
                self.assertEqual(child._eventguard_agent_service_scope["run_id"], value["run_id"])
                self.assertEqual(value["application_owner"]["pid"], parent["pid"])
                original_write(root, "ready.json", {"run_id": value["run_id"], "pid": child.pid,
                    "created_at": child.created_at, "job_keeper": {"fixture": "no-real-process"}})
            original_write(root, name, value)
        with patch.object(service.processes, "identity", return_value=parent), \
             patch.object(service.processes, "spawn_application_host", return_value=child) as spawn, \
             patch.object(service.processes, "spawn_persistent") as independent, \
             patch.object(service.processes, "process_session", return_value=1), \
             patch.object(service, "_write", side_effect=write), \
             patch.object(service.processes, "retain_application_host", return_value={"ownership_transferred": False}) as retain, \
             patch.object(service.processes, "detach_owned") as detach:
            result = self.start(execute=True, lifetime_owner="application", child_owner=held.append,
                                deadline_monotonic=time.monotonic()+30)
        self.assertEqual(result["state"], "started")
        self.assertEqual(result["lifetime_owner"], "application")
        self.assertTrue(result["lifetime_limited"])
        self.assertFalse(result["handoff"]["ownership_transferred"])
        spawn.assert_called_once()
        self.assertNotIn("allow_parent_job", spawn.call_args.kwargs)
        self.assertNotIn("creationflags", spawn.call_args.kwargs)
        retain.assert_called_once()
        independent.assert_not_called()
        detach.assert_not_called()

    def test_application_serve_checks_parent_identity_and_passes_deadline(self):
        parent = {"pid": 9876, "created_at": self.created}
        for observed in ({"state": "missing", "pid": parent["pid"]},
                         {"state": "unknown", **parent},
                         {"state": "alive", **parent, "pid": 5432},
                         {"state": "alive", **parent, "created_at": "2026-10-24T00:00:01+00:00"}):
            deadline = time.monotonic()+30
            control = self.control(lifetime_owner="application", application_owner=parent, deadline_monotonic=deadline)
            service._write(self.root, "launch.json", {"state": "launch_intent", **control})
            def dispatch(*args, **kwargs):
                self.assertEqual(kwargs["deadline_monotonic"], deadline)
                self.assertFalse(kwargs["dispatch_enabled"]())
                self.assertTrue(kwargs["cancel"].is_set())
                return 0
            with self.subTest(observed=observed), patch.object(service.processes, "identity", return_value=observed), \
                 patch.object(service.processes, "adopt_current_job", return_value=self.keeper()), \
                 patch.object(service.agent_dispatch, "run", side_effect=dispatch) as run, \
                 patch.object(service.agent_dispatch, "status", return_value={"state": "stopped", "tasks_started": 0}):
                result = service.serve(self.root, self.run_id, self.job)
            self.assertEqual(result["state"], "stopped")
            self.assertEqual(result["reason"], "application_owner_exit_or_unverifiable")
            self.assertEqual(result["model_calls"], 0)
            run.assert_called_once()

    def test_application_serve_cancels_when_its_deadline_expires(self):
        parent = {"pid": 9876, "created_at": self.created}
        control = self.control(lifetime_owner="application", application_owner=parent,
                               deadline_monotonic=time.monotonic()-1)
        service._write(self.root, "launch.json", {"state": "launch_intent", **control})
        def dispatch(*args, **kwargs):
            self.assertFalse(kwargs["dispatch_enabled"]())
            self.assertTrue(kwargs["cancel"].is_set())
            return 0
        with patch.object(service.processes, "identity", return_value={"state": "alive", **parent}), \
             patch.object(service.processes, "adopt_current_job", return_value=self.keeper()), \
             patch.object(service.agent_dispatch, "run", side_effect=dispatch), \
             patch.object(service.agent_dispatch, "status", return_value={"state": "stopped", "tasks_started": 0}):
            result = service.serve(self.root, self.run_id, self.job)
        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["reason"], "application_lifetime_deadline_elapsed")

    def test_smoke_teardown_reaps_proven_job_even_when_stop_raises(self):
        child = Mock(pid=1234, created_at=self.created, returncode=1460)
        child.wait.side_effect = [subprocess.TimeoutExpired("synthetic-worker", 5), 1460]
        evidence = {}
        receipt = {"forcibly_terminated": True, "child_exited": True, "remaining_owned_processes": 0}
        with patch.object(service, "stop", side_effect=OSError("fixture control unavailable")), \
             patch.object(service.processes, "stop_persistent", return_value=receipt) as cleanup:
            with self.assertRaises(OSError):
                _stop_test_hosts(self.root, [(child, self.job)], evidence)
        cleanup.assert_called_once_with(self.job, pid=child.pid, created_at=self.created,
                                       reason="test_teardown", grace=2)
        self.assertEqual(evidence["teardown"], [receipt])
        self.assertEqual(child.wait.call_count, 2)

    @unittest.skipUnless(os.name == "nt" and service.importlib.util.find_spec("mcp") is not None,
                         "Windows private Job and existing optional MCP SDK required")
    def test_real_windows_empty_host_pause_resume_stop_without_executing_provider(self):
        # Scope: real Windows host/jobs and an empty synthetic fixture source.
        # The executable is deliberately invalid. No provider can be invoked.
        # No quota is read. Without an event the child never reaches the
        # launch gate.
        config = self.root / "config/default.json"
        config.parent.mkdir(parents=True)
        shutil.copyfile(service.ROOT / "config/default.json", config)
        children = []
        def own_child(child):
            children.append((child, child.job.name))
        def wait_dispatch_state(expected):
            deadline = time.monotonic() + 8
            value = None
            while time.monotonic() < deadline:
                value = service.status(self.root)
                if (value.get("dispatcher") or {}).get("state") in expected:
                    return value
                time.sleep(.05)
            self.fail("bounded fixture host did not publish expected state: " + repr(value))
        try:
            started = self.start(execute=True, lifetime_owner="application", child_owner=own_child,
                                 deadline_monotonic=time.monotonic()+45)
            self.assertEqual(started["state"], "started", started)
            self.assertTrue(started["handoff"]["lifetime_limited"])
            self.assertFalse(started["handoff"]["ownership_transferred"])
            self.assertEqual(started["lifetime_owner"], "application")
            waiting = wait_dispatch_state({"waiting"})
            self.assertEqual(waiting["model_calls"], 0)
            self.assertEqual(waiting["dispatcher"]["tasks_started"], 0)
            service.pause(self.root)
            paused = wait_dispatch_state({"waiting_paused"})
            self.assertEqual(paused["model_calls"], 0)
            service.resume(self.root, execute=True)
            resumed = wait_dispatch_state({"waiting"})
            self.assertEqual(resumed["model_calls"], 0)
            self.assertEqual(resumed["pending_events"], 0)
        finally:
            self.evidence = {"scope": "real Windows private Job; empty synthetic source; no provider/model"}
            stopped = _stop_test_hosts(self.root, children, self.evidence)
        self.assertEqual(stopped["state"], "stopped", stopped)
        self.assertFalse(stopped["process"]["forcibly_terminated"])
        if stopped["process"]["exit_code"] is not None:
            self.assertEqual(stopped["process"]["exit_code"], 0)
        self.assertEqual(stopped["process"]["remaining_owned_processes"], 0)
        self.assertEqual(self.evidence["teardown"], [])
        self.assertTrue(all(receipt["exit_code"] == 0 and receipt["remaining_owned_processes"] == 0
                            and receipt["forcibly_terminated"] is False
                            for receipt in self.evidence["retained_handle_exits"]))
        self.assertTrue(all(child.returncode == 0 for child, _ in children))
        self.evidence.update({"scope": "real Windows application-owned private Job with empty synthetic source; no quota read; no provider/model",
                         "launch_api": "spawn_application_host", "handoff_api": "retain_application_host",
                         "lifetime_limited": True, "provider_attempt_count": 0,
                         "started": started, "waiting": waiting, "paused": paused, "resumed": resumed,
                         "stop": stopped, "child_exit_codes": [child.returncode for child, _ in children],
                         "model_calls": 0})


if __name__ == "__main__":
    unittest.main()
