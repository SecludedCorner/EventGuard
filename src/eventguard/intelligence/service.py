"""Manual, ordinary-user advisory host. No scheduler, service or model loop."""
from __future__ import annotations

import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

from ..acceptance_control import FileLease
from ..runtime import Runtime, atomic_json, read_json
from .. import processes
from .engine import stamp, config_path, cycle

ROOT = Path(__file__).resolve().parents[3]
_KEEPERS = []  # The host retains its private Job until natural OS exit.
_TOKEN = re.compile(r"[a-f0-9]{32}\Z")


def _path(root, name):
    return Runtime(root).path(Path("data/advisories") / name)


def _read(root, name):
    path = _path(root, name)
    return read_json(path) if path.exists() else None


def _write(root, name, value):
    atomic_json(_path(root, name), value)


def status(root):
    from .engine import status as evidence_status
    result = evidence_status(root)
    desired, owner, run = _read(root, "control.json"), _read(root, "owner.json"), _read(root, "run.json")
    result.update(desired_enabled=bool(desired and desired.get("enabled")), host_liveness="not_recorded",
                  host_state="not_started", blocked_reason=None)
    if run:
        result.update(host_state=run.get("state", "unknown"), heartbeat_at=run.get("heartbeat_at"),
                      last_progress=run.get("last_progress"), blocked_reason=run.get("reason"))
    if owner:
        observed = processes.identity(owner.get("pid"))
        if observed.get("state") == "alive" and observed.get("created_at") == owner.get("created_at"):
            result["host_liveness"] = "alive_verified"
            result["host_state"] = run.get("state", "unknown") if run else "unknown"
            try:
                from datetime import datetime,timezone
                heartbeat=datetime.fromisoformat(run["heartbeat_at"].replace("Z","+00:00"))
                age=(datetime.now(timezone.utc)-heartbeat).total_seconds()
                if not 0<=age<=90:
                    raise ValueError()
                result["heartbeat_freshness"]="fresh"
            except (ValueError,TypeError,KeyError):
                result.update(host_state="unknown",heartbeat_freshness="stale_or_unknown",blocked_reason="advisory_heartbeat_stale_or_unknown")
        elif observed.get("state") in {"missing", "exited"} or observed.get("created_at") and observed["created_at"] != owner.get("created_at"):
            result["host_liveness"] = "exited_verified"
            result["host_state"] = "stopped" if run and run.get("state") == "stopped" else "interrupted"
        else:
            result.update(host_liveness="unknown", host_state="unknown", blocked_reason="owner_identity_unverifiable")
    return result


def start(root, path=None, *, ready_timeout=15, _bounded_test=False):
    """Explicit command only. Child is Job-bound before it can execute."""
    if type(ready_timeout) not in (int,float) or not math.isfinite(ready_timeout) or not 1 <= ready_timeout <= 30 or type(_bounded_test) is not bool:
        raise ValueError("advisory_start_bounds_invalid")
    from .sources import load_config
    configured = config_path(root, path)
    load_config(configured)
    _path(root, "start.lock").parent.mkdir(parents=True, exist_ok=True)
    lease = FileLease(_path(root, "start.lock"))
    if not lease.acquire():
        return {"state": "busy", "reason": "advisory_start_busy", "model_calls": 0}
    child = None
    try:
        owner = _read(root, "owner.json")
        if owner:
            observed = processes.identity(owner.get("pid"))
            if observed.get("state") == "alive" and observed.get("created_at") == owner.get("created_at"):
                return {"state": "running", "reason": "advisory_already_running", "model_calls": 0}
            if observed.get("state") not in {"missing", "exited"} and not (observed.get("created_at") and observed["created_at"] != owner.get("created_at")):
                return {"state": "blocked", "reason": "previous_owner_unverifiable", "model_calls": 0}
        run_id, job = uuid.uuid4().hex, "Global\\EventGuard-" + uuid.uuid4().hex
        control = {"enabled": True, "run_id": run_id, "config": str(configured.relative_to(Path(root).absolute())), "job_name": job}
        _write(root, "control.json", control)
        executable = Path(sys.executable)
        # pythonw avoids a new console. It is the same existing installation.
        hidden = executable.with_name("pythonw.exe")
        if hidden.is_file():
            executable = hidden
        argv = [str(executable), "-B", str(ROOT / "scripts/eventguard.py"), "advisories", "_serve",
                "--host-root", str(Path(root).absolute()), "--run-id", run_id, "--job-name", job]
        child = processes.spawn_persistent(argv, job_name=job, allow_parent_job=_bounded_test,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(ROOT))
        _write(root, "owner.json", {"run_id": run_id, "pid": child.pid, "created_at": child.created_at,
                                    "job_name": job, "session_id": processes.process_session(child.pid)})
        deadline = time.monotonic() + ready_timeout
        while time.monotonic() < deadline:
            ready = _read(root, "ready.json")
            if ready and ready.get("run_id") == run_id and ready.get("pid") == child.pid and ready.get("created_at") == child.created_at:
                handoff = processes.detach_owned(child, ready["job_keeper"])
                return {"state": "started", "model_calls": 0, "run_id": run_id, "handoff": handoff}
            if child.poll() is not None:
                break
            time.sleep(.05)
        control["enabled"] = False
        _write(root, "control.json", control)
        receipt = processes.finish(child, "launch_failure", grace=5, request_stop=False)
        _write(root, "stop-receipt.json", receipt)
        return {"state": "startup_failed", "reason": "advisory_ready_not_verified", "process": receipt, "model_calls": 0}
    except BaseException:
        # Metadata failure must never skip cleanup of the child whose Job
        # handle this launcher still owns. Detached hosts are never adopted.
        try:
            control = _read(root, "control.json")
            if control:
                _write(root, "control.json", dict(control, enabled=False))
        except (OSError,ValueError,RuntimeError):
            pass
        finally:
            if child is not None and not child.detached:
                receipt = processes.finish(child, "launch_failure", grace=5, request_stop=False)
                try:
                    _write(root, "stop-receipt.json", receipt)
                except (OSError,ValueError,RuntimeError):
                    pass
        raise
    finally:
        lease.release()


