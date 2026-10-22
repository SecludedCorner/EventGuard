"""Bounded foreground monitor + event-driven agent; no service installation."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import threading
import time
import uuid

from .acceptance_control import FileLease, read_json, write_json
from .local_wait import _guard
from .monitor import Monitor
from .runtime import Runtime

ROOT = Path(__file__).resolve().parents[2]
KIND = "eventguard-bounded-live-watch-v1"


def _native(codex):
    executable = shutil.which(codex)
    if not executable or Path(executable).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        raise ValueError("native_codex_required")
    if importlib.util.find_spec("mcp") is None:
        raise ValueError("installed_mcp_sdk_required")
    return executable


def _load(directory):
    directory = _guard(directory)
    value = read_json(directory / "watch.json")
    if value.get("kind") != KIND or not isinstance(value.get("watch_id"), str):
        raise ValueError("foreign_watch_directory")
    return value


def status(directory):
    from . import agent_dispatch
    directory = _guard(directory)
    value = _load(directory)
    agent = directory / "agent"
    if (agent / "status.json").exists():
        value = {**value, "agent": agent_dispatch.status(agent)}
    return value


def stop(directory):
    from . import agent_dispatch
    directory = _guard(directory)
    value = _load(directory)
    write_json(directory / "stop.request", {"watch_id": value["watch_id"]})
    result = {"state": "stop_requested", "process_signal_sent": False}
    if (directory / "agent/status.json").exists():
        result["agent"] = agent_dispatch.stop(directory / "agent")
    # The foreground owner notices this request and cancels its own Monitor.
    # Never stop another monitor by consulting an unrelated global PID/owner.
    return result


def run(directory, *, root=ROOT, codex="codex", max_seconds=3600, max_tasks=5,
        execute=False, allow_live=False):
    from . import agent_dispatch
    if type(max_seconds) is not int or not 1 <= max_seconds <= 3600:
        raise ValueError("invalid_max_seconds")
    if type(max_tasks) is not int or not 1 <= max_tasks <= 5:
        raise ValueError("invalid_max_tasks")
    if not execute:
        return {"state": "preflight_only", "model_calls": 0, "native_collection_started": False,
                "max_seconds": max_seconds, "max_tasks": max_tasks, "requires": "--execute --allow-live"}
    if not allow_live:
        raise ValueError("explicit_live_scope_required")
    codex = _native(codex)
    root = _guard(root)
    directory = _guard(directory)
    if not directory.is_relative_to(root / "reports"):
        raise ValueError("watch_reports_directory_required")
    directory.mkdir(parents=True, exist_ok=False)
    lease = FileLease(directory / "watch.lock")
    if not lease.acquire():
        raise ValueError("watch_already_owned")
    token = uuid.uuid4().hex
    state = {"kind": KIND, "watch_id": token, "state": "starting_monitor",
             "max_seconds": max_seconds, "max_tasks": max_tasks,
             "native_collection_started": False, "monitor_exited": False,
             "agent_exit_code": None, "process_signal_sent": False}
    write_json(directory / "watch.json", state)
    monitor = Monitor(root)
    ready = threading.Event()
    observation = {}
    failure = []
    deadline = time.monotonic() + max_seconds

    def cycle(health):
        observation.update({"instance_id": health["instance_id"],
                            "coverage": health.get("coverage", {}), "cycles": health.get("cycles", 0)})
        ready.set()

    def collect():
        try:
            result = monitor.run(max_seconds=max_seconds, on_cycle=cycle, deadline_monotonic=deadline)
            observation["final"] = result
        except (OSError, ValueError, RuntimeError):
            failure.append("monitor_failed")

    def requested():
        path = directory / "stop.request"
        return path.exists() and read_json(path).get("watch_id") == token

    worker = threading.Thread(target=collect)
    state.update(monitor_start_requested=True, native_collection_started=None)
    write_json(directory / "watch.json", state)
    worker.start()
    agent_done = threading.Event()

    def follow_stop():
        # Notify the owner; it applies EOF grace and only its private-job cleanup.
        while not agent_done.wait(.2):
            try:
                if requested():
                    monitor.cancel.set()
                    path = directory / "agent/status.json"
                    if path.exists():
                        agent_dispatch.stop(directory / "agent")
                    # Preflight may not have published status yet. Keep the
                    # shared cancellation set and wait for that owner to exit.
            except (OSError, ValueError, RuntimeError):
                monitor.cancel.set()
                return

    watcher = None
    try:
        while worker.is_alive() and not ready.wait(.1):
            if requested() or time.monotonic() >= deadline:
                monitor.cancel.set()
                break
        if failure:
            state.update(state="monitor_failed", reason=failure[0])
        elif not ready.is_set():
            final = observation.get("final", {})
            state.update(state="monitor_busy" if final.get("status") == "busy" else "stopped_before_delivery",
                         monitor_result=final.get("status", final.get("state", "unknown")))
        elif requested() or time.monotonic() >= deadline:
            state.update(state="stopped_before_delivery")
        else:
            state.update(state="dispatching", native_collection_started=True,
                         monitor_instance_id=observation["instance_id"])
            write_json(directory / "watch.json", state)
            watcher = threading.Thread(target=follow_stop)
            watcher.start()
            remaining = max(1, min(3600, int(deadline - time.monotonic())))
            code = agent_dispatch.run(directory / "agent", source_dir=root / "data/live",
                                      state_dir=root / "data/agent-delivery", codex=codex,
                                      max_seconds=remaining, max_tasks=max_tasks,
                                      allow_live=True, execute=True,
                                      cancel=monitor.cancel, deadline_monotonic=deadline)
            state.update(state="completed" if code == 0 else "delivery_blocked", agent_exit_code=code)
    except KeyboardInterrupt:
        state.update(state="stop_requested")
        if (directory / "agent/status.json").exists():
            agent_dispatch.stop(directory / "agent")
    except (OSError, ValueError, RuntimeError):
        state.update(state="watch_blocked", reason="inspect_owned_status_and_receipts")
    finally:
        agent_done.set()
        if watcher:
            watcher.join()
        monitor.cancel.set()
        if worker.is_alive():
            state["monitor_shutdown"] = "waiting_for_existing_read_only_operation"
            write_json(directory / "watch.json", state)
        while worker.is_alive():
            try:
                worker.join(.5)
            except KeyboardInterrupt:
                pass  # The collector owns job cleanup; never target the thread/PID.
        state["monitor_exited"] = True
        final = observation.get("final", {})
        if ready.is_set() or final.get("cycles", 0) > 0:
            state["native_collection_started"] = True
        elif final.get("status") == "busy":
            state["native_collection_started"] = False
        state["monitor_stop_reason"] = final.get("stop_reason", "cooperative_stop")
        state["monitor_cycles"] = final.get("cycles", 0)
        if final.get("query_shutdown"):
            state["query_shutdown"] = final["query_shutdown"]
        state["coverage"] = {key: row.get("status", "unknown") for key, row in final.get("coverage", {}).items()}
        if failure:
            state.update(state="monitor_failed", reason=failure[0])
        try:
            write_json(directory / "watch.json", state)
        finally:
            lease.release()
    return status(directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "status", "stop"))
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--codex-executable", default="codex")
    parser.add_argument("--max-seconds", type=int, default=3600)
    parser.add_argument("--max-tasks", type=int, default=5)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "run":
            result = run(args.run_dir, codex=args.codex_executable, max_seconds=args.max_seconds,
                         max_tasks=args.max_tasks, execute=args.execute, allow_live=args.allow_live)
        else:
            result = (status if args.action == "status" else stop)(args.run_dir)
        print(json.dumps(result))
        return 0 if result["state"] in {"preflight_only", "completed", "stop_requested", "stopped_before_delivery"} else 2
    except (OSError, ValueError, RuntimeError):
        print(json.dumps({"state": "watch_refused", "reason": "check_explicit_scope_and_owned_evidence", "process_signal_sent": False}))
        return 2
