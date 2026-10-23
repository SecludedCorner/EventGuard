"""Private persistent Job handoff; bounded fixtures, never a long-lived monitor."""
import ctypes as C
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
from eventguard.processes import (Job, JobError, JobKeeper, adopt_current_job,
    current_job_active, detach_owned, finish, identity, kernel, process_session,
    remaining_owned, spawn_persistent, standalone_host_job, stop_persistent,
    _object_comparison)


class ObjectComparisonBindingTests(unittest.TestCase):
    """Mock DLL binding contracts; actual handoff is tested separately below."""

    def setUp(self):
        _object_comparison.cache_clear()
        self.addCleanup(_object_comparison.cache_clear)

    def test_documented_kernelbase_export_uses_system32_only_loading(self):
        function = Mock()
        api = SimpleNamespace(CompareObjectHandles=function)
        with patch("eventguard.processes.C.WinDLL", create=True, return_value=api) as load:
            self.assertIs(_object_comparison(), function)
            self.assertIs(_object_comparison(), function)
        load.assert_called_once_with("kernelbase.dll", use_last_error=True, winmode=0x800)
        self.assertIs(function.restype, C.c_int)
        self.assertEqual(function.argtypes, [C.c_void_p, C.c_void_p])

    def test_missing_documented_export_has_no_alternate_dll_or_handle_fallback(self):
        with patch("eventguard.processes.C.WinDLL", create=True,
                   return_value=SimpleNamespace()) as load:
            self.assertIsNone(_object_comparison())
        load.assert_called_once_with("kernelbase.dll", use_last_error=True, winmode=0x800)

    def test_system_dll_load_failure_remains_unavailable(self):
        with patch("eventguard.processes.C.WinDLL", create=True,
                   side_effect=OSError("fixture_loader_failure")) as load:
            self.assertIsNone(_object_comparison())
        load.assert_called_once_with("kernelbase.dll", use_last_error=True, winmode=0x800)


class PersistentStopReceiptTests(unittest.TestCase):
    """Mock signalling races; not proof that a Windows process was stopped."""

    def stop_with_owner_signal(self, signalled):
        api = SimpleNamespace(
            OpenJobObjectW=Mock(return_value=100),
            OpenProcess=Mock(return_value=200),
            TerminateJobObject=Mock(return_value=1),
            CloseHandle=Mock(return_value=1),
            WaitForSingleObject=Mock(side_effect=lambda handle, milliseconds:
                                    0 if signalled and milliseconds > 0 else 258))
        with patch("eventguard.processes.kernel", return_value=api), \
             patch("eventguard.processes._kill_on_close"), \
             patch("eventguard.processes._active_job", side_effect=[1, 1, 1, 0, 0]), \
             patch("eventguard.processes.creation_time", return_value="fixture_creation"), \
             patch("eventguard.processes._membership", return_value=True), \
             patch("eventguard.processes.time.monotonic", return_value=10):
            receipt = stop_persistent("Global\\EventGuard-" + "a" * 32, pid=123,
                                      created_at="fixture_creation", grace=0)
        api.TerminateJobObject.assert_called_once_with(100, 1460)
        api.WaitForSingleObject.assert_called_once_with(200, 3000)
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.assertTrue(receipt["forcibly_terminated"])
        self.assertEqual(api.CloseHandle.call_args_list, [unittest.mock.call(200), unittest.mock.call(100)])
        return receipt

    def test_empty_job_waits_within_existing_budget_for_verified_process_signal(self):
        self.assertTrue(self.stop_with_owner_signal(True)["child_exited"])

    def test_empty_job_does_not_prove_process_exit_when_bounded_wait_times_out(self):
        self.assertFalse(self.stop_with_owner_signal(False)["child_exited"])

    def test_exit_code_only_comes_from_signalled_owned_handle(self):
        from eventguard.processes import _signalled_exit_code
        def code(handle, pointer):
            self.assertEqual(handle, 200)
            C.cast(pointer, C.POINTER(C.c_uint32)).contents.value = 7
            return 1
        api = SimpleNamespace(GetExitCodeProcess=Mock(side_effect=code))
        with patch("eventguard.processes.kernel", return_value=api):
            self.assertIsNone(_signalled_exit_code(200, False))
            api.GetExitCodeProcess.assert_not_called()
            self.assertEqual(_signalled_exit_code(200, True), 7)

    def test_exit_code_read_failure_remains_unknown(self):
        from eventguard.processes import _signalled_exit_code
        with patch("eventguard.processes.kernel", return_value=SimpleNamespace(GetExitCodeProcess=lambda *_: 0)):
            self.assertIsNone(_signalled_exit_code(200, True))


