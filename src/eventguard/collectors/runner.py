"""Single in-flight PowerShell query, with cooperative cancellation.

Timeout/cancellation never terminates a process. Output continues to drain until
the child exits naturally, and another query is refused during that interval.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import threading
import time

from .contract import evidence, error_from_exception

MAX_OUTPUT_BYTES = 4 * 1024 * 1024


class Runner:
    def __init__(self, popen_factory=None, executable=None, evidence_sink=None):
        self._popen = popen_factory or subprocess.Popen
        self.executable = str(executable or (Path(os.environ.get("SystemRoot", r"C:\Windows")) /
                              "System32/WindowsPowerShell/v1.0/powershell.exe"))
        self._lock = threading.Lock()
        self._active = None
        self.evidence_sink = evidence_sink

    @property
    def pending(self):
        with self._lock:
            return bool(self._active and not self._active["done"].is_set())

    @staticmethod
    def _drain(stream, job, key):
        pieces = []
        try:
            while True:
                data = stream.read(8192)
                if not data:
                    break
                with job["output_lock"]:
                    job["output_total"] += len(data)
                    if job["output_total"] <= MAX_OUTPUT_BYTES:
                        pieces.append(data)
                    else:
                        job["oversize"] = True
            job[key] = b"".join(pieces)
        except Exception:
            job["read_error"] = True
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _watch(self, job):
        readers = [threading.Thread(target=self._drain, args=(job["child"].stdout, job, "stdout"), daemon=True),
                   threading.Thread(target=self._drain, args=(job["child"].stderr, job, "stderr"), daemon=True)]
        for thread in readers:
            thread.start()
        try:
            job["returncode"] = job["child"].wait()
        except Exception:
            job["read_error"] = True
        for thread in readers:
            thread.join()
        job["done"].set()

    def run(self, script, timeout=15, cancel=None):
        started = time.monotonic()
        job, argv = None, None

        def result(status, note, data=None, error=None):
            elapsed = int((time.monotonic() - started) * 1000)
            problem = error_from_exception(error, "launch", "PowerShellLaunch", note) if error else evidence(
                "policy" if status in ("busy", "cancelled", "timeout") else "provider", note,
                exception_type="RunnerState", operation="PowerShellQuery", status=status)
            if self.evidence_sink is not None:
                self.evidence_sink({"kind": "powershell_process", "argv": argv,
                    "status": status, "reason_code": note, "elapsed_ms": elapsed,
                    "process_started": job is not None,
                    "child_exited": job is not None and job["done"].is_set(),
                    "pid": job["child"].pid if job is not None and hasattr(job["child"], "pid") else None,
                    "exit_code": job.get("returncode") if job else None,
                    "stdout": job.get("stdout", b"").decode("utf-8-sig", errors="replace") if job else "",
                    "stderr": job.get("stderr", b"").decode("utf-8-sig", errors="replace") if job else "",
                    "exception_text": str(error)[:8192] if error else None})
            return {"status": status, "data": data, "note": note, "elapsed_ms": elapsed,
                    "errors": [] if status == "ok" else [problem]}

        if not isinstance(script, str) or not script or len(script) > 24000:
            return result("error", "invalid_static_query")
        if type(timeout) not in (int, float) or not 0 < timeout <= 60:
            return result("error", "invalid_deadline")
        if cancel is not None and cancel.is_set():
            return result("cancelled", "cancelled_before_query")
        with self._lock:
            if self._active and not self._active["done"].is_set():
                return result("busy", "prior_query_finishing_naturally")
            try:
                prefix = "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); $ProgressPreference='SilentlyContinue'; "
                argv = [self.executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", prefix + script]
                child = self._popen(argv,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), shell=False)
            except PermissionError as error:
                return result("denied", "query_launch_access_denied", error=error)
            except FileNotFoundError as error:
                return result("not_applicable", "builtin_powershell_unavailable", error=error)
            except OSError as error:
                return result("error", "query_launch_failed", error=error)
            job = {"child": child, "done": threading.Event(), "output_lock": threading.Lock(), "output_total": 0}
            self._active = job
            threading.Thread(target=self._watch, args=(job,), daemon=True).start()
        while not job["done"].wait(0.025):
            if cancel is not None and cancel.is_set():
                return result("cancelled", "cancelled_no_process_termination")
            if time.monotonic() - started >= timeout:
                return result("timeout", "deadline_exceeded_no_process_termination")
        if cancel is not None and cancel.is_set():
            return result("cancelled", "late_output_ignored")
        if job.get("oversize"):
            return result("error", "query_output_limit_exceeded")
        if job.get("read_error") or job.get("returncode") != 0:
            return result("error", "query_failed_without_raw_error")
        try:
            data = json.loads(job.get("stdout", b"").decode("utf-8-sig"))
            if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
                raise ValueError()
        except (ValueError, UnicodeError):
            return result("error", "invalid_query_output")
        return result("ok", "query_complete", data)
