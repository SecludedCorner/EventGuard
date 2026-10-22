"""Small ctypes ABI helpers for local, read-only Windows metadata APIs."""
from __future__ import annotations

import ctypes as C
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import os
from pathlib import Path
import uuid

from .contract import evidence

DWORD = C.c_uint32
LONG = C.c_int32
BOOL = C.c_int32
HANDLE = C.c_void_p
LPDWORD = C.POINTER(DWORD)
LPWSTR = C.c_wchar_p
MAX_BUFFER = 4 * 1024 * 1024


class NativeError(Exception):
    def __init__(self, operation, code, stage="provider", *, hresult=False, reason=None):
        self.operation, self.stage = operation, stage
        self.winerror = None if hresult or code is None else int(code)
        self.hresult = C.c_int32(code).value if hresult else None
        self.reason = reason
        super().__init__("native_query_failed")

    def evidence(self):
        code = self.winerror
        hr = (self.hresult or 0) & 0xffffffff
        denied = code in (5, 1314, 1260) or hr == 0x80070005 or (code is None and self.stage == "policy")
        missing = code in (2, 3, 50, 127) or hr in (0x80040154, 0x80004002, 0x80070002)
        transient = (code in (6, 87, 1168) or hr in (0x80070002, 0x80070003)) and self.stage in ("object", "field")
        status = "denied" if denied else "not_applicable" if missing else "unknown" if transient else "error"
        stage = "policy" if code in (1314, 1260) else self.stage
        return evidence(stage, self.reason or ("access_denied" if denied else "object_unavailable" if transient else "api_unavailable" if missing else "query_failed"),
                        exception_type="COMError" if self.hresult is not None else "Win32Error" if code is not None else "CollectorContractError",
                        win32_error=code, hresult=self.hresult, operation=self.operation, status=status)


@lru_cache(maxsize=8)
def dll(name):
    if name not in ("kernel32", "advapi32", "iphlpapi", "wscapi", "shell32", "ole32", "oleaut32", "version"):
        raise ValueError("unallowlisted_system_library")
    if os.name != "nt":
        raise NotImplementedError("windows_only")
    # System32-only DLL resolution; never load a library from cwd or PATH.
    return C.WinDLL(name + ".dll", use_last_error=True, winmode=0x800)


def function(library, name, args, result=BOOL):
    try:
        call = getattr(library, name)
    except AttributeError:
        raise NativeError(name, 127, "launch") from None
    call.argtypes, call.restype = args, result
    return call


def last_error(operation, stage="provider"):
    return NativeError(operation, C.get_last_error(), stage)


class FILETIME(C.Structure):
    _fields_ = [("low", DWORD), ("high", DWORD)]


def filetime_iso(value):
    ticks = (int(value.high) << 32) | int(value.low)
    return (datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks // 10)).isoformat(timespec="microseconds")


def process_created_at(pid):
    """Read one observed owner's creation time, never enumerate or read commands."""
    if type(pid) is not int or not 1 <= pid <= 2**32-1:
        raise NativeError("ListenerProcessIdentity", 87, "object")
    kernel = dll("kernel32")
    opened = function(kernel, "OpenProcess", [DWORD, BOOL, DWORD], HANDLE)
    times = function(kernel, "GetProcessTimes", [HANDLE, *([C.POINTER(FILETIME)] * 4)])
    close = function(kernel, "CloseHandle", [HANDLE])
    handle = opened(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION only.
    if not handle:
        raise last_error("ListenerOpenProcess", "object")
    try:
        created, exited, system, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if not times(handle, C.byref(created), C.byref(exited), C.byref(system), C.byref(user)):
            raise last_error("ListenerGetProcessTimes", "field")
        return filetime_iso(created)
    finally:
        close(handle)


class GUID(C.Structure):
    _fields_ = [("data1", DWORD), ("data2", C.c_uint16), ("data3", C.c_uint16), ("data4", C.c_ubyte * 8)]

    @classmethod
    def parse(cls, value):
        return cls.from_buffer_copy(uuid.UUID(value).bytes_le)


def fixed_local_path(path):
    """Metadata only; do not traverse UNC, mapped drives or reparse components."""
    path = Path(path)
    if not path.is_absolute() or not path.drive or str(path).startswith("\\\\"):
        raise NativeError("LocalPathPolicy", None, "policy", reason="nonlocal_path_refused")
    get_type = function(dll("kernel32"), "GetDriveTypeW", [LPWSTR], DWORD)
    if get_type(path.anchor) != 3:
        raise NativeError("LocalPathPolicy", None, "policy", reason="nonfixed_drive_refused")
    for component in (*reversed(path.parents), path):
        if component.is_symlink() or component.is_junction():
            raise NativeError("LocalPathPolicy", None, "policy", reason="reparse_path_refused")
    return path
