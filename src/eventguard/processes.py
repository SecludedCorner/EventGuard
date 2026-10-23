"""Windows jobs for children created by EventGuard, never PID-based killing.

The atomic JOB_LIST creation attribute prevents a child running or escaping
before job assignment. Only our private job handle can terminate a tree.
CPython 3.13 owns pipes/wait/communicate; this module replaces process creation.
"""
from __future__ import annotations

import ctypes as C
from datetime import datetime, timedelta, timezone
import os
import re
import subprocess
import sys
import threading
import time

ORIGINAL_POPEN = subprocess.Popen
_OWNED = set()
_LOCK = threading.RLock()
DWORD, HANDLE, SIZE = C.c_uint32, C.c_void_p, C.c_size_t


class JobError(OSError):
    """Win32 error code only, never command/path or account text."""


class STARTUPINFO(C.Structure):
    _fields_ = [("cb", DWORD), ("lpReserved", C.c_wchar_p), ("lpDesktop", C.c_wchar_p),
                ("lpTitle", C.c_wchar_p), ("dwX", DWORD), ("dwY", DWORD), ("dwXSize", DWORD),
                ("dwYSize", DWORD), ("dwXCountChars", DWORD), ("dwYCountChars", DWORD),
                ("dwFillAttribute", DWORD), ("dwFlags", DWORD), ("wShowWindow", C.c_uint16),
                ("cbReserved2", C.c_uint16), ("lpReserved2", C.c_void_p),
                ("hStdInput", HANDLE), ("hStdOutput", HANDLE), ("hStdError", HANDLE)]


class STARTUPINFOEX(C.Structure):
    _fields_ = [("StartupInfo", STARTUPINFO), ("lpAttributeList", C.c_void_p)]


class PROCESS_INFORMATION(C.Structure):
    _fields_ = [("hProcess", HANDLE), ("hThread", HANDLE), ("dwProcessId", DWORD), ("dwThreadId", DWORD)]


class BASIC_LIMIT(C.Structure):
    _fields_ = [("PerProcessUserTimeLimit", C.c_int64), ("PerJobUserTimeLimit", C.c_int64),
                ("LimitFlags", DWORD), ("MinimumWorkingSetSize", SIZE), ("MaximumWorkingSetSize", SIZE),
                ("ActiveProcessLimit", DWORD), ("Affinity", SIZE), ("PriorityClass", DWORD), ("SchedulingClass", DWORD)]


class EXTENDED_LIMIT(C.Structure):
    _fields_ = [("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", C.c_uint64 * 6),
                ("ProcessMemoryLimit", SIZE), ("JobMemoryLimit", SIZE), ("PeakProcessMemoryUsed", SIZE), ("PeakJobMemoryUsed", SIZE)]


class ACCOUNTING(C.Structure):
    _fields_ = [("TotalUserTime", C.c_int64), ("TotalKernelTime", C.c_int64),
                ("ThisPeriodTotalUserTime", C.c_int64), ("ThisPeriodTotalKernelTime", C.c_int64),
                ("TotalPageFaultCount", DWORD), ("TotalProcesses", DWORD), ("ActiveProcesses", DWORD), ("TotalTerminatedProcesses", DWORD)]


class FILETIME(C.Structure):
    _fields_ = [("low", DWORD), ("high", DWORD)]


def kernel():
    if os.name != "nt":
        raise JobError("windows_job_unavailable")
    return _kernel()


from functools import lru_cache


