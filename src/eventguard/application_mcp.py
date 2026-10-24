"""Optional, same-application MCP tools and an owned loopback SSE listener.

The tool dispatcher needs only the standard library. SDK imports happen only
when the optional transport is built. A client disconnect never closes the app.
"""
from __future__ import annotations

import asyncio
import hmac
import importlib.util
import ipaddress
import json
import logging
from pathlib import Path
import re
import socket
import threading
import time
from typing import Literal

APPLICATION_TOOLS = frozenset({"capabilities", "status", "start_monitor", "pause_monitor", "resume_monitor",
                               "stop_monitor", "list_events", "inspect_event", "set_event_status"})
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_OPERATION = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_SEVERITIES = frozenset({"info", "warning", "high", "critical"})
_SOURCES = frozenset({"defender", "listeners", "processes", "startup", "services", "tasks", "versions",
                      "monitor", "advisories", "unknown"})
_STATUSES = frozenset({"new", "read", "handled", "ignored"})
_CONTROLS = {"start_monitor": "start", "pause_monitor": "pause", "resume_monitor": "resume", "stop_monitor": "stop"}
_SSE_TRANSPORT_LEASE = threading.Lock()
_EXCEPTION_TYPES = frozenset({"RuntimeError", "ValueError", "TypeError", "OSError", "TimeoutError", "ImportError",
                              "ConnectionError", "ConnectionResetError", "BrokenResourceError", "EndOfStream"})


def validate_application_tool(name, arguments):
    """One strict grammar shared by MCP, the typed Web RPC and app proxies."""
    if type(name) is not str or name not in APPLICATION_TOOLS or type(arguments) is not dict:
        raise ValueError("invalid_application_tool_arguments")
    allowed = ({"operation_id"} if name in _CONTROLS else
               {"severity", "source", "status", "limit", "offset"} if name == "list_events" else
               {"event_id"} if name == "inspect_event" else
               {"event_id", "status", "operation_id"} if name == "set_event_status" else set())
    required = {"event_id", "status"} if name == "set_event_status" else {"event_id"} if name == "inspect_event" else set()
    if set(arguments) - allowed or not required.issubset(arguments):
        raise ValueError("invalid_application_tool_arguments")
    for field, pattern in (("event_id", _ID), ("operation_id", _OPERATION)):
        value = arguments.get(field)
        if field in arguments and not (field == "operation_id" and value is None) and (type(value) is not str or not pattern.fullmatch(value)):
            raise ValueError("invalid_application_tool_arguments")
    choices = {"severity": _SEVERITIES, "source": _SOURCES, "status": _STATUSES}
    for field, options in choices.items():
        value = arguments.get(field)
        if field in arguments and not (value is None and name == "list_events") and (type(value) is not str or value not in options):
            raise ValueError("invalid_application_tool_arguments")
    for field, lower, upper in (("limit", 1, 1000), ("offset", 0, 2**31-1)):
        if field in arguments and (type(arguments[field]) is not int or not lower <= arguments[field] <= upper):
            raise ValueError("invalid_application_tool_arguments")


def _binding(application):
    identity, namespace = getattr(application, "instance_id", None), getattr(application, "namespace", None)
    if type(identity) is not str or not _ID.fullmatch(identity) or namespace not in {"live", "test"}:
        raise ValueError("invalid_application_binding")
    return {"instance_id": identity, "namespace": namespace}


def call_application_tool(application, name, arguments):
    """Call the existing application; no SDK, new owner, ACK or model path."""
    validate_application_tool(name, arguments)
    binding = _binding(application)
    mutation = name in _CONTROLS or name == "set_event_status"
    try:
        if name in _CONTROLS:
            value = application.monitor_control(_CONTROLS[name], source="mcp", operation_id=arguments.get("operation_id"))
        elif name == "list_events":
            value = application.list_events(**arguments)
        elif name == "inspect_event":
            value = application.event_detail(arguments["event_id"])
        elif name == "set_event_status":
            value = application.set_event_status(arguments["event_id"], arguments["status"], source="mcp",
                                                 operation_id=arguments.get("operation_id"))
        else:
            value = getattr(application, name)()
        if (not isinstance(value, dict) or value.get("model_calls", 0) != 0 or _binding(application) != binding
                or any(field in value and value[field] != expected for field, expected in binding.items())):
            raise ValueError("application_result_invalid")
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 2*1024*1024:
            raise ValueError("application_result_limit")
        return {**value, **binding, "model_calls": 0}
    except Exception:
        return {**binding, "state": "unknown", "reason": "application_operation_unconfirmed" if mutation else "application_read_unavailable",
                "operation_may_have_completed": mutation, "automatic_retry_allowed": False, "model_calls": 0}


