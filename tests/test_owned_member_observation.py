"""Read-only member HANDLE contracts; real children are synthetic owned Jobs."""
from datetime import datetime, timedelta
import ctypes as C
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from eventguard import processes

ROOT = Path(__file__).resolve().parents[1]
CREATED = "2026-10-25T00:00:00.000000+00:00"
PARENT = '''import json,subprocess,sys
sys.path.insert(0,sys.argv[1])
from eventguard.processes import spawn,finish
child=spawn([sys.executable,"-B","-c","import sys;sys.stdin.buffer.read(1)"],stdin=subprocess.PIPE)
try:
    print(json.dumps({"pid":child.pid,"created_at":child.created_at}),flush=True)
    sys.stdin.buffer.read(1)
    child.stdin.close()
    child.wait(timeout=5)
    receipt=finish(child,"descendants_remaining",grace=1,request_stop=False)
    print(json.dumps(receipt),flush=True)
    if receipt.get("exit_code")!=0 or receipt.get("forcibly_terminated") is not False:
        raise SystemExit(2)
finally:
    finish(child,"owner_exception",grace=1,request_stop=True)
'''


class MemberSnapshotContracts(unittest.TestCase):
    def observer(self, api):
        return processes._OwnedMemberObservation(api, 300, pid=123, created_at=CREATED,
            owner_pid=456, owner_created_at=CREATED)

    def test_running_or_failed_wait_never_queries_exit_code_or_invents_exit(self):
        api = SimpleNamespace(WaitForSingleObject=Mock(return_value=258), GetExitCodeProcess=Mock(),
                              CloseHandle=Mock(return_value=1))
        observation = self.observer(api)
        self.assertIs(observation.snapshot()["child_exited"], False)
        api.WaitForSingleObject.return_value = 0xFFFFFFFF
        snapshot = observation.snapshot()
        self.assertIsNone(snapshot["child_exited"])
        self.assertIsNone(snapshot["exit_code"])
        api.GetExitCodeProcess.assert_not_called()
        observation.close()

    def test_signalled_handle_with_failed_code_query_remains_unknown(self):
        api = SimpleNamespace(WaitForSingleObject=Mock(return_value=0),
                              GetExitCodeProcess=Mock(return_value=0), CloseHandle=Mock(return_value=1))
        observation = self.observer(api)
        snapshot = observation.snapshot()
        self.assertIs(snapshot["child_exited"], True)
        self.assertIsNone(snapshot["exit_code"])
        self.assertNotIn("natural_exit_verified", snapshot)
        observation.close()

    def test_closed_handle_stays_unknown_and_close_is_idempotent(self):
        api = SimpleNamespace(CloseHandle=Mock(return_value=1), WaitForSingleObject=Mock(),
                              GetExitCodeProcess=Mock())
        observation = self.observer(api)
        observation.close()
        observation.close()
        snapshot = observation.snapshot()
        self.assertIs(snapshot["handle_retained"], False)
        self.assertIsNone(snapshot["child_exited"])
        self.assertIsNone(snapshot["exit_code"])
        api.CloseHandle.assert_called_once_with(300)
        api.WaitForSingleObject.assert_not_called()