@lru_cache(maxsize=1)
def _kernel():
    api = C.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    declarations = {
        "CreateJobObjectW": (HANDLE, [C.c_void_p, C.c_wchar_p]),
        "OpenJobObjectW": (HANDLE, [DWORD, C.c_int, C.c_wchar_p]),
        "SetInformationJobObject": (C.c_int, [HANDLE, C.c_int, C.c_void_p, DWORD]),
        "QueryInformationJobObject": (C.c_int, [HANDLE, C.c_int, C.c_void_p, DWORD, C.c_void_p]),
        "TerminateJobObject": (C.c_int, [HANDLE, C.c_uint]), "CloseHandle": (C.c_int, [HANDLE]),
        "InitializeProcThreadAttributeList": (C.c_int, [C.c_void_p, DWORD, DWORD, C.POINTER(SIZE)]),
        "UpdateProcThreadAttribute": (C.c_int, [C.c_void_p, DWORD, SIZE, C.c_void_p, SIZE, C.c_void_p, C.c_void_p]),
        "DeleteProcThreadAttributeList": (None, [C.c_void_p]),
        "CreateProcessW": (C.c_int, [C.c_wchar_p, C.c_wchar_p, C.c_void_p, C.c_void_p, C.c_int, DWORD, C.c_void_p, C.c_wchar_p, C.POINTER(STARTUPINFOEX), C.POINTER(PROCESS_INFORMATION)]),
        "ResumeThread": (DWORD, [HANDLE]), "OpenProcess": (HANDLE, [DWORD, C.c_int, DWORD]),
        "GetProcessTimes": (C.c_int, [HANDLE, C.POINTER(FILETIME), C.POINTER(FILETIME), C.POINTER(FILETIME), C.POINTER(FILETIME)]),
        "WaitForSingleObject": (DWORD, [HANDLE, DWORD]),
        "GetCurrentProcess": (HANDLE, []),
        "IsProcessInJob": (C.c_int, [HANDLE, HANDLE, C.POINTER(C.c_int)]),
        "AssignProcessToJobObject": (C.c_int, [HANDLE, HANDLE]),
        "DuplicateHandle": (C.c_int, [HANDLE, HANDLE, HANDLE, C.POINTER(HANDLE), DWORD, C.c_int, DWORD]),
        "ProcessIdToSessionId": (C.c_int, [DWORD, C.POINTER(DWORD)]),
    }
    for name, (result, args) in declarations.items():
        function = getattr(api, name)
        function.restype, function.argtypes = result, args
    return api


@lru_cache(maxsize=1)
def _object_comparison():
    """Bind the documented Windows 10 API from its System32-only DLL.

    CompareObjectHandles is exported by KernelBase, not necessarily Kernel32.
    Its absence cannot be replaced with numeric-handle or name comparisons.
    """
    try:
        api = C.WinDLL("kernelbase.dll", use_last_error=True, winmode=0x800)
        function = api.CompareObjectHandles
    except (OSError, AttributeError):
        return None
    function.restype, function.argtypes = C.c_int, [HANDLE, HANDLE]
    return function


def checked(ok, operation):
    if not ok:
        error = JobError(operation)
        error.winerror = C.get_last_error()
        raise error


def creation_time(handle):
    created, exited, kernel_time, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    checked(kernel().GetProcessTimes(handle, C.byref(created), C.byref(exited), C.byref(kernel_time), C.byref(user)), "process_time_unavailable")
    ticks = created.low | (created.high << 32)
    return (datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks // 10)).isoformat(timespec="microseconds")


def identity(pid=None):
    """Read only creation time/liveness for self or a prior recorded owner PID."""
    pid = os.getpid() if pid is None else pid
    if type(pid) is not int or not 1 <= pid <= 2**32-1:
        return {"pid": None, "created_at": None, "state": "unknown"}
    if os.name != "nt":
        return {"pid": pid, "created_at": None, "state": "unknown"}
    handle = kernel().OpenProcess(0x101000, False, pid)  # Limited metadata + wait only.
    if not handle:
        code = C.get_last_error()
        return {"pid": pid, "created_at": None, "state": "missing" if code == 87 else "denied" if code == 5 else "unknown", "win32_error": code}
    try:
        return {"pid": pid, "created_at": creation_time(handle), "state": "alive" if kernel().WaitForSingleObject(handle, 0) == 258 else "exited"}
    except OSError:
        return {"pid": pid, "created_at": None, "state": "unknown"}
    finally:
        kernel().CloseHandle(handle)


class Job:
    def __init__(self, name=None):
        if name is not None and not re.fullmatch(r"(?:Local|Global)\\EventGuard-[a-f0-9]{32}", name):
            raise ValueError("invalid_private_job_name")
        self.name = name
        C.set_last_error(0)
        self.handle = kernel().CreateJobObjectW(None, name)
        checked(self.handle, "job_create_failed")
        if name is not None and C.get_last_error() == 183:
            self.close()
            raise JobError("private_job_name_already_exists")
        self.forced, self.reason = False, None
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE.
        try:
            checked(kernel().SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)), "job_limits_failed")
        except BaseException:
            self.close()
            raise

    def active(self):
        if not self.handle:
            return 0
        info = ACCOUNTING()
        checked(kernel().QueryInformationJobObject(self.handle, 1, C.byref(info), C.sizeof(info), None), "job_query_failed")
        return int(info.ActiveProcesses)

    def terminate(self, reason):
        # The only forced termination API in the product targets our job handle.
        if reason not in {"timeout", "cancelled", "owner_exception", "descendants_remaining", "test_teardown", "launch_failure"}:
            raise ValueError("invalid_job_termination_reason")
        if self.handle and self.active():
            checked(kernel().TerminateJobObject(self.handle, 1460), "owned_job_termination_failed")
            self.forced, self.reason = True, reason

    def close(self):
        if getattr(self, "handle", None):
            kernel().CloseHandle(self.handle)
            self.handle = None


