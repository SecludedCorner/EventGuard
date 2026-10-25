"""MCP held-HANDLE evidence fixtures; no model, native CLI or network."""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from eventguard import mcp_lifecycle as lifecycle
from eventguard.acceptance_control import read_json, write_json


class McpLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.attempt, self.instance = "a"*32, "b"*32
        self.created = "2026-10-25T00:00:00.000000+00:00"
        self.member_created = "2026-10-25T00:00:01.000000+00:00"
        self.child = SimpleNamespace(pid=101, created_at=self.created)
        self.marker = {"kind": lifecycle.MARKER_KIND, "phase": "server-started", "instance_id": self.instance,
                       "pid": 202, "created_at": self.member_created}
        self.initial = {"identity_verified": True, "owner_job_membership_verified": True, "handle_retained": True,
                        "owner_pid": 101, "owner_created_at": self.created, "pid": 202,
                        "created_at": self.member_created, "child_exited": False, "exit_code": None}

    def save(self, name, value):
        write_json(self.directory / name, value)

    def fixture(self):
        self.save("mcp-server-started.json", self.marker)
        self.save("mcp-tools-listed.json", {**self.marker, "phase": "tools-listed", "tool_count": 3,
            "tool_names": ["ack_event", "query_evidence", "receive_event"], "response_prepared": True})
        self.save("mcp-stdio-exit.json", {**self.marker, "phase": "stdio-exit", "return_code": 0,
            "stdio_entered": True, "ack_response_flushed": True, "os_exit_verified": False})
        self.save("capture-start.json", {"attempt_id": self.attempt, "codex_pid": 101, "created_at": self.created})
        process = {"managed": True, "pid": 101, "created_at": self.created, "child_exited": True,
                   "exit_code": 0, "remaining_owned_processes": 0, "forcibly_terminated": False,
                   "reason": "natural_exit", "shutdown_requested_reason": "descendants_remaining"}
        self.save("capture-exit.json", {"attempt_id": self.attempt, "codex_pid": 101, "capture_complete": True,
            "codex_exit_code": 0, "child_exited": True, "forcibly_terminated": False,
            "stop_reason": "descendants_remaining", "stdout_truncated": False, "stderr_truncated": False,
            "process": process})
        observation = Mock()
        observation.snapshot.side_effect = [deepcopy(self.initial), {**self.initial, "child_exited": True, "exit_code": 0}]
        with patch.object(lifecycle.processes, "observe_owned_member", return_value=observation, create=True):
            held, binding = lifecycle.bind_mcp_member(self.child, self.directory, self.attempt)
        lifecycle.finish_mcp_observation(held, binding, self.directory)
        return observation

    def test_missing_marker_does_not_observe_or_create_evidence(self):
        with patch.object(lifecycle.processes, "observe_owned_member", create=True) as observe:
            self.assertEqual(lifecycle.bind_mcp_member(self.child, self.directory, self.attempt), (None, None))
        observe.assert_not_called()
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_bind_retains_only_live_matching_member_and_finish_closes_query_handle(self):
        observation = self.fixture()
        observation.close.assert_called_once_with()
        started = read_json(self.directory / "mcp-process-start.json")
        ended = read_json(self.directory / "mcp-process-exit.json")
        self.assertIs(started["process"]["child_exited"], False)
        self.assertIs(ended["process"]["child_exited"], True)
        self.assertEqual(ended["process"]["exit_code"], 0)
        self.assertTrue(lifecycle.assess_mcp_exit(self.directory, self.attempt)["passed"])
        with patch.object(lifecycle.processes, "observe_owned_member", create=True) as observe:
            with self.assertRaisesRegex(lifecycle.McpLifecycleError, "already_used"):
                lifecycle.bind_mcp_member(self.child, self.directory, self.attempt)
        observe.assert_not_called()

    def test_invalid_oversized_and_false_markers_never_open_process(self):
        variants = [dict(self.marker, kind="foreign"), dict(self.marker, phase="tools-listed"),
                    dict(self.marker, instance_id="not-a-token"), dict(self.marker, pid=True),
                    dict(self.marker, created_at="unknown")]
        for marker in variants:
            with self.subTest(marker=marker):
                self.save("mcp-server-started.json", marker)
                with patch.object(lifecycle.processes, "observe_owned_member", create=True) as observe:
                    with self.assertRaises(lifecycle.McpLifecycleError):
                        lifecycle.bind_mcp_member(self.child, self.directory, self.attempt)
                observe.assert_not_called()
        (self.directory / "mcp-server-started.json").write_bytes(b"x"*(lifecycle.LIMIT+1))
        with patch.object(lifecycle.processes, "observe_owned_member", create=True) as observe:
            with self.assertRaises(lifecycle.McpLifecycleError):
                lifecycle.bind_mcp_member(self.child, self.directory, self.attempt)
        observe.assert_not_called()

    def test_rejected_binding_closes_handle_and_never_terminates(self):
        self.save("mcp-server-started.json", self.marker)
        for field, value in (("identity_verified", False), ("owner_job_membership_verified", False),
                             ("handle_retained", False), ("child_exited", True), ("pid", 999),
                             ("owner_pid", 999), ("created_at", self.created)):
            with self.subTest(field=field):
                observation = Mock()
                observation.snapshot.return_value = {**self.initial, field: value}
                with patch.object(lifecycle.processes, "observe_owned_member", return_value=observation, create=True):
                    with self.assertRaisesRegex(lifecycle.McpLifecycleError, "live_member_handle"):
                        lifecycle.bind_mcp_member(self.child, self.directory, self.attempt)
                observation.close.assert_called_once_with()
                observation.terminate.assert_not_called()
        self.assertFalse((self.directory / "mcp-process-start.json").exists())

    def test_start_write_failure_closes_retained_handle_and_omits_raw_error(self):
        self.save("mcp-server-started.json", self.marker)
        observation = Mock()
        observation.snapshot.return_value = self.initial
        with patch.object(lifecycle.processes, "observe_owned_member", return_value=observation, create=True), \
                patch.object(lifecycle, "_write_new", side_effect=OSError("PRIVATE_FAILURE")):
            with self.assertRaisesRegex(lifecycle.McpLifecycleError, "^mcp_member_binding_unconfirmed$"):
                lifecycle.bind_mcp_member(self.child, self.directory, self.attempt)
        observation.close.assert_called_once_with()

    def test_unknown_exit_is_saved_without_success_and_closes_handle(self):
        self.fixture()
        (self.directory / "mcp-process-exit.json").unlink()
        binding = {field: read_json(self.directory / "mcp-process-start.json")[field]
                   for field in lifecycle.BINDING_FIELDS}
        observation = Mock()
        observation.snapshot.return_value = {**self.initial, "child_exited": None, "exit_code": None}
        result = lifecycle.finish_mcp_observation(observation, binding, self.directory)
        self.assertIsNone(result["child_exited"])
        observation.close.assert_called_once_with()
        self.assertFalse(lifecycle.assess_mcp_exit(self.directory, self.attempt)["passed"])

    def test_assessment_rechecks_markers_owner_membership_and_zero_exit(self):
        self.fixture()
        mutations = [
            ("mcp-server-started.json", lambda value: value.update(pid=303)),
            ("mcp-tools-listed.json", lambda value: value.update(instance_id="c"*32)),
            ("mcp-tools-listed.json", lambda value: value.update(tool_names=["receive_event"]*3)),
            ("mcp-stdio-exit.json", lambda value: value.update(return_code=1)),
            ("mcp-stdio-exit.json", lambda value: value.update(ack_response_flushed=False)),
            ("mcp-process-start.json", lambda value: value["process"].update(child_exited=True)),
            ("mcp-process-start.json", lambda value: value.update(owner_pid=999)),
            ("mcp-process-exit.json", lambda value: value["process"].update(owner_job_membership_verified=False)),
            ("mcp-process-exit.json", lambda value: value["process"].update(handle_retained=False)),
            ("mcp-process-exit.json", lambda value: value["process"].update(exit_code=1)),
            ("mcp-process-exit.json", lambda value: value["process"].update(child_exited=None)),
            ("capture-exit.json", lambda value: value["process"].update(forcibly_terminated=True)),
        ]
        for name, mutate in mutations:
            original = read_json(self.directory / name)
            value = deepcopy(original)
            mutate(value)
            value["passed"] = True
            self.save(name, value)
            with self.subTest(name=name):
                proof = lifecycle.assess_mcp_exit(self.directory, self.attempt)
                self.assertFalse(proof["passed"])
                self.assertFalse(proof["mcp_natural_exit_verified"])
                self.assertTrue(proof["evidence_errors"])
            self.save(name, original)

    def test_assessment_is_pure_read_and_missing_legacy_proof_stays_false(self):
        self.fixture()
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        with patch.object(lifecycle, "_write_new") as write, \
                patch.object(lifecycle.processes, "observe_owned_member", create=True) as observe:
            self.assertTrue(lifecycle.assess_mcp_exit(self.directory, self.attempt)["passed"])
        write.assert_not_called()
        observe.assert_not_called()
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.directory.iterdir()})
        (self.directory / "mcp-stdio-exit.json").unlink()
        proof = lifecycle.assess_mcp_exit(self.directory, self.attempt)
        self.assertFalse(proof["passed"])
        self.assertEqual(proof["evidence_errors"], ["mcp_lifecycle_evidence_missing_or_invalid"])

    def test_finish_write_failure_always_closes_query_handle(self):
        self.fixture()
        binding = {field: read_json(self.directory / "mcp-process-start.json")[field]
                   for field in lifecycle.BINDING_FIELDS}
        observation = Mock()
        observation.snapshot.return_value = {**self.initial, "child_exited": True, "exit_code": 0}
        with patch.object(lifecycle, "_write_new", side_effect=OSError("PRIVATE_FAILURE")):
            with self.assertRaisesRegex(lifecycle.McpLifecycleError, "^mcp_member_exit_evidence_unconfirmed$"):
                lifecycle.finish_mcp_observation(observation, binding, self.directory)
        observation.close.assert_called_once_with()
