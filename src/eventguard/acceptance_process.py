"""Owned CLI capture worker with bounded logs, deadline and job exit receipts."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import math
import re
import hashlib
from contextlib import ExitStack, contextmanager

from .acceptance_control import FileLease, write_json
from .local_paths import _guard
from .processes import spawn, finish, JobPopen

CAPTURE_LIMIT = 4 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2]
LAUNCH_LOCK = ROOT / "data/agent-runtime/launch.lock"


class LaunchGateError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@contextmanager
def launch_gate():
    """Serialize the final pause gate and OS creation. No usage quota."""
    lease = None
    try:
        path = _guard(LAUNCH_LOCK)
        path.parent.mkdir(parents=True, exist_ok=True)
        lease = FileLease(path)
        if not lease.acquire():
            raise LaunchGateError("launch_gate_busy")
        yield
    except LaunchGateError:
        raise
    except (OSError, ValueError, RuntimeError):
        raise LaunchGateError("launch_gate_unavailable") from None
    finally:
        if lease is not None:
            lease.release()


def open_authority():
    """Legacy budget reader, retained for historical explicit tools only.

    The communication path never calls this function.
    """
    from .agent_budget import BudgetAuthority
    return BudgetAuthority.open_existing()


def launch_hash(argv, prompt):
    return hashlib.sha256(json.dumps([list(map(str, argv)), prompt],
        ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def capture(argv, directory, token, prompt, limit=CAPTURE_LIMIT, start_allowed=None,
            deadline_monotonic=None, stop_requested=None, timeout_seconds=300):
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 3600:
        raise ValueError("invalid_capture_timeout")
    deadline = min(time.monotonic() + timeout_seconds, deadline_monotonic) if deadline_monotonic is not None else time.monotonic() + timeout_seconds
    if type(token) is not str or re.fullmatch(r"[a-f0-9]{32}", token) is None or type(prompt) is not str:
        raise ValueError("invalid_capture_binding")
    directory = _guard(directory)
    lease = FileLease(directory / "capture.lock")
    if not lease.acquire():
        return 3
    child = None
    mcp_member, mcp_binding, mcp_observation_failed = None, None, False
    launch_scope = ExitStack()
    result = {"attempt_id": token, "capture_complete": False, "codex_exit_code": None,
              "stdout_truncated": False, "stderr_truncated": False}
    readers, writer, capture_errors = [], None, []
    reason = "owner_exception"
    try:
        paths = [_guard(directory / name) for name in ("codex.jsonl", "codex.stderr.txt")]
        with paths[0].open("xb") as output, paths[1].open("xb") as errors:
            launch_scope.enter_context(launch_gate())
            if any((directory / name).exists() for name in ("capture-launch-intent.json", "capture-start.json", "capture-exit.json")):
                raise ValueError("capture_attempt_already_used")
            if time.monotonic() >= deadline or start_allowed is not None and start_allowed() is not True:
                output.flush()
                errors.flush()
                os.fsync(output.fileno())
                os.fsync(errors.fileno())
                write_json(directory / "capture-skipped.json", {
                    "attempt_id": token, "launch_not_started": True, "capture_complete": False})
                return 4
            # Persist the same attempt/argv binding before OS creation. This is
            # an explicit-run intent, not a quota or a reusable authorization.
            write_json(directory / "capture-launch-intent.json", {
                "kind": "eventguard-capture-launch-intent-v1", "attempt_id": token,
                "launch_hash": launch_hash(argv, prompt), "at": time.time(),
                "application_quota": "not_used"})
            if time.monotonic() >= deadline or start_allowed is not None and start_allowed() is not True:
                write_json(directory / "capture-skipped.json", {
                    "attempt_id": token, "launch_not_started": True, "capture_complete": False})
                return 4
            child = spawn(argv, popen_factory=subprocess.Popen, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, bufsize=0)
            result["codex_pid"] = child.pid

            def drain(pipe, destination, key):
                written = 0
                try:
                    while chunk := pipe.read(8192):
                        keep = chunk[:max(0, limit - written)]
                        if keep:
                            destination.write(keep)
                            destination.flush()
                        written += len(keep)
                        if len(keep) < len(chunk):
                            result[key] = True
                except (OSError, ValueError):
                    capture_errors.append(True)
                finally:
                    pipe.close()

            readers = [threading.Thread(target=drain, args=(child.stdout, output, "stdout_truncated"), daemon=True),
                       threading.Thread(target=drain, args=(child.stderr, errors, "stderr_truncated"), daemon=True)]
            for thread in readers:
                thread.start()
            def feed():
                try:
                    data = prompt.encode("utf-8")
                    while data:
                        written = child.stdin.write(data[:4096])
                        if not written:
                            break
                        data = data[written:]
                except (BrokenPipeError, OSError, ValueError):
                    pass
                finally:
                    child.stdin.close()
            try:
                write_json(directory / "capture-start.json", {"attempt_id": token, "codex_pid": child.pid,
                                                              "created_at": getattr(child, "created_at", None)})
                launch_scope.close()
                writer = threading.Thread(target=feed, daemon=True)
                writer.start()
                reason = "descendants_remaining"
                while child.poll() is None:
                    if mcp_member is None and not mcp_observation_failed and isinstance(child, JobPopen):
                        from .mcp_lifecycle import bind_mcp_member
                        try:
                            mcp_member, mcp_binding = bind_mcp_member(child, directory, token)
                        except (OSError, ValueError, RuntimeError, TypeError, KeyError):
                            mcp_observation_failed = True
                    if time.monotonic() >= deadline:
                        reason = "timeout"
                        break
                    if stop_requested is not None and stop_requested():
                        reason = "cancelled"
                        break
                    time.sleep(.025)
            finally:
                if writer is None and child.stdin is not None and not child.stdin.closed:
                    child.stdin.close()
                lifecycle = finish(child, reason, request_stop=False)
                result.update(process=lifecycle, stop_reason=reason, forcibly_terminated=lifecycle.get("forcibly_terminated", False),
                              child_exited=lifecycle.get("child_exited", False), codex_exit_code=child.poll())
                if mcp_member is not None:
                    from .mcp_lifecycle import finish_mcp_observation
                    try:
                        result["mcp_process"] = finish_mcp_observation(mcp_member, mcp_binding, directory)
                    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
                        mcp_observation_failed = True
                result["mcp_observation_failed"] = mcp_observation_failed
                if writer:
                    writer.join(timeout=3)
                for thread in readers:
                    thread.join(timeout=3)
                result["capture_complete"] = result["child_exited"] and not capture_errors and all(not thread.is_alive() for thread in readers) and not (writer and writer.is_alive())
                output.flush()
                errors.flush()
                os.fsync(output.fileno())
                os.fsync(errors.fileno())
                write_json(directory / "capture-exit.json", result)
        return 0 if result["capture_complete"] else 3
    except LaunchGateError as error:
        try:
            write_json(directory / "capture-blocked.json", {"attempt_id": token, "reason": error.code})
        except (OSError, ValueError, RuntimeError):
            pass
        return 2
    except (OSError, ValueError, RuntimeError):
        # Without a complete exit receipt, the parent MUST refuse model retries.
        return 2
    finally:
        try:
            try:
                if mcp_member is not None:
                    mcp_member.close()
            finally:
                if child is not None and isinstance(child, JobPopen):
                    finish(child, "owner_exception", request_stop=False)
                if child is not None and child.stdin is not None and not child.stdin.closed and not (writer and writer.is_alive()):
                    child.stdin.close()
        finally:
            launch_scope.close()
            lease.release()


def main(argv=None):
    print(json.dumps({"state": "capture_cli_retired", "model_started": False,
                      "reason": "use_managed_dispatch_or_delivery_validation"}))
    return 2


def read_start(directory):
    from .acceptance_control import read_json
    return read_json(directory / "capture-start.json")