class JobPopen(ORIGINAL_POPEN):
    def __init__(self, *args, **kwargs):
        self.job, self.created_at = Job(kwargs.pop("job_name", None)), None
        self.receipt = None
        self.detached = False
        self.cleanup_lock = threading.RLock()
        try:
            super().__init__(*args, **kwargs)
        except BaseException:
            try:
                self.job.terminate("launch_failure")
                if getattr(self, "_child_created", False):
                    try:
                        self.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                self.job.close()
            raise
        with _LOCK:
            _OWNED.add(self)

    def _execute_child(self, args, executable, preexec_fn, close_fds, pass_fds, cwd, env,
                       startupinfo, creationflags, shell, p2cread, p2cwrite, c2pread, c2pwrite,
                       errread, errwrite, *unused):
        import _winapi
        if shell or pass_fds or startupinfo is not None or not isinstance(args, (list, tuple)):
            raise ValueError("unsupported_owned_process_launch")
        command = subprocess.list2cmdline([os.fspath(item) for item in args])
        standard = [int(h) for h in (p2cread, c2pwrite, errwrite)]
        if -1 in standard:
            raise ValueError("owned_process_requires_redirected_stdio")
        handles = self._filter_handle_list(standard)
        info, process = STARTUPINFOEX(), PROCESS_INFORMATION()
        info.StartupInfo.cb = C.sizeof(info)
        info.StartupInfo.dwFlags = 0x100 | 1
        info.StartupInfo.hStdInput, info.StartupInfo.hStdOutput, info.StartupInfo.hStdError = standard
        environment = None
        if env is not None:
            if any(type(k) is not str or type(v) is not str or "\0" in k + v or "=" in k for k, v in env.items()):
                raise ValueError("invalid_child_environment")
            environment = C.create_unicode_buffer("\0".join(k + "=" + v for k, v in sorted(env.items(), key=lambda pair: pair[0].upper())) + "\0\0")
        size = SIZE()
        kernel().InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
        memory = C.create_string_buffer(size.value)
        info.lpAttributeList = C.cast(memory, C.c_void_p)
        checked(kernel().InitializeProcThreadAttributeList(info.lpAttributeList, 2, 0, C.byref(size)), "job_attributes_failed")
        handle_array = (HANDLE * len(handles))(*handles)
        job_array = (HANDLE * 1)(self.job.handle)
        try:
            checked(kernel().UpdateProcThreadAttribute(info.lpAttributeList, 0, 0x20002, handle_array, C.sizeof(handle_array), None, None), "stdio_attributes_failed")
            checked(kernel().UpdateProcThreadAttribute(info.lpAttributeList, 0, 0x2000D, job_array, C.sizeof(job_array), None, None), "job_assignment_attributes_failed")
            sys.audit("subprocess.Popen", executable, command, cwd, None if env is None else "explicit_environment")
            flags = creationflags | 0x8000000 | 0x80000 | 0x400 | 4
            checked(kernel().CreateProcessW(os.fspath(executable) if executable else os.fspath(args[0]), C.create_unicode_buffer(command), None, None, True, flags,
                                           environment, os.fspath(cwd) if cwd else None, C.byref(info), C.byref(process)), "owned_process_creation_failed")
            self._child_created, self.pid, self._handle = True, int(process.dwProcessId), subprocess.Handle(process.hProcess)
            self.created_at = creation_time(process.hProcess)
            checked(kernel().ResumeThread(process.hThread) != 0xFFFFFFFF, "owned_process_resume_failed")
        finally:
            if process.hThread:
                kernel().CloseHandle(process.hThread)
            kernel().DeleteProcThreadAttributeList(info.lpAttributeList)
            self._close_pipe_fds(p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite)

    def terminate(self):
        if self.detached:
            raise JobError("persistent_job_ownership_transferred")
        self.job.terminate("owner_exception")

    kill = terminate

    def send_signal(self, sig):
        import signal
        if sig != signal.SIGTERM:
            raise ValueError("only_owned_job_termination_supported")
        self.terminate()


