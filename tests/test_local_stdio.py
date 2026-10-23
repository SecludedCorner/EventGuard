"""Real SDK ClientSession + stdio subprocess, with EOF-only process cleanup.

SDK 1.6.0 stdio_client explicitly terminates its child in finally. This test
therefore uses owned asyncio pipes and SDK memory streams, without that cleanup.
No model, server socket, native collector, token, or external network is used.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

try:
    import anyio
    from mcp import ClientSession, types
    try:
        from mcp.shared.message import SessionMessage
    except ImportError:
        SessionMessage = None  # SDK 1.6 uses bare JSONRPCMessage streams.
    HAS_SDK = True
except ImportError:
    HAS_SDK = False


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts" / "eventguard_local_mcp.py"
OWNED_CHILDREN = []
# Allow cold imports of the installed SDK without changing the server's bounded
# wait/EOF contracts. These are transport deadlines, not model or event waits.
SDK_RESPONSE_TIMEOUT = timedelta(seconds=20)


def synthetic_event(identity="evt-stdio-test"):
    return {"schema_version": "2.0", "event_id": identity, "host_id": "host-test", "episode_id": "ep-test",
            "correlation_id": "corr-test", "sequence": 1, "event_type": "listener.changed",
            "transition": "new", "severity": "warning", "synthetic": True,
            "observed_at": "2026-10-22T00:00:00Z", "persisted_at": "2026-10-22T00:00:01Z",
            "evidence": {"protocol": "TCP", "port": 18080, "scope": "all_interfaces"},
            "coverage": {"status": "ok", "gaps": []}}


def result_json(result):
    if result.isError:
        raise AssertionError("tool returned error: " + str(result.content))
    return json.loads(next(item.text for item in result.content if item.type == "text"))


def child_environment():
    # Explicit non-secret process necessities only; do not copy all environment.
    result = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
              "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    # Windows Python discovers its already-installed user-site SDK from this
    # explicit runtime directory. No credential/configuration content is read.
    appdata = os.environ.get("APPDATA")
    if appdata:
        result["APPDATA"] = appdata
    return result


class OwnedTransport:
    def __init__(self, process):
        self.process = process
        self.requests = []
        self.errors = bytearray()

    def close_stdin(self):
        if self.process.stdin is not None and not self.process.stdin.is_closing():
            self.process.stdin.close()


async def communicate_owned(process):
    communication = asyncio.create_task(process.communicate())
    try:
        return await asyncio.wait_for(asyncio.shield(communication), timeout=15)
    finally:
        # Preserve a timeout failure while allowing the same child to finish
        # draining. Never cancel its pipe reader, retry it or kill by PID.
        if not communication.done():
            await asyncio.wait_for(communication, timeout=10)


@asynccontextmanager
async def owned_stdio(data_dir, single_wait=False):
    process = await asyncio.create_subprocess_exec(sys.executable, "-B", str(ENTRY), "--data-dir", str(data_dir),
                                                  *(["--single-wait"] if single_wait else []),
                                                  stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                  stderr=asyncio.subprocess.PIPE, cwd=str(ROOT), env=child_environment())
    transport = OwnedTransport(process)
    OWNED_CHILDREN.append(process)
    read_sender, read_stream = anyio.create_memory_object_stream(8)
    write_stream, write_receiver = anyio.create_memory_object_stream(8)

    async def reader():
        async with read_sender:
            while line := await process.stdout.readline():
                message = types.JSONRPCMessage.model_validate_json(line)
                await read_sender.send(SessionMessage(message) if SessionMessage else message)

    async def writer():
        try:
            async with write_receiver:
                async for message in write_receiver:
                    message = getattr(message, "message", message)
                    raw = message.model_dump(by_alias=True, mode="json", exclude_none=True)
                    if raw.get("method") == "tools/call":
                        transport.requests.append(raw)
                    if process.stdin.is_closing():
                        break
                    process.stdin.write((message.model_dump_json(by_alias=True, exclude_none=True) + "\n").encode("utf-8"))
                    await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            transport.close_stdin()

    async def errors():
        while chunk := await process.stderr.read(4096):
            if len(transport.errors) < 16384:
                transport.errors.extend(chunk[:16384 - len(transport.errors)])

    tasks = [asyncio.create_task(reader()), asyncio.create_task(writer()), asyncio.create_task(errors())]
    try:
        yield transport, read_stream, write_stream
    finally:
        await write_stream.aclose()
        transport.close_stdin()
        try:
            # wait_for cancels only the wait coroutine, never kills the process.
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            raise AssertionError("stdio child did not exit cooperatively after EOF; no kill attempted") from None
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await read_stream.aclose()


@unittest.skipUnless(HAS_SDK, "Optional already-installed MCP SDK unavailable; core does not require it")
class LocalStdioTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / "experiment"
        self.started = time.monotonic()
        self.pending_calls = []

    async def asyncTearDown(self):
        for task in self.pending_calls:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.pending_calls, return_exceptions=True)
        self.temp.cleanup()
        self.assertLess(time.monotonic() - self.started, getattr(self, "allowed_seconds", 60))
        self.assertEqual(sum(child.returncode is None for child in OWNED_CHILDREN), 0,
                         "remaining_owned_children must be zero without kill/terminate")

    async def test_real_sdk_wait_query_ack_and_timeout(self):
        from eventguard.local_wait import LocalWait
        producer = LocalWait(self.directory)
        async with owned_stdio(self.directory) as (transport, incoming, outgoing):
            async with ClientSession(incoming, outgoing, read_timeout_seconds=SDK_RESPONSE_TIMEOUT) as session:
                initialized = await session.initialize()
                self.assertTrue(initialized.serverInfo.name)
                tools = await session.list_tools()
                self.assertEqual({tool.name for tool in tools.tools}, {"wait_for_event", "query_evidence", "ack_event"})
                schemas = {tool.name: tool.inputSchema for tool in tools.tools}
                self.assertEqual(schemas["ack_event"]["properties"]["decision"]["enum"],
                                 ["needs_more_evidence", "reviewed_synthetic"])
                self.assertEqual(schemas["wait_for_event"]["properties"]["timeout_seconds"]["minimum"], 1)
                self.assertEqual(schemas["wait_for_event"]["properties"]["timeout_seconds"]["maximum"], 45)
                waiting = asyncio.create_task(session.call_tool("wait_for_event", {"timeout_seconds": 5}))
                self.pending_calls.append(waiting)
                await asyncio.sleep(0.15)
                self.assertFalse(waiting.done())
                producer.store.enqueue(synthetic_event())
                event = result_json(await waiting)
                self.assertEqual(event["status"], "event_available")
                self.assertEqual(event["event_id"], "evt-stdio-test")
                evidence = result_json(await session.call_tool("query_evidence", {"event_id": event["event_id"]}))
                self.assertEqual(evidence["status"], "synthetic_snapshot")
                self.assertFalse(evidence["system_query_executed"])
                ack = result_json(await session.call_tool("ack_event", {"event_id": event["event_id"],
                                  "query_id": evidence["query_id"], "decision": "reviewed_synthetic"}))
                self.assertEqual(ack["status"], "synthetic_result_recorded")
                self.assertFalse(ack["real_agent_wake_verified"])
                self.assertTrue(ack["outbox_acknowledged"])
                for args in ({"timeout_seconds": True}, {"timeout_seconds": "1"}, {"timeout_seconds": 1, "shell": "forbidden"}):
                    self.assertTrue((await session.call_tool("wait_for_event", args)).isError)
                expired = result_json(await session.call_tool("wait_for_event", {"timeout_seconds": 1}))
                self.assertEqual(expired["status"], "wait_expired")
                self.assertTrue(expired["do_not_model_repoll"])
        self.assertEqual(transport.process.returncode, 0, transport.errors.decode("utf-8", errors="replace"))

    async def test_single_wait_refuses_model_repoll_after_expiry(self):
        async with owned_stdio(self.directory, single_wait=True) as (transport, incoming, outgoing):
            async with ClientSession(incoming, outgoing, read_timeout_seconds=SDK_RESPONSE_TIMEOUT) as session:
                await session.initialize()
                result = result_json(await session.call_tool("wait_for_event", {"timeout_seconds": 1}))
                self.assertEqual(result["status"], "wait_expired")
                second = await session.call_tool("wait_for_event", {"timeout_seconds": 1})
                self.assertTrue(second.isError)
        ledger = json.loads((self.directory / "local-wait-results.json").read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["waits"]), 1)
        self.assertEqual(transport.process.returncode, 0)

    async def test_runtime_rejects_second_stdio_process(self):
        async with owned_stdio(self.directory) as (transport, incoming, outgoing):
            async with ClientSession(incoming, outgoing, read_timeout_seconds=SDK_RESPONSE_TIMEOUT) as session:
                await session.initialize()
                second = await asyncio.create_subprocess_exec(
                    sys.executable, "-B", str(ENTRY), "--data-dir", str(self.directory),
                    stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, env=child_environment())
                OWNED_CHILDREN.append(second)
                stdout, stderr = await communicate_owned(second)
                self.assertEqual(second.returncode, 3)
                self.assertEqual(stdout, b"")
                self.assertIn(b"active stdio server", stderr)
                # The first server still owns a working protocol session.
                self.assertEqual(len((await session.list_tools()).tools), 3)
        self.assertEqual(transport.process.returncode, 0)

    async def test_request_cancellation_and_eof_cancel_pending_wait(self):
        from eventguard.local_wait import LocalWait
        LocalWait(self.directory)
        async with owned_stdio(self.directory) as (transport, incoming, outgoing):
            async with ClientSession(incoming, outgoing, read_timeout_seconds=SDK_RESPONSE_TIMEOUT) as session:
                await session.initialize()
                waiting = asyncio.create_task(session.call_tool("wait_for_event", {"timeout_seconds": 5}))
                self.pending_calls.append(waiting)
                await asyncio.sleep(0.15)
                request_id = transport.requests[-1]["id"]
                await session.send_notification(types.ClientNotification(types.CancelledNotification(
                    method="notifications/cancelled",
                    params=types.CancelledNotificationParams(requestId=request_id, reason="synthetic cancellation test"))))
                await asyncio.sleep(0.2)
                self.assertFalse(waiting.done(), "cancelled request must not produce a model-visible response")
                waiting.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await waiting
                ledger = json.loads((self.directory / "local-wait-results.json").read_text(encoding="utf-8"))
                self.assertEqual(ledger["waits"][-1]["status"], "cancelled")
                pending = asyncio.create_task(session.call_tool("wait_for_event", {"timeout_seconds": 5}))
                self.pending_calls.append(pending)
                await asyncio.sleep(0.15)
                self.assertFalse(pending.done())
                transport.close_stdin()
                await asyncio.wait_for(transport.process.wait(), timeout=3)
                pending.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await pending
        self.assertEqual(transport.process.returncode, 0, transport.errors.decode("utf-8", errors="replace"))
        ledger = json.loads((self.directory / "local-wait-results.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["waits"][-1]["status"], "cancelled")

    async def test_missing_sdk_friendly_exit_and_required_directory(self):
        for args, phrase in ((["--data-dir", str(self.directory)], b"SDK is unavailable"), ([], b"--data-dir")):
            process = await asyncio.create_subprocess_exec(sys.executable, "-B", "-S", str(ENTRY), *args,
                         stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                         env=child_environment(), cwd=str(ROOT))
            OWNED_CHILDREN.append(process)
            stdout, stderr = await communicate_owned(process)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(stdout, b"")
            self.assertIn(phrase, stderr)

    async def test_external_program_emits_synthetic_event_without_sdk_or_server(self):
        from eventguard.local_wait import LocalWait
        producer = LocalWait(self.directory)
        self.allowed_seconds = 45  # Includes cold Windows process/filesystem startup.
        identities = []
        for _ in range(2):
            process = await asyncio.create_subprocess_exec(sys.executable, "-B", "-S", str(ENTRY),
                         "--data-dir", str(self.directory), "--emit-synthetic",
                         stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                         env=child_environment(), cwd=str(ROOT))
            OWNED_CHILDREN.append(process)
            stdout, stderr = await communicate_owned(process)
            self.assertEqual(process.returncode, 0, stderr.decode("utf-8", errors="replace"))
            identities.append(json.loads(stdout)["event_id"])
        self.assertNotEqual(*identities)
        for event_id in identities:
            event = producer.store.get_event(event_id)
            self.assertTrue(event["synthetic"])
            self.assertEqual(event["evidence"], {"protocol": "TCP", "port": 45454, "scope": "all_interfaces"})


if __name__ == "__main__":
    unittest.main()