@unittest.skipUnless(os.name == "nt", "Actual Windows private Job ownership")
class BackgroundJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.children = []
        self.addCleanup(self.cleanup_children)
        self.entry = self.root / "bounded-host.py"
        self.entry.write_text(
            "import json,sys,time\nfrom pathlib import Path\n"
            + "sys.path.insert(0," + repr(str(BASE / "src")) + ")\n"
            + "from eventguard.processes import adopt_current_job\n"
            + "job,ready,stop,mode=sys.argv[1:]\n"
            + "keeper=adopt_current_job(job)\n"
            + "Path(ready).write_text(json.dumps(keeper.receipt()),encoding='utf-8')\n"
            + "deadline=time.monotonic()+10\n"
            + "while time.monotonic()<deadline:\n"
            + " if mode=='cooperative' and Path(stop).exists(): break\n"
            + " time.sleep(.02)\n"
            + "# Keep the raw Job handle until OS natural process exit.\n",
            encoding="utf-8")

    def cleanup_children(self):
        for item in self.children:
            child, receipt, stop = item
            stop.touch()
            if child.detached:
                try:
                    stop_persistent(child.job.name, pid=child.pid, created_at=child.created_at,
                                    session_id=process_session(), reason="test_teardown", grace=.1)
                except JobError as error:
                    if getattr(error, "winerror", None) != 2:
                        raise
            else:
                finish(child, "test_teardown", grace=.1)
            child.wait(timeout=4)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()

    def start_host(self, mode="cooperative"):
        name = "Global\\EventGuard-" + uuid.uuid4().hex
        ready, stop = self.root / (uuid.uuid4().hex + ".json"), self.root / (uuid.uuid4().hex + ".stop")
        child = spawn_persistent([sys.executable, "-B", str(self.entry), name, str(ready), str(stop), mode],
                                 job_name=name, allow_parent_job=True)
        item = [child, None, stop]
        self.children.append(item)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if ready.is_file():
                try:
                    value = json.loads(ready.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    time.sleep(.01)
                    continue
                item[1] = value
                return child, value, stop
            if child.poll() is not None:
                self.fail("bounded keeper host exited before ready")
            time.sleep(.01)
        self.fail("bounded keeper host did not publish ready")

    def test_verified_host_keeps_its_job_after_launcher_handle_release(self):
        before = remaining_owned()
        child, keeper, stop = self.start_host()
        receipt = detach_owned(child, keeper)
        self.assertTrue(receipt["ownership_transferred"])
        self.assertIsNone(receipt["child_exited"])
        self.assertIsNone(child.job.handle)
        self.assertIsNone(child.poll())
        with self.assertRaisesRegex(JobError, "persistent_job_ownership_transferred"):
            finish(child, "owner_exception", grace=0)
        self.assertIsNone(child.poll(), "a detached child is not an exited child")
        self.assertGreater(current_job_active(receipt["job_name"]), 0)
        self.assertEqual(remaining_owned(), before)
        stop.touch()
        exit_receipt = stop_persistent(receipt["job_name"], pid=child.pid, created_at=child.created_at,
                                       session_id=keeper["session_id"], grace=2)
        self.assertTrue(exit_receipt["child_exited"])
        self.assertEqual(exit_receipt["remaining_owned_processes"], 0)
        self.assertFalse(exit_receipt["forcibly_terminated"])
        self.assertEqual(child.wait(timeout=3), 0)
        self.evidence = {"scope": "real_windows_private_jobs_bounded_python_fixture",
                         "handoff": receipt, "stop": exit_receipt}

    def test_hanging_owned_host_is_only_forced_inside_verified_private_job(self):
        child, keeper, _ = self.start_host(mode="ignore_stop")
        receipt = detach_owned(child, keeper)
        stopped = stop_persistent(receipt["job_name"], pid=child.pid, created_at=child.created_at,
                                  session_id=keeper["session_id"], grace=.05)
        self.assertTrue(stopped["forcibly_terminated"])
        self.assertTrue(stopped["child_exited"])
        self.assertEqual(stopped["remaining_owned_processes"], 0)
        self.assertNotEqual(child.wait(timeout=3), 0)
        self.evidence = {"scope": "real_windows_job_hanging_fixture_not_monitor", "stop": stopped}

    def test_keeper_receipt_identity_mismatch_never_detaches(self):
        child, keeper, _ = self.start_host()
        with self.assertRaises(JobError):
            detach_owned(child, {**keeper, "created_at": "2000-01-01T00:00:00+00:00"})
        self.assertFalse(child.detached)
        self.assertIsNotNone(child.job.handle)

    def test_unavailable_object_comparison_never_releases_launcher_ownership(self):
        child, keeper, _ = self.start_host()
        with patch("eventguard.processes._object_comparison", return_value=None):
            with self.assertRaisesRegex(JobError, "persistent_keeper_object_comparison_unavailable"):
                detach_owned(child, keeper)
        self.assertFalse(child.detached)
        self.assertIsNotNone(child.job.handle)
        self.assertIsNone(child.poll())

    def test_closed_or_forged_keeper_handle_cannot_authorize_detach(self):
        child, keeper, _ = self.start_host()
        with self.assertRaises(JobError):
            detach_owned(child, {**keeper, "keeper_handle": 0x12345678})
        self.assertFalse(child.detached)
        self.assertIsNotNone(child.job.handle)

    def test_unrelated_owner_pid_cannot_authorize_private_job_termination(self):
        child, keeper, _ = self.start_host()
        receipt = detach_owned(child, keeper)
        own = identity()
        result = stop_persistent(receipt["job_name"], pid=own["pid"], created_at=own["created_at"],
                                 session_id=keeper["session_id"], grace=0)
        self.assertEqual(result["reason"], "persistent_owner_identity_unverifiable")
        self.assertIsNone(result["child_exited"])
        self.assertFalse(result["forcibly_terminated"])
        self.assertIsNone(child.poll(), "an unrelated PID must not grant termination")

    def test_adoption_rejects_job_that_does_not_contain_current_host(self):
        job = Job("Global\\EventGuard-" + uuid.uuid4().hex)
        try:
            with self.assertRaises(JobError):
                adopt_current_job(job.name)
        finally:
            job.close()

    def test_production_external_parent_job_is_rejected_without_launch(self):
        with patch("eventguard.processes._membership", return_value=True), \
             patch("eventguard.processes.spawn") as launch:
            with self.assertRaisesRegex(JobError, "independent_background_unverifiable"):
                spawn_persistent([sys.executable], job_name="Global\\EventGuard-" + "a" * 32)
        launch.assert_not_called()

    def test_global_job_denial_does_not_fall_back_to_local_or_unmanaged_launch(self):
        with patch("eventguard.processes._membership", return_value=False), \
             patch("eventguard.processes.spawn", side_effect=JobError("job_create_failed")) as launch:
            with self.assertRaisesRegex(JobError, "job_create_failed"):
                spawn_persistent([sys.executable], job_name="Global\\EventGuard-" + "a" * 32)
        launch.assert_called_once()

    def test_local_persistent_job_is_rejected_before_spawn(self):
        with patch("eventguard.processes.spawn") as launch:
            with self.assertRaisesRegex(ValueError, "persistent_global_job_required"):
                spawn_persistent([sys.executable], job_name="Local\\EventGuard-" + "a" * 32)
        launch.assert_not_called()

    def test_persistent_pipes_and_breakaway_are_rejected_before_launch(self):
        for kwargs in ({"stdout": subprocess.PIPE}, {"creationflags": 0x01000000}, {"shell": True}):
            with self.subTest(kwargs=kwargs), patch("eventguard.processes.spawn") as launch:
                with self.assertRaises(ValueError):
                    spawn_persistent([sys.executable], job_name="Global\\EventGuard-" + "a" * 32, **kwargs)
                launch.assert_not_called()

    def test_standalone_scheduler_nested_assignment_only_modifies_new_private_job(self):
        api = SimpleNamespace(GetCurrentProcess=Mock(return_value=100), AssignProcessToJobObject=Mock(return_value=1))
        job = SimpleNamespace(handle=200, close=Mock())
        with patch("eventguard.processes.kernel", return_value=api), \
             patch("eventguard.processes._membership", return_value=True), \
             patch("eventguard.processes.Job", return_value=job):
            keeper = standalone_host_job("Global\\EventGuard-" + "a" * 32)
        api.AssignProcessToJobObject.assert_called_once_with(200, 100)
        self.assertTrue(keeper.parent_job_present)
        self.assertEqual(keeper.lifetime_owner, "scheduler_or_foreground_host")
        self.assertIsNone(job.handle)

    def test_standalone_scheduler_assignment_denial_closes_only_new_job_and_stays_blocked(self):
        api = SimpleNamespace(GetCurrentProcess=Mock(return_value=100), AssignProcessToJobObject=Mock(return_value=0))
        job = SimpleNamespace(handle=200, close=Mock())
        with patch("eventguard.processes.kernel", return_value=api), \
             patch("eventguard.processes._membership", return_value=True), \
             patch("eventguard.processes.Job", return_value=job), \
             patch("eventguard.processes.C.get_last_error", return_value=5):
            with self.assertRaisesRegex(JobError, "host_private_job_assignment_failed") as failure:
                standalone_host_job("Global\\EventGuard-" + "a" * 32)
        self.assertEqual(failure.exception.winerror, 5)
        api.AssignProcessToJobObject.assert_called_once_with(200, 100)
        job.close.assert_called_once()

    def test_standalone_scheduler_ownership_assignment_contract_is_mock_only(self):
        api = SimpleNamespace(GetCurrentProcess=Mock(return_value=100), AssignProcessToJobObject=Mock(return_value=1))
        job = SimpleNamespace(handle=200, close=Mock())
        with patch("eventguard.processes.kernel", return_value=api), \
             patch("eventguard.processes._membership", return_value=False), \
             patch("eventguard.processes.Job", return_value=job):
            keeper = standalone_host_job("Global\\EventGuard-" + "a" * 32)
        self.assertIsInstance(keeper, JobKeeper)
        self.assertEqual(keeper.handle, 200)
        api.AssignProcessToJobObject.assert_called_once_with(200, 100)
        self.assertIsNone(job.handle)
        self.evidence = {"scope": "mock_assignment_contract_not_actual_scheduler_start"}


if __name__ == "__main__":
    unittest.main()