def spawn(argv, *, popen_factory=None, **kwargs):
    """Only a non-default injected factory may opt into unmanaged fixtures."""
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    kwargs.setdefault("stdout", subprocess.DEVNULL)
    kwargs.setdefault("stderr", subprocess.DEVNULL)
    kwargs.setdefault("shell", False)
    if popen_factory is not None and popen_factory is not ORIGINAL_POPEN:
        return popen_factory(argv, **kwargs)
    if os.name != "nt":
        return ORIGINAL_POPEN(argv, **kwargs)  # Mock-only portability, no Windows job claim.
    return JobPopen(argv, **kwargs)


def _private_job_name(name):
    if not isinstance(name, str) or not re.fullmatch(r"(?:Local|Global)\\EventGuard-[a-f0-9]{32}", name):
        raise ValueError("invalid_private_job_name")
    return name


def process_session(pid=None):
    """Read the session of self or one already recorded owned process."""
    pid = os.getpid() if pid is None else pid
    if type(pid) is not int or not 1 <= pid <= 2**32-1:
        raise ValueError("invalid_owned_process_id")
    value = DWORD()
    checked(kernel().ProcessIdToSessionId(pid, C.byref(value)), "owned_process_session_unavailable")
    return int(value.value)


def _membership(process_handle, job_handle=None):
    member = C.c_int()
    checked(kernel().IsProcessInJob(process_handle, job_handle, C.byref(member)), "private_job_membership_unavailable")
    return bool(member.value)


def _kill_on_close(job_handle):
    limits = EXTENDED_LIMIT()
    checked(kernel().QueryInformationJobObject(job_handle, 9, C.byref(limits), C.sizeof(limits), None), "private_job_limits_unavailable")
    if not limits.BasicLimitInformation.LimitFlags & 0x2000:
        raise JobError("private_job_kill_on_close_required")


def _active_job(job_handle):
    info = ACCOUNTING()
    checked(kernel().QueryInformationJobObject(job_handle, 1, C.byref(info), C.sizeof(info), None), "private_job_query_failed")
    return int(info.ActiveProcesses)


class JobKeeper:
    """A host-owned Job handle retained until OS process exit.

    There is deliberately no destructor/context-manager auto-close. Closing
    the last handle while the host is alive triggers KILL_ON_JOB_CLOSE, so a
    running host retains this keeper and lets its natural OS exit close it.
    """
    def __init__(self, name, handle, *, parent_job_present=None, lifetime_owner="host_os_exit"):
        self.name, self.handle = _private_job_name(name), handle
        self.parent_job_present, self.lifetime_owner = parent_job_present, lifetime_owner

    def receipt(self):
        if not self.handle or not _membership(kernel().GetCurrentProcess(), self.handle):
            raise JobError("host_private_job_membership_required")
        _kill_on_close(self.handle)
        return {"kind": "eventguard-private-job-keeper-v1", "job_name": self.name,
                "pid": os.getpid(), "created_at": creation_time(kernel().GetCurrentProcess()),
                "session_id": process_session(), "keeper_handle": int(self.handle),
                "parent_job_present": self.parent_job_present, "lifetime_owner": self.lifetime_owner}

    def close(self):
        """Explicit abort only; a live normal host must retain its keeper."""
        if self.handle:
            kernel().CloseHandle(self.handle)
            self.handle = None


