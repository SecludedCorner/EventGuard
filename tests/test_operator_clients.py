"""Actual concurrent stdio clients; isolated synthetic data, no agent or scan."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

from eventguard.acceptance_control import FileLease
from eventguard.events.store import EventStore
from eventguard.processes import spawn, finish
from eventguard.runtime import Runtime
from eventguard.synthetic import make_synthetic

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts/eventguard_inbox_mcp.py"


class Client:
    def __init__(self, argv):
        self.child = spawn([sys.executable, "-B", str(ENTRY), *map(str, argv)],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.incoming, self.transcript, self.stderr = queue.Queue(), [], bytearray()
        self.request_id = 0
        def read():
            try:
                for line in self.child.stdout:
                    self.incoming.put(json.loads(line))
            finally:
                self.incoming.put({"eof": True})
        def errors():
            while chunk := self.child.stderr.read(4096):
                self.stderr.extend(chunk[:max(0, 16384-len(self.stderr))])
        self.readers = [threading.Thread(target=read, daemon=True), threading.Thread(target=errors, daemon=True)]
        for reader in self.readers:
            reader.start()

    def request(self, method, params):
        self.request_id += 1
        request = {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params}
        self.send(request)
        response = self.incoming.get(timeout=30)
        self.transcript.append({"response": response})
        if response.get("id") != self.request_id or "error" in response:
            raise AssertionError("stdio_response_missing_or_invalid")
        return response["result"]

    def send(self, request):
        self.transcript.append({"request": request})
        self.child.stdin.write((json.dumps(request) + "\n").encode())
        self.child.stdin.flush()

    def initialize(self):
        self.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                     "clientInfo": {"name": "fixture-no-model", "version": "1"}})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self.request("tools/list", {})["tools"]

    def call(self, name, **arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise AssertionError("stdio_tool_error")
        return json.loads(next(item["text"] for item in result["content"] if item["type"] == "text"))

    def close(self):
        self.child.stdin.close()
        try:
            self.child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        self.receipt = finish(self.child, "test_teardown", grace=1)
        for reader in self.readers:
            reader.join(1)
        self.child.stdout.close()
        self.child.stderr.close()


@unittest.skipUnless(os.name == "nt", "actual Windows owned-job stdio test")
class OperatorClientsTests(unittest.TestCase):
    def test_two_clients_share_recovery_ack_and_stop_while_mutation_busy(self):
        try:
            import mcp  # noqa: F401
        except ImportError:
            self.skipTest("optional installed MCP SDK unavailable; no installation")
        clients, receipts = [], []
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as cleanup:
            root = Path(temporary)
            for name in ("config/default.json", "playbooks/default.json"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, path)
            runtime = Runtime(root)
            runtime.ensure()
            event = make_synthetic()
            store = EventStore(root / "data/test")
            store.enqueue(event)
            # Simulate an already connected old operator without deleting or
            # replacing its persistent file/OS lease.
            legacy = FileLease(root / "data/operator-stdio.lock")
            self.assertTrue(legacy.acquire())
            cleanup.callback(legacy.release)
            for _ in range(2):
                client = Client(["--operator-root", root])
                clients.append(client)
                cleanup.callback(client.close)
                self.assertEqual(len(client.initialize()), 15)
            a, b = clients
            self.assertTrue(all(client.child.poll() is None for client in clients))
            mutation = FileLease(root / "data/operator-mutation.lock")
            self.assertTrue(mutation.acquire())
            try:
                blocked = a.call("receive_event", event_id=event["event_id"])
                self.assertEqual((blocked["status"], blocked["reason"]), ("busy", "operator_operation_busy"))
                self.assertFalse(blocked["operation_started"])
                self.assertFalse(blocked["automatic_retry_allowed"])
                self.assertEqual(b.call("list_events")["events"][0]["event_id"], event["event_id"])
                self.assertEqual(b.call("stop")["status"], "not_running")
                self.assertFalse((root / "data/agent-delivery-test").exists())
            finally:
                mutation.release()
            first = a.call("receive_event", event_id=event["event_id"])
            recovered = b.call("receive_event", event_id=event["event_id"])
            self.assertEqual((first["event_id"], first["query_id"]), (recovered["event_id"], recovered["query_id"]))
            self.assertEqual(store.stats()["pending"], 1)
            ack = b.call("ack_event", event_id=event["event_id"], query_id=recovered["query_id"])
            replay = a.call("ack_event", event_id=event["event_id"], query_id=first["query_id"])
            self.assertTrue(ack["outbox_acknowledged"])
            self.assertTrue(replay["ack_replay_verified"])
            self.assertEqual((store.stats()["pending"], store.stats()["receipt_count"]), (0, 1))
            # Legacy event-bound state remains an exclusive stdio owner.
            state = root / "data/agent-delivery-test"
            bound = FileLease(state / "inbox-owner.lock")
            self.assertTrue(bound.acquire())
            try:
                refused = Client(["--source-dir", root / "data/test", "--state-dir", state,
                                  "--event-id", event["event_id"]])
                clients.append(refused)
                cleanup.callback(refused.close)
                self.assertEqual(refused.child.wait(timeout=30), 3)
            finally:
                bound.release()
            stats = store.stats()
            # ExitStack closes all three transports by EOF before temp cleanup.
            cleanup.close()
            for client in clients:
                receipt = client.receipt
                receipts.append(receipt)
                self.assertTrue(receipt["child_exited"])
                self.assertFalse(receipt["forcibly_terminated"])
                self.assertEqual(receipt["remaining_owned_processes"], 0)
                self.assertFalse(any(reader.is_alive() for reader in client.readers))
            self.assertEqual([r["exit_code"] for r in receipts], [0, 0, 3])
            self.assertEqual(bytes(refused.stderr), b"EventGuard: this inbox state already has an active stdio owner.\r\n")
            self.evidence = {"scope": "real Windows stdio with synthetic fixtures; not model reception",
                "generated_ids": [event["event_id"]], "received_ids": [first["event_id"], recovered["event_id"]],
                "query_ids": [first["query_id"], recovered["query_id"]], "ack_ids": [ack["event_id"]],
                "receipt_count": stats["receipt_count"], "missing": [], "pending_before_ack": 1,
                "ack_replay_verified": replay["ack_replay_verified"], "processes": receipts,
                "transports": [client.transcript for client in clients],
                "legacy_busy_stderr_sha256": hashlib.sha256(refused.stderr).hexdigest(),
                "model_calls": 0, "native_provider_queries": 0}