def stop(root, *, grace_seconds=15):
    if type(grace_seconds) not in (int, float) or not math.isfinite(grace_seconds) or not 1 <= grace_seconds <= 30:
        raise ValueError("advisory_stop_bounds_invalid")
    _path(root,"start.lock").parent.mkdir(parents=True,exist_ok=True)
    lease=FileLease(_path(root,"start.lock"))
    deadline=time.monotonic()+16
    while not lease.acquire():
        if time.monotonic()>=deadline:
            return {"state":"busy","reason":"advisory_start_stop_busy","model_calls":0}
        time.sleep(.05)
    try:
        return _stop_locked(root,grace_seconds)
    finally:
        lease.release()


def _stop_locked(root,grace_seconds):
    desired = _read(root, "control.json")
    if desired is None:
        return {"state": "stopped", "reason": "not_started", "model_calls": 0}
    _write(root, "control.json", dict(desired, enabled=False))
    owner = _read(root, "owner.json")
    if owner is None:
        return {"state": "stopped", "reason": "no_owner_recorded", "model_calls": 0}
    try:
        receipt = processes.stop_persistent(owner["job_name"], pid=owner["pid"], created_at=owner["created_at"],
            session_id=owner["session_id"], reason="cancelled", grace=grace_seconds)
    except OSError as error:
        observed = processes.identity(owner["pid"])
        exited = observed.get("state") in {"missing", "exited"} or observed.get("created_at") and observed["created_at"] != owner["created_at"]
        saved = _read(root, "exit.json")
        verified = bool(getattr(error,"winerror",None) == 2 and exited and saved
                        and saved.get("run_id") == owner["run_id"] and saved.get("created_at") == owner["created_at"])
        receipt = {"child_exited": bool(exited) if exited else None, "remaining_owned_processes": 0 if verified else None,
                   "forcibly_terminated": False, "reason": "natural_exit" if verified else "job_exit_unconfirmed"}
    _write(root, "stop-receipt.json", receipt)
    confirmed = receipt.get("child_exited") is True and receipt.get("remaining_owned_processes") == 0
    return {"state": "stopped" if confirmed else "shutdown_unconfirmed", "process": receipt, "model_calls": 0}


def serve(root, run_id, job_name):
    if not _TOKEN.fullmatch(run_id):
        raise ValueError("advisory_run_identity_invalid")
    desired = _read(root, "control.json")
    if not desired or not desired.get("enabled") or desired.get("run_id") != run_id or desired.get("job_name") != job_name:
        return {"state": "disabled", "model_calls": 0}
    keeper = processes.adopt_current_job(job_name)
    _KEEPERS.append(keeper)
    held = keeper.receipt()
    lease = FileLease(_path(root, "host.lock"))
    if not lease.acquire():
        return {"state": "busy", "model_calls": 0}
    state = {"run_id": run_id, "state": "waiting", "heartbeat_at": stamp(), "last_progress": "ready",
             "reason": None, "model_calls": 0, "pid": held["pid"], "created_at": held["created_at"]}
    _write(root, "run.json", state)
    _write(root, "ready.json", {"run_id": run_id, "pid": held["pid"], "created_at": held["created_at"], "job_keeper": held})
    stop_observed=[False]
    def stopped():
        control = _read(root, "control.json")
        if control is None:
            raise ValueError("advisory_control_missing")
        requested=control.get("enabled") is False or control.get("run_id") != run_id
        if requested:
            stop_observed[0]=True
        return requested
    def publish(phase):
        state.update(last_progress=phase,heartbeat_at=stamp())
        _write(root,"run.json",state)
    try:
        while not stopped():
            try:
                result = cycle(root, desired["config"],cancelled=stopped,progress=publish)
                state.update(state=result["state"], last_progress=result["last_progress"],
                             reason="tracking_evidence_incomplete" if result["errors"] else None,source_errors=result["errors"])
            except InterruptedError:
                break
            except Exception as error:
                # Retry durable cache/outbox after backpressure. Never erase a
                # source failure or pending change to obtain a clean status.
                safe = str(error) if type(error).__name__ in {"IntelligenceError","IntelligenceCapacityError","SourceError","StoreError","CapacityError"} and re.fullmatch(r"[A-Za-z0-9_]{1,100}",str(error)) else "advisory_cycle_failed"
                state.update(state="blocked", reason=safe,
                             last_progress="cycle_failed")
            # One CPU-only wait. No model or network calls while waiting.
            for _ in range(60):
                if stopped():
                    break
                state["heartbeat_at"] = stamp()
                _write(root, "run.json", state)
                time.sleep(.5)
    finally:
        state.update(state="stopped" if stop_observed[0] else "failed", heartbeat_at=stamp(),
                     last_progress="cooperative_stop" if stop_observed[0] else "unexpected_host_exit",
                     reason=state.get("reason") if stop_observed[0] else "advisory_control_or_host_failure")
        try:
            _write(root, "run.json", state)
            _write(root, "exit.json", {"run_id": run_id, "pid": held["pid"], "created_at": held["created_at"],
                                       "reason": "natural_exit_requested" if stop_observed[0] else "unexpected_host_failure",
                                       "forcibly_terminated": False, "at": stamp()})
        finally:
            lease.release()
    return state
