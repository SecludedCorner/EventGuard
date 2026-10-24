"""Local application rendezvous and stdio compatibility. No model or new owner.

The optional SDK lives in application_mcp. The core rendezvous uses only the
standard library and the existing FileLease. Tokens are installation-local,
ephemeral capabilities, never printed or included in public status.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from .acceptance_control import FileLease
from .runtime import Runtime, atomic_json, read_json, utc_now

TOKEN = re.compile(r"[a-f0-9]{64}\Z")
INSTANCE = re.compile(r"[a-f0-9]{32}\Z")
LOCAL_URL = re.compile(r"http://127\.0\.0\.1:([0-9]{1,5})\Z")
DESCRIPTOR = "data/application/connection.json"


class ApplicationHostError(RuntimeError):
    pass


def _scope(runtime):
    return hashlib.sha256(str(runtime.root).casefold().encode("utf-8")).hexdigest()


class ApplicationControlServices:
    """One root lease and optional SDK listener owned by the GUI application."""

    def __init__(self, application):
        self.application = application
        self.runtime = application.runtime
        lock = self.runtime.path("data/application/instance.lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        self.lease = FileLease(lock)
        self.manager = None
        self.record = None
        self.view = {"state": "not_started", "transport": None, "model_calls": 0}
        if not self.lease.acquire():
            raise ApplicationHostError("application_instance_already_running")

    def start(self):
        from .processes import identity
        app = self.application
        owner = identity()
        if owner.get("state") != "alive" or not isinstance(owner.get("created_at"), str):
            raise ApplicationHostError("application_identity_unconfirmed")
        self.view = {"state": "disabled", "transport": None, "model_calls": 0}
        if app.mcp_enabled:
            from .application_mcp import AppMCPServer
            self.manager = AppMCPServer(app, app.web.token)
            self.view = self.manager.start()
        self.record = {"kind": "eventguard-application-connection-v1", "state": "ready",
            "instance_id": app.instance_id, "namespace": app.namespace, "root_scope": _scope(self.runtime),
            "pid": owner["pid"], "created_at": owner["created_at"], "url": app.web.url,
            "control_token": app.web.token, "mcp": dict(self.view), "updated_at": utc_now(),
            "model_calls": 0}
        atomic_json(self.runtime.path(DESCRIPTOR), self.record)
        return dict(self.view)

    def close(self):
        receipt = ({"thread_exited": True, "state": "disabled", "forcibly_terminated": False}
                   if self.manager is None else self.manager.close())
        saved = True
        try:
            current = read_json(self.runtime.path(DESCRIPTOR), 16384) if self.runtime.path(DESCRIPTOR).is_file() else None
            if current is not None and not isinstance(current, dict):
                raise ValueError("application_descriptor_invalid")
            if current is not None and current.get("instance_id") == self.application.instance_id:
                # A stopped collector retains the active connection descriptor.
                # Only actual application shutdown revokes this capability.
                current.update(state="closed" if receipt.get("thread_exited") else "shutdown_unconfirmed",
                               updated_at=utc_now(), mcp=receipt)
                current.pop("control_token", None)
                atomic_json(self.runtime.path(DESCRIPTOR), current)
        except (OSError, ValueError, TypeError, RuntimeError):
            saved = False
        self.view = {"state": "closed" if receipt.get("thread_exited") else "shutdown_unconfirmed",
                     "model_calls": 0}
        return {"mcp": receipt, "thread_exited": receipt.get("thread_exited"),
                "descriptor_saved": saved, "model_calls": 0}

    def release(self, *, clean):
        # Keep the root exclusive until Web and owned collectors also exit.
        if clean:
            self.lease.release()


def connection(runtime, namespace):
    """Read only this root's recorded application identity and capability."""
    from .processes import identity
    path = runtime.path(DESCRIPTOR)
    if not path.exists():
        return None
    try:
        record = read_json(path, 16384)
        if (not isinstance(record, dict) or record.get("kind") != "eventguard-application-connection-v1"
                or record.get("root_scope") != _scope(runtime)
                or record.get("namespace") != namespace or not INSTANCE.fullmatch(record.get("instance_id", ""))
                or type(record.get("pid")) is not int or not isinstance(record.get("created_at"), str)):
            raise ApplicationHostError("application_connection_scope_invalid")
        observed = identity(record["pid"])
        if observed.get("state") in {"missing", "exited"} or (
                observed.get("created_at") is not None and observed["created_at"] != record["created_at"]):
            return None
        if observed.get("state") != "alive" or observed.get("created_at") != record["created_at"]:
            raise ApplicationHostError("application_connection_identity_unconfirmed")
        if record.get("state") != "ready":
            raise ApplicationHostError("application_connection_not_ready")
        url = record.get("url")
        match = LOCAL_URL.fullmatch(url) if isinstance(url, str) else None
        if (not match or not 1 <= int(match.group(1)) <= 65535
                or not TOKEN.fullmatch(record.get("control_token", ""))):
            raise ApplicationHostError("application_connection_invalid")
        return record
    except (OSError, ValueError, TypeError) as error:
        raise ApplicationHostError("application_connection_unreadable") from None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "application_redirect_rejected", headers, fp)


