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

from .acceptance_control import FileLease, write_json
from .local_paths import _guard
from .processes import spawn, finish, JobPopen

CAPTURE_LIMIT = 4 * 1024 * 1024


def capture(argv, directory, token, prompt, limit=CAPTURE_LIMIT, start_allowed=None,
            deadline_monotonic=None, stop_requested=None, timeout_seconds=300):
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 3600:
        raise ValueError("invalid_capture_timeout")
    deadline = min(time.monotonic() + timeout_seconds, deadline_monotonic) if deadline_monotonic is not None else time.monotonic() + timeout_seconds
    directory = _guard(directory)
    lease = FileLease(directory / "capture.lock")
    if not lease.acquire():
        return 3
    child = None
    result = {"attempt_id": token, "capture_complete": False, "codex_exit_code": None,
              "stdout_truncated": False, "stderr_truncated": False}
    readers, writer, capture_errors = [], None, []
    reason = "owner_exception"
    try:
        paths = [_guard(directory / name) for name in ("codex.jsonl", "codex.stderr.txt")]
        with paths[0].open("xb") as output, paths[1].open("xb") as errors:
            if start_allowed is not None and start_allowed() is not True:
                output.flush()
                errors.flush()
                os.fsync(output.fileno())
                os.fsync(errors.fileno())
                write_json(directory / "capture-skipped.json", {
                    "attempt_id": token, "launch_not_started": True, "capture_complete": False})
                return 4  # No child, no invented exit receipt.
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
                writer = threading.Thread(target=feed, daemon=True)
                writer.start()
                reason = "descendants_remaining"
                while child.poll() is None:
                    if time.monotonic() >= deadline:
                        reason = "timeout"
                        break
                    if stop_requested is not None and stop_requested():
                        reason = "cancelled"
                        break
                    time.sleep(.025)
            finally:
                lifecycle = finish(child, reason, request_stop=False)
                result.update(process=lifecycle, stop_reason=reason, forcibly_terminated=lifecycle.get("forcibly_terminated", False),
                              child_exited=lifecycle.get("child_exited", False), codex_exit_code=child.poll())
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
    except (OSError, ValueError, RuntimeError):
        # Without a complete exit receipt, the parent MUST refuse model retries.
        return 2
    finally:
        try:
            if child is not None and isinstance(child, JobPopen):
                finish(child, "owner_exception", request_stop=False)
            if child is not None and child.stdin is not None and not child.stdin.closed and not (writer and writer.is_alive()):
                child.stdin.close()
        finally:
            lease.release()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-dir", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    from .codex_acceptance import PROMPT
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        return 2
    return capture(command, args.attempt_dir, args.attempt_id, PROMPT, timeout_seconds=args.timeout_seconds)
