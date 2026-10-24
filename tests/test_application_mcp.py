"""Real installed SDK/SSE protocol; fixture app only, no OS sources or model."""
import asyncio
import builtins
from datetime import timedelta
import http.client
import importlib.util
import json
import logging
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from eventguard.application_mcp import (
    APPLICATION_TOOLS, AppMCPServer, _LoopbackOnly,
    call_application_tool, validate_application_tool,
)

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "a" * 64  # A public fixture token, never an account credential.
SDK_AVAILABLE = all(importlib.util.find_spec(name) is not None for name in ("mcp", "uvicorn", "starlette"))


class FixtureApplication:
    """Same object/API boundary. Monitor actions are explicit fixture states."""
    instance_id = "b" * 32
    namespace = "test"

    def __init__(self):
        self.state, self.calls, self.handling = "stopped", [], "new"

    def capabilities(self):
        return {"ack_available": False, "model_calls": 0}

    def status(self):
        return {"monitor_state": self.state, "model_calls": 0}

    def monitor_control(self, action, source="mcp", operation_id=None):
        self.calls.append((action, source, operation_id))
        self.state = {"start": "running", "pause": "paused", "resume": "running", "stop": "stopped", "shutdown": "stopped"}[action]
        return {"state": self.state, "operation_id": operation_id, "model_calls": 0}

    def list_events(self, **filters):
        self.calls.append(("list", filters))
        return {"events": [{"event_id": "evt-fixture", "status": self.handling}], "model_calls": 0}

    def event_detail(self, event_id):
        return {"event_id": event_id, "status": self.handling, "model_calls": 0}

    def set_event_status(self, event_id, status, source="mcp", operation_id=None):
        self.calls.append(("handling", event_id, status, source, operation_id))
        self.handling = status
        return {"event_id": event_id, "status": status, "ack_performed": False, "model_calls": 0}


class ApplicationToolContractTests(unittest.TestCase):
    def test_same_application_dispatch_has_no_sdk_dependency(self):
        original_import = builtins.__import__

        def no_sdk(name, *args, **kwargs):
            if name == "mcp" or name.startswith("mcp.") or name in {"uvicorn", "starlette"}:
                raise AssertionError("standard-library dispatcher cannot import SDK")
            return original_import(name, *args, **kwargs)

        app = FixtureApplication()
        with patch("builtins.__import__", side_effect=no_sdk):
            for name in ("capabilities", "status", "start_monitor", "pause_monitor", "resume_monitor", "stop_monitor"):
                result = call_application_tool(app, name, {})
                self.assertEqual(result["instance_id"], app.instance_id)
                self.assertEqual(result["namespace"], "test")
                self.assertEqual(result["model_calls"], 0)
            call_application_tool(app, "set_event_status", {"event_id": "evt-fixture", "status": "handled", "operation_id": "fixture-1"})
            self.assertEqual(call_application_tool(app, "inspect_event", {"event_id": "evt-fixture"})["status"], "handled")
            self.assertFalse(call_application_tool(app, "set_event_status", {"event_id": "evt-fixture", "status": "read"})["ack_performed"])
        self.assertEqual([row[1] for row in app.calls[:4]], ["mcp"] * 4)

    def test_unknown_keys_scope_commands_and_invalid_types_are_rejected_before_app(self):
        app = FixtureApplication()
        cases = [(name, {"root": "elsewhere"}) for name in APPLICATION_TOOLS]
        cases += [("status", {"namespace": "live"}), ("ack_event", {}),
                  ("start_monitor", {"operation_id": "x" * 129}), ("stop_monitor", {"operation_id": "unsafe\n"}),
                  ("inspect_event", {"event_id": "../private"}),
                  ("set_event_status", {"event_id": "evt-fixture", "status": "run-command"}),
                  ("list_events", {"limit": True}), ("list_events", {"limit": 1001}),
                  ("list_events", {"offset": -1}), ("list_events", {"severity": []})]
        for name, arguments in cases:
            with self.subTest(name=name, arguments=arguments), self.assertRaisesRegex(ValueError, "^invalid_application_tool_arguments$"):
                call_application_tool(app, name, arguments)
        self.assertEqual(app.calls, [])

    def test_fixed_enums_bounded_filters_and_operation_id_are_shared(self):
        arguments = {"severity": "high", "source": "listeners", "status": "new", "limit": 1000, "offset": 0}
        validate_application_tool("list_events", arguments)
        app = FixtureApplication()
        call_application_tool(app, "list_events", arguments)
        self.assertEqual(app.calls, [("list", arguments)])
        call_application_tool(app, "start_monitor", {"operation_id": "x" * 128})
        self.assertEqual(app.calls[-1], ("start", "mcp", "x" * 128))

    def test_raw_application_exceptions_do_not_cross_tool_boundary(self):
        app = FixtureApplication()
        with patch.object(app, "status", side_effect=OSError("PRIVATE-CANARY")):
            result = call_application_tool(app, "status", {})
        self.assertEqual(result["reason"], "application_read_unavailable")
        self.assertNotIn("PRIVATE-CANARY", json.dumps(result))
        with patch.object(app, "monitor_control", side_effect=OSError("PRIVATE-CANARY")):
            result = call_application_tool(app, "start_monitor", {})
        self.assertTrue(result["operation_may_have_completed"])
        self.assertFalse(result["automatic_retry_allowed"])

    def test_wrong_application_result_scope_is_not_relabelled_as_confirmed(self):
        app = FixtureApplication()
        with patch.object(app, "status", return_value={"instance_id": "other", "namespace": "live", "private": "CANARY"}):
            value = call_application_tool(app, "status", {})
        self.assertEqual(value["state"], "unknown")
        self.assertEqual(value["instance_id"], app.instance_id)
        self.assertEqual(value["namespace"], "test")
        self.assertNotIn("CANARY", json.dumps(value))

    def test_missing_sdk_is_blocked_and_never_closes_application(self):
        app = FixtureApplication()
        server = AppMCPServer(app, TOKEN)
        original_import = builtins.__import__

        def missing(name, *args, **kwargs):
            if name == "uvicorn":
                raise ImportError("synthetic optional dependency unavailable")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=missing):
            result = server.start()
        self.assertEqual(result["reason"], "application_mcp_dependencies_unavailable")
        self.assertEqual(app.state, "stopped")
        self.assertEqual(app.calls, [])
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertTrue(server.close()["thread_exited"])


