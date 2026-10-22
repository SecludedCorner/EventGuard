"""Owned CLI capture worker. It drains bounded logs until natural child exit."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import threading

from .acceptance_control import FileLease, write_json
from .local_wait import _guard

CAPTURE_LIMIT = 4 * 1024 * 1024


def capture(argv, directory, token, prompt, limit=CAPTURE_LIMIT):
    directory = _guard(directory)
    lease = FileLease(directory / "capture.lock")
    if not lease.acquire():
        return 3
    child = None
    result = {"attempt_id": token, "capture_complete": False, "codex_exit_code": None,
              "stdout_truncated": False, "stderr_truncated": False}
    try:
        paths = [_guard(directory / name) for name in ("codex.jsonl", "codex.stderr.txt")]
        with paths[0].open("xb") as output, paths[1].open("xb") as errors:
            child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
            result["codex_pid"] = child.pid
            write_json(directory / "capture-start.json", {"attempt_id": token, "codex_pid": child.pid})

            capture_errors = []

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
            try:
                child.stdin.write(prompt.encode("utf-8"))
                child.stdin.close()
            except (BrokenPipeError, OSError):
                child.stdin.close()
            result["codex_exit_code"] = child.wait()  # Never terminate or kill.
            for thread in readers:
                thread.join(timeout=2)
            result["capture_complete"] = not capture_errors and all(not thread.is_alive() for thread in readers)
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
        if child is not None and child.stdin is not None and not child.stdin.closed:
            child.stdin.close()
        lease.release()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-dir", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    from .codex_acceptance import PROMPT
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        return 2
    return capture(command, args.attempt_dir, args.attempt_id, PROMPT)
