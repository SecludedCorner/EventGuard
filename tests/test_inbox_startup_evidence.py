"""Optional MCP phase markers; fixtures and actual installed-SDK stdio only."""
import importlib.util
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from eventguard.acceptance_control import read_json
from eventguard.events.store import EventStore
from eventguard.processes import spawn, finish
from eventguard.synthetic import make_synthetic

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts/eventguard_inbox_mcp.py"
SPEC = importlib.util.spec_from_file_location("fixture_inbox_startup", ENTRY)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class StartupEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_only_runtime_subtrees_accept_markers_and_existing_evidence_is_not_replaced(self):
        for name in ("data", "logs", "reports"):
            with self.subTest(name=name):
                directory = self.root / name / "attempt"
                evidence = module._StartupEvidence(self.root, directory)
                evidence.finish(0)
                original = (directory / "mcp-server-started.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "startup_evidence_already_used"):
                    module._StartupEvidence(self.root, directory)
                self.assertEqual((directory / "mcp-server-started.json").read_bytes(), original)
        for directory in (self.root / "src", self.root.parent / "outside-marker-scope", self.root):
            with self.subTest(directory=directory), self.assertRaises(ValueError):
                module._StartupEvidence(self.root, directory)

    def test_redirect_is_rejected_before_marker_creation(self):
        redirect = self.root / "reports" / "redirect"
        with patch.object(Path, "is_symlink", autospec=True, side_effect=lambda path: path == redirect):
            with self.assertRaisesRegex(RuntimeError, "redirect_rejected"):
                module._StartupEvidence(self.root, redirect)
        self.assertFalse(redirect.exists())

    def test_observer_without_optional_argument_never_creates_markers(self):
        with patch.object(module, "_run", return_value=0) as run, patch.object(module, "_StartupEvidence") as evidence:
            self.assertEqual(module.main(["--operator-root", str(self.root)]), 0)
        evidence.assert_not_called()
        self.assertIsNone(run.call_args.args[1])

    def test_initialization_failure_records_non_stdio_exit_without_raw_error(self):
        directory = self.root / "reports" / "failed-attempt"
        with patch.object(module, "build_server", side_effect=ValueError("PRIVATE_RAW_FAILURE")), \
                patch("builtins.print") as output:
            code = module.main(["--source-dir", str(self.root / "source"), "--state-dir", str(self.root / "state"),
                "--event-id", "synthetic-event", "--project-root", str(self.root),
                "--startup-evidence-dir", str(directory)])
        self.assertEqual(code, 2)
        self.assertFalse((directory / "mcp-tools-listed.json").exists())
        ended = read_json(directory / "mcp-stdio-exit.json")
        self.assertEqual(ended["return_code"], 2)
        self.assertIs(ended["stdio_entered"], False)
        self.assertIs(ended["os_exit_verified"], False)
        self.assertNotIn("PRIVATE_RAW_FAILURE", str(output.call_args_list))

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "optional installed MCP SDK")
    def test_sdk_tools_list_records_bound_phases_and_eof_without_receiving_or_ack(self):
        source = self.root / "source"
        store = EventStore(source)
        event = make_synthetic("listener")
        store.enqueue(event)
        directory = self.root / "reports" / "attempt"
        messages, stderr_bytes = queue.Queue(), []
        child = spawn([sys.executable, "-B", str(ENTRY), "--source-dir", str(source),
            "--state-dir", str(self.root / "inbox"), "--event-id", event["event_id"],
            "--project-root", str(self.root), "--startup-evidence-dir", str(directory)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def read_output():
            try:
                for line in child.stdout:
                    messages.put(json.loads(line))
            finally:
                child.stdout.close()
        def drain_errors():
            try:
                while chunk := child.stderr.read(4096):
                    stderr_bytes.append(len(chunk))
            finally:
                child.stderr.close()
        readers = [threading.Thread(target=read_output, daemon=True), threading.Thread(target=drain_errors, daemon=True)]
        for reader in readers:
            reader.start()
        def send(value):
            child.stdin.write(json.dumps(value).encode()+b"\n")
            child.stdin.flush()
        try:
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "synthetic-marker-fixture", "version": "1"}}})
            self.assertEqual(messages.get(timeout=20)["id"], 1)
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            reply = messages.get(timeout=20)
            self.assertEqual(reply["id"], 2)
            self.assertEqual({tool["name"] for tool in reply["result"]["tools"]},
                             {"receive_event", "query_evidence", "ack_event"})
            child.stdin.close()
            self.assertEqual(child.wait(timeout=15), 0)
        finally:
            if child.stdin is not None and not child.stdin.closed:
                child.stdin.close()
            receipt = finish(child, "descendants_remaining", grace=2, request_stop=True)
            for reader in readers:
                reader.join(timeout=2)
        self.assertIs(receipt["forcibly_terminated"], False)
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        markers = [read_json(directory / ("mcp-"+phase+".json")) for phase in module._StartupEvidence.PHASES]
        self.assertEqual(len({marker["instance_id"] for marker in markers}), 1)
        self.assertTrue(all(marker["pid"] == child.pid and marker["created_at"] == child.created_at for marker in markers))
        self.assertEqual(markers[1]["tool_names"], ["ack_event", "query_evidence", "receive_event"])
        self.assertIs(markers[1]["response_prepared"], True)
        self.assertEqual(markers[2]["return_code"], 0)
        self.assertIs(markers[2]["stdio_entered"], True)
        self.assertIs(markers[2]["os_exit_verified"], False)
        self.assertEqual(store.stats()["pending"], 1)
        self.assertEqual(store.get_event(event["event_id"])["delivery_status"], "pending")
        self.assertFalse(list((self.root / "inbox").glob("snapshot-*.json")))
        self.assertTrue(all(path.stat().st_size < 2048 for path in directory.glob("*.json")))
        self.evidence = {"scope": "actual installed SDK tools/list with synthetic event; no model/network",
                         "event_received": False, "event_acknowledged": False, "process": receipt,
                         "phases": list(module._StartupEvidence.PHASES)}