def adopt_current_job(job_name):
    """Hold only a private job to which this host already belongs."""
    name = _private_job_name(job_name)
    handle = kernel().OpenJobObjectW(4, False, name)  # QUERY is enough to retain.
    checked(handle, "host_private_job_open_failed")
    try:
        if not _membership(kernel().GetCurrentProcess(), handle):
            raise JobError("host_private_job_membership_required")
        _kill_on_close(handle)
        return JobKeeper(name, handle)
    except BaseException:
        kernel().CloseHandle(handle)
        raise


def standalone_host_job(job_name):
    """Wrap a scheduler-created host in a new private job, without breakaway.

    A scheduler starts the host, rather than EventGuard launching an unmanaged
    child. Its ancestor job is allowed to govern this synchronous action's
    lifetime; only the new private job is configured. No detach or independent
    lifetime is claimed, and an assignment failure stays blocked.
    """
    _private_job_name(job_name)
    if not job_name.startswith("Global\\"):
        raise ValueError("persistent_global_job_required")
    parent_job = _membership(kernel().GetCurrentProcess())
    job = Job(job_name)
    try:
        checked(kernel().AssignProcessToJobObject(job.handle, kernel().GetCurrentProcess()), "host_private_job_assignment_failed")
        keeper = JobKeeper(job_name, job.handle, parent_job_present=parent_job,
                           lifetime_owner="scheduler_or_foreground_host")
        job.handle = None  # Keeper owns the handle until natural OS exit.
        return keeper
    finally:
        job.close()


def spawn_persistent(argv, *, job_name, allow_parent_job=False, **kwargs):
    """Start a host atomically in its named job; keep launcher ownership first.

    allow_parent_job is only an injected bounded-test seam. Production callers
    must not expose it as a CLI escape hatch or claim independent lifetime.
    """
    _private_job_name(job_name)
    if not job_name.startswith("Global\\"):
        raise ValueError("persistent_global_job_required")
    if type(allow_parent_job) is not bool:
        raise ValueError("invalid_parent_job_test_scope")
    if os.name != "nt":
        raise JobError("windows_persistent_job_required")
    if kwargs.get("shell") or kwargs.get("creationflags", 0) & 0x01000000:
        raise ValueError("persistent_job_breakaway_or_shell_rejected")
    if any(kwargs.get(key) == subprocess.PIPE for key in ("stdin", "stdout", "stderr")):
        raise ValueError("persistent_host_requires_independent_stdio")
    parent_job = _membership(kernel().GetCurrentProcess())
    if parent_job and not allow_parent_job:
        raise JobError("independent_background_unverifiable")
    child = spawn(argv, job_name=job_name, **kwargs)
    if not isinstance(child, JobPopen):
        raise JobError("persistent_owned_job_required")
    child._persistent_host = True
    child._persistent_parent_job = parent_job
    return child


def detach_owned(child, keeper_receipt):
    """Transfer only after proving the host holds this exact private job.

    The caller validates its run-token/ready file first. A source-provided
    handle number is never authority: duplicate it from our still-owned child
    and compare the actual kernel object with the job we created.
    """
    if not isinstance(child, JobPopen) or getattr(child, "_persistent_host", False) is not True:
        raise JobError("persistent_owned_host_required")
    with child.cleanup_lock:
        with _LOCK:
            if child not in _OWNED or child.detached:
                raise JobError("persistent_owned_host_required")
        value = keeper_receipt
        if (not isinstance(value, dict) or value.get("kind") != "eventguard-private-job-keeper-v1"
                or value.get("pid") != child.pid or value.get("created_at") != child.created_at
                or value.get("job_name") != child.job.name
                or type(value.get("session_id")) is not int or value["session_id"] != process_session(child.pid)
                or type(value.get("keeper_handle")) is not int or not 1 <= value["keeper_handle"] < 2**(C.sizeof(SIZE)*8)
                or child.poll() is not None):
            raise JobError("persistent_keeper_receipt_mismatch")
        compare = _object_comparison()
        if compare is None:
            raise JobError("persistent_keeper_object_comparison_unavailable")
        duplicate = HANDLE()
        try:
            checked(kernel().DuplicateHandle(int(child._handle), value["keeper_handle"], kernel().GetCurrentProcess(),
                                             C.byref(duplicate), 0, False, 2), "persistent_keeper_duplicate_failed")
            if not compare(child.job.handle, duplicate):
                raise JobError("persistent_keeper_job_mismatch")
            if not _membership(int(child._handle), duplicate):
                raise JobError("persistent_keeper_membership_mismatch")
            _kill_on_close(duplicate)
            if child.poll() is not None:
                raise JobError("persistent_host_exited_before_handoff")
            receipt = {"managed": True, "ownership_transferred": True, "detached": True,
                       "pid": child.pid, "created_at": child.created_at, "session_id": value["session_id"],
                       "job_name": child.job.name, "child_exited": None, "exit_code": None,
                       "forcibly_terminated": False, "lifetime_limited": bool(child._persistent_parent_job),
                       "reason": "host_private_job_keeper_verified"}
            child.job.close()
            child.detached = True
            with _LOCK:
                _OWNED.discard(child)
            return receipt
        finally:
            if duplicate.value:
                kernel().CloseHandle(duplicate)


