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
        # Bind the port before starting a collector. A port conflict starts no monitor.
        self.web = LocalWeb(root, self.namespace, port=port, status_provider=self.status)

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
        return {"namespace": self.namespace, "monitor_state": saved.get("state", "unknown"),
                "reason": saved.get("reason"), "config_error": error,
                "notifications": dict(self.notification_state),
                "model_calls": 0, "local_url": self.web.url}

    def run(self, *, max_seconds=None, announce=None):
        from .background import start
        if max_seconds is not None and (type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 1 <= max_seconds <= 3600):
            self.web.close()
            raise ValueError("invalid_application_duration")
        started = time.monotonic()
        stop_receipt = None
        web_receipt = None
        try:
            from .rules.configured import load_rules
            load_rules(self.runtime.root)  # Reject a broken rule file before any child launch.
            self.launch = start(self.runtime.root, fixture=self.fixture, max_cycles=self.max_cycles,
                                lifetime_owner="application", child_owner=self.owner._own_monitor_child)
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
                stop_receipt = self.owner.close_owned_monitor()
        clean = web_receipt["web_thread_exited"] and stop_receipt.get("child_exited") is True
        started_ok = self.launch.get("state") in {"started", "already_running"}
        return {"state": ("stopped" if started_ok else "blocked") if clean else "shutdown_unconfirmed", "namespace": self.namespace,
                "url": self.web.url, "web": web_receipt, "monitor": stop_receipt,
                "launch_state": self.launch.get("state"), "reason": self.launch.get("reason") if not started_ok else None,
                "model_calls": 0}


def run(root, **options):
    max_seconds = options.pop("max_seconds", None)
    def announce(value):
        if sys.stderr is not None:
            print("EventGuard：" + value["url"] + "\n前景執行。按 Ctrl+C 停止。模型呼叫：0。", file=sys.stderr, flush=True)
    return Application(root, **options).run(max_seconds=max_seconds, announce=announce)
