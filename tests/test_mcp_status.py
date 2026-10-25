"""Bounded human MCP lifecycle status over raw synthetic evidence; no agent."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from eventguard import agent_dispatch as dispatch, agent_service as service
from eventguard.acceptance_control import read_json, write_json
from eventguard.cli import main
from eventguard.gui import view_snapshot
from eventguard.presentation import mcp_lifecycle_text
from test_dispatch_inspection import build_inspection_fixture


class McpStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        shutil.copyfile(dispatch.ROOT / "config/default.json", self.root / "config/default.json")
        self.fixture = build_inspection_fixture(self.root)
        self.directory = self.fixture["run_dir"]
        self.attempt = self.fixture["attempt_dir"]
        self.token = self.fixture["record"]["attempt_id"]
        state = read_json(self.directory / "status.json")
        state.update(active_attempt_id=self.token, child_exited=True,
                     delivery_progress={"capture_worker_started": True})
        state.update({key: self.fixture["record"][key] for key in
                      ("supervisor_identity_required", "supervisor_exit_required", "supervisor_nonce", "supervisor_start")})
        write_json(self.directory / "status.json", state)

    def lifecycle(self):
        captured = read_json(self.attempt / "capture-start.json")
        marker = {"kind": "eventguard-inbox-startup-evidence-v1", "phase": "server-started",
                  "instance_id": "e"*32, "pid": 303, "created_at": "2026-10-24T00:00:03.100000+00:00"}
        write_json(self.attempt / "mcp-server-started.json", marker)
        write_json(self.attempt / "mcp-tools-listed.json", {**marker, "phase": "tools-listed", "tool_count": 3,
            "tool_names": ["ack_event", "query_evidence", "receive_event"], "response_prepared": True})
        write_json(self.attempt / "mcp-stdio-exit.json", {**marker, "phase": "stdio-exit", "return_code": 0,
            "stdio_entered": True, "ack_response_flushed": True, "os_exit_verified": False})
        binding = {"kind": "eventguard-mcp-process-binding-v1", "attempt_id": self.token,
            "server_instance": marker["instance_id"], "pid": marker["pid"], "created_at": marker["created_at"],
            "owner_pid": captured["codex_pid"], "owner_created_at": captured["created_at"]}
        process = {"identity_verified": True, "owner_job_membership_verified": True, "handle_retained": True,
            "pid": binding["pid"], "created_at": binding["created_at"], "owner_pid": binding["owner_pid"],
            "owner_created_at": binding["owner_created_at"], "child_exited": False, "exit_code": None}
        write_json(self.attempt / "mcp-process-start.json", {**binding, "phase": "start", "process": process})
        write_json(self.attempt / "mcp-process-exit.json", {**binding, "phase": "exit",
            "process": {**process, "child_exited": True, "exit_code": 0}})

    def status(self):
        return dispatch.status(self.directory, read_only=True)

    def service_context(self, saved=None):
        owner = {"kind": service.OWNER_KIND, "run_id": self.directory.name, "job_name": "Global\\EventGuard-"+"f"*32,
                 "pid": 300, "created_at": "2026-10-24T00:00:01.000000+00:00", "session_id": 1}
        desired = {"run_id": owner["run_id"], "enabled": False, "paused": False, "allow_live": False,
                   "source_dir": str(self.fixture["source"]), "state_dir": str(self.fixture["state"])}
        saved = saved or {"run_id": owner["run_id"], "state": "stopped", "dispatcher": self.status(),
                          "dispatch_run_dir": str(self.directory), "model_calls": None}
        stack = ExitStack()
        stack.enter_context(patch.object(service, "_control", return_value=desired))
        stack.enter_context(patch.object(service, "_selection_policy", return_value={}))
        stack.enter_context(patch.object(service, "_pending", return_value={"pending": 0}))
        stack.enter_context(patch.object(service, "_read", side_effect=lambda root, name: deepcopy({
            "owner.json": owner, "run.json": saved}.get(name))))
        stack.enter_context(patch.object(service.processes, "identity", return_value={"state": "missing"}))
        stack.enter_context(patch.object(service, "_job_state", return_value={"state": "exited_verified", "remaining_owned_processes": 0}))
        return stack

    def test_raw_evidence_verifies_bounded_status_without_writing_or_process_observation(self):
        self.lifecycle()
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        with patch("eventguard.mcp_lifecycle.processes.observe_owned_member") as observe, patch.object(dispatch, "write_json") as write:
            result = self.status()["mcp_lifecycle"]
        self.assertEqual(result, {"status": "verified", "exit_code": 0, "ack_flushed": True,
                                  "reason": "mcp_natural_exit_verified"})
        self.assertLess(len(json.dumps(result)), 256)
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()})
        observe.assert_not_called()
        write.assert_not_called()

    def test_legacy_or_missing_raw_proof_cannot_use_saved_passed_claim(self):
        state = read_json(self.directory / "status.json")
        state["mcp_lifecycle"] = {"status": "verified", "exit_code": 0, "ack_flushed": True,
                                  "reason": "mcp_natural_exit_verified"}
        write_json(self.directory / "status.json", state)
        result = self.status()["mcp_lifecycle"]
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["ack_flushed"])
        self.lifecycle()
        self.assertEqual(self.status()["mcp_lifecycle"]["status"], "verified")
        (self.attempt / "mcp-stdio-exit.json").unlink()
        self.assertEqual(self.status()["mcp_lifecycle"]["status"], "unknown")

    def test_only_selected_attempt_is_assessed_and_new_unknown_does_not_inherit_old_success(self):
        self.lifecycle()
        state = read_json(self.directory / "status.json")
        token = "9"*32
        state.update(active_attempt_id=token, child_exited=True, delivery_progress={})
        write_json(self.directory / "status.json", state)
        from eventguard.mcp_lifecycle import assess_mcp_exit
        with patch("eventguard.mcp_lifecycle.assess_mcp_exit", wraps=assess_mcp_exit) as assess:
            self.assertEqual(self.status()["mcp_lifecycle"]["status"], "unknown")
        assess.assert_called_once_with(self.directory / "attempts" / token, token)
        state.pop("active_attempt_id")
        write_json(self.directory / "status.json", state)
        with patch("eventguard.mcp_lifecycle.assess_mcp_exit") as assess:
            self.assertEqual(self.status()["mcp_lifecycle"], dispatch.unknown_mcp_lifecycle())
        assess.assert_not_called()

    def test_nonzero_member_exit_remains_unknown_with_only_the_bounded_exit_code(self):
        self.lifecycle()
        value = read_json(self.attempt / "mcp-process-exit.json")
        value["process"]["exit_code"] = 1
        value.update(passed=True, pid=303)
        write_json(self.attempt / "mcp-process-exit.json", value)
        result = self.status()["mcp_lifecycle"]
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["exit_code"], 1)
        self.assertIsNone(result["ack_flushed"])
        self.assertEqual(set(result), {"status", "exit_code", "ack_flushed", "reason"})

    def test_service_rereads_raw_proof_instead_of_cached_dispatcher_summary(self):
        self.lifecycle()
        with self.service_context():
            value = service.status(self.root)
            self.assertEqual(value["mcp_lifecycle"]["status"], "verified")
            self.assertEqual(value["dispatcher"]["mcp_lifecycle"], value["mcp_lifecycle"])
            (self.attempt / "mcp-process-exit.json").unlink()
            value = service.status(self.root)
        self.assertEqual(value["mcp_lifecycle"]["status"], "unknown")
        self.assertEqual(value["dispatcher"]["mcp_lifecycle"]["status"], "unknown")

    def test_foreign_service_path_does_not_trigger_a_raw_evidence_read(self):
        self.lifecycle()
        saved = {"run_id": self.directory.name, "state": "stopped", "dispatcher": self.status(),
                 "dispatch_run_dir": str(self.root.parent / "PRIVATE-FOREIGN-DIRECTORY")}
        with self.service_context(saved), patch.object(dispatch, "status") as status:
            value = service.status(self.root)
        status.assert_not_called()
        self.assertEqual(value["mcp_lifecycle"]["status"], "unknown")

    def test_cli_and_gui_show_verified_and_unknown_as_separate_from_event_ack(self):
        self.lifecycle()
        for verified in (True, False):
            if not verified:
                (self.attempt / "mcp-stdio-exit.json").unlink()
            with self.service_context():
                stream = io.StringIO()
                with redirect_stdout(stream):
                    self.assertEqual(main(["--format", "text", "agent", "status"], root=self.root), 0)
                status = service.status(self.root)["mcp_lifecycle"]
            label = "MCP退出已驗證" if verified else "MCP退出未驗證"
            self.assertIn(label, stream.getvalue())
            self.assertIn("ACK 只代表收到", stream.getvalue())
            shown = view_snapshot({"automatic_agent": {"state": "stopped", "mcp_lifecycle": status},
                                   "counts": {"acked": 1}})
            self.assertIn(label, shown["automatic_status"])
        self.assertIn("MCP退出未驗證", mcp_lifecycle_text({"status": "verified", "exit_code": False,
            "ack_flushed": True, "reason": ["PRIVATE-CANARY"]}))