def stop_persistent(job_name, *, pid, created_at, session_id=None, reason="cancelled", grace=2.0):
    """Wait for cooperative host stop, then only its proven private job.

    The controller sends its run-bound cooperative stop before calling this.
    A missing/reused owner while a job is active is insufficient ownership
    proof and never permits forced termination by job name alone.
    """
    name = _private_job_name(job_name)
    if type(pid) is not int or not 1 <= pid <= 2**32-1 or not isinstance(created_at, str):
        raise ValueError("invalid_persistent_owner_identity")
    if type(grace) not in (int, float) or not 0 <= grace <= 30 or reason not in {"cancelled", "timeout", "owner_exception", "test_teardown"}:
        raise ValueError("invalid_persistent_stop_scope")
    if session_id is not None and (type(session_id) is not int or not 0 <= session_id <= 2**32-1):
        raise ValueError("invalid_persistent_owner_session")
    if not name.startswith("Global\\"):
        raise ValueError("persistent_global_job_required")
    job = kernel().OpenJobObjectW(4 | 8, False, name)  # QUERY + TERMINATE only.
    checked(job, "persistent_owned_job_open_failed")
    process = None
    forced = False
    try:
        _kill_on_close(job)
        remaining = _active_job(job)
        if remaining == 0:
            observed = identity(pid)
            owner_exited = (True if observed.get("state") in {"missing", "exited"} or
                            observed.get("created_at") is not None and observed.get("created_at") != created_at else
                            False if observed.get("state") == "alive" else None)
            return {"managed": True, "job_name": name, "pid": pid, "created_at": created_at,
                    "child_exited": owner_exited, "remaining_owned_processes": 0, "forcibly_terminated": False,
                    "reason": "private_job_empty", "shutdown_requested_reason": reason}
        process = kernel().OpenProcess(0x101000, False, pid)
        if (not process or creation_time(process) != created_at or not _membership(process, job)
                or session_id is not None and process_session(pid) != session_id):
            return {"managed": True, "job_name": name, "pid": pid, "created_at": created_at,
                    "child_exited": None, "remaining_owned_processes": remaining, "forcibly_terminated": False,
                    "reason": "persistent_owner_identity_unverifiable", "shutdown_requested_reason": reason}
        deadline = time.monotonic() + grace
        while _active_job(job) and time.monotonic() < deadline:
            time.sleep(.01)
        if _active_job(job):
            checked(kernel().TerminateJobObject(job, 1460), "owned_job_termination_failed")
            forced = True
        deadline = time.monotonic() + 3
        while _active_job(job) and time.monotonic() < deadline:
            time.sleep(.01)
        remaining = _active_job(job)
        # Job accounting can reach zero before the verified owner's process
        # HANDLE is signalled. Share the existing bounded exit budget rather
        # than claiming failure from one zero-timeout observation of that race.
        wait_ms = max(0, min(3000, int((deadline - time.monotonic()) * 1000))) if remaining == 0 else 0
        exited = kernel().WaitForSingleObject(process, wait_ms) == 0
        return {"managed": True, "job_name": name, "pid": pid, "created_at": created_at,
                "child_exited": exited, "remaining_owned_processes": remaining,
                "forcibly_terminated": forced, "reason": reason if forced else "natural_exit",
                "shutdown_requested_reason": reason}
    finally:
        if process:
            kernel().CloseHandle(process)
        kernel().CloseHandle(job)


