"""One foreground application: existing owned supervisor + local product UI."""
from __future__ import annotations

import math
import re
import copy
from collections import OrderedDict
from datetime import datetime, timezone
import sys
import threading
import time
import uuid

_SOURCES = frozenset({"gui", "mcp", "cli", "startup", "system"})
_ACTIONS = frozenset({"start", "pause", "resume", "stop", "shutdown"})
_OPERATION = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


class Application:
    def __init__(self, root, *, port=8765, fixture=None, max_cycles=None, notifications=True,
                 notification_sink=None, auto_start=True, mcp_enabled=False):
        from .runtime import Runtime
        from .operations import OperatorAPI
        from .web import LocalWeb
        from .notifications import NotificationService
        if type(auto_start) is not bool or type(mcp_enabled) is not bool:
            raise ValueError("invalid_application_options")
        self.runtime = Runtime(root)
        self.auto_start, self.mcp_enabled = auto_start, mcp_enabled
        self.instance_id = uuid.uuid4().hex
        self.namespace = "test" if fixture else "live"
        self.fixture, self.max_cycles = fixture, max_cycles
        self.owner = OperatorAPI(root, background_lifetime_owner="application")
        self.cancel = threading.Event()
        self.notification_service = NotificationService(root, self.namespace, sink=notification_sink) if notifications else None
        self.notification_state = {"status": "waiting" if notifications else "disabled", "model_calls": 0}
        self.launch = {"state": "not_started"}
        self._control_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._state_revision = 0
        self._last_action = None
        self._operations = OrderedDict()
        self._transition = None
        self._closing = False
        self._started = False
        self._paused = False
        self._stopped = True
        self._shutdown_unconfirmed = False
        self._owned_scope = None
        self._pause_generation = None
        self._last_control = None
        self._pause_receipt = None
        self._pause_count = self._resume_count = 0
        self._stop_count = self._start_count = 0
        self.control_services = None
        self.mcp_state = {"state": "not_started", "transport": None, "model_calls": 0}
        # Bind the port before starting a collector. A port conflict starts no monitor.
        self.web = LocalWeb(root, self.namespace, port=port, status_provider=self.status,
                            monitor_control=self.monitor_control, operator_call=self._operator_call,
                            event_status_control=lambda event_id, status, **kw: self.set_event_status(event_id, status, source="gui", **kw))

    def _operator_call(self, name, arguments, source="mcp"):
        from .application_mcp import call_application_tool
        return call_application_tool(self, name, arguments, source=source)

    def _own_monitor_child(self, child):
        self.owner._own_monitor_child(child)
        scope = getattr(child, "_eventguard_background_scope", None)
        if isinstance(scope, dict) and scope.get("namespace") == self.namespace:
            with self._state_lock:
                self._owned_scope = dict(scope)

    def _same_monitor(self, saved):
        return (isinstance(self._owned_scope, dict) and saved.get("namespace") == self.namespace
                and saved.get("run_id") == self._owned_scope.get("run_id"))

    def _disabled_scope(self, saved):
        return (self._same_monitor(saved) and saved.get("control_generation") == self._pause_generation
                and saved.get("desired_enabled") is False and saved.get("host_liveness") == "exited_verified")

    @staticmethod
    def _request(source, operation_id):
        if type(source) is not str or source not in _SOURCES:
            raise ValueError("invalid_operation_source")
        if operation_id is None:
            operation_id = uuid.uuid4().hex
        if type(operation_id) is not str or not _OPERATION.fullmatch(operation_id):
            raise ValueError("invalid_operation_id")
        return operation_id

    def _record_action(self, action, source, operation_id, state, result_code):
        with self._state_lock:
            self._state_revision += 1
            self._last_action = {"action": action, "source": source, "state": state,
                "result_code": result_code, "operation_id": operation_id,
                "at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "revision": self._state_revision}

    def _reply(self, result, operation_id=None, *, replayed=False, original_revision=None):
        view = self.status()
        return {**result, "operation_id": operation_id, "instance_id": self.instance_id,
                "result_code": result.get("reason", result.get("state")),
                "state_revision": view["state_revision"], "last_action": view["last_action"],
                "monitor_state": view["monitor_state"], "monitor_controls": view["monitor_controls"],
                "replayed": replayed, "original_revision": original_revision, "model_calls": 0}

    def _operate(self, action, source, operation_id, fingerprint, execute):
        operation_id = self._request(source, operation_id)
        with self._state_lock:
            previous = self._operations.get(operation_id)
            if previous is not None:
                if previous["fingerprint"] != fingerprint:
                    return self._reply({"state": "conflict", "reason": "operation_id_conflict"}, operation_id)
                if previous["result"] is not None:
                    return self._reply(copy.deepcopy(previous["result"]), operation_id,
                        replayed=True, original_revision=previous["revision"])
                return self._reply({"state": "busy", "reason": "operation_in_progress"}, operation_id)
        if not self._control_lock.acquire(blocking=False):
            return self._reply({"state": "busy", "reason": "monitor_control_busy"}, operation_id)
        # Another caller can finish between the first cache read and this
        # nonblocking acquisition. Recheck under ownership before admitting.
        with self._state_lock:
            previous = self._operations.get(operation_id)
            if previous is not None:
                self._control_lock.release()
                if previous["fingerprint"] != fingerprint:
                    return self._reply({"state": "conflict", "reason": "operation_id_conflict"}, operation_id)
                if previous["result"] is not None:
                    return self._reply(copy.deepcopy(previous["result"]), operation_id,
                        replayed=True, original_revision=previous["revision"])
                return self._reply({"state": "busy", "reason": "operation_in_progress"}, operation_id)
        result = {"state": "blocked", "reason": "operation_interrupted"}
        try:
            with self._state_lock:
                while len(self._operations) >= 128:
                    self._operations.popitem(last=False)
                self._operations[operation_id] = {"fingerprint": fingerprint, "result": None, "revision": None}
                self._transition = action
                self._record_action(action, source, operation_id, "processing", "operation_in_progress")
            try:
                result = execute()
            except (OSError, ValueError, TypeError, RuntimeError):
                result = {"state": "blocked", "reason": "application_operation_failed", "raw_error_omitted": True}
        finally:
            with self._state_lock:
                self._last_control = {**result, "model_calls": 0}
                self._record_action(action, source, operation_id, result["state"], result.get("reason", result["state"]))
                self._operations[operation_id].update(result=copy.deepcopy(result), revision=self._state_revision)
                self._transition = None
            self._control_lock.release()
        return self._reply(result, operation_id)

    def _start_monitor(self, *, expected_generation=None):
        from .background import start
        options = {} if expected_generation is None else {"expected_control_generation": expected_generation}
        self.launch = start(self.runtime.root, fixture=self.fixture, max_cycles=self.max_cycles,
                            lifetime_owner="application", child_owner=self._own_monitor_child, **options)
        return self.launch

    def monitor_control(self, action, source="gui", operation_id=None):
        """One typed control surface for GUI and MCP; no model or external owner."""
        if type(action) is not str or action not in _ACTIONS:
            raise ValueError("invalid_monitor_action")
        return self._operate(action, source, operation_id, ("monitor", action), lambda: self._monitor_action(action))

    def _monitor_action(self, action):
        if self._closing or self.cancel.is_set():
            return {"state": "blocked", "reason": "monitor_application_closing"}
        if action == "shutdown":
            # The caller receives its result before run() closes Web or MCP.
            self._closing = True
            self.cancel.set()
            return {"state": "shutdown_requested", "reason": "monitor_application_shutdown_requested"}
        if not self._started:
            return {"state": "blocked", "reason": "monitor_application_not_running"}
        from .background import status
        saved = status(self.runtime.root)
        if action in {"start", "resume"}:
            if self._shutdown_unconfirmed:
                return {"state": "blocked", "reason": "monitor_previous_shutdown_unconfirmed"}
            if self._owned_scope is None:
                if action == "resume":
                    return {"state": "blocked", "reason": "monitor_not_owned"}
                if saved.get("host_liveness") not in {"not_recorded", "exited_verified"}:
                    return {"state": "blocked", "reason": "monitor_not_owned"}
                expected = None
            else:
                if not self._same_monitor(saved):
                    return {"state": "blocked", "reason": "monitor_ownership_changed"}
                if not self._paused and not self._stopped:
                    return ({"state": "running", "reason": "monitor_already_running"}
                            if saved.get("state") == "running" and saved.get("desired_enabled") is True
                            and saved.get("host_liveness") == "alive_verified"
                            else {"state": "blocked", "reason": "monitor_restart_required"})
                if action == "start" and self._paused:
                    return {"state": "blocked", "reason": "monitor_resume_required"}
                if action == "resume" and self._stopped:
                    return {"state": "blocked", "reason": "monitor_start_required"}
                if not self._disabled_scope(saved):
                    return {"state": "blocked", "reason": "monitor_resume_scope_changed"}
                expected = self._pause_generation
            from .rules.configured import load_rules
            load_rules(self.runtime.root)
            if self._owned_scope is not None:
                from .operations import OperatorAPI
                self.owner = OperatorAPI(self.runtime.root, background_lifetime_owner="application")
            launch = self._start_monitor(expected_generation=expected)
            if launch.get("state") == "started" and self._owned_scope is not None:
                with self._state_lock:
                    self._paused = self._stopped = False
                    self._pause_generation = None
                    if action == "resume":
                        self._resume_count += 1
                    else:
                        self._start_count += 1
                return {"state": "running", "reason": "monitor_started_events_preserved" if action == "start"
                        else "monitor_resumed_events_preserved"}
            return {"state": "blocked", "reason": "monitor_start_failed", "launch_state": launch.get("state")}
        if self._owned_scope is None:
            if action == "stop" and saved.get("host_liveness") in {"not_recorded", "exited_verified"}:
                return {"state": "stopped", "reason": "monitor_already_stopped"}
            return {"state": "blocked", "reason": "monitor_not_owned"}
        if not self._same_monitor(saved):
            return {"state": "blocked", "reason": "monitor_ownership_changed"}
        if action == "pause" and self._paused or action == "stop" and self._stopped:
            return ({"state": "paused" if action == "pause" else "stopped", "reason": "monitor_already_paused" if action == "pause" else "monitor_already_stopped"}
                    if self._disabled_scope(saved) else {"state": "blocked", "reason": "monitor_pause_scope_unconfirmed"})
        if action == "pause" and self._stopped:
            return {"state": "blocked", "reason": "monitor_start_required"}
        receipt = self.owner.close_owned_monitor(grace_seconds=10)
        self._pause_receipt = receipt
        saved = status(self.runtime.root)
        reason = None
        if receipt.get("child_exited") is not True:
            reason = "monitor_pause_exit_unconfirmed"
        elif receipt.get("evidence_write_failed") is True:
            reason = "monitor_pause_receipt_save_failed"
        elif (not self._same_monitor(saved) or saved.get("desired_enabled") is not False
              or saved.get("host_liveness") != "exited_verified"):
            reason = "monitor_pause_scope_unconfirmed"
        elif (type(saved.get("control_generation")) is not str
              or re.fullmatch(r"[a-f0-9]{32}", saved["control_generation"]) is None):
            reason = "monitor_pause_generation_unconfirmed"
        if reason:
            self._shutdown_unconfirmed = True
            return {"state": "shutdown_unconfirmed" if receipt.get("child_exited") is not True else "blocked", "reason": reason}
        with self._state_lock:
            self._shutdown_unconfirmed = False
            self._pause_generation = saved["control_generation"]
            self._paused, self._stopped = action == "pause", action == "stop"
            if action == "pause":
                self._pause_count += 1
            else:
                self._stop_count += 1
        return {"state": "paused" if action == "pause" else "stopped", "reason": "monitor_" + action + "_events_preserved",
                "child_exited": True, "forcibly_terminated": receipt.get("forcibly_terminated", False)}

    def capabilities(self):
        from .events.catalog import SEVERITIES, SOURCE_FILTERS, STATUSES
        return {"instance_id": self.instance_id, "namespace": self.namespace,
                "monitor_actions": sorted(_ACTIONS), "operation_sources": sorted(_SOURCES),
                "event_statuses": sorted(STATUSES), "event_filters": {"severity": sorted(SEVERITIES),
                    "source": sorted(SOURCE_FILTERS), "status": sorted(STATUSES), "limit": [1, 1000]},
                "event_operations": ["list_events", "event_detail", "set_event_status"],
                "operation_cache_limit": 128, "ack_available": False, "model_calls": 0}

    def list_events(self, **filters):
        from .events.catalog import EventCatalog
        if set(filters) - {"severity", "source", "status", "limit", "offset"}:
            raise ValueError("invalid_event_filters")
        return EventCatalog(self.runtime.root, self.namespace).list(**filters)

    def event_detail(self, event_id):
        from .events.catalog import EventCatalog
        return EventCatalog(self.runtime.root, self.namespace).detail(event_id)

    def set_event_status(self, event_id, status, source="mcp", operation_id=None):
        from .events.catalog import EventCatalog, STATUSES, _identifier
        _identifier(event_id)
        if type(status) is not str or status not in STATUSES:
            raise ValueError("invalid_event_status")
        def update():
            if self._closing or self.cancel.is_set():
                return {"state": "blocked", "reason": "monitor_application_closing"}
            return {**EventCatalog(self.runtime.root, self.namespace).set_status(event_id, status),
                    "state": "event_status_updated", "reason": "event_status_saved"}
        return self._operate("set_event_status", source, operation_id, ("event_status", event_id, status), update)

    def status(self):
        from .background import status
        saved = status(self.runtime.root)
        if self.control_services is not None and self.control_services.manager is not None:
            self.mcp_state = self.control_services.manager.status()
        try:
            health = self.runtime.health()
            error = health.get("last_error") if health.get("namespace") == self.namespace else None
            if type(error) is not str or re.fullmatch(r"rules_[a-z0-9_]{1,80}", error) is None:
                error = None
        except (OSError, ValueError, TypeError):
            error = "saved_health_unavailable"
        from .intelligence.views import public_advisories
        advisories = public_advisories(self.runtime.root, self.namespace, limit=5)
        from .agent_service import status as agent_service_status
        try:
            agent = agent_service_status(self.runtime.root)
            if agent.get("namespace") not in (None, self.namespace):
                agent = {"state": "not_applicable", "reason": "agent_service_outside_application_namespace", "model_calls": 0}
        except (OSError, ValueError, RuntimeError, TypeError):
            agent = {"state": "unknown", "reason": "agent_service_status_unavailable", "model_calls": 0}
        with self._state_lock:
            available = self._started and not self._closing and not self.cancel.is_set()
            closed = self._closing and not self._started
            paused = self._paused and self._disabled_scope(saved) and not self._shutdown_unconfirmed
            safe_empty = saved.get("host_liveness") in {"not_recorded", "exited_verified"}
            stopped = (closed and not self._shutdown_unconfirmed) or (self._stopped and safe_empty
                       and (self._owned_scope is None or self._disabled_scope(saved)))
            running = (not closed and self._same_monitor(saved) and saved.get("state") == "running"
                       and saved.get("desired_enabled") is True and saved.get("host_liveness") == "alive_verified"
                       and not self._shutdown_unconfirmed)
            state = "paused" if paused else "stopped" if stopped else "running" if running else (
                "unknown" if saved.get("state") == "unknown" or saved.get("host_liveness") in {"unknown", "alive_unverified"}
                else "blocked")
            transition = self._transition or ("shutdown" if self._closing and self._started else None)
            idle = available and transition is None
            can_start = idle and stopped and not self._shutdown_unconfirmed
            controls = {"available": available, "paused": bool(paused), "stopped": bool(stopped),
                        "transition": transition, "can_start": bool(can_start),
                        "can_pause": bool(idle and running), "can_resume": bool(idle and paused),
                        "can_stop": bool(idle and (running or paused)), "can_shutdown": bool(idle)}
            return {"namespace": self.namespace, "monitor_state": state,
                    "reason": saved.get("reason"), "config_error": error,
                    "instance_id": self.instance_id, "state_revision": self._state_revision,
                    "last_action": copy.deepcopy(self._last_action), "monitor_controls": controls,
                    "last_monitor_control": copy.deepcopy(self._last_control),
                    "notifications": dict(self.notification_state),
                    "advisories": advisories,
                    "agent_service": agent,
                    "mcp": dict(self.mcp_state),
                    "model_calls": 0, "local_url": self.web.url}

    def run(self, *, max_seconds=None, announce=None):
        if max_seconds is not None and (type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 1 <= max_seconds <= 3600):
            self.web.close()
            raise ValueError("invalid_application_duration")
        started = time.monotonic()
        stop_receipt = None
        web_receipt = None
        services_receipt = {"thread_exited": True, "descriptor_saved": True}
        try:
            from .rules.configured import load_rules
            if self.auto_start:
                load_rules(self.runtime.root)  # Reject broken startup rules before any child launch.
            from .application_host import ApplicationControlServices
            self.control_services = ApplicationControlServices(self)
            self.web.start()
            self.mcp_state = self.control_services.start()
            with self._state_lock:
                self._started = True
            if self.auto_start:
                self.monitor_control("start", source="startup")
            # Keep the local page usable when a source/collector cannot start.
            # Its status exposes the error. There is no model retry path.
            if announce is not None:
                announce({"url": self.web.url, "namespace": self.namespace, "state": self.launch.get("state"),
                          "model_calls": 0, "stop": "Ctrl+C"})
            while not self.cancel.wait(1):
                if max_seconds is not None and time.monotonic() - started >= max_seconds:
                    break
                if self.notification_service is not None:
                    try:
                        self.notification_state = self.notification_service.poll()
                    except (OSError, ValueError, RuntimeError):
                        self.notification_state = {"status": "error", "reason": "notification_storage_unavailable"}
        except KeyboardInterrupt:
            self.cancel.set()
        finally:
            self.cancel.set()
            with self._state_lock:
                self._closing = True
            if self.control_services is not None:
                try:
                    services_receipt = self.control_services.close()
                except (OSError, ValueError, RuntimeError):
                    services_receipt = {"thread_exited": False, "descriptor_saved": False,
                                        "reason": "application_control_shutdown_unconfirmed"}
            try:
                web_receipt = self.web.close()
            except (OSError, RuntimeError):
                web_receipt = {"web_thread_exited": False}
            try:
                if self.notification_service is not None:
                    self.notification_service.close()
            except (OSError, RuntimeError):
                self.notification_state = {"status": "error", "reason": "notification_close_failed"}
            finally:
                with self._control_lock:
                    stop_receipt = self.owner.close_owned_monitor(grace_seconds=10)
                    with self._state_lock:
                        self._shutdown_unconfirmed = (stop_receipt.get("child_exited") is not True
                            or stop_receipt.get("evidence_write_failed") is True or not web_receipt["web_thread_exited"]
                            or services_receipt.get("thread_exited") is not True or not services_receipt.get("descriptor_saved"))
                        self._started = False
                        self._paused = False
                        self._stopped = not self._shutdown_unconfirmed
                        previous = self._last_action or {}
                        action_source = previous.get("source", "system") if previous.get("action") == "shutdown" else "system"
                        operation_id = previous.get("operation_id") if previous.get("action") == "shutdown" else uuid.uuid4().hex
                        self._record_action("shutdown", action_source, operation_id,
                            "stopped" if not self._shutdown_unconfirmed
                            else "shutdown_unconfirmed",
                            "monitor_application_closed" if not self._shutdown_unconfirmed
                            else "monitor_exit_unconfirmed")
                if self.control_services is not None:
                    self.control_services.release(clean=not self._shutdown_unconfirmed)
        clean = (web_receipt["web_thread_exited"] and stop_receipt.get("child_exited") is True
                 and stop_receipt.get("evidence_write_failed") is not True
                 and services_receipt.get("thread_exited") is True and services_receipt.get("descriptor_saved") is True)
        started_ok = not self.auto_start or self.launch.get("state") in {"started", "already_running"}
        return {"state": ("stopped" if started_ok else "blocked") if clean else "shutdown_unconfirmed", "namespace": self.namespace,
                "url": self.web.url, "web": web_receipt, "monitor": stop_receipt, "control_services": services_receipt,
                "launch_state": self.launch.get("state"), "reason": self.launch.get("reason") if not started_ok else None,
                "monitor_transitions": {"pauses": self._pause_count, "resumes": self._resume_count,
                                        "stops": self._stop_count, "starts": self._start_count, "last_pause": self._pause_receipt},
                "model_calls": 0}


def run(root, **options):
    max_seconds = options.pop("max_seconds", None)
    def announce(value):
        if sys.stderr is not None:
            print("EventGuard：" + value["url"] + "\n前景執行。按 Ctrl+C 停止。模型呼叫：0。", file=sys.stderr, flush=True)
    return Application(root, **options).run(max_seconds=max_seconds, announce=announce)
