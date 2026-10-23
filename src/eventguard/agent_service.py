"""Explicit, ordinary-user host for the existing event-driven dispatcher.

The host owns no second queue or budget. A pause stops admission, not an active
task. Start and resume default to preflight. This module never installs tasks,
attaches desktop chats, or restarts a failed dispatcher automatically.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

from . import agent_dispatch, processes
from .acceptance_control import FileLease
from .local_paths import _guard
from .runtime import Runtime, atomic_json, read_json

ROOT = Path(__file__).resolve().parents[2]
KIND = "eventguard-agent-service-control-v1"
OWNER_KIND = "eventguard-agent-service-owner-v1"
_TOKEN = re.compile(r"[a-f0-9]{32}\Z")
_JOB = re.compile(r"Global\\EventGuard-[a-f0-9]{32}\Z")
_KEEPERS = []  # Closing the last keeper while alive would terminate this host.
HEARTBEAT_SECONDS = 2
HEARTBEAT_MAX_AGE = 15


class AgentServiceError(RuntimeError):
    """Fixed operational codes only; no raw exception or event text."""


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _date(value):
    if type(value) is not str or not 1 <= len(value) <= 80:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _path(root, name):
    return Runtime(root).path(Path("data/agent-service") / name)


def _read(root, name):
    path = _path(root, name)
    value = read_json(path) if path.exists() else None
    if value is not None and not isinstance(value, dict):
        raise AgentServiceError("agent_service_metadata_invalid")
    return value


def _write(root, name, value):
    atomic_json(_path(root, name), value)


@contextmanager
def _mutation(root):
    _path(root, "control.lock").parent.mkdir(parents=True, exist_ok=True)
    lease = FileLease(_path(root, "control.lock"))
    if not lease.acquire():
        raise AgentServiceError("agent_service_control_busy")
    try:
        yield
    finally:
        lease.release()


def _control(root):
    value = _read(root, "control.json")
    if value is None:
        return None
    if (value.get("kind") != KIND or type(value.get("enabled")) is not bool
            or type(value.get("paused")) is not bool or type(value.get("allow_live")) is not bool
            or type(value.get("run_id")) is not str or not _TOKEN.fullmatch(value["run_id"])
            or type(value.get("job_name")) is not str or not _JOB.fullmatch(value["job_name"])
            or _date(value.get("updated_at")) is None):
        raise AgentServiceError("agent_service_control_invalid")
    for key in ("source_dir", "state_dir", "codex_executable"):
        if (type(value.get(key)) is not str or not value[key] or len(value[key]) > 4096
                or any(ord(char) < 32 for char in value[key])):
            raise AgentServiceError("agent_service_control_invalid")
        _guard(value[key])
    if value["allow_live"] and Path(root).resolve() != ROOT.resolve():
        raise AgentServiceError("agent_service_live_root_refused")
    return value


def _owner_valid(value):
    return (isinstance(value, dict) and value.get("kind") == OWNER_KIND
            and type(value.get("run_id")) is str and _TOKEN.fullmatch(value["run_id"])
            and type(value.get("job_name")) is str and _JOB.fullmatch(value["job_name"])
            and type(value.get("pid")) is int and 0 < value["pid"] <= 2**32-1
            and _date(value.get("created_at")) is not None
            and type(value.get("session_id")) is int and 0 <= value["session_id"] <= 2**32-1)


def _job_state(job):
    try:
        active = processes.current_job_active(job)
        if type(active) is not int or active < 0:
            raise ValueError()
        return {"state": "exited_verified" if active == 0 else "active",
                "remaining_owned_processes": active}
    except OSError as error:
        if getattr(error, "winerror", None) == 2:
            return {"state": "exited_verified", "remaining_owned_processes": 0}
    except (ValueError, RuntimeError):
        pass
    return {"state": "unknown", "remaining_owned_processes": None}


def _pending(source):
    """Read counts without constructing/migrating an EventStore or inbox."""
    path = _guard(source) / "eventguard.sqlite3"
    if not path.is_file():
        return {"state": "unavailable", "pending": None, "reason": "existing_event_source_required"}
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
            db.execute("PRAGMA query_only=ON")
            counts = dict(db.execute("SELECT delivery_status,COUNT(*) FROM events GROUP BY delivery_status"))
        ready = counts.get("pending", 0) + counts.get("retry", 0)
        return {"state": "available", "pending": sum(count for name, count in counts.items() if name != "ack"),
                "ready_count": ready, "attention_count": counts.get("failed", 0), "counts": counts}
    except (OSError, ValueError, sqlite3.Error):
        return {"state": "unavailable", "pending": None, "reason": "event_source_unreadable"}


def _selection_policy(root):
    from .dispatch_policy import load_policy
    path = Runtime(root).path("config/agent-dispatch.json")
    return load_policy(path if path.exists() else None)


def status(root):
    """Read recorded identity, private Job, queue counts and fixed budget."""
    from .agent_budget import public_status
    result = {"state": "not_started", "desired_enabled": False, "paused": False,
              "host_liveness": "not_recorded", "execution_verified": False,
              "real_agent_wake_verified": False, "model_calls": 0,
              "pending_disposition": "retained", "pending_events": None,
              "ready_count": None, "attention_count": None, "budget": public_status()}
    try:
        result["selection_policy"] = _selection_policy(root)
    except (OSError, ValueError, TypeError, RuntimeError):
        result.update(selection_policy=None, selection_policy_error="agent_dispatch_policy_invalid")
    try:
        desired = _control(root)
        if desired:
            result.update(desired_enabled=desired["enabled"], paused=desired["paused"],
                          source_dir=desired["source_dir"], state_dir=desired["state_dir"],
                          namespace="live" if desired["allow_live"] else "test",
                          run_id=desired["run_id"], queue=_pending(desired["source_dir"]))
            result.update(pending_events=result["queue"].get("pending"),
                          ready_count=result["queue"].get("ready_count"),
                          attention_count=result["queue"].get("attention_count"))
            if desired["paused"]:
                barrier = _read(root, "pause-receipt.json")
                result["admission_barrier"] = (barrier.get("admission_barrier", "unconfirmed")
                    if barrier and barrier.get("run_id") == desired["run_id"] else "unconfirmed")
        owner, launch, saved = _read(root, "owner.json"), _read(root, "launch.json"), _read(root, "run.json")
        if saved and desired and saved.get("run_id") == desired["run_id"]:
            result["model_calls"] = saved.get("model_calls")
        if launch and (owner is None or launch.get("run_id") != owner.get("run_id")):
            if (launch.get("state") != "launch_intent" or type(launch.get("run_id")) is not str
                    or not _TOKEN.fullmatch(launch["run_id"]) or type(launch.get("job_name")) is not str
                    or not _JOB.fullmatch(launch["job_name"])):
                raise AgentServiceError("agent_service_launch_invalid")
            job = _job_state(launch["job_name"])
            return dict(result, state="interrupted" if job["state"] == "exited_verified" else "unknown",
                        host_liveness=job["state"], reason="launch_owner_unconfirmed", job=job, model_calls=None)
        if owner is None:
            return dict(result, state="enabled_not_running" if result["desired_enabled"] else "not_started")
        if not _owner_valid(owner):
            raise AgentServiceError("agent_service_owner_invalid")
        result["owner"] = owner
        observed = processes.identity(owner["pid"])
        matches = observed.get("state") == "alive" and observed.get("created_at") == owner["created_at"]
        if saved and saved.get("run_id") == owner["run_id"]:
            result.update(last_progress=saved.get("last_progress"), reason=saved.get("reason"),
                          heartbeat_at=saved.get("heartbeat_at"), dispatcher=saved.get("dispatcher"),
                          dispatch_run_dir=saved.get("dispatch_run_dir"), model_calls=saved.get("model_calls"))
        else:
            result["model_calls"] = None
        if matches:
            heartbeat = _date(result.get("heartbeat_at"))
            age = (datetime.now(timezone.utc) - heartbeat).total_seconds() if heartbeat else None
            session_matches = processes.process_session(owner["pid"]) == owner["session_id"]
            fresh = age is not None and 0 <= age <= HEARTBEAT_MAX_AGE and session_matches
            result.update(host_liveness="alive_verified" if fresh else "alive_unverified",
                          heartbeat_age_seconds=age if age is not None and age >= 0 else None)
            terminal_state = saved.get("state") if saved and saved.get("state") in {"blocked", "failed", "stopped"} else None
            return dict(result, state=terminal_state if fresh and terminal_state else ("paused" if result["paused"] else "running") if fresh and result["desired_enabled"]
                        else "stopping" if fresh else "unknown",
                        reason=result.get("reason") if fresh else "agent_service_heartbeat_or_session_unverified")
        job = _job_state(owner["job_name"])
        terminal = job["state"] == "exited_verified"
        saved_state = saved.get("state") if saved and saved.get("run_id") == owner["run_id"] else None
        terminal_state = saved_state if saved_state in {"stopped", "blocked", "failed"} else "interrupted"
        return dict(result, state=terminal_state
                    if terminal else "shutdown_unconfirmed", host_liveness=job["state"], job=job)
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError) as error:
        reason = str(error) if type(error) is AgentServiceError else "agent_service_state_unverifiable"
        return dict(result, state="blocked", reason=reason, host_liveness="unknown", model_calls=None)


def _preflight(root, codex_executable, allow_live, source_dir, state_dir):
    root = Runtime(root).root
    if type(allow_live) is not bool or allow_live and root.resolve() != ROOT.resolve():
        raise AgentServiceError("agent_service_live_root_refused")
    source = _guard(source_dir if source_dir is not None else root / "data" / ("live" if allow_live else "test"))
    state = _guard(state_dir if state_dir is not None else root / "data" / ("agent-delivery" if allow_live else "agent-delivery-test"))
    if not source.is_relative_to(root) or not state.is_relative_to(root) or state == source or source in state.parents:
        raise AgentServiceError("agent_service_scope_invalid")
    if not (source / "eventguard.sqlite3").is_file():
        raise AgentServiceError("existing_event_source_required")
    candidate = shutil.which(str(codex_executable))
    if candidate is None or Path(candidate).suffix.lower() != ".exe":
        raise AgentServiceError("native_codex_executable_required")
    if _pending(source)["state"] != "available":
        raise AgentServiceError("event_source_unreadable")
    binding = _guard(source / "agent-channel.json")
    expected = {"kind": agent_dispatch.KIND,
                "state_dir_sha256": hashlib.sha256(str(state).casefold().encode("utf-8")).hexdigest()}
    if binding.exists() and read_json(binding) != expected:
        raise AgentServiceError("dispatch_source_already_bound_to_other_state")
    if state.exists():
        if not state.is_dir():
            raise AgentServiceError("agent_service_inbox_scope_invalid")
        if (state / "inbox-state.json").exists():
            from .queue_inbox import QueueInbox
            QueueInbox.open_readonly(source, state, allow_live=allow_live)
        elif any(p.name not in {"inbox-owner.lock", "inbox-mutation.lock"} for p in state.iterdir()):
            raise AgentServiceError("agent_service_inbox_scope_invalid")
    return root, source, state, _guard(candidate)


def start(root, codex_executable, *, allow_live=False, source_dir=None, state_dir=None,
          execute=False, ready_timeout=15):
    """Preflight unless explicitly executed. Never initializes a model budget."""
    if type(execute) is not bool or type(ready_timeout) not in (int, float) or not math.isfinite(ready_timeout) or not 1 <= ready_timeout <= 30:
        raise ValueError("agent_service_start_bounds_invalid")
    try:
        root, source, state_dir, executable = _preflight(root, codex_executable, allow_live, source_dir, state_dir)
    except (OSError, ValueError, RuntimeError) as error:
        return {"state": "blocked", "reason": str(error) if type(error) is AgentServiceError else "agent_service_preflight_failed",
                "model_calls": 0, "execute_required": True}
    from .agent_budget import public_status
    capability_reasons, waiting_reasons = [], []
    try:
        selection_policy = _selection_policy(root)
    except (OSError, ValueError, TypeError, RuntimeError):
        selection_policy = None
        capability_reasons.append("agent_dispatch_policy_invalid")
    if importlib.util.find_spec("mcp") is None:
        capability_reasons.append("missing_existing_mcp_sdk")
    if allow_live:
        from .agent_access import guard
        blocked = guard(root, "live")
        if blocked:
            capability_reasons.append(blocked["reason"])
    budget = public_status()
    if budget.get("state") != "ready":
        reason = budget.get("reason") or "budget_unavailable"
        (waiting_reasons if reason in {"budget_exhausted", "budget_bootstrap_usage_unknown"}
         else capability_reasons).append(reason)
    preflight = {"state": "blocked" if capability_reasons else "preflight_ready", "execute_required": True,
                 "model_calls": 0, "source_dir": str(source), "state_dir": str(state_dir),
                 "namespace": "live" if allow_live else "test", "budget": budget,
                 "selection_policy": selection_policy,
                 "capability_reasons": capability_reasons, "blocked_reasons": capability_reasons + waiting_reasons,
                 "reason": capability_reasons[0] if capability_reasons else waiting_reasons[0] if waiting_reasons else None}
    if not execute or capability_reasons:
        return preflight
    child = None
    with _mutation(root):
        current = status(root)
        if current["host_liveness"] in {"alive_verified", "alive_unverified"}:
            return dict(current, reason="agent_service_already_running")
        if current["host_liveness"] not in {"not_recorded", "exited_verified"}:
            return dict(current, state="blocked", reason="previous_agent_host_exit_unconfirmed")
        previous = _control(root)
        run_id, job_name = uuid.uuid4().hex, "Global\\EventGuard-" + uuid.uuid4().hex
        control = {"kind": KIND, "run_id": run_id, "job_name": job_name, "enabled": True,
                   "paused": bool(previous and previous["paused"]), "updated_at": _stamp(),
                   "source_dir": str(source), "state_dir": str(state_dir),
                   "codex_executable": str(executable), "allow_live": allow_live}
        _write(root, "control.json", control)
        _write(root, "launch.json", {"state": "launch_intent", "run_id": run_id, "job_name": job_name})
        try:
            python = Path(sys.executable)
            hidden = python.with_name("pythonw.exe")
            if hidden.is_file():
                python = hidden
            argv = [str(python), "-B", "-m", "eventguard.agent_service", "_serve", "--root", str(root),
                    "--run-id", run_id, "--job-name", job_name]
            child = processes.spawn_persistent(argv, job_name=job_name, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(ROOT),
                env=dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1"))
            owner = {"kind": OWNER_KIND, "run_id": run_id, "pid": child.pid, "created_at": child.created_at,
                     "job_name": job_name, "session_id": processes.process_session(child.pid)}
            _write(root, "owner.json", owner)
            deadline = time.monotonic() + ready_timeout
            while time.monotonic() < deadline:
                ready = _read(root, "ready.json")
                if ready and all(ready.get(key) == owner[key] for key in ("run_id", "pid", "created_at")):
                    receipt = processes.detach_owned(child, ready["job_keeper"])
                    return {"state": "started", "run_id": run_id, "handoff": receipt,
                            "model_calls": None, "real_agent_wake_verified": False}
                if child.poll() is not None:
                    break
                time.sleep(.05)
            _write(root, "control.json", dict(control, enabled=False, updated_at=_stamp()))
            receipt = processes.finish(child, "launch_failure", grace=5, request_stop=False)
            _write(root, "stop-receipt.json", receipt)
            return {"state": "startup_failed", "reason": "agent_service_ready_unverified", "process": receipt, "model_calls": None}
        except BaseException:
            try:
                _write(root, "control.json", dict(control, enabled=False, updated_at=_stamp()))
            finally:
                if child is not None and not child.detached:
                    receipt = processes.finish(child, "launch_failure", grace=5, request_stop=False)
                    _write(root, "stop-receipt.json", receipt)
            raise


def _admission_barrier(wait_seconds=1):
    """Serialize after any capture already past its final launch gate.

    This never refunds, reserves or finalizes an attempt. Lack of authority or
    a busy lock remains visible; durable pause still prevents later admission.
    """
    from .acceptance_process import open_authority
    from .agent_budget import BudgetError
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            authority = open_authority()  # Fixed installation path, never root.
            with authority.launch_lease():
                return {"admission_barrier": "confirmed", "admission_barrier_reason": "launch_gate_serialized"}
        except BudgetError as error:
            if error.code == "budget_launch_busy" and time.monotonic() < deadline:
                time.sleep(.05)
                continue
            return {"admission_barrier": "unconfirmed", "admission_barrier_reason": error.code}


def pause(root):
    with _mutation(root):
        control = _control(root)
        if control is None:
            return {"state": "not_started", "model_calls": 0}
        _write(root, "control.json", dict(control, paused=True, updated_at=_stamp()))
        barrier = _admission_barrier()
        _write(root, "pause-receipt.json", {"run_id": control["run_id"], "at": _stamp(), **barrier})
    return {"state": "pause_requested", "paused": True, "active_task_cancelled": False,
            "pending_disposition": "retained", **barrier}


def resume(root, *, execute=False):
    if type(execute) is not bool:
        raise ValueError("agent_service_execute_boolean_required")
    if not execute:
        return {"state": "preflight_ready", "execute_required": True, "reason": "resume_may_start_agent", "model_calls": 0}
    with _mutation(root):
        control = _control(root)
        if control is None or not control["enabled"]:
            return {"state": "blocked", "reason": "agent_service_explicit_start_required", "model_calls": 0}
        current = status(root)
        if current.get("host_liveness") != "alive_verified" or current.get("state") not in {"running", "paused"}:
            return {"state": "blocked", "reason": "agent_service_host_not_running",
                    "host_liveness": current.get("host_liveness"), "pending_disposition": "retained"}
        _write(root, "control.json", dict(control, paused=False, updated_at=_stamp()))
    return {"state": "resume_requested", "paused": False, "pending_disposition": "retained"}


def stop(root, *, grace_seconds=15):
    if type(grace_seconds) not in (int, float) or not math.isfinite(grace_seconds) or not 1 <= grace_seconds <= 30:
        raise ValueError("agent_service_stop_bounds_invalid")
    with _mutation(root):
        control = _control(root)
        if control is None:
            return {"state": "not_started", "model_calls": 0}
        _write(root, "control.json", dict(control, enabled=False, updated_at=_stamp()))
        owner = _read(root, "owner.json")
        if not _owner_valid(owner) or owner["run_id"] != control["run_id"]:
            job = _job_state(control["job_name"])
            return {"state": "stopped" if job["state"] == "exited_verified" else "shutdown_unconfirmed",
                    "reason": "agent_service_owner_unverified", "job": job, "process_signal_sent": False}
        try:
            receipt = processes.stop_persistent(owner["job_name"], pid=owner["pid"], created_at=owner["created_at"],
                session_id=owner["session_id"], reason="cancelled", grace=grace_seconds)
        except OSError as error:
            job = _job_state(owner["job_name"])
            observed = processes.identity(owner["pid"])
            exited = observed.get("state") in {"missing", "exited"} or bool(observed.get("created_at") and observed["created_at"] != owner["created_at"])
            verified = getattr(error, "winerror", None) == 2 and exited and job["state"] == "exited_verified"
            receipt = {"child_exited": bool(exited), "remaining_owned_processes": 0 if verified else None,
                       "forcibly_terminated": False, "reason": "owned_job_missing" if verified else "owned_job_exit_unconfirmed"}
        _write(root, "stop-receipt.json", receipt)
        confirmed = receipt.get("child_exited") is True and receipt.get("remaining_owned_processes") == 0
        return {"state": "stopped" if confirmed else "shutdown_unconfirmed", "process": receipt,
                "pending_disposition": "retained"}


def serve(root, run_id, job_name):
    """Internal Job-bound host. One dispatcher lifetime, no restart loop."""
    if type(run_id) is not str or not _TOKEN.fullmatch(run_id) or type(job_name) is not str or not _JOB.fullmatch(job_name):
        raise ValueError("agent_service_run_identity_invalid")
    desired = _control(root)
    if not desired or not desired["enabled"] or desired["run_id"] != run_id or desired["job_name"] != job_name:
        return {"state": "disabled", "model_calls": 0}
    keeper = processes.adopt_current_job(job_name)
    _KEEPERS.append(keeper)
    held = keeper.receipt()
    lease = FileLease(_path(root, "host.lock"))
    if not lease.acquire():
        return {"state": "busy", "model_calls": 0}
    cancel, finished = threading.Event(), threading.Event()
    directory = _path(root, "runs") / run_id
    state = {"run_id": run_id, "state": "starting", "heartbeat_at": _stamp(), "last_progress": "host_ready",
             "reason": None, "dispatch_run_dir": str(directory), "model_calls": 0}
    monitor = None
    def dispatch_enabled():
        current = _control(root)
        return bool(current and current["enabled"] and not current["paused"] and current["run_id"] == run_id)
    def select_event(inbox):
        from .dispatch_policy import select_pending
        return select_pending(inbox, _selection_policy(root))
    def heartbeat():
        while not finished.wait(HEARTBEAT_SECONDS):
            try:
                current = _control(root)
                if current is None or not current["enabled"] or current["run_id"] != run_id:
                    cancel.set()
                try:
                    view = agent_dispatch.status(directory, read_only=True)
                except (OSError, ValueError, RuntimeError):
                    view = None
                state.update(heartbeat_at=_stamp(), dispatcher=view)
                if view:
                    state.update(last_progress=view.get("state"), reason=view.get("reason"),
                                 model_calls=None if view.get("tasks_started", 0) else 0)
                _write(root, "run.json", state)
            except (OSError, ValueError, TypeError, RuntimeError):
                cancel.set()  # Broken control or durable health fails closed.
                return
    try:
        _write(root, "run.json", state)
        _write(root, "ready.json", {"run_id": run_id, "pid": held["pid"], "created_at": held["created_at"], "job_keeper": held})
        monitor = threading.Thread(target=heartbeat, name="eventguard-agent-heartbeat", daemon=True)
        monitor.start()
        code = agent_dispatch.run(directory, desired["source_dir"], desired["state_dir"],
            codex=desired["codex_executable"], allow_live=desired["allow_live"], execute=True,
            continuous=True, cancel=cancel, root=root, dispatch_enabled=dispatch_enabled,
            admission_path=_path(root, "control.json"), admission_run_id=run_id,
            select_event=select_event)
        state.update(state="stopped" if cancel.is_set() and code == 0 else "blocked", exit_code=code)
        try:
            view = agent_dispatch.status(directory, read_only=True)
            state.update(dispatcher=view, last_progress=view.get("state"), reason=view.get("reason"),
                         model_calls=None if view.get("tasks_started", 0) else 0)
        except (OSError, ValueError, RuntimeError):
            state.update(reason="dispatcher_exit_evidence_unavailable", model_calls=None)
    except (KeyboardInterrupt, OSError, ValueError, RuntimeError):
        cancel.set()
        state.update(state="failed", reason="agent_service_host_failure", model_calls=None)
    finally:
        finished.set()
        if monitor is not None:
            monitor.join(timeout=HEARTBEAT_SECONDS + 1)
        state["heartbeat_at"] = _stamp()
        try:
            _write(root, "run.json", state)
            _write(root, "exit.json", {"run_id": run_id, "pid": held["pid"], "created_at": held["created_at"],
                "state": state["state"], "reason": state.get("reason"), "forcibly_terminated": False, "at": _stamp()})
        finally:
            lease.release()
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("_serve",))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job-name", required=True)
    args = parser.parse_args(argv)
    value = serve(args.root, args.run_id, args.job_name)
    return 0 if value["state"] in {"disabled", "stopped"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
