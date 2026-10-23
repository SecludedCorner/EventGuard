"""Background controller fixtures; no real monitor, model, scheduler or reboot."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import json
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from eventguard import background as bg
from eventguard.events.store import EventStore
from eventguard.runtime import Runtime
from eventguard.synthetic import make_synthetic

ROOT = Path(__file__).resolve().parents[1]
CREATED = "2026-10-23T00:00:00.000000+00:00"
PID = 4242


class Keeper:
    def __init__(self, name):
        self.name = name

    def receipt(self):
        return {"kind": "eventguard-private-job-keeper-v1", "job_name": self.name, "pid": PID,
                "created_at": CREATED, "session_id": 1, "keeper_handle": 123,
                "parent_job_present": True, "lifetime_owner": "scheduler_or_foreground_host"}


class Child:
    pid, created_at, detached = PID, CREATED, False

    def poll(self):
        return None


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("config/default.json", "tests/fixtures/normal.json"):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        self.runtime = Runtime(self.root)
        self.enterContext(patch.object(bg, "_KEEPERS", []))
        self.enterContext(patch.object(bg.processes, "process_session", return_value=1))
        self.identity = self.enterContext(patch.object(bg.processes, "identity", return_value={"pid": PID, "created_at": CREATED, "state": "alive"}))
        self.job = self.enterContext(patch.object(bg.processes, "current_job_active", return_value=0))

    def enable(self, fixture=False):
        value = {"kind": bg.CONTROL_KIND, "enabled": True, "generation": "a" * 32,
                 "namespace": "test" if fixture else "live", "updated_at": bg._stamp(),
                 "fixture": "tests/fixtures/normal.json" if fixture else None,
                 "max_cycles": 1 if fixture else None, "reason": "explicit_fixture"}
        bg._write(self.runtime, "control.json", value)
        return value

    def owner(self, *, name=None, session=1, heartbeat=None):
        value = {"kind": bg.OWNER_KIND, "run_id": "b" * 32, "generation": "a" * 32,
                 "namespace": "live", "pid": PID, "created_at": CREATED,
                 "session_id": session, "job_name": name or "Global\\EventGuard-" + "c" * 32,
                 "started_at": bg._stamp()}
        bg._write(self.runtime, "owner.json", value)
        bg._write(self.runtime, "run.json", {"kind": bg.RUN_KIND, "run_id": value["run_id"],
                 "state": "running", "heartbeat_at": heartbeat or bg._stamp(), "restart_count": 0})
        return value

    def disable(self):
        value = bg._control(self.runtime)
        value.update(enabled=False, updated_at=bg._stamp())
        bg._write(self.runtime, "control.json", value)

    def test_status_before_first_start_is_readonly_and_no_model_or_pid_is_needed(self):
        value = bg.status(self.root)
        self.assertFalse(value["desired_enabled"])
        self.assertEqual(value["host_liveness"], "not_recorded")
        self.assertEqual(value["model_calls"], 0)
        self.assertFalse((self.root / "data").exists())
        self.identity.assert_not_called()

    def test_public_serve_without_enabled_control_never_creates_job_or_enables_itself(self):
        with patch.object(bg.processes, "standalone_host_job") as job:
            value = bg.serve(self.root)
        self.assertEqual(value["state"], "disabled")
        job.assert_not_called()
        self.assertFalse((self.root / "data").exists())

    def test_explicit_stop_is_durable_and_resume_does_not_enable_it(self):
        self.enable()
        value = bg.stop(self.root, grace_seconds=0)
        self.assertEqual(value["state"], "stopped")
        self.assertFalse(bg._control(self.runtime)["enabled"])
        with patch.object(bg.processes, "spawn_persistent") as spawn:
            resumed = bg.start(self.root, resume=True)
        spawn.assert_not_called()
        self.assertEqual(resumed["state"], "disabled")
        self.assertEqual(bg.serve(self.root)["state"], "disabled")

    def test_failed_disabled_write_does_not_claim_durable_stop(self):
        with patch.object(bg, "_write", side_effect=PermissionError("fixture denied")):
            value = bg.stop(self.root, grace_seconds=0)
        self.assertEqual(value["state"], "stop_not_persisted")
        self.assertIsNone(value["desired_enabled"])
        self.assertNotIn("fixture denied", json.dumps(value))

    def test_explicit_stop_preserves_bad_control_and_writes_disabled(self):
        path = bg._path(self.runtime, "control.json")
        path.parent.mkdir(parents=True)
        path.write_bytes(b"invalid fixture control")
        value = bg.stop(self.root, grace_seconds=0)
        self.assertFalse(bg._control(self.runtime)["enabled"])
        self.assertEqual(value["state"], "stopped")
        self.assertEqual(bg._path(self.runtime, "control-invalid.json").read_bytes(), b"invalid fixture control")

    def test_scoped_stop_rejects_changed_namespace_without_changing_control(self):
        self.enable()
        path = bg._path(self.runtime, "control.json")
        before = path.read_bytes()
        with patch.object(bg.processes, "stop_persistent") as stop:
            value = bg.stop(self.root, grace_seconds=0, expected_namespace="test")
        self.assertEqual(value["reason"], "background_outside_launcher_namespace")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(bg._path(self.runtime, "stop.json").exists())
        stop.assert_not_called()

    def test_scoped_stop_cannot_rename_or_repair_unknown_control(self):
        path = bg._path(self.runtime, "control.json")
        path.parent.mkdir(parents=True)
        path.write_bytes(b"invalid fixture control")
        value = bg.stop(self.root, grace_seconds=0, expected_namespace="test")
        self.assertEqual(value["reason"], "background_scope_unverifiable")
        self.assertEqual(path.read_bytes(), b"invalid fixture control")
        self.assertFalse(bg._path(self.runtime, "control-invalid.json").exists())
        self.assertFalse(bg._path(self.runtime, "stop.json").exists())

    def test_scoped_stop_without_control_preserves_unknown_scope(self):
        value = bg.stop(self.root, grace_seconds=0, expected_namespace="test")
        self.assertEqual(value["reason"], "background_scope_unverifiable")
        self.assertFalse(bg._path(self.runtime, "control.json").exists())

    def test_scoped_stop_can_disable_matching_fixture_without_host(self):
        self.enable(fixture=True)
        value = bg.stop(self.root, grace_seconds=0, expected_namespace="test")
        self.assertEqual(value["state"], "stopped")
        self.assertFalse(bg._control(self.runtime)["enabled"])
        self.assertEqual(bg._control(self.runtime)["namespace"], "test")

    def test_scoped_stop_rejects_owner_outside_matching_control_scope(self):
        self.enable(fixture=True)
        self.owner()  # An old live owner does not become a test-scoped target.
        before = bg._path(self.runtime, "control.json").read_bytes()
        with patch.object(bg.processes, "stop_persistent") as stop:
            value = bg.stop(self.root, grace_seconds=0, expected_namespace="test")
        self.assertEqual(value["reason"], "background_outside_launcher_namespace")
        self.assertEqual(bg._path(self.runtime, "control.json").read_bytes(), before)
        stop.assert_not_called()

    def test_scoped_stop_does_not_follow_replacement_owner_after_disable(self):
        for namespace in ("live", "test"):
            with self.subTest(replacement_namespace=namespace):
                self.enable(fixture=True)
                owner = self.owner()
                owner["namespace"] = "test"
                bg._write(self.runtime, "owner.json", owner)
                original_status = bg.status
                calls = 0

                def replacement(root):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        self.enable(fixture=namespace == "test")
                        new_owner = dict(owner, namespace=namespace, run_id="d" * 32,
                                         job_name="Global\\EventGuard-" + "e" * 32)
                        bg._write(self.runtime, "owner.json", new_owner)
                    return original_status(root)

                with patch.object(bg, "status", side_effect=replacement), \
                        patch.object(bg.processes, "stop_persistent") as stop:
                    value = bg.stop(self.root, grace_seconds=0, expected_namespace="test")
                self.assertEqual((value["state"], value["reason"]), ("busy", "background_owner_changed"))
                self.assertTrue(bg._control(self.runtime)["enabled"])
                self.assertEqual(bg._control(self.runtime)["namespace"], namespace)
                stop.assert_not_called()

    def test_invalid_scoped_stop_namespace_is_rejected_without_control_write(self):
        for namespace in ("elsewhere", [], 1, True):
            with self.subTest(namespace=namespace), self.assertRaisesRegex(ValueError, "invalid_background_stop_namespace"):
                bg.stop(self.root, grace_seconds=0, expected_namespace=namespace)
        self.assertFalse(bg._path(self.runtime, "control.json").exists())

    def test_scoped_stop_reports_reenabled_control_before_new_launch_is_written(self):
        for existing_owner in (False, True):
            with self.subTest(existing_owner=existing_owner):
                self.enable(fixture=True)
                if existing_owner:
                    owner = self.owner()
                    owner["namespace"] = "test"
                    bg._write(self.runtime, "owner.json", owner)
                original_status = bg.status
                calls = 0

                def reenabled(root):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        # A concurrent Start has saved enabled, but its new
                        # launch/owner has not yet replaced the old run ID.
                        self.enable(fixture=True)
                    return original_status(root)

                with patch.object(bg, "status", side_effect=reenabled), \
                        patch.object(bg.processes, "stop_persistent") as stop:
                    value = bg.stop(self.root, grace_seconds=0, expected_namespace="test")
                self.assertEqual((value["state"], value["reason"]), ("busy", "background_owner_changed"))
                self.assertTrue(value["desired_enabled"])
                self.assertTrue(bg._control(self.runtime)["enabled"])
                stop.assert_not_called()

    def test_external_parent_job_block_retains_enabled_intent_but_never_claims_started(self):
        with patch.object(bg.processes, "spawn_persistent", side_effect=bg.processes.JobError("independent_background_unverifiable")):
            value = bg.start(self.root)
        self.assertEqual(value["state"], "blocked")
        self.assertEqual(value["reason"], "independent_background_unverifiable")
        self.assertTrue(bg._control(self.runtime)["enabled"])
        self.assertFalse(value["external_job_escape_attempted"])
        self.assertEqual(bg._read(self.runtime, "launch.json")["state"], "not_started")
        self.assertEqual(bg.status(self.root)["host_liveness"], "not_recorded")

    def test_launcher_transfers_only_matching_ready_and_keeper(self):
        child = Child()
        def spawn(argv, *, job_name, **kwargs):
            self.assertEqual(kwargs["stdin"], bg.subprocess.DEVNULL)
            self.assertNotIn("allow_parent_job", kwargs)
            self.assertIn("--host-root", argv)
            launch = bg._read(self.runtime, "launch.json")
            keeper = Keeper(job_name).receipt()
            owner = dict(launch, kind=bg.OWNER_KIND, pid=PID, created_at=CREATED)
            bg._write(self.runtime, "owner.json", owner)
            bg._write(self.runtime, "run.json", {"kind": bg.RUN_KIND, "run_id": launch["run_id"], "state": "running", "heartbeat_at": bg._stamp()})
            bg._write(self.runtime, "ready.json", {"kind": bg.READY_KIND, "run_id": launch["run_id"],
                "generation": launch["generation"], "job_name": job_name, "pid": PID, "created_at": CREATED,
                "job_keeper": keeper})
            return child
        transferred = {"ownership_transferred": True, "detached": True, "child_exited": None, "lifetime_limited": False}
        with patch.object(bg.processes, "spawn_persistent", side_effect=spawn), \
             patch.object(bg.processes, "detach_owned", return_value=transferred) as detach, \
             patch.object(bg.processes, "finish") as finish:
            value = bg.start(self.root, ready_timeout=1)
        self.assertEqual(value["state"], "started")
        self.assertIs(detach.call_args.args[0], child)
        self.assertEqual(detach.call_args.args[1]["keeper_handle"], 123)
        self.assertTrue(bg._read(self.runtime, "handoff.json")["process"]["ownership_transferred"])
        finish.assert_not_called()
        self.assertEqual(value["model_calls"], 0)

    def test_missing_ready_does_not_detach_and_disables_failed_start(self):
        child = Child()
        child.poll = lambda: 0
        receipt = {"managed": True, "child_exited": True, "remaining_owned_processes": 0, "forcibly_terminated": False}
        self.identity.return_value = {"pid": PID, "state": "missing", "created_at": None}
        with patch.object(bg.processes, "spawn_persistent", return_value=child), \
             patch.object(bg.processes, "detach_owned") as detach, \
             patch.object(bg.processes, "finish", return_value=receipt):
            value = bg.start(self.root, ready_timeout=1)
        detach.assert_not_called()
        self.assertEqual(value["state"], "startup_failed")
        self.assertFalse(bg._control(self.runtime)["enabled"])

    def test_handoff_write_failure_preserves_the_fact_that_host_was_transferred(self):
        child, write = Child(), bg._write
        def spawn(argv, *, job_name, **kwargs):
            launch = bg._read(self.runtime, "launch.json")
            write(self.runtime, "owner.json", dict(launch, kind=bg.OWNER_KIND, pid=PID, created_at=CREATED))
            write(self.runtime, "run.json", {"kind": bg.RUN_KIND, "run_id": launch["run_id"], "state": "running", "heartbeat_at": bg._stamp()})
            write(self.runtime, "ready.json", {"kind": bg.READY_KIND, "run_id": launch["run_id"],
                "generation": launch["generation"], "job_name": job_name, "pid": PID, "created_at": CREATED,
                "job_keeper": Keeper(job_name).receipt()})
            return child
        def transfer(*args):
            child.detached = True
            return {"ownership_transferred": True, "detached": True, "child_exited": None, "lifetime_limited": False}
        def save(runtime, name, value):
            if name == "handoff.json":
                raise PermissionError("fixture durable receipt denied")
            return write(runtime, name, value)
        with patch.object(bg.processes, "spawn_persistent", side_effect=spawn), \
             patch.object(bg.processes, "detach_owned", side_effect=transfer), \
             patch.object(bg.processes, "finish") as finish, patch.object(bg, "_write", side_effect=save):
            value = bg.start(self.root, ready_timeout=1)
        self.assertEqual(value["state"], "started")
        self.assertTrue(value["handoff"]["ownership_transferred"])
        self.assertTrue(value["evidence_write_failed"])
        self.assertFalse(value["handoff_persisted"])
        finish.assert_not_called()
        self.assertNotIn("fixture durable", json.dumps(value))

    def test_launcher_keyboard_interrupt_disables_and_finishes_only_its_owned_child(self):
        child, read = Child(), bg._read
        receipt = {"managed": True, "child_exited": True, "remaining_owned_processes": 0,
                   "forcibly_terminated": False, "reason": "cancelled"}
        def interrupt_ready(runtime, name):
            if name == "ready.json":
                raise KeyboardInterrupt
            return read(runtime, name)
        with patch.object(bg.processes, "spawn_persistent", return_value=child), \
             patch.object(bg, "_read", side_effect=interrupt_ready), \
             patch.object(bg.processes, "finish", return_value=receipt) as finish, \
             patch.object(bg.processes, "stop_persistent") as persistent_stop:
            value = bg.start(self.root, ready_timeout=1)
        finish.assert_called_once_with(child, "cancelled", grace=5, request_stop=False)
        persistent_stop.assert_not_called()
        self.assertEqual(value["state"], "stopped")
        self.assertFalse(value["ownership_transferred"])
        self.assertFalse(bg._control(self.runtime)["enabled"])
        self.assertEqual(bg._read(self.runtime, "stop-receipt.json")["process"], receipt)
        with patch.object(bg.processes, "spawn_persistent") as spawn:
            self.assertEqual(bg.start(self.root, resume=True)["state"], "disabled")
        spawn.assert_not_called()

    def test_launcher_interrupt_after_transfer_never_finishes_transferred_wrapper(self):
        child, write = Child(), bg._write
        handoff = {"ownership_transferred": True, "detached": True, "child_exited": None, "lifetime_limited": False}
        receipt = {"managed": True, "child_exited": True, "remaining_owned_processes": 0,
                   "forcibly_terminated": False, "reason": "cancelled"}
        def spawn(argv, *, job_name, **kwargs):
            launch = bg._read(self.runtime, "launch.json")
            write(self.runtime, "ready.json", {"kind": bg.READY_KIND, "run_id": launch["run_id"],
                "generation": launch["generation"], "job_name": job_name, "pid": PID,
                "created_at": CREATED, "job_keeper": Keeper(job_name).receipt()})
            return child
        def transfer(*args):
            child.detached = True
            return handoff
        def interrupt_handoff(runtime, name, value):
            if name == "handoff.json":
                raise KeyboardInterrupt
            return write(runtime, name, value)
        with patch.object(bg.processes, "spawn_persistent", side_effect=spawn), \
             patch.object(bg.processes, "detach_owned", side_effect=transfer), \
             patch.object(bg.processes, "finish") as finish, \
             patch.object(bg.processes, "stop_persistent", return_value=receipt) as persistent_stop, \
             patch.object(bg, "_write", side_effect=interrupt_handoff):
            value = bg.start(self.root, ready_timeout=1)
        finish.assert_not_called()
        self.assertTrue(value["ownership_transferred"])
        self.assertEqual(value["handoff"], handoff)
        self.assertEqual(value["state"], "stopped")
        self.assertFalse(bg._control(self.runtime)["enabled"])
        self.assertEqual(persistent_stop.call_args.args[0], bg._read(self.runtime, "launch.json")["job_name"])
        self.assertEqual(persistent_stop.call_args.kwargs, {"pid": PID, "created_at": CREATED,
            "session_id": 1, "reason": "cancelled", "grace": 5})

    def test_interrupted_old_launcher_does_not_disable_a_newer_explicit_start(self):
        child, read = Child(), bg._read
        replacement = "e" * 32
        def replace_then_interrupt(runtime, name):
            if name == "ready.json":
                control = bg._control(runtime)
                control.update(generation=replacement, updated_at=bg._stamp())
                bg._write(runtime, "control.json", control)
                raise KeyboardInterrupt
            return read(runtime, name)
        with patch.object(bg.processes, "spawn_persistent", return_value=child), \
             patch.object(bg, "_read", side_effect=replace_then_interrupt), \
             patch.object(bg.processes, "finish", return_value={"child_exited": True, "remaining_owned_processes": 0}) as finish:
            value = bg.start(self.root, ready_timeout=1)
        self.assertTrue(bg._control(self.runtime)["enabled"])
        self.assertEqual(bg._control(self.runtime)["generation"], replacement)
        self.assertFalse(value["control_generation_matches"])
        self.assertTrue(value["desired_enabled"])
        self.assertEqual(value["state"], "shutdown_unconfirmed")
        finish.assert_called_once_with(child, "cancelled", grace=5, request_stop=False)

    def test_stale_and_future_heartbeat_do_not_verify_active_monitor(self):
        self.enable()
        for offset in (-31, 1):
            self.owner(heartbeat=(datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat())
            value = bg.status(self.root)
            self.assertEqual(value["host_liveness"], "alive_unverified")
            self.assertEqual(value["state"], "unknown")

    def test_pid_reuse_and_unknown_job_are_not_verified_exit(self):
        self.enable()
        self.owner()
        self.identity.return_value = {"pid": PID, "state": "alive", "created_at": "2026-10-23T01:00:00+00:00"}
        self.job.return_value = 1
        value = bg.status(self.root)
        self.assertEqual(value["state"], "shutdown_unconfirmed")
        self.assertNotEqual(value["host_liveness"], "exited_verified")

    def test_global_missing_job_verifies_old_session_exit_but_local_missing_does_not(self):
        self.enable()
        self.identity.return_value = {"pid": PID, "state": "missing", "created_at": None}
        self.owner(session=2)
        value = bg.status(self.root)
        self.assertEqual(value["host_liveness"], "exited_verified")
        self.assertEqual(value["state"], "enabled_not_running")
        self.owner(session=2, name="Local\\EventGuard-" + "d" * 32)
        self.job.reset_mock()
        value = bg.status(self.root)
        self.assertEqual(value["host_liveness"], "unknown")
        self.job.assert_not_called()

    def test_denied_reused_pid_does_not_block_when_global_job_is_explicitly_missing(self):
        self.enable()
        self.owner(session=2)
        self.identity.return_value = {"pid": PID, "state": "denied", "created_at": None}
        missing = FileNotFoundError("fixture missing job")
        missing.winerror = 2
        self.job.side_effect = missing
        value = bg.status(self.root)
        self.assertEqual(value["host_liveness"], "exited_verified")
        self.assertEqual(value["state"], "enabled_not_running")
        self.assertEqual(value["reason"], "owned_job_missing")

    def test_latest_launch_identity_is_not_overridden_by_wall_clock_rollback(self):
        control = self.enable()
        owner = self.owner()
        owner["started_at"] = "2100-01-01T00:00:00+00:00"
        bg._write(self.runtime, "owner.json", owner)
        launch = dict(owner, kind=bg.LAUNCH_KIND, run_id="d" * 32, generation=control["generation"],
                      state="started", started_at="2020-01-01T00:00:00+00:00")
        bg._write(self.runtime, "launch.json", launch)
        value = bg.status(self.root)
        self.assertEqual(value["run_id"], launch["run_id"])
        self.assertEqual(value["host_liveness"], "alive_unverified")

    def test_orphaned_pre_spawn_intent_can_only_recover_when_private_job_is_empty(self):
        control = self.enable()
        bg._write(self.runtime, "launch.json", {"kind": bg.LAUNCH_KIND, "run_id": "b" * 32,
            "generation": control["generation"], "namespace": "live", "state": "launch_intent",
            "session_id": 1, "job_name": "Global\\EventGuard-" + "c" * 32, "started_at": bg._stamp()})
        self.job.return_value = 1
        self.assertEqual(bg.status(self.root)["state"], "unknown")
        self.job.return_value = 0
        self.assertEqual(bg.status(self.root)["state"], "enabled_not_running")

    def test_orphaned_intent_stop_records_missing_job_without_invented_child_identity(self):
        control = self.enable()
        name = "Global\\EventGuard-" + "c" * 32
        bg._write(self.runtime, "launch.json", {"kind": bg.LAUNCH_KIND, "run_id": "b" * 32,
            "generation": control["generation"], "namespace": "live", "state": "launch_intent",
            "session_id": 1, "job_name": name, "started_at": bg._stamp()})
        missing = FileNotFoundError("fixture missing job")
        missing.winerror = 2
        self.job.side_effect = missing
        with patch.object(bg.processes, "stop_persistent") as persistent_stop:
            value = bg.stop(self.root, grace_seconds=0)
        persistent_stop.assert_not_called()
        self.identity.assert_not_called()
        self.assertEqual(value["state"], "stopped")
        receipt = bg._read(self.runtime, "stop-receipt.json")["process"]
        self.assertEqual(receipt["job_name"], name)
        self.assertEqual(receipt["reason"], "owned_job_missing")
        self.assertFalse(receipt["owner_identity_recorded"])
        self.assertIsNone(receipt["pid"])
        self.assertIsNone(receipt["created_at"])
        self.assertNotIn("exit_code", receipt)

    def test_cooperative_stop_persists_observed_identity_and_empty_or_missing_job(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                self.enable()
                owner = self.owner(session=2)
                self.identity.return_value = {"pid": PID, "state": "missing", "created_at": None}
                self.job.side_effect = None
                if missing:
                    error = FileNotFoundError("fixture missing job")
                    error.winerror = 2
                    self.job.side_effect = error
                with patch.object(bg.processes, "stop_persistent") as persistent_stop:
                    value = bg.stop(self.root, grace_seconds=0)
                persistent_stop.assert_not_called()
                self.assertEqual(value["state"], "stopped")
                document = bg._read(self.runtime, "stop-receipt.json")
                self.assertEqual(document["run_id"], owner["run_id"])
                receipt = document["process"]
                self.assertTrue(receipt["child_exited"])
                self.assertFalse(receipt["forcibly_terminated"])
                self.assertTrue(receipt["owner_identity_recorded"])
                self.assertEqual(receipt["recorded_owner"]["created_at"], CREATED)
                self.assertEqual(receipt["owner_observation"], {"pid": PID, "state": "missing", "created_at": None})
                self.assertEqual(receipt["job"]["remaining_owned_processes"], 0)
                self.assertEqual(receipt["reason"], "owned_job_missing" if missing else "owned_job_empty")
                self.assertNotIn("exit_code", receipt)

    def test_later_empty_job_verification_preserves_original_forced_stop_receipt(self):
        self.enable()
        owner = self.owner()
        self.identity.return_value = {"pid": PID, "state": "missing", "created_at": None}
        forced = {"managed": True, "child_exited": True, "remaining_owned_processes": 0,
                  "forcibly_terminated": True, "reason": "cancelled", "exit_code": 1}
        bg._write(self.runtime, "stop-receipt.json", {"run_id": owner["run_id"], "at": CREATED, "process": forced})
        value = bg.stop(self.root, grace_seconds=0)
        document = bg._read(self.runtime, "stop-receipt.json")
        self.assertEqual(document["process"], forced)
        self.assertEqual(document["at"], CREATED)
        self.assertEqual(document["verification"]["reason"], "owned_job_empty")
        self.assertEqual(value["reason"], "owned_job_forcibly_terminated")

    def test_cooperative_exit_without_durable_receipt_is_not_reported_as_completed(self):
        self.enable()
        self.owner()
        self.identity.return_value = {"pid": PID, "state": "missing", "created_at": None}
        write = bg._write
        def reject_receipt(runtime, name, value):
            if name == "stop-receipt.json":
                raise PermissionError("PRIVATE receipt denied")
            return write(runtime, name, value)
        with patch.object(bg, "_write", side_effect=reject_receipt):
            value = bg.stop(self.root, grace_seconds=0)
        self.assertEqual(value["state"], "shutdown_unconfirmed")
        self.assertFalse(value["desired_enabled"])
        self.assertFalse(bg._control(self.runtime)["enabled"])
        self.assertNotIn("PRIVATE", json.dumps(value))

    def test_stop_never_requests_stop_of_an_unrelated_foreground_monitor(self):
        self.enable()
        owner = self.owner()
        self.identity.return_value = {"pid": PID, "state": "denied", "created_at": None}
        self.job.return_value = 1
        receipt = {"managed": True, "child_exited": None, "remaining_owned_processes": 1, "forcibly_terminated": False}
        with patch.object(bg.processes, "stop_persistent", return_value=receipt) as stop, \
             patch.object(Runtime, "request_stop", side_effect=AssertionError("unrelated stop request")):
            value = bg.stop(self.root, grace_seconds=0)
        self.assertFalse(bg._control(self.runtime)["enabled"])
        self.assertEqual(value["state"], "shutdown_unconfirmed")
        self.assertEqual(stop.call_args.kwargs["pid"], owner["pid"])
        self.assertEqual(stop.call_args.kwargs["created_at"], owner["created_at"])

    def test_serve_holds_private_job_before_ready_and_uses_no_time_or_agent_budget_cap(self):
        self.enable(fixture=True)
        root, observed = self.root, []
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
            def run(self, **kwargs):
                observed.append(kwargs)
                self_ready = bg._read(Runtime(root), "ready.json")
                assert self_ready["job_keeper"]["keeper_handle"] == 123
                assert len(bg._KEEPERS) == 1
                kwargs["on_progress"]({"state": "running", "healthy": False, "last_error": None})
                return {"state": "stopped", "healthy": False, "model_calls": 0}
        with patch.object(bg.processes, "standalone_host_job", side_effect=Keeper), patch.object(bg, "Monitor", FakeMonitor):
            value = bg.serve(self.root)
        self.assertEqual(value["state"], "stopped")
        self.assertEqual(value["reason"], "bounded_fixture_completed")
        self.assertEqual(observed[0]["max_cycles"], 1)
        self.assertNotIn("max_seconds", observed[0])
        self.assertEqual(value["lifetime_owner"], "scheduler_or_foreground_host")
        self.assertTrue(value["parent_job_present"])
        self.assertFalse(any(thread.name == "eventguard-background-control" and thread.is_alive() for thread in threading.enumerate()))

    def test_foreground_keyboard_interrupt_persists_disabled_instead_of_restarting(self):
        self.enable()
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
            def run(self, **kwargs):
                return {"state": "stopped", "stop_reason": "keyboard_interrupt"}
        with patch.object(bg.processes, "standalone_host_job", side_effect=Keeper), patch.object(bg, "Monitor", FakeMonitor):
            value = bg.serve(self.root)
        self.assertFalse(bg._control(self.runtime)["enabled"])
        self.assertEqual(value["reason"], "explicit_keyboard_stop")
        self.assertFalse(value["desired_enabled"])

    def test_keyboard_interrupt_during_supervisor_backoff_disables_without_self_termination(self):
        self.enable()
        attempts = []
        class FailingMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
            def run(self, **kwargs):
                attempts.append(True)
                raise RuntimeError("PRIVATE fixture failure")
        with patch.object(bg.processes, "standalone_host_job", side_effect=Keeper), \
             patch.object(bg, "Monitor", FailingMonitor), \
             patch.object(bg, "_wait_retry", side_effect=KeyboardInterrupt) as wait, \
             patch.object(bg.processes, "finish") as finish, \
             patch.object(bg.processes, "stop_persistent") as persistent_stop:
            value = bg.serve(self.root)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(wait.call_args.args[1], bg.RESTART_DELAYS[0])
        self.assertFalse(bg._control(self.runtime)["enabled"])
        self.assertFalse(value["desired_enabled"])
        self.assertEqual(value["reason"], "explicit_keyboard_stop")
        self.assertTrue(value["host_exit_pending"])
        self.assertNotIn("child_exited", value)
        self.assertEqual(len(bg._KEEPERS), 1)
        finish.assert_not_called()
        persistent_stop.assert_not_called()
        self.assertNotIn("PRIVATE", json.dumps(value))
        self.assertFalse(any(thread.name == "eventguard-background-control" and thread.is_alive() for thread in threading.enumerate()))

    def test_keyboard_interrupt_during_host_setup_disables_and_releases_controller_lease(self):
        self.enable()
        with patch.object(bg.processes, "standalone_host_job", side_effect=KeyboardInterrupt), \
             patch.object(bg.processes, "finish") as finish, \
             patch.object(bg.processes, "stop_persistent") as persistent_stop, \
             patch.object(bg, "Monitor") as monitor:
            value = bg.serve(self.root)
        self.assertFalse(bg._control(self.runtime)["enabled"])
        self.assertEqual(value["reason"], "explicit_keyboard_stop")
        self.assertTrue(value["host_exit_pending"])
        self.assertNotIn("child_exited", value)
        finish.assert_not_called()
        persistent_stop.assert_not_called()
        monitor.assert_not_called()
        lease = bg.FileLease(bg._path(self.runtime, "host.lock"))
        try:
            self.assertTrue(lease.acquire())
        finally:
            lease.release()

    def test_keyboard_interrupt_with_disable_write_failure_does_not_claim_reboot_stop(self):
        self.enable()
        write = bg._write
        def reject_disable(runtime, name, value):
            if name == "control.json" and value.get("enabled") is False:
                raise PermissionError("PRIVATE control denied")
            return write(runtime, name, value)
        class InterruptedMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
            def run(self, **kwargs):
                raise KeyboardInterrupt
        with patch.object(bg.processes, "standalone_host_job", side_effect=Keeper), \
             patch.object(bg, "Monitor", InterruptedMonitor), patch.object(bg, "_write", side_effect=reject_disable), \
             patch.object(bg.processes, "finish") as finish:
            value = bg.serve(self.root)
        self.assertEqual(value["state"], "stop_not_persisted")
        self.assertFalse(value["disabled_persisted"])
        self.assertIsNone(value["desired_enabled"])
        self.assertTrue(bg._control(self.runtime)["enabled"])
        self.assertTrue(value["host_exit_pending"])
        finish.assert_not_called()
        self.assertNotIn("PRIVATE", json.dumps(value))

    def test_unexpected_monitor_exception_has_bounded_backoff_then_resumes(self):
        self.enable()
        records, attempts = [], []
        write = bg._write
        def record(runtime, name, value):
            records.append(copy.deepcopy(value))
            return write(runtime, name, value)
        test = self
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
            def run(self, **kwargs):
                test.disable()
                self.cancel.wait(2)
                return {"state": "stopped"}
        def factory(root):
            attempts.append(True)
            if len(attempts) == 1:
                raise RuntimeError("PRIVATE exception must not be copied")
            return FakeMonitor(root)
        with patch.object(bg.processes, "standalone_host_job", side_effect=Keeper), \
             patch.object(bg, "Monitor", side_effect=factory), patch.object(bg, "RESTART_DELAYS", (.01, .02)), \
             patch.object(bg, "_write", side_effect=record):
            value = bg.serve(self.root)
        self.assertEqual(len(attempts), 2)
        failures = [row for row in records if row.get("state") == "backoff"]
        self.assertTrue(failures)
        self.assertEqual(failures[0]["reason"], "monitor_exception_without_raw_error")
        self.assertEqual(failures[0]["backoff_seconds"], .01)
        self.assertEqual(value["reason"], "durable_stop_observed")
        self.assertNotIn("PRIVATE", json.dumps(records))

    def test_backpressure_waits_and_preserves_same_outbox_ids(self):
        self.enable()
        store = EventStore(self.root / "data/live")
        event = make_synthetic()
        store.enqueue(event)
        before, test, attempts, records = store.path.read_bytes(), self, [], []
        write = bg._write
        def record(runtime, name, value):
            records.append(copy.deepcopy(value))
            return write(runtime, name, value)
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
            def run(self, **kwargs):
                attempts.append(True)
                if len(attempts) == 1:
                    return {"state": "stopped", "stop_reason": "persistence_backpressure"}
                test.disable()
                self.cancel.wait(2)
                return {"state": "stopped"}
        with patch.object(bg.processes, "standalone_host_job", side_effect=Keeper), patch.object(bg, "Monitor", FakeMonitor), \
             patch.object(bg, "RESTART_DELAYS", (.01, .02)), patch.object(bg, "_write", side_effect=record):
            value = bg.serve(self.root)
        self.assertEqual(len(attempts), 2)
        self.assertTrue(any(row.get("reason") == "persistence_backpressure" and row.get("state") == "backoff" for row in records))
        self.assertEqual(store.path.read_bytes(), before)
        self.assertEqual(store.get_event(event["event_id"])["delivery_status"], "pending")
        self.assertEqual(value["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