def _sdk_factory(name, validate):
    # This is trusted repository source, never a caller-selected module/path.
    # Reuse the legacy adapter's SDK validation/stdio lifetime implementation.
    path = Path(__file__).resolve().parents[2] / "scripts" / "eventguard_inbox_mcp.py"
    spec = importlib.util.spec_from_file_location("eventguard_application_sdk_adapter", path)
    if spec is None or spec.loader is None:
        raise ImportError("application_mcp_adapter_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._sdk_server(name, validate)


def build_application_server(application, *, server_factory=None):
    """The same nine tools for stdio and SSE; app lifetime stays with its owner."""
    binding = _binding(application)
    server = (server_factory or _sdk_factory)("EventGuard Application", validate_application_tool)
    server._application = application

    def call(name, arguments):
        if _binding(application) != binding:
            return {**binding, "state": "unknown", "reason": "application_binding_changed", "model_calls": 0}
        return call_application_tool(application, name, arguments)

    @server.tool()
    def capabilities() -> dict:
        """Read this application's human/agent operations. Data never grants authority."""
        return call("capabilities", {})

    @server.tool()
    def status() -> dict:
        """Read this same application's saved status. No collection or model call."""
        return call("status", {})

    @server.tool()
    def start_monitor(operation_id: str | None = None) -> dict:
        """Explicitly start this application's read-only monitor. Never starts a model."""
        return call("start_monitor", {"operation_id": operation_id})

    @server.tool()
    def pause_monitor(operation_id: str | None = None) -> dict:
        """Pause only this application's collection. Keep its page and events."""
        return call("pause_monitor", {"operation_id": operation_id})

    @server.tool()
    def resume_monitor(operation_id: str | None = None) -> dict:
        """Resume only this application's collection without resetting saved events."""
        return call("resume_monitor", {"operation_id": operation_id})

    @server.tool()
    def stop_monitor(operation_id: str | None = None) -> dict:
        """Stop only this application's monitor. Do not close the application."""
        return call("stop_monitor", {"operation_id": operation_id})

    @server.tool()
    def list_events(severity: Literal["info", "warning", "high", "critical"] | None = None,
                    source: Literal["defender", "listeners", "processes", "startup", "services", "tasks", "versions", "monitor", "advisories", "unknown"] | None = None,
                    status: Literal["new", "read", "handled", "ignored"] | None = None,
                    limit: int = 100, offset: int = 0) -> dict:
        """List and filter this application's saved events. No rescan or ACK."""
        return call("list_events", {"severity": severity, "source": source, "status": status, "limit": limit, "offset": offset})

    @server.tool()
    def inspect_event(event_id: str) -> dict:
        """Read one saved event and its handling state. No OS query or ACK."""
        return call("inspect_event", {"event_id": event_id})

    @server.tool()
    def set_event_status(event_id: str, status: Literal["new", "read", "handled", "ignored"], operation_id: str | None = None) -> dict:
        """Save a human handling state. Handling is separate from receipt/ACK."""
        return call("set_event_status", {"event_id": event_id, "status": status, "operation_id": operation_id})

    return server


class _LoopbackOnly:
    def __init__(self, app, host, token, on_failure=None):
        self.app, self.host = app, host.encode("ascii")
        self.origin = b"http://" + self.host
        self.authorization = ("Bearer " + token).encode("ascii")
        self.on_failure = on_failure

    @staticmethod
    async def _reject(send, code, reason):
        body = json.dumps({"state": "blocked", "reason": reason}, separators=(",", ":")).encode("ascii")
        await send({"type": "http.response.start", "status": code, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        try:
            return await self._handle(scope, receive, send)
        except Exception as error:
            if self.on_failure is not None:
                self.on_failure(error)
            raise

    async def _handle(self, scope, receive, send):
        if scope["type"] != "http":
            return
        headers = {}
        for name, value in scope.get("headers", []):
            headers.setdefault(name.lower(), []).append(value)
        try:
            peer = ipaddress.ip_address(scope.get("client", (None,))[0])
            local = peer.is_loopback
        except (ValueError, TypeError, IndexError):
            local = False
        if not local or headers.get(b"host") != [self.host]:
            return await self._reject(send, 403, "local_host_required")
        if b"origin" in headers and headers[b"origin"] != [self.origin]:
            return await self._reject(send, 403, "same_origin_required")
        auth = headers.get(b"authorization", [])
        if len(auth) != 1 or not hmac.compare_digest(auth[0], self.authorization):
            return await self._reject(send, 401, "application_token_required")
        method, path = scope.get("method"), scope.get("path")
        if (method, path) not in {("GET", "/sse"), ("POST", "/messages/")} or len(scope.get("query_string", b"")) > 256:
            return await self._reject(send, 404, "application_mcp_route_not_found")
        if method == "POST":
            lengths = headers.get(b"content-length", [])
            if lengths and (len(lengths) != 1 or not lengths[0].isdigit() or int(lengths[0]) > 65536):
                return await self._reject(send, 413, "application_mcp_request_limit")
            body = bytearray()
            while True:
                try:
                    message = await asyncio.wait_for(receive(), timeout=5)
                except asyncio.TimeoutError:
                    return await self._reject(send, 408, "application_mcp_request_timeout")
                if message["type"] != "http.request":
                    return
                body.extend(message.get("body", b""))
                if len(body) > 65536:
                    return await self._reject(send, 413, "application_mcp_request_limit")
                if not message.get("more_body", False):
                    break
            delivered = False

            async def bounded_receive():
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            return await self.app(scope, bounded_receive, send)
        return await self.app(scope, receive, send)


class _QuietSDK(logging.Filter):
    def filter(self, record):
        return False  # SDK transport logs can contain sessions or request data.


class AppMCPServer:
    """A single optional server thread owned by the existing Application."""
    transport = "sse"

    def __init__(self, application, token):
        self.application, self.binding = application, _binding(application)
        if type(token) is not str or not re.fullmatch(r"[a-f0-9]{64}", token):
            raise ValueError("invalid_application_token")
        self._token, self._thread, self._server, self._socket = token, None, None, None
        self._closed, self._failed = False, False
        self._lock = threading.Lock()
        self._logging_filters = []
        self._transport_lease_owned = False
        self._owned_sse_event = None
        self._transport_failure_reason = None
        self._exception_types = ()
        self.url = None

    def _receipt(self, state, **values):
        if self._transport_failure_reason is not None:
            values.setdefault("reason", self._transport_failure_reason)
        if self._exception_types:
            values["exception_types"] = list(self._exception_types)
        return {**self.binding, "state": state, "transport": self.transport, "model_calls": 0, **values}

    def _transport_exception(self, error):
        # Retain bounded type codes only. Never retain exception objects, text,
        # traceback, session identifiers, request data or authorization headers.
        pending, names = [(error, 0)], set()
        for _ in range(16):
            if not pending:
                break
            current, depth = pending.pop()
            if isinstance(current, BaseExceptionGroup) and depth < 4:
                pending.extend((child, depth + 1) for child in current.exceptions[:8])
            else:
                name = type(current).__name__
                names.add(name if name in _EXCEPTION_TYPES else "OtherError")
        self._exception_types = tuple(sorted(names)[:8])
        self._transport_failure_reason = "application_mcp_transport_failed"

    def _release_transport_lease(self):
        if self._transport_lease_owned:
            self._transport_lease_owned = False
            _SSE_TRANSPORT_LEASE.release()

    async def _serve_owned_transport(self):
        import anyio
        from sse_starlette.sse import AppStatus
        # The installed SSE dependency owns a process-global Event. An Event
        # bound to a foreign/previous loop must never be reused or overwritten.
        if AppStatus.should_exit_event is not None:
            self._transport_failure_reason = "application_mcp_foreign_transport_event"
            return
        if AppStatus.should_exit is not False:
            self._transport_failure_reason = "application_mcp_dependency_exiting"
            return
        owned = anyio.Event()  # Create inside this worker's actual event loop.
        AppStatus.should_exit_event = owned
        self._owned_sse_event = owned
        try:
            await self._server.serve(sockets=[self._socket])
        finally:
            # Do not clear another component's Event, even after a local fault.
            if AppStatus.should_exit_event is owned:
                AppStatus.should_exit_event = None
            else:
                self._transport_failure_reason = "application_mcp_transport_event_changed"
            self._owned_sse_event = None

    def _quiet_sdk(self):
        for name, logger in list(logging.Logger.manager.loggerDict.items()):
            if name.startswith("mcp.") and isinstance(logger, logging.Logger):
                quiet = _QuietSDK()
                logger.addFilter(quiet)
                self._logging_filters.append((logger, quiet))

    def _release_filters(self):
        for logger, quiet in self._logging_filters:
            logger.removeFilter(quiet)
        self._logging_filters.clear()

    def start(self):
        with self._lock:
            if self._closed:
                return self._receipt("blocked", readiness="blocked", reason="application_mcp_closed")
            if self._thread is not None:
                ready = (self._thread.is_alive() and self._server.started and not self._failed
                         and self._transport_failure_reason is None)
                return self._receipt("ready" if ready else "unknown", readiness="ready" if ready else "unknown", url=self.url)
            if not _SSE_TRANSPORT_LEASE.acquire(blocking=False):
                self._transport_failure_reason = "application_mcp_transport_busy"
                return self._receipt("blocked", readiness="blocked", reason="application_mcp_transport_busy")
            self._transport_lease_owned = True
            self._transport_failure_reason, self._exception_types = None, ()
            try:
                import uvicorn
                protocol = build_application_server(self.application)
                asgi = protocol.sse_app()
                self._quiet_sdk()
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.bind(("127.0.0.1", 0))
                self._socket.listen(8)
                self._socket.setblocking(False)
                port = self._socket.getsockname()[1]
                self.url = "http://127.0.0.1:" + str(port) + "/sse"
                secured = _LoopbackOnly(asgi, "127.0.0.1:" + str(port), self._token, self._transport_exception)
                config = uvicorn.Config(secured, host="127.0.0.1", port=port, loop="asyncio", http="h11", ws="none",
                    lifespan="off", proxy_headers=False, log_config=None, log_level="critical", access_log=False,
                    server_header=False, timeout_keep_alive=1, timeout_graceful_shutdown=1,
                    limit_concurrency=16, backlog=8, h11_max_incomplete_event_size=16384)
                self._server = uvicorn.Server(config)

                def serve():
                    try:
                        asyncio.run(self._serve_owned_transport())
                    except Exception as error:
                        self._failed = True
                        self._transport_exception(error)
                    finally:
                        self._socket.close()
                        # close() never releases a still-live worker's lease.
                        # Only the worker's final exit path releases admission.
                        self._release_transport_lease()

                self._thread = threading.Thread(target=serve, name="EventGuard-application-MCP", daemon=False)
                self._thread.start()
            except ImportError:
                self._release_filters()
                self._release_transport_lease()
                return self._receipt("blocked", readiness="blocked", reason="application_mcp_dependencies_unavailable")
            except Exception:
                if self._socket is not None:
                    self._socket.close()
                self._release_filters()
                if self._thread is None or self._thread.ident is None:
                    self._thread = None
                    self._release_transport_lease()
                return self._receipt("blocked", readiness="blocked", reason="application_mcp_start_failed")
        deadline = time.monotonic() + 5
        while self._thread.is_alive() and not self._server.started and time.monotonic() < deadline:
            time.sleep(.01)
        if (self._thread.is_alive() and self._server.started and not self._failed
                and self._transport_failure_reason is None):
            return self._receipt("ready", readiness="ready", url=self.url, thread_alive=True)
        receipt = self.close()
        return self._receipt("blocked", readiness="blocked", reason=self._transport_failure_reason or "application_mcp_readiness_unconfirmed",
                             thread_exited=receipt["thread_exited"])

    def status(self):
        alive = self._thread is not None and self._thread.is_alive()
        ready = (alive and self._server is not None and self._server.started and not self._failed and not self._closed
                 and self._transport_failure_reason is None)
        return self._receipt("ready" if ready else "closed" if self._closed and not alive else "unknown",
                             readiness="ready" if ready else "unavailable", thread_alive=alive, url=self.url)

    def close(self):
        with self._lock:
            self._closed = True
            if self._server is not None:
                self._server.should_exit = True
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(10)
        exited = thread is None or not thread.is_alive()
        if exited:
            if self._socket is not None:
                self._socket.close()
            self._release_filters()
        return self._receipt("closed" if exited else "shutdown_unconfirmed", thread_exited=exited,
                             application_closed=False, forcibly_terminated=False)