@unittest.skipUnless(os.name == "nt", "real Windows owned-Job observation; not Linux runtime support")
class OwnedMemberObservationTests(unittest.TestCase):
    def setUp(self):
        self.children, self.observations = [], []

    def tearDown(self):
        for observation in self.observations:
            observation.close()
        receipts = []
        for child in self.children:
            if child.stdin is not None and not child.stdin.closed:
                child.stdin.close()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            receipts.append(processes.finish(child, "test_teardown", grace=1, request_stop=True))
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
        self.assertTrue(all(r["remaining_owned_processes"] == 0 for r in receipts))
        self.assertTrue(all(r["forcibly_terminated"] is False for r in receipts), "fixture cooperation failed")

    def child(self, source, *arguments):
        child = processes.spawn([sys.executable, "-B", "-c", source, *arguments],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.children.append(child)
        return child

    def family(self):
        owner = self.child(PARENT, str(ROOT / "src"))
        output = queue.Queue()
        reader = threading.Thread(target=lambda: output.put(owner.stdout.readline()), daemon=True)
        reader.start()
        member = json.loads(output.get(timeout=10))
        reader.join(timeout=1)
        return owner, member

    def observe(self, owner, member):
        observation = processes.observe_owned_member(owner, member["pid"], member["created_at"])
        self.observations.append(observation)
        return observation

    def release(self, owner):
        owner.stdin.close()
        self.assertEqual(owner.wait(timeout=10), 0, "synthetic parent failed")
        receipt = processes.finish(owner, "descendants_remaining", grace=1, request_stop=False)
        self.assertIs(receipt["forcibly_terminated"], False)
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        return receipt

    def test_retained_handle_observes_grandchild_exit_after_owner_job_closes(self):
        owner, member = self.family()
        observation = self.observe(owner, member)
        before = observation.snapshot()
        self.assertIs(before["child_exited"], False)
        self.assertIsNone(before["exit_code"])
        self.assertEqual((before["owner_pid"], before["owner_created_at"]), (owner.pid, owner.created_at))
        self.assertTrue(before["identity_verified"] and before["owner_job_membership_verified"])
        owner_receipt = self.release(owner)
        after = observation.snapshot()
        self.assertIs(after["child_exited"], True)
        self.assertEqual(after["exit_code"], 0)
        self.assertIs(after["handle_retained"], True)
        self.assertEqual((after["pid"], after["created_at"]), (member["pid"], member["created_at"]))
        self.assertNotIn("natural_exit_verified", after)
        self.evidence = {"scope": "real Windows synthetic owned-grandchild query HANDLE; no model",
                         "member_before": before, "member_after": after, "owner_process": owner_receipt}

    def test_wrong_creation_is_rejected_and_query_handle_is_closed(self):
        owner, member = self.family()
        api = processes.kernel()
        observed = SimpleNamespace(OpenProcess=Mock(wraps=api.OpenProcess),
            CloseHandle=Mock(wraps=api.CloseHandle), GetProcessTimes=api.GetProcessTimes,
            IsProcessInJob=api.IsProcessInJob)
        changed = (datetime.fromisoformat(member["created_at"]) + timedelta(microseconds=1)).isoformat(timespec="microseconds")
        with patch.object(processes, "kernel", return_value=observed):
            with self.assertRaisesRegex(processes.JobError, "^owned_member_creation_mismatch$"):
                processes.observe_owned_member(owner, member["pid"], changed)
        observed.OpenProcess.assert_called_once_with(0x101000, False, member["pid"])
        observed.CloseHandle.assert_called_once()
        self.assertIsNone(owner.poll())
        self.release(owner)

    def test_other_owned_job_is_rejected_and_stays_alive(self):
        owner = self.child("import sys;sys.stdin.buffer.read(1)")
        other = self.child("import sys;sys.stdin.buffer.read(1)")
        api = processes.kernel()
        observed = SimpleNamespace(OpenProcess=Mock(wraps=api.OpenProcess),
            CloseHandle=Mock(wraps=api.CloseHandle), GetProcessTimes=api.GetProcessTimes,
            IsProcessInJob=api.IsProcessInJob)
        with patch.object(processes, "kernel", return_value=observed):
            with self.assertRaisesRegex(processes.JobError, "^owned_member_job_mismatch$"):
                processes.observe_owned_member(owner, other.pid, other.created_at)
        observed.OpenProcess.assert_called_once_with(0x101000, False, other.pid)
        observed.CloseHandle.assert_called_once()
        self.assertIsNone(other.poll(), "read-only refusal must not affect the other owned Job")
        self.release(owner)
        self.release(other)

    def test_close_releases_only_observer_handle_without_stopping_member(self):
        owner, member = self.family()
        observation = self.observe(owner, member)
        api = observation._api
        closes = Mock(wraps=api.CloseHandle)
        observation._api = SimpleNamespace(CloseHandle=closes)
        observation.close()
        observation.close()
        closes.assert_called_once()
        self.assertIsNone(observation.snapshot()["child_exited"])
        state = processes.identity(member["pid"])
        self.assertEqual((state["state"], state["created_at"]), ("alive", member["created_at"]))
        self.release(owner)

    def test_owner_itself_detached_or_closed_is_rejected_before_opening_pid(self):
        owner = self.child("import sys;sys.stdin.buffer.read(1)")
        with patch.object(processes, "kernel") as api:
            with self.assertRaisesRegex(processes.JobError, "^owned_member_owner_unavailable$"):
                processes.observe_owned_member(owner, owner.pid, owner.created_at)
            with patch.object(owner, "detached", True):
                with self.assertRaisesRegex(processes.JobError, "^owned_member_owner_unavailable$"):
                    processes.observe_owned_member(owner, owner.pid + 1, owner.created_at)
        api.assert_not_called()
        self.release(owner)
        with patch.object(processes, "kernel") as api:
            with self.assertRaisesRegex(processes.JobError, "^owned_member_owner_unavailable$"):
                processes.observe_owned_member(owner, owner.pid + 1, owner.created_at)
        api.assert_not_called()
