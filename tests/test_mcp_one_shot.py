"""Finite event-bound ACK shutdown; mocks and actual SDK/Windows remain distinct."""
import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest

from eventguard.acceptance_control import read_json
from eventguard.events.store import EventStore
from eventguard.processes import spawn, finish
from eventguard.synthetic import make_synthetic

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts/eventguard_inbox_mcp.py"
SPEC = importlib.util.spec_from_file_location("fixture_one_shot_inbox", ENTRY)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class OneShotReplyTests(unittest.TestCase):
    def test_only_same_request_and_exact_successful_ack_reply_can_end_scope(self):
        result = {"status": "review_recorded", "event_id": "event-one", "query_id": "query-one",
                  "outbox_acknowledged": True}
        guard = module._OneShotAckExit()
        good = {"jsonrpc": "2.0", "id": 1, "result": {
            "content": [{"type": "text", "text": json.dumps(result)}], "isError": False}}
        guard.response_flushed(good)
        self.assertFalse(guard.stop_event.is_set())
        guard.arm(1, result)
        changed = json.loads(json.dumps(good))
        changed["id"] = True
        guard.response_flushed(changed)
        self.assertFalse(guard.stop_event.is_set())
        changed = json.loads(json.dumps(good))
        changed["result"]["content"][0]["text"] = json.dumps({**result, "query_id": "other"})
        guard.response_flushed(changed)
        self.assertFalse(guard.stop_event.is_set())
        changed = json.loads(json.dumps(good))
        changed["result"]["isError"] = True
        guard.response_flushed(changed)
        self.assertFalse(guard.stop_event.is_set())
        guard.response_flushed(good)
        self.assertTrue(guard.stop_event.is_set())

    def test_non_ack_results_and_rearming_are_rejected(self):
        guard = module._OneShotAckExit()
        with self.assertRaisesRegex(ValueError, "one_shot_durable_ack_required"):
            guard.arm(1, {"status": "event_available"})
        result = {"status": "review_recorded", "outbox_acknowledged": True}
        guard.arm("request-one", result)
        with self.assertRaisesRegex(ValueError, "one_shot_ack_already_pending"):
            guard.arm("request-two", result)


@unittest.skipUnless(os.name == "nt" and importlib.util.find_spec("mcp"), "Windows and installed optional SDK")
class OneShotStdioTests(unittest.TestCase):
    def test_exact_ack_reply_is_delivered_then_process_exits_with_stdin_still_open(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = EventStore(root / "source")
            event = make_synthetic("listener")
            store.enqueue(event)
            directory = root / "reports/attempt"
            messages, error_sizes = queue.Queue(), []
            child = spawn([sys.executable, "-B", str(ENTRY), "--source-dir", str(root / "source"),
                "--state-dir", str(root / "inbox"), "--event-id", event["event_id"],
                "--project-root", str(root), "--startup-evidence-dir", str(directory), "--exit-after-ack"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            def read_output():
                try:
                    for line in child.stdout:
                        messages.put(json.loads(line))
                finally:
                    child.stdout.close()
            def read_errors():
                try:
                    while chunk := child.stderr.read(4096):
                        error_sizes.append(len(chunk))
                finally:
                    child.stderr.close()
            readers = [threading.Thread(target=read_output, daemon=True), threading.Thread(target=read_errors, daemon=True)]
            for reader in readers:
                reader.start()
            def request(identity, method, params):
                child.stdin.write((json.dumps({"jsonrpc": "2.0", "id": identity, "method": method,
                    "params": params}) + "\n").encode())
                child.stdin.flush()
                reply = messages.get(timeout=20)
                self.assertEqual(reply.get("id"), identity)
                self.assertNotIn("error", reply)
                return reply["result"]
            def tool(identity, name, arguments):
                value = request(identity, "tools/call", {"name": name, "arguments": arguments})
                self.assertIs(value.get("isError", False), False)
                return json.loads(value["content"][0]["text"])
            try:
                request(1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "one-shot-synthetic-fixture", "version": "1"}})
                child.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                child.stdin.flush()
                request(2, "tools/list", {})
                tool(3, "receive_event", {})
                query_id = tool(4, "query_evidence", {"event_id": event["event_id"]})["query_id"]
                result = tool(5, "ack_event", {"event_id": event["event_id"], "query_id": query_id,
                    "decision": "reviewed_metadata"})
                self.assertIs(result["outbox_acknowledged"], True)
                self.assertFalse(child.stdin.closed)
                self.assertEqual(child.wait(timeout=10), 0)
                self.assertFalse(child.stdin.closed, "Exit is ACK-driven, not a client EOF")
            finally:
                if not child.stdin.closed:
                    child.stdin.close()
                receipt = finish(child, "descendants_remaining", grace=2, request_stop=True)
                for reader in readers:
                    reader.join(timeout=2)
            self.assertFalse(receipt["forcibly_terminated"])
            self.assertEqual(receipt["remaining_owned_processes"], 0)
            ended = read_json(directory / "mcp-stdio-exit.json")
            self.assertEqual(ended["return_code"], 0)
            self.assertIs(ended["ack_response_flushed"], True)
            self.assertIs(ended["one_shot"], True)
            self.assertIs(ended["os_exit_verified"], False)
            self.assertEqual(store.stats()["pending"], 0)
            self.evidence = {"scope": "real SDK synthetic ACK; no model/native scan/network", "process": receipt,
                             "ack_reply_received_before_exit": True, "client_stdin_still_open_at_exit": True}
