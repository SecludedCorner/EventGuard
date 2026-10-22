"""Synthetic-only local MCP stdio experiment; never listens on a network port."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Annotated, Literal
import uuid


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")


def build_server(data_dir):
    """Use the already-installed SDK. No dependency download or configuration."""
    import anyio
    from mcp.server.fastmcp import FastMCP
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent
    from pydantic import Field
    from eventguard.local_wait import LocalWait

    backend = LocalWait(data_dir)

    class LocalStdioMCP(FastMCP):
        async def call_tool(self, name, arguments):
            # SDK 1.6.0 Pydantic arguments can coerce scalar types and ignore
            # extras. Validate original JSON arguments before SDK conversion.
            allowed = {
                "wait_for_event": {"timeout_seconds"},
                "query_evidence": {"event_id"},
                "ack_event": {"event_id", "query_id", "decision"},
            }
            if name not in allowed:
                raise ValueError("unknown_local_tool")
            if not isinstance(arguments, dict) or set(arguments) - allowed[name]:
                raise ValueError("invalid_local_tool_arguments")
            if name == "wait_for_event":
                timeout = arguments.get("timeout_seconds", 30)
                if type(timeout) is not int or not 1 <= timeout <= 45:
                    raise ValueError("invalid_local_tool_arguments")
            else:
                if set(arguments) != allowed[name]:
                    raise ValueError("invalid_local_tool_arguments")
                for field in ("event_id", "query_id"):
                    if field in arguments and (type(arguments[field]) is not str or not _ID.fullmatch(arguments[field])):
                        raise ValueError("invalid_local_tool_arguments")
                if name == "ack_event" and (type(arguments["decision"]) is not str
                                           or arguments["decision"] not in {"needs_more_evidence", "reviewed_synthetic"}):
                    raise ValueError("invalid_local_tool_arguments")
            if name != "wait_for_event":
                return await super().call_tool(name, arguments)
            request_id = self.get_context().request_id
            with anyio.CancelScope() as scope:
                self._wait_scopes[request_id] = scope
                try:
                    result = await super().call_tool(name, arguments)
                finally:
                    self._wait_scopes.pop(request_id, None)
            if scope.cancel_called:
                return [TextContent(type="text", text=json.dumps({"status": "wait_cancelled", "experiment_only": True,
                                    "real_agent_wake_verified": False}, separators=(",", ":")))]
            return result

        async def run_stdio_async(self):
            # SDK's normal low-level task group waits for active requests at EOF.
            # Forward through an owned scope so EOF cancels async waiting tools,
            # lets their finally blocks persist cancellation, and exits naturally.
            async with stdio_server() as (incoming, outgoing):
                sender, receiver = anyio.create_memory_object_stream(0)
                reply_sender, reply_receiver = anyio.create_memory_object_stream(0)

                async def forward_replies():
                    async with reply_receiver, outgoing:
                        async for reply in reply_receiver:
                            reply_id = getattr(reply.root, "id", None)
                            if type(reply_id) in (int, str) and str(reply_id) in self._cancelled_replies:
                                self._cancelled_replies.discard(str(reply_id))
                                continue  # A cancelled request produces no model-visible result.
                            await outgoing.send(reply)

                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(forward_replies)
                    tasks.start_soon(self._mcp_server.run, receiver, reply_sender,
                                     self._mcp_server.create_initialization_options())
                    try:
                        async with sender:
                            async for message in incoming:
                                # SDK 1.6.0's cancellation path can close its
                                # session after one cancelled request. Own only
                                # our async wait scope instead; unknown/finished
                                # request cancellation is a harmless no-op.
                                if getattr(message.root, "method", None) == "notifications/cancelled":
                                    params = getattr(message.root, "params", None)
                                    request_id = params.get("requestId") if isinstance(params, dict) else None
                                    if type(request_id) in (int, str):
                                        scope = self._wait_scopes.get(str(request_id))
                                        if scope is not None:
                                            self._cancelled_replies.add(str(request_id))
                                            scope.cancel()
                                    continue
                                await sender.send(message)
                    finally:
                        tasks.cancel_scope.cancel()

    server = LocalStdioMCP("EventGuard Local Synthetic Wait")
    server._wait_scopes = {}
    server._cancelled_replies = set()

    async def wait_for_event(timeout_seconds: int = 30) -> dict:
        """Wait locally for a synthetic EventGuard event (1..45s). No model polling or system scan."""
        return await backend.wait_for_event(timeout_seconds=timeout_seconds)

    wait_for_event.__annotations__["timeout_seconds"] = Annotated[int, Field(ge=1, le=45)]
    server.tool()(wait_for_event)

    @server.tool()
    def query_evidence(event_id: str) -> dict:
        """Read a delivered synthetic event snapshot only; never executes native diagnostics."""
        return backend.query_evidence(event_id=event_id)

    @server.tool()
    def ack_event(event_id: str, query_id: str, decision: Literal["needs_more_evidence", "reviewed_synthetic"]) -> dict:
        """Record reviewed_synthetic or needs_more_evidence, linked to a prior snapshot query. No remediation."""
        return backend.ack_event(event_id=event_id, query_id=query_id, decision=decision)

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description="EventGuard synthetic-only local MCP stdio server; no network listener.")
    parser.add_argument("--data-dir", required=True, type=Path,
                        help="Dedicated synthetic experiment directory, initially empty or absent.")
    parser.add_argument("--emit-synthetic", action="store_true",
                        help="Enqueue a public synthetic listener fixture and exit; does not run MCP or a model.")
    args = parser.parse_args(argv)
    if args.emit_synthetic:
        try:
            from eventguard.local_wait import LocalWait
            identity = uuid.uuid4().hex
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            event = {"schema_version": "2.0", "event_id": "evt-local-" + identity,
                     "host_id": "host-synthetic-local", "episode_id": "ep-local-" + identity,
                     "correlation_id": "corr-local-" + identity, "sequence": 1,
                     "event_type": "listener.changed", "transition": "new", "severity": "warning",
                     "synthetic": True, "observed_at": stamp, "persisted_at": stamp,
                     "evidence": {"protocol": "TCP", "port": 45454, "scope": "all_interfaces"},
                     "coverage": {"status": "ok", "gaps": []}}
            LocalWait(args.data_dir).store.enqueue(event)
            print(json.dumps({"event_id": event["event_id"]}, separators=(",", ":")))
            return 0
        except Exception:
            print("EventGuard: synthetic event could not be enqueued. Exit 2.", file=sys.stderr)
            return 2
    try:
        server = build_server(args.data_dir)
    except ImportError:
        print("EventGuard: the required installed MCP Python SDK is unavailable. Nothing was installed. Exit 2.", file=sys.stderr)
        return 2
    except Exception:
        print("EventGuard: local synthetic experiment initialization failed. Exit 2.", file=sys.stderr)
        return 2
    try:
        server.run(transport="stdio")
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("EventGuard: local stdio server stopped with an error.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