class RemoteApplication:
    """Observer of one root/namespace; it never creates or owns an app.

    An absent application uses the explicit ``unbound`` marker. Tool discovery
    remains available. Only a metadata read may bind to a later application.
    """

    def __init__(self, root, namespace, *, expected_instance_id=None):
        self.runtime = Runtime(root)
        if namespace not in {"live", "test"}:
            raise ValueError("invalid_application_namespace")
        self.namespace = namespace
        self._instance_id = "unbound"
        self._binding_lock = threading.Lock()
        self._operation_instances = OrderedDict()
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())
        try:
            record = connection(self.runtime, self.namespace)
        except ApplicationHostError:
            if expected_instance_id is not None:
                raise
            # A missing, stale or invalid descriptor must not prevent MCP tool
            # discovery. Reads report its fixed reason without writing runtime.
            record = None
        if expected_instance_id is not None and (record is None or expected_instance_id != record["instance_id"]):
            raise ApplicationHostError("application_connection_changed")
        if record is not None:
            self._instance_id = record["instance_id"]

    def refresh_binding(self):
        """Explicit metadata read may observe a replacement in this same root.

        Mutation never refreshes. It still checks this exact identity before
        issuing HTTP and never retries an uncertain result on a new instance.
        """
        record = connection(self.runtime, self.namespace)
        if record is None:
            return False  # _call reports blocked; never create a new owner.
        with self._binding_lock:
            self._instance_id = record["instance_id"]
        return True

    def _call(self, name, arguments, source="mcp"):
        from .application_mcp import validate_application_tool
        if type(source) is not str or source not in {"mcp", "cli"}:
            raise ValueError("invalid_application_proxy_source")
        validate_application_tool(name, arguments)
        try:
            record = connection(self.runtime, self.namespace)
        except ApplicationHostError as error:
            return {"state": "blocked", "reason": str(error), "namespace": self.namespace,
                    "instance_id": self.instance_id, "automatic_retry_allowed": False, "model_calls": 0}
        if record is None or record["instance_id"] != self.instance_id:
            return {"state": "blocked", "reason": "application_not_running" if record is None else "application_instance_changed", "namespace": self.namespace,
                    "instance_id": self.instance_id,
                    "automatic_retry_allowed": False, "model_calls": 0}
        operation = arguments.get("operation_id")
        if name in {"start_monitor", "pause_monitor", "resume_monitor", "stop_monitor", "shutdown_application", "set_event_status"} and operation is not None:
            with self._binding_lock:
                old = self._operation_instances.get(operation)
                if old is not None and old != record["instance_id"]:
                    return {"state": "conflict", "reason": "operation_instance_conflict", "namespace": self.namespace,
                            "instance_id": record["instance_id"], "automatic_retry_allowed": False, "model_calls": 0}
                self._operation_instances[operation] = record["instance_id"]
                while len(self._operation_instances) > 128:
                    self._operation_instances.popitem(last=False)
        body = json.dumps({"instance_id": record["instance_id"], "name": name, "source": source,
                           "arguments": arguments}, allow_nan=False).encode("utf-8")
        request = Request(record["url"] + "/api/operator", data=body, method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + record["control_token"]})
        try:
            with self.opener.open(request, timeout=35) as response:
                if response.status != 200 or response.geturl() != request.full_url:
                    raise ValueError("application_response_invalid")
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("application_response_too_large")
            value = json.loads(raw)
            if not isinstance(value, dict) or value.get("instance_id") != record["instance_id"] or value.get("namespace") != self.namespace:
                raise ValueError("application_response_scope_mismatch")
            return value
        except (OSError, ValueError, TypeError, HTTPError, URLError):
            # Do not replay a mutation after an uncertain response or attach a
            # replacement instance behind the caller's back.
            return {"state": "unknown", "reason": "application_response_unconfirmed",
                    "instance_id": record["instance_id"], "namespace": self.namespace,
                    "operation_id": operation,
                    "operation_may_have_completed": name not in {"capabilities", "status", "list_events", "inspect_event"},
                    "automatic_retry_allowed": False, "model_calls": 0}

    @property
    def instance_id(self):
        with self._binding_lock:
            return self._instance_id

    def capabilities(self):
        return self._call("capabilities", {})

    def status(self):
        return self._call("status", {})

    def monitor_control(self, action, source="mcp", operation_id=None):
        mapping = {"start": "start_monitor", "pause": "pause_monitor", "resume": "resume_monitor", "stop": "stop_monitor",
                   "shutdown": "shutdown_application"}
        if action not in mapping or source not in {"mcp", "cli"}:
            raise ValueError("invalid_application_proxy_action")
        return self._call(mapping[action], {} if operation_id is None else {"operation_id": operation_id}, source=source)

    def list_events(self, **filters):
        return self._call("list_events", filters)

    def event_detail(self, event_id):
        return self._call("inspect_event", {"event_id": event_id})

    def set_event_status(self, event_id, status, source="mcp", operation_id=None):
        if source not in {"mcp", "cli"}:
            raise ValueError("invalid_application_proxy_source")
        arguments = {"event_id": event_id, "status": status}
        if operation_id is not None:
            arguments["operation_id"] = operation_id
        return self._call("set_event_status", arguments, source=source)


def serve_stdio(root, *, allow_live=False, fixture=None, max_cycles=None, port=0, max_seconds=None):
    """Serve fixed observer tools. EOF ends only this stdio adapter.

    Start the independent foreground app with ``eventguard run``. A cold MCP
    adapter still lists its tools and reports blocked until metadata can bind.
    Legacy startup options remain accepted but never create an application.
    """
    from .application_mcp import build_application_server
    namespace = "test" if fixture else "live"
    if namespace == "live" and allow_live is not True:
        raise ApplicationHostError("application_live_scope_not_authorized")
    target = RemoteApplication(root, namespace)
    server = build_application_server(target)
    from .application_stdio import application_stdio_server
    server.stdio_streams_factory = application_stdio_server
    server.run(transport="stdio")
    return 0
