"""One query at a time; Windows-owned jobs get an EOF grace then bounded cleanup."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

from .contract import evidence, error_from_exception
from .progress import Progress
from .bounded_json import BoundedJSONError, loads, MAX_JSON_BYTES
from ..processes import spawn, finish, JobPopen, ORIGINAL_POPEN

MAX_OUTPUT_BYTES = MAX_JSON_BYTES


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
            return bool(self._active and self._unresolved(self._active))

    @staticmethod
    def _unresolved(job):
        if not job["done"].is_set():
            return True
        if isinstance(job.get("child"), JobPopen):
            receipt = job.get("process", {})
            return (receipt.get("child_exited") is not True
                    or type(receipt.get("remaining_owned_processes")) is not int
                    or receipt["remaining_owned_processes"] != 0)
        return False

    @property
    def last_process(self):
        with self._lock:
            return self._process_metadata(self._active) if self._active else {}

    @staticmethod
    def _process_metadata(job):
        value = dict(job.get("process", {}))
        child = job.get("child")
        if isinstance(child, JobPopen):
            value.update(managed=True, pid=child.pid, created_at=child.created_at, job_name=child.job.name)
        if job.get("oversize"):
            value.update(output_limit_exceeded=True, output_limit_bytes=MAX_OUTPUT_BYTES,
                         output_bytes_observed=job["output_total"])
        return value

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
                        job["output_limit"].set()
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
            if isinstance(job["child"], JobPopen):
                job["process"] = finish(job["child"], "descendants_remaining", grace=.2)
        except Exception:
            job["read_error"] = True
        for thread in readers:
            thread.join(timeout=3)
            if thread.is_alive():
                job["read_error"] = True
        job["done"].set()

    def run(self, script, timeout=15, cancel=None, _argv=None, progress=None, source_id=None):
        started = time.monotonic()
        job, argv = None, None
        observer = Progress(progress, source_id, "native" if _argv else "powershell")

        def result(status, note, data=None, error=None):
            observer.emit("completed")
            elapsed = int((time.monotonic() - started) * 1000)
            problem = error_from_exception(error, "launch", "PowerShellLaunch", note) if error else evidence(
                "policy" if status in ("busy", "cancelled", "timeout") else "provider", note,
                exception_type="RunnerState", operation="PowerShellQuery", status=status)
            if self.evidence_sink is not None:
                self.evidence_sink({"kind": "native_worker_process" if _argv else "powershell_process", "argv": argv,
                    "process": self._process_metadata(job) if job else {},
                    "status": status, "reason_code": note, "elapsed_ms": elapsed,
                    "process_started": job is not None,
                    "child_exited": job is not None and job["done"].is_set(),
                    "pid": job["child"].pid if job is not None and hasattr(job["child"], "pid") else None,
                    "exit_code": job.get("returncode") if job else None,
                    "stdout": job.get("stdout", b"").decode("utf-8-sig", errors="replace") if job else "",
                    "stderr": job.get("stderr", b"").decode("utf-8-sig", errors="replace") if job else "",
                    "exception_text": str(error)[:8192] if error else None})
            return {"status": status, "data": data, "note": note, "elapsed_ms": elapsed,
                    "process": self._process_metadata(job) if job else {},
                    "errors": [] if status == "ok" else [problem]}

        if not isinstance(script, str) or not script or len(script) > 24000:
            return result("error", "invalid_static_query")
        if type(timeout) not in (int, float) or not 0 < timeout <= 60:
            return result("error", "invalid_deadline")
        if cancel is not None and cancel.is_set():
            return result("cancelled", "cancelled_before_query")
        # Never invoke an observer while holding the runner state lock: an
        # observer may query pending/last_process when publishing its snapshot.
        observer.emit("launch")
        launch_problem, busy = None, None
        with self._lock:
            if self._active and self._unresolved(self._active):
                busy = ("prior_query_finishing_naturally" if not self._active["done"].is_set()
                        else "prior_owned_query_exit_unconfirmed")
            else:
                try:
                    prefix = "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); $ProgressPreference='SilentlyContinue'; "
                    argv = _argv or [self.executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", prefix + script]
                    child = spawn(argv, popen_factory=self._popen,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), shell=False,
                                        **({"job_name": "Global\\EventGuard-" + uuid.uuid4().hex}
                                           if os.name == "nt" and self._popen is ORIGINAL_POPEN else {}))
                except PermissionError as error:
                    launch_problem = ("denied", "query_launch_access_denied", error)
                except FileNotFoundError as error:
                    launch_problem = ("not_applicable", "builtin_powershell_unavailable", error)
                except OSError as error:
                    launch_problem = ("error", "query_launch_failed", error)
                if launch_problem is None:
                    job = {"child": child, "done": threading.Event(), "output_lock": threading.Lock(),
                           "output_limit": threading.Event(), "output_total": 0}
                    self._active = job
                    threading.Thread(target=self._watch, args=(job,), daemon=True).start()
        if busy:
            return result("busy", busy)
        if launch_problem is not None:
            status, note, error = launch_problem
            return result(status, note, error=error)
        while not job["done"].wait(0.025):
            observer.emit("waiting")
            if job["output_limit"].is_set():
                if isinstance(child, JobPopen):
                    job["process"] = finish(child, "output_limit")
                    job["done"].wait(3)
                # Injected fixtures/unmanaged children remain pending until
                # their owner ends them; exceeding a limit never grants PID
                # termination authority.
                return result("error", "query_output_limit_exceeded")
            if cancel is not None and cancel.is_set():
                if isinstance(child, JobPopen):
                    job["process"] = finish(child, "cancelled")
                    job["done"].wait(3)
                    return result("cancelled", "cancelled_owned_job_stopped")
                return result("cancelled", "cancelled_no_process_termination")
            if time.monotonic() - started >= timeout:
                if isinstance(child, JobPopen):
                    job["process"] = finish(child, "timeout")
                    job["done"].wait(3)
                    return result("timeout", "deadline_exceeded_owned_job_stopped")
                return result("timeout", "deadline_exceeded_no_process_termination")
        if cancel is not None and cancel.is_set():
            return result("cancelled", "late_output_ignored")
        if job.get("oversize"):
            return result("error", "query_output_limit_exceeded")
        if job.get("read_error") or job.get("returncode") != 0:
            return result("error", "query_failed_without_raw_error")
        if job.get("process", {}).get("forcibly_terminated"):
            return result("error", "owned_descendants_forcibly_stopped")
        try:
            data = loads(job.get("stdout", b"").decode("utf-8-sig"))
            if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
                raise ValueError()
        except BoundedJSONError as error:
            return result("error", error.reason)
        except (ValueError, UnicodeError):
            return result("error", "invalid_query_output")
        return result("ok", "query_complete", data)

    def shutdown(self, grace=2):
        with self._lock:
            job = self._active
        if job and isinstance(job["child"], JobPopen):
            job["process"] = finish(job["child"], "cancelled", grace=grace)
            job["done"].wait(3)
            return self._process_metadata(job)
        return {"managed": False, "child_exited": not self.pending, "forcibly_terminated": False}
