"""Application lifetime controller shared by a small local desktop window.

The GUI owns its host Job and stays alive while monitoring. This is deliberately
different from an independently detached background process: no ancestor Job,
security policy, scheduler or model authorization is bypassed. Methods are
synchronous and intended for the GUI's single worker, never its Tk thread.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import threading
import uuid

from . import background, processes
from .operations import OperatorAPI, SOURCES

CODE = re.compile(r"[a-z][a-z0-9_]{0,95}\Z")


def _code(value, fallback=None):
    return value if type(value) is str and CODE.fullmatch(value) else fallback


def _confirmed(receipt):
    return (isinstance(receipt, dict) and receipt.get("child_exited") is True
            and type(receipt.get("remaining_owned_processes")) is int
            and receipt["remaining_owned_processes"] == 0)


class DesktopController:
    """Own only EventGuard children; expose saved facts without claiming safety."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.api = OperatorAPI(self.root)
        self._lock = threading.RLock()
        self._children = []
        self._receipts = []
        self._last_action = None
        self._last_error = None
        self._closed = False
        # Separate from the receive permission: only an explicit automatic
        # processing action may start this process-local dispatcher owner.
        self._agent_thread = None
        self._agent_cancel = threading.Event()
        self._agent_run_dir = None
        self._agent_result = {"state": "disabled", "enabled": False}
        self._agent_lock = threading.Lock()

    def _own(self, child):
        # Called by background.start immediately after atomic private Job spawn,
        # including failures before the host's ready handshake completes.
        self._children.append(child)

    def _remember(self, action, result):
        state = result.get("state", result.get("status"))
        failure = state in {"blocked", "error", "invalid_request", "unknown",
                            "shutdown_unconfirmed", "stop_not_persisted", "startup_failed"}
        self._last_action = {"action": action, "state": _code(state, "unknown"),
                             "reason": _code(result.get("reason", result.get("error_code")))}
        self._last_error = self._last_action["reason"] if failure else None
        return result

    def _error(self, action, code):
        return self._remember(action, {"state": "blocked", "reason": code,
            "model_calls": 0, "raw_error_omitted": True})

    def start(self):
        with self._lock:
            if self._closed:
                return self._error("start", "desktop_controller_closed")
            self._release_exited()
            try:
                previous = background.status(self.root)
                if (previous.get("namespace") == "test"
                        and previous.get("host_liveness") not in {"not_recorded", "exited_verified"}):
                    return self._error("start", "monitor_outside_live_namespace")
                result = background.start(self.root, lifetime_owner="application", child_owner=self._own)
            except (OSError, ValueError, TypeError, RuntimeError):
                return self._error("start", "desktop_start_failed")
            if result.get("namespace") not in (None, "live"):
                return self._error("start", "monitor_outside_live_namespace")
            if result.get("state") in {"started", "starting", "running", "running_verified"}:
                result = dict(result, automatic_agent=self._resume_automatic_agent())
            return self._remember("start", result)

    def _release_exited(self):
        """Close only our handles after existing Job/PID exit proof.

        This does not initiate termination. The background stop path owns the
        cooperative deadline and verified, private Job-only timeout policy.
        """
        remaining = []
        for child in self._children:
            try:
                if child.poll() is None or child.job.active() != 0:
                    remaining.append(child)
                    continue
                receipt = processes.finish(child, reason="cancelled", grace=0, request_stop=False)
                if _confirmed(receipt):
                    self._receipts.append(receipt)
                    self._receipts = self._receipts[-32:]
                else:
                    remaining.append(child)
            except (OSError, ValueError, TypeError, RuntimeError):
                remaining.append(child)
        self._children = remaining
        return not remaining

    def pause(self):
        with self._lock:
            # Stop admitting agent work before stopping collection. The
            # dispatcher owns and verifies its own private child Job.
            self._agent_cancel.set()
            try:
                current = background.status(self.root)
                if (current.get("namespace") == "test"
                        and current.get("host_liveness") not in {"not_recorded", "exited_verified"}):
                    return dict(self._error("pause", "monitor_outside_live_namespace"), can_close=False)
                result = background.stop(self.root, grace_seconds=10)
            except (OSError, ValueError, TypeError, RuntimeError):
                return self._error("pause", "desktop_stop_failed")
            released = self._release_exited()
            agent_stopped = self._stop_automatic_agent()
            host_gone = result.get("host_liveness") in {"not_recorded", "exited_verified"}
            if _confirmed(result.get("process")):
                host_gone = True
            confirmed = (result.get("desired_enabled") is False and host_gone
                         and result.get("state") in {"stopped", "disabled"} and released and agent_stopped)
            value = dict(result, child_exited=True if confirmed else None,
                         application_children_released=released,
                         automatic_agent_exited=agent_stopped,
                         application_receipts=list(self._receipts), can_close=confirmed)
            if not confirmed and value.get("state") in {"stopped", "disabled"}:
                value.update(state="shutdown_unconfirmed", reason="desktop_child_exit_unconfirmed")
            return self._remember("pause", value)

    def close(self):
        with self._lock:
            if self._closed:
                return {"state": "closed", "can_close": True, "desired_enabled": False,
                        "child_exited": True, "model_calls": 0}
            result = self.pause()
            if result.get("can_close") is True:
                self._closed = True
                result = dict(result, state="closed")
            return self._remember("close", result)

    def set_agent_delivery(self, enabled):
        with self._lock:
            if self._closed:
                return self._error("agent_delivery", "desktop_controller_closed")
            if type(enabled) is not bool:
                return self._error("agent_delivery", "agent_delivery_boolean_required")
            try:
                from .agent_access import set_enabled
                result = set_enabled(self.root, enabled)
            except (ImportError, OSError, ValueError, TypeError, RuntimeError):
                return self._error("agent_delivery", "agent_delivery_policy_unavailable")
            if not enabled and result.get("setting_saved") is True:
                stopped = self._stop_automatic_agent()
                result = dict(result, automatic_agent_exited=stopped)
                if not stopped:
                    result.update(state="shutdown_unconfirmed", reason="automatic_agent_exit_unconfirmed")
            return self._remember("agent_delivery", result)

    def _stop_automatic_agent(self):
        """Cancel and wait; never discard an unconfirmed dispatcher owner."""
        self._agent_cancel.set()
        worker = self._agent_thread
        if worker is not None:
            worker.join(timeout=15)
            if worker.is_alive():
                return False
        with self._agent_lock:
            result = dict(self._agent_result)
            if result.get("child_exited") is False or worker is not None and result.get("child_exited") is not True:
                return False
            self._agent_result = dict(result, enabled=False)
        self._agent_thread = None
        return True

    def _automatic_snapshot(self):
        from .agent_automation import status as settings
        policy = settings(self.root)
        with self._agent_lock:
            result = dict(self._agent_result)
        worker = self._agent_thread
        if worker is not None and worker.is_alive() and self._agent_run_dir is not None:
            try:
                from .agent_dispatch import status
                value = status(self._agent_run_dir)
                # Only bounded operational values reach the GUI. No CLI trace,
                # prompt, command line or event content is read here.
                for name in ("state", "reason", "child_exited", "tasks_started", "tasks_passed", "queue_checks"):
                    if name in value:
                        result[name] = value[name]
            except (OSError, ValueError, RuntimeError):
                pass  # The worker may not have published its first receipt yet.
        result["worker_alive"] = worker is not None and worker.is_alive()
        result["enabled"] = policy["enabled"]
        result["executable"] = policy["executable"]
        if policy.get("blocked"):
            result.update(state="blocked", reason=policy["reason"])
        elif not result["worker_alive"] and result.get("state") in {"disabled", "stopped"} and policy["enabled"]:
            result.update(state="armed", reason="explicit_start_required")
        result["desktop_task_resumed"] = False
        return result

    def set_automatic_agent(self, enabled, executable=None):
        """Explicit model opt-in; existing receive permission is insufficient.

        Opening the GUI or reading status never starts a model. An explicit
        Start may use a previously saved opt-in; Pause preserves that setting.
        """
        with self._lock:
            if self._closed:
                return self._error("automatic_agent", "desktop_controller_closed")
            if type(enabled) is not bool:
                return self._error("automatic_agent", "automatic_agent_boolean_required")
            from .agent_automation import set_enabled, status as settings
            if not enabled:
                try:
                    set_enabled(self.root, False)
                except (OSError, ValueError, TypeError, RuntimeError):
                    return self._error("automatic_agent", "automation_setting_write_failed")
                stopped = self._stop_automatic_agent()
                return self._remember("automatic_agent", {"state": "disabled" if stopped else "shutdown_unconfirmed",
                    "enabled": False, "child_exited": stopped,
                    "reason": None if stopped else "automatic_agent_exit_unconfirmed"})
            from .agent_access import guard
            blocked = guard(self.root, "live")
            if blocked is not None:
                return self._error("automatic_agent", "agent_receive_permission_required")
            policy = settings(self.root)
            candidate = executable if type(executable) is str and executable else policy["executable"] or shutil.which("codex.exe")
            try:
                set_enabled(self.root, True, candidate)
            except (OSError, ValueError, TypeError, RuntimeError):
                return self._error("automatic_agent", "native_codex_or_setting_unavailable")
            # A click while monitoring is an explicit action. A saved choice
            # in an otherwise idle window waits for the next explicit Start.
            current = background.status(self.root)
            if current.get("state") not in {"started", "starting", "running", "running_verified"}:
                return self._remember("automatic_agent", {"state": "armed", "enabled": True,
                    "reason": "explicit_start_required"})
            return self._remember("automatic_agent", self._resume_automatic_agent())

    def _resume_automatic_agent(self):
        from .agent_automation import status as settings
        policy = settings(self.root)
        if not policy["enabled"]:
            return {"state": "disabled", "enabled": False}
        if self._agent_thread is not None and self._agent_thread.is_alive():
            return self._automatic_snapshot()
        if not self._stop_automatic_agent():
            return {"state": "shutdown_unconfirmed", "reason": "automatic_agent_exit_unconfirmed"}
        from .agent_access import guard
        if guard(self.root, "live") is not None:
            result = {"state": "blocked", "reason": "agent_receive_permission_required", "child_exited": True}
            with self._agent_lock:
                self._agent_result = result
            return result
        native = policy["executable"]
        if not native or Path(native).suffix.lower() != ".exe" or not Path(native).is_file():
            result = {"state": "blocked", "reason": "native_codex_executable_required", "child_exited": True}
            with self._agent_lock:
                self._agent_result = result
            return result
        try:
            run_dir = self.root / "reports" / "automatic-agent" / uuid.uuid4().hex
            run_dir.parent.mkdir(parents=True, exist_ok=True)
            self._agent_run_dir = run_dir
            self._agent_cancel = threading.Event()
            cancel = self._agent_cancel
            with self._agent_lock:
                self._agent_result = {"state": "starting", "enabled": True, "child_exited": True}

            def dispatch():
                try:
                    from .agent_dispatch import run, status
                    code = run(run_dir, source_dir=self.root / "data/live",
                               state_dir=self.root / "data/agent-delivery", codex=native,
                               max_seconds=3600, continuous=True, allow_live=True,
                               execute=True, cancel=cancel)
                    final = status(run_dir)
                    final = {name: final[name] for name in ("state", "reason", "child_exited", "tasks_started", "tasks_passed") if name in final}
                    final.update(enabled=False, exit_code=code)
                except Exception:
                    # The dispatcher itself owns cleanup; absent evidence is
                    # unknown, never a claim that a model process exited.
                    final = {"state": "shutdown_unconfirmed", "enabled": False,
                             "reason": "automatic_agent_failed", "child_exited": False}
                with self._agent_lock:
                    self._agent_result = final

            self._agent_thread = threading.Thread(target=dispatch, name="EventGuard-automatic-agent", daemon=False)
            self._agent_thread.start()
            return {"state": "starting", "enabled": True,
                "reason": "event_driven_dispatch_enabled", "desktop_task_resumed": False}
        except (OSError, ValueError, RuntimeError):
            self._agent_thread = None
            result = {"state": "blocked", "reason": "automatic_agent_start_failed", "enabled": True,
                      "child_exited": True}
            with self._agent_lock:
                self._agent_result = result
            return result

    def inspect(self, event_id):
        with self._lock:
            return self.api.call("inspect_event", event_id, namespace="live")

    def snapshot(self):
        """Read one saved overview; no collector, model or scheduling operation."""
        with self._lock:
            document = self.api.call("overview", namespace="live", limit=100)
            try:
                from .agent_access import status
                agent = status(self.root)
            except (ImportError, OSError, ValueError, TypeError, RuntimeError):
                agent = {"status": "blocked", "enabled": False, "delivery_allowed": False,
                         "reason": "agent_delivery_policy_unavailable", "receiver_state": "not_verified",
                         "model_calls": 0}
            bg = document.get("background") or {}
            monitor = document.get("current_monitor") or {}
            coverage = document.get("source_coverage") or {}
            storage = document.get("event_storage") or {}
            counts = storage.get("counts") or {}
            known = storage.get("state") in {"available", "not_created"}
            sources = []
            for source in SOURCES:
                item = coverage.get(source) or {}
                errors = item.get("errors") or []
                error = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
                evidence = {"reason": _code(item.get("reason")) or _code(error.get("reason_code")),
                            "stage": error.get("stage") if error.get("stage") in {"launch", "provider", "object", "field", "policy"} else None}
                for name in ("hresult", "win32_error"):
                    value = error.get(name)
                    evidence[name] = value if type(value) is int and -(2**31) <= value <= 2**32-1 else None
                sources.append({"source_id": source, "status": item.get("status", "not_observed"),
                    "row_count": item.get("row_count"), "observed_at": item.get("observed_at"),
                    "freshness": item.get("freshness") or {"state": "unknown"},
                    **evidence, "current_coverage": item.get("current_coverage", "unknown")})
            scope_matches = (monitor.get("scope_matches") is not False
                             and monitor.get("namespace") in (None, "live"))
            monitoring = True if scope_matches and monitor.get("state") == "running_verified" else (
                False if monitor.get("state") == "not_started" or bg.get("host_liveness") == "exited_verified" else None)
            # Retry is still unacknowledged; a failed delivery also remains in
            # durable storage and is displayed independently, never discarded.
            count_view = {"pending": counts.get("pending", 0) + counts.get("retry", 0) if known else None,
                          "acked": counts.get("ack", 0) if known else None,
                          "failed": counts.get("failed", 0) if known else None}
            listing = document.get("event_list") or {}
            state = bg.get("state") or document.get("status") or "unknown"
            return {"state": state, "desired_enabled": bg.get("desired_enabled"),
                "monitoring": monitoring, "updated_at": datetime.now(timezone.utc).isoformat(),
                "namespace": "live", "sources": sources, "counts": count_view,
                "events": listing.get("events", []), "events_truncated": listing.get("truncated"),
                "events_total": listing.get("total") if type(listing.get("total")) is int and listing["total"] >= 0 else None,
                "events_limit": 100,
                "agent_delivery": agent, "last_action": self._last_action,
                "automatic_agent": self._automatic_snapshot(),
                "last_error": self._last_error or _code(document.get("last_error")) or _code(document.get("error_code")) or (
                    "monitor_outside_live_namespace" if not scope_matches else None),
                "background": bg, "monitor": monitor, "operator_summary": document.get("operator_summary"),
                "application_owned_children": len(self._children), "model_calls": 0,
                "agent_required": False, "reboot_recovery_verified": False,
                "lifetime_owner": "application", "data_trust": "untrusted_data"}