def finish(child, reason="owner_exception", grace=2.0, request_stop=True):
    if isinstance(child, JobPopen):
        with child.cleanup_lock:
            return _finish(child, reason, grace, request_stop)
    return _finish(child, reason, grace, request_stop)


def _finish(child, reason, grace, request_stop):
    """EOF grace, then only our job, then verify its actual active count."""
    if type(grace) not in (int, float) or not 0 <= grace <= 30:
        raise ValueError("invalid_shutdown_grace")
    if not isinstance(child, JobPopen):
        return {"managed": False, "child_exited": getattr(child, "returncode", None) is not None, "forcibly_terminated": False, "reason": "fixture_or_non_windows"}
    if child.detached:
        raise JobError("persistent_job_ownership_transferred")
    if child.receipt is not None:
        return dict(child.receipt)
    if request_stop and child.stdin is not None and not child.stdin.closed:
        try:
            child.stdin.close()
        except OSError:
            pass
    deadline = time.monotonic() + grace
    while child.job.active() and time.monotonic() < deadline:
        time.sleep(.01)
    child.job.terminate(reason)
    deadline = time.monotonic() + 3
    while child.job.active() and time.monotonic() < deadline:
        time.sleep(.01)
    remaining = child.job.active()
    code = child.poll()
    if code is None and remaining == 0:
        try:
            code = child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
    receipt = {"managed": True, "pid": child.pid, "created_at": child.created_at,
                     "child_exited": code is not None, "exit_code": code, "remaining_owned_processes": remaining,
                     "forcibly_terminated": child.job.forced, "reason": child.job.reason or "natural_exit",
                     "shutdown_requested_reason": reason}
    if remaining == 0 and code is not None:
        child.receipt = receipt
        child.job.close()
        with _LOCK:
            _OWNED.discard(child)
    return receipt


def cleanup_owned(reason="test_teardown", grace=.2):
    with _LOCK:
        children = list(_OWNED)
    return [finish(child, reason, grace) for child in children]


def remaining_owned():
    with _LOCK:
        return sum(child.job.active() for child in _OWNED if child.job.handle)


def current_job_active(name=None):
    """Read-only count for the test worker's inherited guardian job."""
    if os.name != "nt":
        return None
    if name is None or not re.fullmatch(r"(?:Local|Global)\\EventGuard-[a-f0-9]{32}", name):
        raise ValueError("specific_guardian_job_required")
    handle = kernel().OpenJobObjectW(4, False, name)  # QUERY only, never termination rights.
    checked(handle, "guardian_query_open_failed")
    info = ACCOUNTING()
    try:
        checked(kernel().QueryInformationJobObject(handle, 1, C.byref(info), C.sizeof(info), None), "current_job_query_failed")
        return int(info.ActiveProcesses)
    finally:
        kernel().CloseHandle(handle)


def current_job_members(name):
    """Only the specifically named test guardian; no global process inventory."""
    if os.name != "nt":
        return {}
    if not re.fullmatch(r"(?:Local|Global)\\EventGuard-[a-f0-9]{32}", name):
        raise ValueError("specific_guardian_job_required")
    handle = kernel().OpenJobObjectW(4, False, name)
    checked(handle, "guardian_query_open_failed")
    try:
        data = C.create_string_buffer(8 + C.sizeof(SIZE)*4096)
        checked(kernel().QueryInformationJobObject(handle, 3, data, len(data), None), "guardian_members_query_failed")
        count = DWORD.from_buffer(data, 4).value
        if count > 4096:
            raise JobError("guardian_members_capacity")
        return {int(pid): identity(int(pid)).get("created_at") for pid in (SIZE*count).from_buffer(data, 8)}
    finally:
        kernel().CloseHandle(handle)
