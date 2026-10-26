"""Verifier receipt contracts; fake exact children, no process or Linux claim."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import verify


class VerifyPortabilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    def child(self, code=0):
        child = Mock(spec=["pid", "poll", "wait", "terminate", "kill"])
        child.pid = 123
        child.poll.return_value = code
        return child

    def test_non_windows_start_does_not_fabricate_job_or_creation_identity(self):
        child = self.child()
        start = verify.guardian_start(child, None)
        self.assertIsNone(start["created_at"])
        self.assertIsNone(start["job_name"])
        self.assertFalse(start["managed"])

    def test_natural_non_windows_worker_only_passes_mock_scope(self):
        receipt = verify.guardian_exit(self.child(), None, self.output, "descendants_remaining")
        self.assertTrue(verify.guardian_succeeded(receipt, "mock"))
        self.assertFalse(verify.guardian_succeeded(receipt, "full"))
        self.assertIsNone(receipt["remaining_owned_processes"])
        self.assertFalse(receipt["process_tree_verified"])

    def test_nonzero_worker_does_not_pass(self):
        receipt = verify.guardian_exit(self.child(1), None, self.output, "descendants_remaining")
        self.assertFalse(verify.guardian_succeeded(receipt, "mock"))

    def test_timeout_requests_cooperation_before_terminating_only_exact_child(self):
        child = self.child(None)
        child.poll.side_effect = [None, -15]
        def wait(**unused):
            self.assertTrue((self.output / "guardian-stop.request").exists())
            if child.terminate.call_count == 0:
                raise subprocess.TimeoutExpired("fixture", .1)
            return -15
        child.wait.side_effect = wait
        receipt = verify.guardian_exit(child, None, self.output, "timeout", grace=.1)
        self.assertTrue(receipt["forcibly_terminated"])
        self.assertTrue(receipt["cooperative_stop_requested"])
        child.terminate.assert_called_once_with()
        child.kill.assert_not_called()
        self.assertFalse(verify.guardian_succeeded(receipt, "mock"))

    def test_windows_receipt_still_uses_existing_private_job_finish(self):
        child = self.child()
        expected = {"managed":True,"child_exited":True,"exit_code":0,"forcibly_terminated":False,"remaining_owned_processes":0}
        with patch.object(verify, "finish", return_value=expected) as finish:
            receipt = verify.guardian_exit(child, "Local\\EventGuard-fixture", self.output, "descendants_remaining")
        finish.assert_called_once_with(child, "descendants_remaining", grace=.5)
        self.assertIs(receipt, expected)
        self.assertTrue(verify.guardian_succeeded(receipt, "full"))

    def test_cooperative_zero_exit_after_deadline_cannot_pass_partial_suite(self):
        child = self.child(None)
        child.poll.side_effect = [None, 0]
        child.wait.return_value = 0
        receipt = verify.guardian_exit(child, None, self.output, "timeout", grace=.1)
        self.assertTrue(receipt["child_exited"])
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertTrue(receipt["deadline_or_owner_failure"])
        self.assertFalse(verify.guardian_succeeded(receipt, "mock"))

    def test_failed_cooperation_record_is_not_a_successful_guardian(self):
        child = self.child(None)
        child.poll.side_effect = [None, 0]
        child.wait.return_value = 0
        with patch.object(verify, "atomic_json", side_effect=OSError("fixture write failure")):
            receipt = verify.guardian_exit(child, None, self.output, "owner_exception", grace=.1)
        self.assertFalse(receipt["cooperative_stop_requested"])
        self.assertFalse(verify.guardian_succeeded(receipt, "mock"))