@unittest.skipUnless(SDK_AVAILABLE, "optional installed MCP SDK/uvicorn/starlette unavailable; nothing installed")
class ApplicationSDKProtocolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Create/silence the client logger before the server snapshots SDK
        # loggers. No synthetic SSE session URLs belong in test evidence.
        for name, level in (("httpx", logging.WARNING), ("mcp.client.sse", logging.CRITICAL)):
            logger = logging.getLogger(name)
            previous = logger.level
            logger.setLevel(level)
            self.addCleanup(logger.setLevel, previous)
        self.app = FixtureApplication()
        self.server = AppMCPServer(self.app, TOKEN)
        self.ready = self.server.start()
        self.addCleanup(self.close_server)
        self.assertEqual(self.ready["state"], "ready", self.ready)

    @staticmethod
    def phase(code):
        print("application_mcp_fixture_phase=" + code, flush=True)

    def close_server(self):
        receipt = self.server.close()
        self.assertTrue(receipt["thread_exited"], receipt)
        self.assertFalse(receipt["application_closed"])
        self.assertFalse(receipt["forcibly_terminated"])

    @staticmethod
    def value(result):
        if result.isError:
            raise AssertionError("unexpected fixture SDK tool error")
        return json.loads(next(item.text for item in result.content if item.type == "text"))

    async def test_real_sdk_initialize_list_and_ten_calls_share_one_app(self):
        from mcp.client.sse import sse_client
        from mcp import ClientSession
        self.assertEqual(self.server.start()["url"], self.ready["url"])
        self.assertNotIn(TOKEN, json.dumps(self.ready))
        async with asyncio.timeout(20), sse_client(self.ready["url"], headers={"Authorization": "Bearer " + TOKEN}, timeout=5, sse_read_timeout=10) as streams:
            async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=5)) as session:
                initialized = await session.initialize()
                self.assertEqual(initialized.serverInfo.name, "EventGuard Application")
                names = {tool.name for tool in (await session.list_tools()).tools}
                self.assertEqual(names, APPLICATION_TOOLS)
                for name, args in (
                    ("capabilities", {}), ("status", {}),
                    ("start_monitor", {"operation_id": "sdk-start"}), ("pause_monitor", {"operation_id": "sdk-pause"}),
                    ("resume_monitor", {"operation_id": "sdk-resume"}), ("stop_monitor", {"operation_id": "sdk-stop"}),
                    ("list_events", {"severity": "high", "limit": 1}),
                    ("inspect_event", {"event_id": "evt-fixture"}),
                    ("set_event_status", {"event_id": "evt-fixture", "status": "handled", "operation_id": "sdk-handling"}),
                    ("shutdown_application", {"operation_id": "sdk-shutdown"}),
                ):
                    value = self.value(await session.call_tool(name, args))
                    self.assertEqual((value["instance_id"], value["namespace"], value["model_calls"]), (self.app.instance_id, "test", 0))
                self.assertEqual(self.app.handling, "handled")
                # Leave the fixture running, then disconnect only the client.
                self.value(await session.call_tool("start_monitor", {"operation_id": "sdk-disconnect"}))
        self.assertEqual(self.app.state, "running")
        self.assertTrue(self.server._thread.is_alive())
        self.assertEqual(len([row for row in self.app.calls if row[0] in {"start", "pause", "resume", "stop"}]), 5)
        self.evidence = {"scope": "real SDK initialize/tools/list/tools/call over loopback SSE; fixture app only",
                         "tool_count": 10, "same_application": True, "model_calls": 0, "system_queries": 0}

    async def test_unknown_tool_arguments_reject_before_fixture_mutation(self):
        from mcp.client.sse import sse_client
        from mcp import ClientSession
        self.phase("invalid_preflight_before")
        self.assertEqual(self.server.status()["state"], "ready")
        split = urlsplit(self.ready["url"])
        connection = http.client.HTTPConnection("127.0.0.1", split.port, timeout=5)
        try:
            connection.request("GET", "/sse")
            response = connection.getresponse()
            self.assertEqual(response.status, 401)
            response.read()
        finally:
            connection.close()
        self.phase("invalid_preflight_after")
        self.phase("invalid_connect_before")
        async with asyncio.timeout(20), sse_client(self.ready["url"], headers={"Authorization": "Bearer " + TOKEN}, timeout=5, sse_read_timeout=10) as streams:
            self.phase("invalid_connect_after")
            async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=5)) as session:
                self.phase("invalid_initialize_before")
                await session.initialize()
                self.phase("invalid_initialize_after")
                for label, name, arguments in (
                    ("extra_root", "start_monitor", {"root": "private"}),
                    ("extra_namespace", "list_events", {"namespace": "live"}),
                    ("invalid_status", "set_event_status", {"event_id": "evt-fixture", "status": "closed"}),
                ):
                    self.phase(label + "_before")
                    value = await session.call_tool(name, arguments)
                    # A timeout or transport McpError must fail this test. The
                    # SDK's validator ValueError has a real isError tool reply.
                    self.assertTrue(value.isError, "invalid input requires a protocol tool-error result")
                    self.assertEqual(self.app.calls, [])
                    self.phase(label + "_after")
                self.phase("invalid_session_exit_before")
            self.phase("invalid_session_exit_after")
            self.phase("invalid_sse_exit_before")
        self.phase("invalid_sse_exit_after")

    async def test_server_ready_close_receipts_keep_application_lifetime_separate(self):
        self.assertEqual(self.ready["readiness"], "ready")
        self.assertEqual(self.ready["transport"], "sse")
        self.assertEqual(self.ready["instance_id"], self.app.instance_id)
        self.assertFalse(self.server._thread.daemon)
        self.app.monitor_control("start", operation_id="fixture-lifetime")
        self.phase("server_close_before")
        receipt = self.server.close()
        self.phase("server_close_after")
        self.assertEqual(receipt["state"], "closed")
        self.assertTrue(receipt["thread_exited"])
        self.assertFalse(receipt["application_closed"])
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(self.app.state, "running")
        blocked = self.server.start()
        self.assertEqual(blocked["reason"], "application_mcp_closed")
        self.assertNotIn(TOKEN, json.dumps(receipt))

    async def test_asgi_fault_makes_status_unknown_with_only_bounded_exception_types(self):
        split = urlsplit(self.ready["url"])

        async def failing(scope, receive, send):
            raise ExceptionGroup("PRIVATE-CANARY-" + TOKEN, [RuntimeError("private"), ValueError("private")])

        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(message):
            pass

        secured = _LoopbackOnly(failing, "127.0.0.1:" + str(split.port), TOKEN, self.server._transport_exception)
        with self.assertRaises(ExceptionGroup):
            await secured({"type": "http", "client": ("127.0.0.1", 1), "method": "GET", "path": "/sse",
                "headers": [(b"host", ("127.0.0.1:" + str(split.port)).encode()),
                            (b"authorization", ("Bearer " + TOKEN).encode())]}, receive, send)
        value = self.server.status()
        self.assertEqual(value["state"], "unknown")
        self.assertTrue(value["thread_alive"])
        self.assertEqual(value["reason"], "application_mcp_transport_failed")
        self.assertEqual(value["exception_types"], ["RuntimeError", "ValueError"])
        self.assertNotIn("PRIVATE-CANARY", json.dumps(value))
        self.assertNotIn(TOKEN, json.dumps(value))

    async def test_http_auth_host_origin_and_body_limits_precede_sdk(self):
        split = urlsplit(self.ready["url"])
        cases = (({}, 401), ({"Authorization": "Bearer wrong"}, 401),
                 ({"Authorization": "Bearer " + TOKEN, "Host": "localhost:" + str(split.port)}, 403),
                 ({"Authorization": "Bearer " + TOKEN, "Origin": "http://external.invalid"}, 403))
        for headers, expected in cases:
            connection = http.client.HTTPConnection("127.0.0.1", split.port, timeout=5)
            try:
                connection.request("GET", "/sse", headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, expected)
                self.assertNotIn(TOKEN.encode(), response.read())
            finally:
                connection.close()
        connection = http.client.HTTPConnection("127.0.0.1", split.port, timeout=5)
        try:
            connection.request("POST", "/messages/", b"x" * 65537, headers={"Authorization": "Bearer " + TOKEN})
            response = connection.getresponse()
            self.assertEqual(response.status, 413)
            response.read()
        finally:
            connection.close()
        self.assertEqual(self.app.calls, [])

    async def test_stdio_application_branch_reuses_tools_without_legacy_owner(self):
        path = ROOT / "scripts/eventguard_inbox_mcp.py"
        spec = importlib.util.spec_from_file_location("application_mcp_fixture_adapter", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch("eventguard.operations.OperatorAPI", side_effect=AssertionError("same-app adapter must not create an owner")):
            protocol = module.build_operator_server(ROOT, application=self.app)
        self.assertIs(protocol._application, self.app)
        self.assertFalse(hasattr(protocol, "shutdown_owned_monitor"))
        self.assertEqual({tool.name for tool in await protocol.list_tools()}, APPLICATION_TOOLS)
        contents = await protocol.call_tool("status", {})
        value = json.loads(next(item.text for item in contents if item.type == "text"))
        self.assertEqual(value["instance_id"], self.app.instance_id)


class MiddlewarePeerTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_loopback_peer_and_duplicate_host_cannot_reach_sdk(self):
        reached, sent = [], []

        async def sdk(scope, receive, send):
            reached.append(True)

        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(message):
            sent.append(message)

        secured = _LoopbackOnly(sdk, "127.0.0.1:12345", TOKEN)
        for peer, hosts in (("192.0.2.1", [b"127.0.0.1:12345"]),
                            ("127.0.0.1", [b"127.0.0.1:12345", b"127.0.0.1:12345"])):
            sent.clear()
            await secured({"type": "http", "client": (peer, 1), "method": "GET", "path": "/sse",
                "headers": [(b"host", value) for value in hosts] + [(b"authorization", ("Bearer " + TOKEN).encode())]}, receive, send)
            self.assertEqual(sent[0]["status"], 403)
        self.assertEqual(reached, [])


@unittest.skipUnless(SDK_AVAILABLE, "optional installed SDK unavailable; nothing installed")
class SSETransportOwnershipTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for name, level in (("httpx", logging.WARNING), ("mcp.client.sse", logging.CRITICAL)):
            logger = logging.getLogger(name)
            previous = logger.level
            logger.setLevel(level)
            self.addCleanup(logger.setLevel, previous)

    async def protocol_round_trip(self, server, app):
        from mcp.client.sse import sse_client
        from mcp import ClientSession
        async with asyncio.timeout(10), sse_client(server.url, headers={"Authorization": "Bearer " + TOKEN}, timeout=5, sse_read_timeout=5) as streams:
            async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=5)) as session:
                initialized = await session.initialize()
                self.assertEqual(initialized.serverInfo.name, "EventGuard Application")
                self.assertEqual({tool.name for tool in (await session.list_tools()).tools}, APPLICATION_TOOLS)
                value = ApplicationSDKProtocolTests.value(await session.call_tool("status", {}))
                self.assertEqual(value["instance_id"], app.instance_id)
                self.assertEqual(value["namespace"], app.namespace)
                self.assertEqual(value["model_calls"], 0)

    async def test_two_sequential_servers_in_one_process_each_complete_real_sdk_protocol(self):
        from sse_starlette.sse import AppStatus
        completed = 0
        for identity in ("c" * 32, "d" * 32):
            self.assertIsNone(AppStatus.should_exit_event, "a foreign event must not be reset by the fixture")
            app = FixtureApplication()
            app.instance_id = identity
            server = AppMCPServer(app, TOKEN)
            try:
                self.assertEqual(server.start()["state"], "ready")
                self.assertIsNotNone(server._owned_sse_event)
                self.assertIs(AppStatus.should_exit_event, server._owned_sse_event)
                await self.protocol_round_trip(server, app)
                receipt = server.close()
                self.assertTrue(receipt["thread_exited"], receipt)
                self.assertFalse(server._thread.is_alive())
                self.assertFalse(receipt["forcibly_terminated"])
                self.assertIsNone(AppStatus.should_exit_event)
                completed += 1
            finally:
                self.assertTrue(server.close()["thread_exited"])
        self.assertEqual(completed, 2)
        self.evidence = {"scope": "real SDK SSE, two sequential worker loops in one process, fixture apps only",
                         "initialized_listed_called_closed": completed, "model_calls": 0, "system_queries": 0}

    async def test_concurrent_second_server_is_blocked_without_touching_first_event(self):
        from sse_starlette.sse import AppStatus
        first_app, second_app = FixtureApplication(), FixtureApplication()
        second_app.instance_id = "e" * 32
        first, second = AppMCPServer(first_app, TOKEN), AppMCPServer(second_app, TOKEN)
        try:
            self.assertEqual(first.start()["state"], "ready")
            event = first._owned_sse_event
            denied = second.start()
            self.assertEqual(denied["state"], "blocked")
            self.assertEqual(denied["reason"], "application_mcp_transport_busy")
            self.assertIsNone(second._thread)
            self.assertIs(AppStatus.should_exit_event, event)
            self.assertTrue(second.close()["thread_exited"])
            self.assertIs(AppStatus.should_exit_event, event)
            await self.protocol_round_trip(first, first_app)
        finally:
            self.assertTrue(second.close()["thread_exited"])
            self.assertTrue(first.close()["thread_exited"])

    async def test_same_server_disconnect_reconnect_keeps_ready_and_application_instance(self):
        app = FixtureApplication()
        app.monitor_control("start", operation_id="fixture-reconnect-lifetime")
        server = AppMCPServer(app, TOKEN)
        try:
            self.assertEqual(server.start()["state"], "ready")
            event = server._owned_sse_event
            for _ in range(2):
                await self.protocol_round_trip(server, app)
                # The SDK client's HTTP transport is closed on context exit.
                # Wait for the owned server to observe those closed connections
                # before checking that its fault hook retained readiness.
                deadline = asyncio.get_running_loop().time() + 2
                while server._server.server_state.connections:
                    self.assertLess(asyncio.get_running_loop().time(), deadline,
                                    "the fixture client's connections must close")
                    await asyncio.sleep(.01)
                await asyncio.sleep(.01)
                value = server.status()
                self.assertEqual(value["state"], "ready", value)
                self.assertEqual(value["instance_id"], app.instance_id)
                self.assertEqual(value["namespace"], app.namespace)
                self.assertIs(server._owned_sse_event, event)
                self.assertEqual(app.state, "running")
            receipt = server.close()
            self.assertTrue(receipt["thread_exited"])
            self.assertFalse(receipt["application_closed"])
            self.assertFalse(receipt["forcibly_terminated"])
            self.assertEqual(app.state, "running")
            self.evidence = {"scope": "real SDK, two client sessions on one owned SSE server, fixture app only",
                             "same_instance_after_disconnect": True, "sessions": 2,
                             "model_calls": 0, "system_queries": 0}
        finally:
            self.assertTrue(server.close()["thread_exited"])

    async def test_foreign_event_is_not_adopted_or_cleared_and_failed_start_releases_lease(self):
        from sse_starlette.sse import AppStatus
        # This is an isolated foreign-marker fixture, not another live server's
        # Event. Never replace a non-None Event found on entry.
        self.assertIsNone(AppStatus.should_exit_event)
        marker = object()
        AppStatus.should_exit_event = marker
        server = AppMCPServer(FixtureApplication(), TOKEN)
        try:
            value = server.start()
            self.assertEqual(value["state"], "blocked")
            self.assertEqual(value["reason"], "application_mcp_foreign_transport_event")
            self.assertIsNone(server._owned_sse_event)
            self.assertIs(AppStatus.should_exit_event, marker)
            self.assertNotIn(TOKEN, json.dumps(value))
        finally:
            receipt = server.close()
            self.assertTrue(receipt["thread_exited"])
            if receipt["thread_exited"] and AppStatus.should_exit_event is marker:
                AppStatus.should_exit_event = None  # Remove only our fixture marker.
        probe = AppMCPServer(FixtureApplication(), TOKEN)
        try:
            self.assertEqual(probe.start()["state"], "ready")
        finally:
            self.assertTrue(probe.close()["thread_exited"])


if __name__ == "__main__":
    unittest.main()
