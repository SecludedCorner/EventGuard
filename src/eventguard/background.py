"""Durable local monitor supervisor. No dispatcher, model, service or scheduler.

Only an explicit start enables the controller. A public foreground serve (for
an independently approved scheduler) obeys that persisted intent. Every child
is created in a private Job; no breakaway or PID-based termination exists here.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import math
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

from .acceptance_control import FileLease, read_json, write_json
from .monitor import Monitor
from .runtime import Runtime
from . import processes

ROOT = Path(__file__).resolve().parents[2]
CONTROL_KIND = "eventguard-background-control-v1"
OWNER_KIND = "eventguard-background-owner-v1"
LAUNCH_KIND = "eventguard-background-launch-v1"
RUN_KIND = "eventguard-background-run-v1"
READY_KIND = "eventguard-background-ready-v1"
TOKEN = re.compile(r"[a-f0-9]{32}\Z")
JOB = re.compile(r"(?:Global|Local)\\EventGuard-[a-f0-9]{32}\Z")
RESTART_DELAYS = (5, 15, 30, 60, 120, 300)
HEARTBEAT_SECONDS = 5
HEARTBEAT_MAX_AGE = 30
# A keeper has no destructor. Keep its real Job handle open until OS process
# exit; closing the final KILL_ON_JOB_CLOSE handle from its member kills itself.
_KEEPERS = []


class BackgroundError(RuntimeError):
    """Only fixed operational codes; raw exceptions never become status text."""


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _path(runtime, name):
    return runtime.path("data/background/" + name)


def _read(runtime, name):
    path = _path(runtime, name)
    return read_json(path, limit=65536) if path.is_file() else None


def _write(runtime, name, value):
    _path(runtime, name).parent.mkdir(parents=True, exist_ok=True)
    write_json(_path(runtime, name), value)


def _token(value):
    return type(value) is str and TOKEN.fullmatch(value) is not None


def _date(value):
    if type(value) is not str or len(value) > 80 or any(ord(c) < 32 for c in value):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None and result.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _session(pid=None):
    try:
        return processes.process_session(pid)
    except (OSError, ValueError, RuntimeError):
        return None


def _control(runtime):
    value = _read(runtime, "control.json")
    if value is None:
        return None
    if (value.get("kind") != CONTROL_KIND or type(value.get("enabled")) is not bool
            or not _token(value.get("generation")) or value.get("namespace") not in {"live", "test"}
            or _date(value.get("updated_at")) is None):
        raise BackgroundError("background_control_unverifiable")
    fixture = value.get("fixture")
    cycles = value.get("max_cycles")
    if value["namespace"] == "test":
        if fixture is None:
            raise BackgroundError("background_control_scope_invalid")
        _fixture(runtime, fixture, cycles)
    elif fixture is not None or cycles is not None:
        raise BackgroundError("background_control_scope_invalid")
    return value


def _fixture(runtime, fixture, cycles):
    if fixture is None:
        if cycles is not None:
            raise BackgroundError("bounded_background_requires_fixture")
        return
    if type(fixture) is not str or not fixture or len(fixture) > 200:
        raise BackgroundError("background_fixture_invalid")
    path = runtime.path(fixture)
    if not path.is_relative_to(runtime.path("tests/fixtures")):
        raise BackgroundError("background_fixture_invalid")
    if type(cycles) is not int or not 1 <= cycles <= 100000:
        raise BackgroundError("background_fixture_requires_bounded_cycles")


@contextmanager
def _mutation(runtime, wait_seconds=0):
    _path(runtime, "control.lock").parent.mkdir(parents=True, exist_ok=True)
    lease = FileLease(_path(runtime, "control.lock"))
    until = time.monotonic() + wait_seconds
    while not lease.acquire():
        if time.monotonic() >= until:
            raise BackgroundError("background_control_busy")
        time.sleep(.05)
    try:
        yield
    finally:
        lease.release()


def _owner_valid(value):
    return (isinstance(value, dict) and value.get("kind") in {OWNER_KIND, LAUNCH_KIND}
            and _token(value.get("run_id")) and _token(value.get("generation"))
            and type(value.get("pid")) is int and 0 < value["pid"] <= 2**32 - 1
            and _date(value.get("created_at")) is not None
            and type(value.get("job_name")) is str and JOB.fullmatch(value["job_name"])
            and value.get("namespace") in {"live", "test"}
            and (value.get("session_id") is None or type(value["session_id"]) is int and value["session_id"] >= 0))


def _selected_owner(owner, launch):
    if not launch or launch.get("state") not in {"launch_intent", "started"}:
        return owner
    if owner is None:
        return launch
    # launch.json is the serialized current launch authority. Both launch
    # modes replace it before owner.json; wall-clock order is not authority.
    if owner.get("run_id") != launch.get("run_id"):
        return launch
    return owner


def _job_state(owner):
    if owner["job_name"].startswith("Local\\") and (owner.get("session_id") is None or _session() != owner["session_id"]):
        return {"state": "unknown", "reason": "background_job_session_unverifiable", "remaining_owned_processes": None}
    try:
        active = processes.current_job_active(owner["job_name"])
        if type(active) is not int or active < 0:
            raise BackgroundError("background_job_count_unverifiable")
        return {"state": "exited_verified" if active == 0 else "active",
                "reason": "owned_job_empty" if active == 0 else "owned_job_has_members",
                "remaining_owned_processes": active}
    except OSError as error:
        if getattr(error, "winerror", None) == 2:
            return {"state": "exited_verified", "reason": "owned_job_missing", "remaining_owned_processes": 0}
        return {"state": "unknown", "reason": "background_job_query_unavailable", "remaining_owned_processes": None}
    except (ValueError, RuntimeError):
        return {"state": "unknown", "reason": "background_job_query_unavailable", "remaining_owned_processes": None}


def _identity_view(value):
    """Retain only typed identity evidence, never an exception or command line."""
    if not isinstance(value, dict):
        return {"state": "unknown", "pid": None, "created_at": None}
    state = value.get("state")
    return {"state": state if state in {"alive", "missing", "exited", "denied", "unknown"} else "unknown",
            "pid": value.get("pid") if type(value.get("pid")) is int and 0 < value["pid"] <= 2**32 - 1 else None,
            "created_at": value.get("created_at") if _date(value.get("created_at")) is not None else None}


def _disable_generation(runtime, generation, reason):
    """A cancelled launcher/host must not disable a newer explicit start."""
    with _mutation(runtime, wait_seconds=5):
        desired = _control(runtime)
        matches = desired is not None and desired["generation"] == generation
        if matches:
            desired.update(enabled=False, generation=uuid.uuid4().hex, updated_at=_stamp(), reason=reason)
            _write(runtime, "control.json", desired)
        return {"desired_enabled": desired["enabled"] if desired is not None else None,
                "disabled_persisted": desired is not None and not desired["enabled"],
                "control_generation_matches": matches}


def _interrupt_disable(runtime, generation):
    try:
        return _disable_generation(runtime, generation, "explicit_keyboard_stop")
    except (OSError, ValueError, TypeError, RuntimeError):
        return {"desired_enabled": None, "disabled_persisted": False,
                "control_generation_matches": None, "disable_error": "background_disable_unconfirmed"}


def _wait_retry(cancelled, seconds):
    return cancelled.wait(seconds)


def status(root):
    """Read one recorded host identity and its private Job, never all processes."""
    runtime = Runtime(root)
    result = {"state": "not_started", "namespace": "live", "desired_enabled": False,
              "desired_state": "disabled", "host_liveness": "not_recorded", "model_calls": 0,
              "agent_required": False, "scheduler_installed": None, "reboot_recovery_verified": False,
              "monitoring": None, "monitor_liveness": "use_shared_operator_status_not_host_heartbeat"}
    try:
        control = _control(runtime)
        if control is not None:
            result.update(namespace=control["namespace"], desired_enabled=control["enabled"],
                          desired_state="enabled" if control["enabled"] else "disabled",
                          control_generation=control["generation"])
        owner = _read(runtime, "owner.json")
        launch = _read(runtime, "launch.json")
        saved = _read(runtime, "run.json")
        owner = _selected_owner(owner, launch)
        if owner is None:
            return dict(result, state="enabled_not_running" if result["desired_enabled"] else "disabled",
                        reason=(saved or {}).get("reason", "no_recorded_host"))
        if owner.get("lifetime_owner") == "application":
            application_owner = owner.get("application_owner")
            if (not isinstance(application_owner, dict) or type(application_owner.get("pid")) is not int
                    or not 0 < application_owner["pid"] <= 2**32 - 1
                    or _date(application_owner.get("created_at")) is None):
                raise BackgroundError("application_owner_identity_unverifiable")
            result.update(lifetime_owner="application", lifetime_limited=True,
                          application_owner={key: application_owner[key] for key in ("pid", "created_at")})
        if owner.get("state") == "launch_intent":
            if not _token(owner.get("run_id")) or type(owner.get("job_name")) is not str or not JOB.fullmatch(owner["job_name"]):
                raise BackgroundError("background_launch_unverifiable")
            job = _job_state(owner)
            owner_view = {key: owner.get(key) for key in ("run_id", "namespace", "job_name", "session_id")}
            if result.get("lifetime_owner") == "application":
                owner_view.update(lifetime_owner="application", application_owner=result["application_owner"])
            return dict(result, state=("enabled_not_running" if result["desired_enabled"] else "stopped") if job["state"] == "exited_verified" else "unknown",
                        host_liveness=job["state"], job=job, reason=job["reason"], run_id=owner["run_id"],
                         owner=owner_view)
        if not _owner_valid(owner):
            raise BackgroundError("background_owner_unverifiable")
        result.update(run_id=owner["run_id"], owner={key: owner.get(key) for key in
            ("run_id", "pid", "created_at", "session_id", "namespace", "job_name")})
        if owner.get("lifetime_owner") == "application":
            result["owner"].update(lifetime_owner="application", application_owner=result["application_owner"])
        observed = processes.identity(owner["pid"])
        result["owner_observation"] = _identity_view(observed)
        matches = isinstance(observed, dict) and observed.get("state") == "alive" and observed.get("created_at") == owner["created_at"]
        if matches:
            now = datetime.now(timezone.utc)
            heartbeat = _date(saved.get("heartbeat_at")) if isinstance(saved, dict) and saved.get("run_id") == owner["run_id"] else None
            age = (now - heartbeat).total_seconds() if heartbeat is not None else None
            same_session = owner.get("session_id") is not None and _session(owner["pid"]) == owner["session_id"]
            fresh = age is not None and 0 <= age <= HEARTBEAT_MAX_AGE
            result.update(host_liveness="alive_verified" if fresh and same_session else "alive_unverified",
                          heartbeat_age_seconds=age if age is not None and age >= 0 else None,
                          identity_matches=True, session_matches=same_session,
                          controller_session_matches=owner.get("session_id") == _session())
            if isinstance(saved, dict) and saved.get("run_id") == owner["run_id"]:
                result["last_report"] = {key: saved.get(key) for key in
                    ("state", "reason", "heartbeat_at", "restart_count", "backoff_seconds", "next_retry_at", "monitor_state", "coverage_degraded", "queue_backpressure", "lifetime_owner", "parent_job_present")}
                if owner.get("lifetime_owner") == "application":
                    result["last_report"].update(lifetime_owner="application", lifetime_limited=True)
            phase = (saved or {}).get("state")
            state = "running" if result["desired_enabled"] and fresh and same_session else "stopping" if not result["desired_enabled"] else "unknown"
            if phase in {"backoff", "blocked", "stopping", "shutdown_unconfirmed"} and state == "running":
                state = phase
            elif phase == "stopped" and state == "running":
                state = "host_exit_pending"
            return dict(result, state=state, reason=(saved or {}).get("reason") or ("host_alive_recent_heartbeat" if state == "running" else "host_heartbeat_or_session_unverified"))
        if isinstance(observed, dict):
            job = _job_state(owner)
            result.update(host_liveness=job["state"], identity_matches=False, job=job)
            return dict(result, state=("enabled_not_running" if result["desired_enabled"] else "stopped") if job["state"] == "exited_verified" else "shutdown_unconfirmed",
                        reason=job["reason"])
        return dict(result, state="unknown", host_liveness="unknown", reason="background_owner_identity_unverifiable")
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError) as error:
        code = error.args[0] if type(error) is BackgroundError and error.args else "background_state_unverifiable"
        return dict(result, state="blocked", host_liveness="unknown", reason=code, raw_error_omitted=True)


def _safe_start_previous(current):
    return current["host_liveness"] in {"not_recorded", "exited_verified"} and current["state"] not in {"unknown", "blocked", "shutdown_unconfirmed"}


def _host_argv(runtime, run_id, job_name, fixture, max_cycles):
    argv = [sys.executable, "-B", str(ROOT / "scripts/eventguard.py"), "background", "_serve",
            "--host-root", str(runtime.root), "--run-id", run_id, "--job-name", job_name]
    if fixture is not None:
        argv += ["--fixture", fixture, "--max-cycles", str(max_cycles)]
    return argv


def start(root, *, resume=False, ready_timeout=20, fixture=None, max_cycles=None,
          lifetime_owner="independent", child_owner=None):
    """Explicit enable + one bounded private-Job handoff; no monitor time cap."""
    runtime, child, generation, handoff = Runtime(root), None, None, None
    if lifetime_owner not in {"independent", "application"} or (
            lifetime_owner == "application" and not callable(child_owner)) or (
            lifetime_owner == "independent" and child_owner is not None):
        raise ValueError("invalid_background_lifetime_owner")
    if type(resume) is not bool or type(ready_timeout) not in (int, float) or not math.isfinite(ready_timeout) or not 1 <= ready_timeout <= 60:
        raise ValueError("invalid_background_start_bounds")
    _fixture(runtime, fixture, max_cycles)
    application_owner = None
    if lifetime_owner == "application":
        application_owner = processes.identity()
        if (application_owner.get("state") != "alive" or type(application_owner.get("pid")) is not int
                or _date(application_owner.get("created_at")) is None):
            return {"state": "blocked", "reason": "application_owner_identity_unverifiable", "model_calls": 0}
    run_id, job_name = uuid.uuid4().hex, "Global\\EventGuard-" + uuid.uuid4().hex
    try:
        with _mutation(runtime):
            control = _control(runtime)
            if resume and (control is None or control["enabled"] is not True):
                return {"state": "disabled", "reason": "manual_start_required", "desired_enabled": False, "model_calls": 0}
            current = status(root)
            if current["host_liveness"] in {"alive_verified", "alive_unverified"}:
                return dict(current, reason="background_already_running" if current["desired_enabled"] else "previous_host_still_stopping")
            if not _safe_start_previous(current):
                return dict(current, state="blocked", reason="previous_background_exit_unconfirmed")
            if resume:
                fixture, max_cycles = control.get("fixture"), control.get("max_cycles")
            control = {"kind": CONTROL_KIND, "enabled": True, "generation": uuid.uuid4().hex,
                       "namespace": "test" if fixture else "live", "fixture": fixture, "max_cycles": max_cycles,
                       "updated_at": _stamp(), "reason": "explicit_start" if not resume else "resume_enabled_only"}
            generation = control["generation"]
            _write(runtime, "control.json", control)
            launch = {"kind": LAUNCH_KIND, "run_id": run_id, "generation": control["generation"],
                      "namespace": control["namespace"], "job_name": job_name, "state": "launch_intent",
                      "session_id": _session(), "started_at": _stamp()}
            if application_owner is not None:
                launch.update(lifetime_owner="application", application_owner={key: application_owner[key] for key in ("pid", "created_at")})
            _write(runtime, "launch.json", launch)
            try:
                launch_host = processes.spawn_application_host if lifetime_owner == "application" else processes.spawn_persistent
                child = launch_host(_host_argv(runtime, run_id, job_name, fixture, max_cycles),
                    job_name=job_name, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    cwd=str(ROOT))
            except OSError as error:
                known = error.args == ("independent_background_unverifiable",)
                launch.update(state="not_started" if known else "launch_intent",
                              reason="independent_background_unverifiable" if known else "background_launch_unconfirmed")
                _write(runtime, "launch.json", launch)
                _write(runtime, "run.json", {"kind": RUN_KIND, "run_id": run_id, "state": "blocked",
                       "reason": launch["reason"], "heartbeat_at": _stamp()})
                return {"state": "blocked", "reason": launch["reason"], "namespace": control["namespace"],
                        "desired_enabled": True, "model_calls": 0, "child_exited": True if known else None,
                        "external_job_escape_attempted": False}
            if child_owner is not None:
                # This trusted launch identity is captured before invoking the
                # application owner. Never rediscover ownership from mutable
                # status files, or adopt a different client's existing host.
                child._eventguard_background_scope = {"kind": "eventguard-background-owned-launch-v1",
                    "run_id": run_id, "control_generation": control["generation"],
                    "job_name": job_name, "namespace": control["namespace"],
                    "pid": child.pid, "created_at": child.created_at}
                child_owner(child)
            launch.update(state="started", pid=child.pid, created_at=child.created_at)
            _write(runtime, "launch.json", launch)
        deadline = time.monotonic() + ready_timeout
        while time.monotonic() < deadline:
            desired = _control(runtime)
            if desired is None or not desired["enabled"] or desired["generation"] != control["generation"]:
                break
            ready = _read(runtime, "ready.json")
            if (ready and ready.get("kind") == READY_KIND and ready.get("run_id") == run_id
                    and ready.get("generation") == control["generation"] and ready.get("job_name") == job_name
                    and ready.get("pid") == child.pid and ready.get("created_at") == child.created_at):
                handoff = (processes.retain_application_host(child, ready["job_keeper"]) if lifetime_owner == "application"
                           else processes.detach_owned(child, ready["job_keeper"]))
                persisted = True
                try:
                    _write(runtime, "handoff.json", {"run_id": run_id, "generation": control["generation"],
                        "lifetime_owner": lifetime_owner,
                        "transferred_at": _stamp(), "process": handoff})
                except (OSError, ValueError, RuntimeError):
                    persisted = False
                return {**status(root), "handoff": handoff, "state": "started",
                        "lifetime_owner": lifetime_owner, "lifetime_limited": handoff.get("lifetime_limited"),
                        "reason": "private_job_keeper_verified" if persisted else "host_transferred_handoff_record_unavailable",
                        "handoff_persisted": persisted, "evidence_write_failed": not persisted,
                        "model_calls": 0, "external_parent_job_may_limit_lifetime": handoff.get("lifetime_limited") is True}
            if child.poll() is not None:
                break
            time.sleep(.1)
        # No transfer occurred: this launcher still owns the new child's Job.
        with _mutation(runtime, wait_seconds=5):
            desired = _control(runtime)
            if desired and desired["generation"] == control["generation"]:
                desired.update(enabled=False, generation=uuid.uuid4().hex, updated_at=_stamp(), reason="startup_not_ready")
                _write(runtime, "control.json", desired)
        receipt = processes.finish(child, "launch_failure", grace=5, request_stop=False)
        _write(runtime, "stop-receipt.json", {"run_id": run_id, "at": _stamp(), "process": receipt})
        return {**status(root), "state": "startup_failed" if receipt.get("child_exited") is True else "shutdown_unconfirmed",
                "reason": "background_ready_not_verified", "process": receipt, "model_calls": 0}
    except KeyboardInterrupt:
        disabled = _interrupt_disable(runtime, generation) if generation is not None else {
            "desired_enabled": None, "disabled_persisted": False, "control_generation_matches": None}
        transferred = child is not None and getattr(child, "detached", False)
        result = {**disabled, "state": "shutdown_unconfirmed", "reason": "background_start_interrupted",
                  "run_id": run_id, "model_calls": 0, "child_exited": None,
                  "ownership_transferred": transferred, "raw_error_omitted": True}
        if transferred:
            # detach_owned is irreversible. Never call finish on the launcher
            # wrapper after ownership moved to the host's real keeper.
            result["handoff"] = handoff or {"ownership_transferred": True, "detached": True, "child_exited": None}
        if child is not None:
            try:
                receipt = (processes.stop_persistent(job_name, pid=child.pid, created_at=child.created_at,
                           session_id=_session(child.pid), reason="cancelled", grace=5) if transferred else
                           processes.finish(child, "cancelled", grace=5, request_stop=False))
                _write(runtime, "stop-receipt.json", {"run_id": run_id, "at": _stamp(), "process": receipt})
                confirmed = (receipt.get("child_exited") is True and type(receipt.get("remaining_owned_processes")) is int
                             and receipt["remaining_owned_processes"] == 0)
                result.update(process=receipt, child_exited=receipt.get("child_exited"),
                              state="stopped" if confirmed and disabled["disabled_persisted"] else "shutdown_unconfirmed")
            except (OSError, ValueError, TypeError, RuntimeError):
                result["cleanup_error"] = "background_interrupted_cleanup_unconfirmed"
        return result
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        if child is not None and not getattr(child, "detached", False):
            receipt = processes.finish(child, "launch_failure", grace=5, request_stop=False)
            _write(runtime, "stop-receipt.json", {"run_id": run_id, "at": _stamp(), "process": receipt})
        return {"state": "blocked", "reason": error.args[0] if type(error) is BackgroundError else "background_start_failed",
                "model_calls": 0, "raw_error_omitted": True}


def _verified_stop(runtime, current):
    """Persist an observed empty/missing Job, without inventing an exit code."""
    if current["host_liveness"] == "not_recorded":
        return dict(current, state="stopped", desired_enabled=False, reason="background_exit_verified")
    owner, job = current.get("owner"), current.get("job")
    if not isinstance(owner, dict) or not isinstance(job, dict) or job.get("state") != "exited_verified" or job.get("remaining_owned_processes") != 0:
        raise BackgroundError("background_exit_evidence_unverifiable")
    receipt = {"managed": True, "job_name": owner["job_name"],
               "pid": owner.get("pid"), "created_at": owner.get("created_at"), "session_id": owner.get("session_id"),
               "child_exited": True, "remaining_owned_processes": 0, "forcibly_terminated": False,
               "reason": job["reason"], "job": dict(job),
               "recorded_owner": dict(owner), "owner_observation": current.get("owner_observation"),
               "owner_identity_recorded": type(owner.get("pid")) is int and _date(owner.get("created_at")) is not None}
    previous = _read(runtime, "stop-receipt.json")
    document = {"run_id": current.get("run_id"), "at": _stamp(), "process": receipt}
    if isinstance(previous, dict) and previous.get("run_id") == current.get("run_id") and isinstance(previous.get("process"), dict):
        if previous["process"].get("forcibly_terminated") is True:
            # A later empty-Job check cannot erase a previously forced stop.
            document = dict(previous, verified_at=_stamp(), verification=receipt)
            receipt = previous["process"]
        else:
            document["prior_process"] = previous["process"]
    _write(runtime, "stop-receipt.json", document)
    return dict(current, state="stopped", desired_enabled=False, process=receipt,
                reason="owned_job_forcibly_terminated" if receipt.get("forcibly_terminated") else "background_exit_verified")


def stop(root, *, grace_seconds=10, expected_namespace=None, expected_run_id=None,
         expected_control_generation=None, expected_job_name=None):
    """Persist disabled first, cooperate, then terminate only a proven own Job."""
    if type(grace_seconds) not in (int, float) or not math.isfinite(grace_seconds) or not 0 <= grace_seconds <= 30:
        raise ValueError("invalid_background_stop_bounds")
    if expected_namespace is not None and (type(expected_namespace) is not str or expected_namespace not in {"live", "test"}):
        raise ValueError("invalid_background_stop_namespace")
    expected = (expected_run_id, expected_control_generation, expected_job_name)
    guarded_owner = any(value is not None for value in expected)
    if guarded_owner and (expected_namespace is None or not _token(expected_run_id)
            or not _token(expected_control_generation) or type(expected_job_name) is not str
            or JOB.fullmatch(expected_job_name) is None):
        raise ValueError("invalid_background_stop_owner")
    runtime = Runtime(root)
    disabled_written, scoped_owner, scoped_run = False, None, None
    try:
        with _mutation(runtime):
            try:
                control = _control(runtime)
            except (OSError, ValueError, TypeError, RuntimeError):
                if expected_namespace is not None:
                    return {"state": "blocked", "reason": "background_scope_unverifiable",
                            "desired_enabled": None, "model_calls": 0, "process_terminated": False}
                # Explicit disable is safe even when old control metadata is
                # corrupt. It never clears event data, a Job or a budget.
                invalid = _path(runtime, "control.json")
                if invalid.is_file():
                    invalid.replace(_path(runtime, "control-invalid.json"))
                control = None
            current = status(root)
            if guarded_owner:
                recorded_owner, recorded_launch = _read(runtime, "owner.json"), _read(runtime, "launch.json")
                if any(value is not None and not isinstance(value, dict) for value in (recorded_owner, recorded_launch)):
                    return dict(current, state="blocked", reason="background_scope_unverifiable",
                                process_terminated=False, disabled_persisted=False)
                recorded = _selected_owner(recorded_owner, recorded_launch)
                # Check the desired generation as well as the launch identity:
                # Start writes enabled/generation before replacing launch.json.
                # An old server's EOF must not disable that newer intent.
                if (control is None or control["generation"] != expected_control_generation
                        or control["namespace"] != expected_namespace
                        or not isinstance(recorded, dict)
                        or recorded.get("run_id") != expected_run_id
                        or recorded.get("generation") != expected_control_generation
                        or recorded.get("job_name") != expected_job_name
                        or recorded.get("namespace") != expected_namespace):
                    return dict(current, state="not_applicable", reason="background_owner_changed",
                                process_terminated=False, disabled_persisted=False)
            if expected_namespace is not None:
                if control is None:
                    return {"state": "blocked", "reason": "background_scope_unverifiable",
                            "desired_enabled": None, "model_calls": 0, "process_terminated": False}
                if control["namespace"] != expected_namespace:
                    return dict(current, state="not_applicable", reason="background_outside_launcher_namespace",
                                process_terminated=False)
                recorded_owner, recorded_launch = _read(runtime, "owner.json"), _read(runtime, "launch.json")
                if any(value is not None and not isinstance(value, dict) for value in (recorded_owner, recorded_launch)):
                    return dict(current, state="blocked", reason="background_scope_unverifiable",
                                process_terminated=False)
                scoped_owner = _selected_owner(recorded_owner, recorded_launch)
                if scoped_owner is not None:
                    if not isinstance(scoped_owner, dict) or scoped_owner.get("namespace") not in {"live", "test"}:
                        return dict(current, state="blocked", reason="background_scope_unverifiable",
                                    process_terminated=False)
                    if scoped_owner["namespace"] != expected_namespace:
                        return dict(current, state="not_applicable", reason="background_outside_launcher_namespace",
                                    process_terminated=False)
                scoped_run = current.get("run_id")
            if control is None:
                control = {"kind": CONTROL_KIND, "namespace": "live", "fixture": None, "max_cycles": None}
            control.update(enabled=False, generation=uuid.uuid4().hex, updated_at=_stamp(), reason="explicit_stop")
            _write(runtime, "control.json", control)
            disabled_written = True
            _write(runtime, "stop.json", {"run_id": current.get("run_id"), "generation": control["generation"], "requested_at": _stamp()})
        until = time.monotonic() + grace_seconds
        while time.monotonic() < until:
            current = status(root)
            if expected_namespace is not None and (current.get("namespace") != expected_namespace or current.get("run_id") != scoped_run or current.get("desired_enabled") is not False):
                return dict(current, state="busy", reason="background_owner_changed", process_terminated=False,
                            disabled_persisted=True)
            if current["host_liveness"] in {"not_recorded", "exited_verified"}:
                return _verified_stop(runtime, current)
            time.sleep(.2)
        current = status(root)
        if expected_namespace is not None and (current.get("namespace") != expected_namespace or current.get("run_id") != scoped_run or current.get("desired_enabled") is not False):
            return dict(current, state="busy", reason="background_owner_changed", process_terminated=False,
                        disabled_persisted=True)
        if current["host_liveness"] in {"not_recorded", "exited_verified"}:
            return _verified_stop(runtime, current)
        # A scoped client can stop only the Job selected under control.lock,
        # even if another client starts a replacement after the grace period.
        owner = scoped_owner if expected_namespace is not None else _selected_owner(_read(runtime, "owner.json"), _read(runtime, "launch.json"))
        if not _owner_valid(owner):
            return dict(current, state="shutdown_unconfirmed", desired_enabled=False, reason="background_owner_unverifiable")
        receipt = processes.stop_persistent(owner["job_name"], pid=owner["pid"], created_at=owner["created_at"],
            session_id=owner["session_id"], reason="cancelled", grace=0)
        _write(runtime, "stop-receipt.json", {"run_id": owner["run_id"], "at": _stamp(), "process": receipt})
        confirmed = (receipt.get("child_exited") is True and type(receipt.get("remaining_owned_processes")) is int
                     and receipt["remaining_owned_processes"] == 0)
        current = status(root)
        if expected_namespace is not None and (current.get("namespace") != expected_namespace or current.get("run_id") != scoped_run or current.get("desired_enabled") is not False):
            return dict(current, state="busy", reason="background_owner_changed", process=receipt,
                        disabled_persisted=True)
        return {**current, "state": "stopped" if confirmed else "shutdown_unconfirmed",
                "reason": "owned_job_forcibly_terminated" if receipt.get("forcibly_terminated") else "background_exit_verified" if confirmed else "background_exit_unconfirmed",
                "desired_enabled": False, "process": receipt, "model_calls": 0}
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        return {"state": "shutdown_unconfirmed" if disabled_written else "stop_not_persisted",
                "desired_enabled": False if disabled_written else None,
                "reason": error.args[0] if type(error) is BackgroundError else "background_stop_unconfirmed",
                "raw_error_omitted": True, "model_calls": 0}


def serve(root, *, run_id=None, job_name=None, fixture=None, max_cycles=None):
    """Foreground unlimited supervisor; respects persisted disabled on boot."""
    runtime = Runtime(root)
    if (run_id is None) != (job_name is None) or run_id is not None and (not _token(run_id) or type(job_name) is not str or not JOB.fullmatch(job_name)):
        raise ValueError("background_host_identity_invalid")
    hidden = run_id is not None
    control, lease, application_owner = None, None, None
    done, cancelled, control_fault, state_fault, active_lock = (
        threading.Event(), threading.Event(), threading.Event(), threading.Event(), threading.RLock())
    active, thread, run, cancel_reason = [None], None, None, ["durable_stop_observed"]
    state_write_failures = [0]
    unresolved_query = None
    try:
        control = _control(runtime)
        if control is None or not control["enabled"]:
            return {"state": "disabled", "reason": "manual_start_required", "desired_enabled": False, "model_calls": 0}
        fixture = control.get("fixture") if fixture is None else fixture
        max_cycles = control.get("max_cycles") if max_cycles is None else max_cycles
        _fixture(runtime, fixture, max_cycles)
        if ("test" if fixture else "live") != control["namespace"]:
            raise BackgroundError("background_host_scope_conflict")
        _path(runtime, "host.lock").parent.mkdir(parents=True, exist_ok=True)
        lease = FileLease(_path(runtime, "host.lock"))
        if not lease.acquire():
            return {"state": "busy", "reason": "background_host_already_owned", "model_calls": 0}
        with _mutation(runtime, wait_seconds=5):
            latest = _control(runtime)
            if latest is None or not latest["enabled"] or latest["generation"] != control["generation"]:
                return {"state": "disabled", "reason": "background_start_cancelled", "model_calls": 0}
            if hidden:
                launch = _read(runtime, "launch.json")
                if not launch or launch.get("run_id") != run_id or launch.get("job_name") != job_name or launch.get("generation") != control["generation"]:
                    raise BackgroundError("background_launch_identity_mismatch")
                if launch.get("lifetime_owner") == "application":
                    application_owner = launch.get("application_owner")
                    if (not isinstance(application_owner, dict) or type(application_owner.get("pid")) is not int
                            or _date(application_owner.get("created_at")) is None):
                        raise BackgroundError("application_owner_identity_unverifiable")
                keeper = processes.adopt_current_job(job_name)
            else:
                previous = status(root)
                if not _safe_start_previous(previous):
                    return dict(previous, state="blocked", reason="previous_background_exit_unconfirmed")
                run_id, job_name = uuid.uuid4().hex, "Global\\EventGuard-" + uuid.uuid4().hex
                keeper = processes.standalone_host_job(job_name)
            _KEEPERS.append(keeper)
            held = keeper.receipt()
            owner = {"kind": OWNER_KIND, "run_id": run_id, "generation": control["generation"],
                "namespace": control["namespace"], "pid": held["pid"], "created_at": held["created_at"],
                "session_id": held["session_id"], "job_name": job_name, "started_at": _stamp()}
            if application_owner is not None:
                owner.update(lifetime_owner="application", application_owner=application_owner)
            _write(runtime, "launch.json", dict(owner, kind=LAUNCH_KIND, state="started"))
            _write(runtime, "owner.json", owner)
            run = {"kind": RUN_KIND, "run_id": run_id, "namespace": control["namespace"],
                "state": "starting", "reason": "host_private_job_held", "heartbeat_at": _stamp(),
                "restart_count": 0, "backoff_seconds": 0, "next_retry_at": None, "monitor_state": None,
                "coverage_degraded": None, "queue_backpressure": False, "model_calls": 0,
                "parent_job_present": held.get("parent_job_present"),
                "lifetime_owner": "application" if application_owner is not None else held.get("lifetime_owner", "private_job_keeper")}
            if application_owner is not None:
                run["lifetime_limited"] = True
            _write(runtime, "run.json", run)
            _write(runtime, "ready.json", {"kind": READY_KIND, "run_id": run_id, "generation": control["generation"],
                "pid": held["pid"], "created_at": held["created_at"], "session_id": held["session_id"],
                "job_name": job_name, "job_keeper": held, "ready_at": _stamp()})

        def publish(**changes):
            with active_lock:
                run.update(changes, heartbeat_at=_stamp())
                try:
                    _write(runtime, "run.json", dict(run))
                except (OSError, ValueError, TypeError, RuntimeError):
                    # Metadata backpressure stops observation, not this owner.
                    # Keep the persisted enabled intent and wait for storage to
                    # recover, just as for an outbox persistence failure.
                    state_fault.set()
                    state_write_failures[0] += 1
                    if active[0] is not None:
                        active[0].cancel.set()
                    return False
                state_fault.clear()
                return True

        def wait_backoff(reason):
            delay_index = min(run["restart_count"], len(RESTART_DELAYS) - 1)
            delay = RESTART_DELAYS[delay_index]
            publish(state="backoff", reason=reason, restart_count=run["restart_count"] + 1,
                    backoff_seconds=delay, next_retry_at=datetime.fromtimestamp(time.time() + delay, timezone.utc).isoformat())
            # Ordinary interruptible waiting; never a model or new collection.
            _wait_retry(cancelled, delay)

        def watch_control():
            next_heartbeat = time.monotonic()
            while not done.wait(.5):
                if application_owner is not None:
                    observed = processes.identity(application_owner["pid"])
                    if observed.get("state") != "alive" or observed.get("created_at") != application_owner["created_at"]:
                        cancel_reason[0] = "application_owner_exit_or_unverifiable"
                        cancelled.set()
                        with active_lock:
                            if active[0] is not None:
                                active[0].cancel.set()
                        return
                try:
                    desired = _control(runtime)
                    if desired is None:
                        raise BackgroundError("background_control_missing")
                    stop_now = not desired["enabled"] or desired["generation"] != control["generation"]
                    control_fault.clear()
                except (OSError, ValueError, RuntimeError):
                    control_fault.set()
                    with active_lock:
                        if active[0] is not None:
                            active[0].cancel.set()
                    if time.monotonic() >= next_heartbeat:
                        publish(state="blocked", reason="background_control_unverifiable")
                        next_heartbeat = time.monotonic() + HEARTBEAT_SECONDS
                    continue
                if stop_now:
                    cancelled.set()
                    with active_lock:
                        if active[0] is not None:
                            active[0].cancel.set()
                    publish(state="stopping", reason="durable_disabled_or_control_unverifiable")
                    return
                if time.monotonic() >= next_heartbeat:
                    publish()
                    next_heartbeat = time.monotonic() + HEARTBEAT_SECONDS

        thread = threading.Thread(target=watch_control, name="eventguard-background-control", daemon=True)
        thread.start()
        while not cancelled.is_set():
            try:
                desired = _control(runtime)
                if desired is None:
                    raise BackgroundError("background_control_missing")
            except (OSError, ValueError, RuntimeError):
                publish(state="blocked", reason="background_control_unverifiable", backoff_seconds=RESTART_DELAYS[0])
                _wait_retry(cancelled, RESTART_DELAYS[0])
                continue
            if not desired["enabled"] or desired["generation"] != control["generation"]:
                cancelled.set()
                break
            if unresolved_query is not None:
                # A failed gate write must not make a previous query disappear.
                # Retain its actual Runner and first captured Job identity until
                # the normal durable gate proves that Job empty/missing, then
                # release only that Runner's owned child handles.
                recovered = False
                try:
                    runner = unresolved_query["runner"]
                    pending, latest = runner.pending, runner.last_process
                    process = unresolved_query["process"]
                    if process is None and isinstance(latest, dict) and latest.get("managed") is True:
                        process = unresolved_query["process"] = dict(latest)
                    if (isinstance(process, dict) and process.get("managed") is True
                            and isinstance(latest, dict) and latest.get("managed") is True
                            and latest.get("job_name") == process.get("job_name")):
                        gate = runtime.monitor_shutdown_gate(recover=True)
                        if gate.get("state") == "clear":
                            proof = gate.get("process") or {}
                            if (proof.get("job_name") != process.get("job_name")
                                    or gate.get("remaining_owned_processes") != 0):
                                runtime.block_monitor_shutdown({"namespace": control["namespace"],
                                    "pid": held["pid"], "process_created_at": held["created_at"],
                                    "query_shutdown": process})
                                gate = runtime.monitor_shutdown_gate(recover=True)
                            if (gate.get("state") == "clear" and gate.get("remaining_owned_processes") == 0
                                    and (gate.get("process") or {}).get("job_name") == process.get("job_name")):
                                receipt = runner.shutdown(grace=0)
                                recovered = (receipt.get("managed") is True and receipt.get("child_exited") is True
                                    and receipt.get("job_name") == process.get("job_name")
                                    and type(receipt.get("remaining_owned_processes")) is int
                                    and receipt["remaining_owned_processes"] == 0)
                except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
                    pass  # An unreadable Runner/Job/gate remains unknown.
                if not recovered:
                    publish(state="shutdown_unconfirmed", reason="monitor_query_exit_unconfirmed",
                            monitor_state="shutdown_unconfirmed")
                    wait_backoff("monitor_query_exit_unconfirmed")
                    continue
                unresolved_query = None
            began = time.monotonic()
            if not publish(state="running", reason="monitor_starting", backoff_seconds=0, next_retry_at=None):
                wait_backoff("background_state_persistence_failed")
                continue
            observed_write_failures = state_write_failures[0]

            def progress(health):
                monitor_state = health.get("state")
                monitor_state = monitor_state if type(monitor_state) is str and monitor_state in {"starting", "running", "stopping_pending_query", "shutdown_unconfirmed", "stopped", "blocked_monitor_gap", "blocked_previous_query"} else "unknown"
                publish(monitor_state=monitor_state, coverage_degraded=health.get("healthy") is False,
                        queue_backpressure=health.get("last_error") == "queue_capacity_or_storage_failure")

            monitor = None
            try:
                monitor = Monitor(root)
                with active_lock:
                    active[0] = monitor
                    if cancelled.is_set():
                        break
                    if state_fault.is_set():
                        # A heartbeat can fail after the successful start
                        # publication but before this active owner is assigned.
                        # Do not enter Monitor.run until storage is writable.
                        monitor.cancel.set()
                        raise BackgroundError("background_state_persistence_failed")
                health = monitor.run(fixture=fixture, max_cycles=max_cycles, on_progress=progress)
                monitor_state = health.get("state", health.get("status"))
                monitor_state = monitor_state if type(monitor_state) is str and monitor_state in {"starting", "running", "stopping_pending_query", "shutdown_unconfirmed", "stopped", "blocked_monitor_gap", "blocked_previous_query", "busy"} else "unknown"
                reason = "monitor_returned_" + monitor_state
                if health.get("stop_reason") == "persistence_backpressure":
                    reason = "persistence_backpressure"
                    publish(queue_backpressure=True)
                if health.get("stop_reason") == "keyboard_interrupt":
                    # Use the same outer interrupt path as Ctrl+C during a
                    # controller wait, so a failed disable never restarts it.
                    raise KeyboardInterrupt
                if health.get("state") == "shutdown_unconfirmed":
                    publish(state="shutdown_unconfirmed", reason="monitor_query_exit_unconfirmed", monitor_state="shutdown_unconfirmed")
                if (fixture is not None and not control_fault.is_set() and not state_fault.is_set()
                        and state_write_failures[0] == observed_write_failures
                        and health.get("state") == "stopped" and health.get("stop_reason") != "persistence_backpressure"):
                    publish(state="stopped", reason="bounded_fixture_completed", monitor_state=health.get("state"))
                    break
            except KeyboardInterrupt:
                with active_lock:
                    if active[0] is not None:
                        active[0].cancel.set()
                raise
            except Exception:
                reason = "monitor_exception_without_raw_error"
            finally:
                with active_lock:
                    runner = getattr(getattr(monitor, "collectors", None), "runner", None)
                    if runner is not None:
                        process = None
                        try:
                            pending, process = runner.pending, runner.last_process
                            unconfirmed = (pending or not isinstance(process, dict)
                                or process.get("managed") is True and (process.get("child_exited") is not True
                                    or type(process.get("remaining_owned_processes")) is not int
                                    or process["remaining_owned_processes"] != 0))
                        except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
                            unconfirmed = True
                        if unconfirmed:
                            unresolved_query = {"monitor": monitor, "runner": runner,
                                                "process": dict(process) if isinstance(process, dict) else None}
                    active[0] = None
            if cancelled.is_set():
                break
            if state_write_failures[0] != observed_write_failures or state_fault.is_set():
                reason = "background_state_persistence_failed"
            if time.monotonic() - began >= 300:
                run["restart_count"] = 0
            wait_backoff(reason)
        if cancelled.is_set():
            publish(state="shutdown_unconfirmed" if unresolved_query is not None else "stopped",
                    reason="monitor_query_exit_unconfirmed" if unresolved_query is not None else cancel_reason[0],
                    backoff_seconds=0, next_retry_at=None)
        desired = _control(runtime)
        result = dict(run, desired_enabled=desired["enabled"] if desired is not None else None, host_exit_pending=True,
                    evidence_write_failed=state_fault.is_set(),
                    note="Host function returned; only external PID/Job evidence proves process exit.")
        if state_fault.is_set():
            result.update(state="blocked", reason="background_state_persistence_failed")
        if unresolved_query is not None:
            result.update(state="shutdown_unconfirmed", reason="monitor_query_exit_unconfirmed")
        return result
    except KeyboardInterrupt:
        disabled = _interrupt_disable(runtime, control["generation"] if control is not None else None)
        cancelled.set()
        with active_lock:
            if active[0] is not None:
                active[0].cancel.set()
        result = dict(run or {}, **disabled,
                      state="shutdown_unconfirmed" if unresolved_query is not None else "stopped" if disabled["disabled_persisted"] else "stop_not_persisted",
                      reason="monitor_query_exit_unconfirmed" if unresolved_query is not None else "explicit_keyboard_stop",
                      model_calls=0, host_exit_pending=True,
                      note="Host function returned; only external PID/Job evidence proves process exit.")
        if run is not None:
            try:
                _write(runtime, "run.json", dict(run, state=result["state"], reason=result["reason"],
                       heartbeat_at=_stamp(), backoff_seconds=0, next_retry_at=None))
            except (OSError, ValueError, TypeError, RuntimeError):
                result.update(state="shutdown_unconfirmed" if unresolved_query is not None else "blocked",
                              reason="monitor_query_exit_unconfirmed" if unresolved_query is not None else "background_state_persistence_failed",
                              evidence_write_failed=True)
        # The keeper is intentionally held until natural OS exit. A host must
        # never finish/terminate its own KILL_ON_JOB_CLOSE Job from this path.
        return result
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        reason = error.args[0] if type(error) is BackgroundError else "background_host_failed"
        evidence_write_failed = False
        if run is not None:
            try:
                _write(runtime, "run.json", dict(run, state="blocked", reason=reason, heartbeat_at=_stamp()))
            except (OSError, ValueError, TypeError, RuntimeError):
                evidence_write_failed = True
        return {"state": "blocked", "reason": reason, "model_calls": 0, "raw_error_omitted": True,
                "evidence_write_failed": evidence_write_failed}
    finally:
        done.set()
        with active_lock:
            if active[0] is not None:
                active[0].cancel.set()
        if thread is not None:
            thread.join(2)
        if lease is not None:
            lease.release()
