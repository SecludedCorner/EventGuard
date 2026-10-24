"""One foreground application: existing owned supervisor + local product UI."""
from __future__ import annotations

import math
import re
import sys
import threading
import time


class Application:
    def __init__(self, root, *, port=8765, fixture=None, max_cycles=None, notifications=True,
                 notification_sink=None):
        from .runtime import Runtime
        from .operations import OperatorAPI
        from .web import LocalWeb
        from .notifications import NotificationService
        self.runtime = Runtime(root)
        self.namespace = "test" if fixture else "live"
        self.fixture, self.max_cycles = fixture, max_cycles
        self.owner = OperatorAPI(root, background_lifetime_owner="application")
        self.cancel = threading.Event()
        self.notification_service = NotificationService(root, self.namespace, sink=notification_sink) if notifications else None
        self.notification_state = {"status": "waiting" if notifications else "disabled", "model_calls": 0}
        self.launch = {"state": "not_started"}
        self._control_lock = threading.Lock()
        self._transition = None
        self._closing = False
        self._started = False
        self._paused = False
        self._owned_scope = None
        self._pause_generation = None
        self._last_control = None
        self._pause_receipt = None
        self._pause_count = self._resume_count = 0
        # Bind the port before starting a collector. A port conflict starts no monitor.
        self.web = LocalWeb(root, self.namespace, port=port, status_provider=self.status,
                            monitor_control=self.monitor_control)

    def _own_monitor_child(self, child):
        self.owner._own_monitor_child(child)
        scope = getattr(child, "_eventguard_background_scope", None)
        if isinstance(scope, dict) and scope.get("namespace") == self.namespace:
            self._owned_scope = dict(scope)

    def _same_monitor(self, saved):
        return (isinstance(self._owned_scope, dict) and saved.get("namespace") == self.namespace
                and saved.get("run_id") == self._owned_scope.get("run_id"))

    def _start_monitor(self, *, expected_generation=None):
        from .background import start
        options = {} if expected_generation is None else {"expected_control_generation": expected_generation}
        self.launch = start(self.runtime.root, fixture=self.fixture, max_cycles=self.max_cycles,
                            lifetime_owner="application", child_owner=self._own_monitor_child, **options)
        return self.launch

    def monitor_control(self, action):
        """Typed local controls. Never adopt an existing host or start an agent."""
        if type(action) is not str or action not in {"pause", "resume", "stop"}:
            raise ValueError("invalid_monitor_action")
        if not self._control_lock.acquire(blocking=False):
            return {"state": "busy", "reason": "monitor_control_busy", "model_calls": 0}
        self._transition = action
        try:
            if self._closing or self.cancel.is_set():
                result = {"state": "blocked", "reason": "monitor_application_closing"}
            elif action == "stop":
                # Return the HTTP receipt before the foreground loop closes Web.
                # Cleanup itself uses only this application's captured handles.
                self._closing = True
                self.cancel.set()
                result = {"state": "stop_requested", "reason": "monitor_application_stop_requested"}
            elif not self._started or self._owned_scope is None:
                result = {"state": "blocked", "reason": "monitor_not_owned"}
            else:
                from .background import status
                saved = status(self.runtime.root)
                if not self._same_monitor(saved):
                    result = {"state": "blocked", "reason": "monitor_ownership_changed"}
                elif action == "pause":
                    if self._paused:
                        result = ({"state": "paused", "reason": "monitor_already_paused"}
                                  if saved.get("control_generation") == self._pause_generation
                                  and saved.get("desired_enabled") is False and saved.get("host_liveness") == "exited_verified"
                                  else {"state": "blocked", "reason": "monitor_pause_scope_unconfirmed"})
                    else:
                        # Match the existing monitor CLI's cooperative grace.
                        # Cold-start durable writes can outlast five seconds at
                        # the monitor's background I/O priority.
                        receipt = self.owner.close_owned_monitor(grace_seconds=10)
                        self._pause_receipt = receipt
                        saved = status(self.runtime.root)
                        if receipt.get("child_exited") is not True:
                            result = {"state": "shutdown_unconfirmed", "reason": "monitor_pause_exit_unconfirmed"}
                        elif receipt.get("evidence_write_failed") is True:
                            result = {"state": "blocked", "reason": "monitor_pause_receipt_save_failed"}
                        elif (not self._same_monitor(saved) or saved.get("desired_enabled") is not False
                              or saved.get("host_liveness") != "exited_verified"):
                            result = {"state": "blocked", "reason": "monitor_pause_scope_unconfirmed"}
                        elif (type(saved.get("control_generation")) is not str
                              or re.fullmatch(r"[a-f0-9]{32}", saved["control_generation"]) is None):
                            result = {"state": "blocked", "reason": "monitor_pause_generation_unconfirmed"}
                        else:
                            self._pause_generation = saved["control_generation"]
                            self._paused = True
                            self._pause_count += 1
                            result = {"state": "paused", "reason": "monitor_paused_events_preserved",
                                      "child_exited": True, "forcibly_terminated": receipt.get("forcibly_terminated", False)}
                elif not self._paused:
                    result = ({"state": "running", "reason": "monitor_not_paused"}
                              if saved.get("state") == "running" and saved.get("desired_enabled") is True
                              and saved.get("host_liveness") == "alive_verified"
                              else {"state": "blocked", "reason": "monitor_restart_required"})
                elif (saved.get("control_generation") != self._pause_generation
                      or saved.get("desired_enabled") is not False or saved.get("host_liveness") != "exited_verified"):
                    result = {"state": "blocked", "reason": "monitor_resume_scope_changed"}
                else:
                    from .rules.configured import load_rules
                    load_rules(self.runtime.root)
                    from .operations import OperatorAPI
                    # The old owner is permanently fenced. Its exit was verified
                    # before replacing it with a new owner for this explicit start.
                    self.owner = OperatorAPI(self.runtime.root, background_lifetime_owner="application")
                    self._owned_scope = None
                    launch = self._start_monitor(expected_generation=self._pause_generation)
                    if launch.get("state") == "started" and self._owned_scope is not None:
                        self._paused = False
                        self._pause_generation = None
                        self._resume_count += 1
                        result = {"state": "running", "reason": "monitor_resumed_events_preserved"}
                    else:
                        result = {"state": "blocked", "reason": "monitor_resume_failed",
                                  "launch_state": launch.get("state")}
            self._last_control = {**result, "model_calls": 0}
            return dict(self._last_control)
        except (OSError, ValueError, TypeError, RuntimeError):
            self._last_control = {"state": "blocked", "reason": "monitor_control_failed",
                                  "raw_error_omitted": True, "model_calls": 0}
            return dict(self._last_control)
        finally:
            self._transition = None
            self._control_lock.release()

    def status(self):
        from .background import status
        saved = status(self.runtime.root)
        try:
            health = self.runtime.health()
            error = health.get("last_error") if health.get("namespace") == self.namespace else None
            if type(error) is not str or re.fullmatch(r"rules_[a-z0-9_]{1,80}", error) is None:
                error = None
        except (OSError, ValueError, TypeError):
            error = "saved_health_unavailable"
        controls_available = (self._started and not self._closing and not self.cancel.is_set()
                              and self._same_monitor(saved))
        paused = (self._paused and self._same_monitor(saved)
                  and saved.get("control_generation") == self._pause_generation
                  and saved.get("desired_enabled") is False and saved.get("host_liveness") == "exited_verified")
        return {"namespace": self.namespace, "monitor_state": "paused" if paused else saved.get("state", "unknown"),
                "reason": saved.get("reason"), "config_error": error,
                "monitor_controls": {"available": controls_available, "paused": paused, "transition": self._transition},
                "last_monitor_control": self._last_control,
                "notifications": dict(self.notification_state),
                "model_calls": 0, "local_url": self.web.url}

    def run(self, *, max_seconds=None, announce=None):
        if max_seconds is not None and (type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 1 <= max_seconds <= 3600):
            self.web.close()
            raise ValueError("invalid_application_duration")
        started = time.monotonic()
        stop_receipt = None
        web_receipt = None
        try:
            from .rules.configured import load_rules
            load_rules(self.runtime.root)  # Reject a broken rule file before any child launch.
            with self._control_lock:
                self._transition = "start"
                try:
                    self._start_monitor()
                    self._started = True
                finally:
                    self._transition = None
            # Keep the local page usable when a source/collector cannot start.
            # Its status exposes the error. There is no model retry path.
            self.web.start()
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
            self._closing = True
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
        clean = web_receipt["web_thread_exited"] and stop_receipt.get("child_exited") is True
        started_ok = self.launch.get("state") in {"started", "already_running"}
        return {"state": ("stopped" if started_ok else "blocked") if clean else "shutdown_unconfirmed", "namespace": self.namespace,
                "url": self.web.url, "web": web_receipt, "monitor": stop_receipt,
                "launch_state": self.launch.get("state"), "reason": self.launch.get("reason") if not started_ok else None,
                "monitor_transitions": {"pauses": self._pause_count, "resumes": self._resume_count,
                                        "last_pause": self._pause_receipt},
                "model_calls": 0}


def run(root, **options):
    max_seconds = options.pop("max_seconds", None)
    def announce(value):
        if sys.stderr is not None:
            print("EventGuard：" + value["url"] + "\n前景執行。按 Ctrl+C 停止。模型呼叫：0。", file=sys.stderr, flush=True)
    return Application(root, **options).run(max_seconds=max_seconds, announce=announce)
