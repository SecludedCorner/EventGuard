"""Read-only native Windows collectors. No PowerShell, CIM, commands or model calls."""
from __future__ import annotations

import ctypes as C
import ipaddress
import os
from pathlib import Path
import socket
import sys
import time

from .contract import LIMITS, error_from_exception, evidence, payload
from .winapi import (BOOL, DWORD, LONG, HANDLE, LPDWORD, LPWSTR, FILETIME, GUID,
                     MAX_BUFFER, NativeError, dll, filetime_iso, fixed_local_path,
                     function, last_error)


class TCP4(C.Structure):
    _fields_ = [(n, DWORD) for n in ("state", "address", "port", "remote", "remote_port", "pid")]


class TCP6(C.Structure):
    _fields_ = [("address", C.c_ubyte * 16), ("scope", DWORD), ("port", DWORD),
                ("remote", C.c_ubyte * 16), ("remote_scope", DWORD), ("remote_port", DWORD),
                ("state", DWORD), ("pid", DWORD)]


class UDP4(C.Structure):
    _fields_ = [(n, DWORD) for n in ("address", "port", "pid")]


class UDP6(C.Structure):
    _fields_ = [("address", C.c_ubyte * 16), ("scope", DWORD), ("port", DWORD), ("pid", DWORD)]


class PROCESSENTRY32(C.Structure):
    _fields_ = [("size", DWORD), ("usage", DWORD), ("pid", DWORD), ("heap", C.c_size_t),
                ("module", DWORD), ("threads", DWORD), ("parent", DWORD), ("priority", LONG),
                ("flags", DWORD), ("name", C.c_wchar * 260)]


class SERVICE_STATUS_PROCESS(C.Structure):
    _fields_ = [(n, DWORD) for n in ("type", "state", "controls", "exit", "specific_exit",
                                    "checkpoint", "wait_hint", "pid", "flags")]


class ENUM_SERVICE(C.Structure):
    _fields_ = [("name", LPWSTR), ("display_name", LPWSTR), ("service", SERVICE_STATUS_PROCESS)]


class FIXED_VERSION(C.Structure):
    _fields_ = [(n, DWORD) for n in ("signature", "version", "file_ms", "file_ls", "product_ms",
                                    "product_ls", "flags_mask", "flags", "os", "type", "subtype", "date_ms", "date_ls")]


class NativeBackend:
    name = "native"

    def __init__(self, evidence_sink=None, timeout=15):
        self.evidence_sink, self.timeout = evidence_sink, timeout

    def _failure(self, error, operation, stage="provider"):
        record = error.evidence() if isinstance(error, NativeError) else error_from_exception(error, stage, operation)
        if self.evidence_sink is not None:
            # Explicit acceptance sink only; production coverage never contains raw text.
            code = record["win32_error"] if record["win32_error"] is not None else record["hresult"]
            raw = C.FormatError(C.c_int32(code).value) if code is not None and os.name == "nt" else str(error)
            self.evidence_sink({"kind": "native_error", "error": record,
                                "os_message": raw[:8192], "message_source": "FormatMessage" if code is not None else "exception"})
        return record

    def collect(self, section_id, cancel=None):
        if section_id not in LIMITS:
            raise ValueError("unsupported_section")
        if cancel is not None and cancel.is_set():
            return payload(status="cancelled", errors=[evidence("policy", "cancelled_before_query", status="cancelled")])
        try:
            if os.name != "nt":
                raise NotImplementedError("windows_only")
            deadline = time.monotonic() + self.timeout
            class Budget:
                def is_set(self):
                    return (cancel is not None and cancel.is_set()) or time.monotonic() >= deadline
            result = getattr(self, "_" + section_id)(Budget())
            if cancel is not None and cancel.is_set():
                result["status"] = "cancelled"
            elif time.monotonic() >= deadline:
                result["status"] = "timeout"
                result["errors"] = [evidence("policy", "native_budget_exceeded", exception_type="CollectorDeadline", status="timeout")] + result["errors"][:63]
                result["error_count"] = result.get("error_count", 0) + 1
                result["errors_truncated"] = result["error_count"] > 64
            return result
        except (NativeError, OSError, NotImplementedError, AttributeError) as error:
            record = self._failure(error, section_id)
            return payload(errors=[record], status=record["status"])

    @staticmethod
    def _cancelled(cancel):
        return cancel is not None and cancel.is_set()

    def _listeners(self, cancel):
        library = dll("iphlpapi")
        rows, errors, checks = [], [], []
        truncated = False
        for protocol, af, structure, table_class in (("TCP", 2, TCP4, 3), ("TCP", 23, TCP6, 3),
                                                     ("UDP", 2, UDP4, 1), ("UDP", 23, UDP6, 1)):
            if self._cancelled(cancel):
                return payload(rows, errors, status="cancelled", checks=checks)
            operation = "GetExtended" + protocol.title() + "Table"
            # Actual exports spell Tcp/Udp, not TCP/UDP.
            call = function(library, operation, [C.c_void_p, LPDWORD, BOOL, DWORD, C.c_int, DWORD], DWORD)
            size = DWORD(0)
            try:
                code = call(None, C.byref(size), False, af, table_class, 0)
                for _ in range(4):
                    if code not in (0, 122) or not 4 <= size.value <= MAX_BUFFER:
                        raise NativeError(operation, code or 13)
                    buffer = C.create_string_buffer(size.value)
                    code = call(buffer, C.byref(size), False, af, table_class, 0)
                    if code == 0:
                        break
                if code:
                    raise NativeError(operation, code)
                count = DWORD.from_buffer_copy(buffer.raw[:4]).value
                if 4 + count * C.sizeof(structure) > len(buffer):
                    raise NativeError(operation, None, reason="invalid_table_size")
                remaining = max(0, LIMITS["listeners"] - len(rows))
                truncated |= count > remaining
                for i in range(min(count, remaining)):
                    value = structure.from_buffer_copy(buffer, 4 + i * C.sizeof(structure))
                    address = str(ipaddress.IPv4Address(int(value.address).to_bytes(4, "little"))) if af == 2 else str(ipaddress.IPv6Address(bytes(value.address)))
                    if af == 23 and value.scope:
                        address += "%" + str(value.scope)
                    rows.append({"protocol": protocol, "address": address,
                                 "port": socket.ntohs(value.port & 0xffff), "pid": int(value.pid), "status": "ok"})
                checks.append({"operation": operation + ("IPv4" if af == 2 else "IPv6"), "status": "ok", "count": count})
            except NativeError as error:
                record = self._failure(error, operation)
                errors.append(record)
                checks.append({"operation": operation + ("IPv4" if af == 2 else "IPv6"), "status": record["status"], "count": 0})
        # Successful empty tables are evidence too; do not turn a mixed empty/error into a total denial.
        status = "partial" if errors and any(c["status"] == "ok" for c in checks) else None
        return payload(rows, errors, truncated=truncated, status=status, checks=checks)

    def _processes(self, cancel):
        kernel = dll("kernel32")
        snapshot = function(kernel, "CreateToolhelp32Snapshot", [DWORD, DWORD], HANDLE)
        first = function(kernel, "Process32FirstW", [HANDLE, C.POINTER(PROCESSENTRY32)])
        following = function(kernel, "Process32NextW", [HANDLE, C.POINTER(PROCESSENTRY32)])
        open_process = function(kernel, "OpenProcess", [DWORD, BOOL, DWORD], HANDLE)
        image = function(kernel, "QueryFullProcessImageNameW", [HANDLE, DWORD, C.c_wchar_p, LPDWORD])
        times = function(kernel, "GetProcessTimes", [HANDLE, *([C.POINTER(FILETIME)] * 4)])
        close = function(kernel, "CloseHandle", [HANDLE])
        handle = snapshot(2, 0)
        if handle in (None, C.c_void_p(-1).value):
            raise last_error("CreateToolhelp32Snapshot")
        rows, errors, truncated = [], [], False
        try:
            entry = PROCESSENTRY32()
            entry.size = C.sizeof(entry)
            more = first(handle, C.byref(entry))
            while more:
                if self._cancelled(cancel):
                    return payload(rows, errors, status="cancelled")
                if len(rows) >= LIMITS["processes"]:
                    truncated = True
                    break
                row = {"pid": int(entry.pid), "name": entry.name, "path": None,
                       "path_status": "unknown", "created_at": None, "status": "ok"}
                process = open_process(0x1000, False, entry.pid)
                if not process:
                    record = self._failure(last_error("OpenProcess", "object"), "OpenProcess")
                    errors.append(record)
                    row.update(status="partial", path_status=record["status"])
                else:
                    try:
                        length = DWORD(32768)
                        buffer = C.create_unicode_buffer(length.value)
                        if image(process, 0, buffer, C.byref(length)):
                            row.update(path=buffer.value, path_status="ok")
                        else:
                            record = self._failure(last_error("QueryFullProcessImageNameW", "field"), "QueryFullProcessImageNameW")
                            errors.append(record)
                            row.update(status="partial", path_status=record["status"])
                        created, exited, system, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                        if times(process, C.byref(created), C.byref(exited), C.byref(system), C.byref(user)):
                            row["created_at"] = filetime_iso(created)
                        else:
                            errors.append(self._failure(last_error("GetProcessTimes", "field"), "GetProcessTimes"))
                            row["status"] = "partial"
                    finally:
                        close(process)
                rows.append(row)
                more = following(handle, C.byref(entry))
            if not more and C.get_last_error() != 18:
                errors.append(self._failure(last_error("Process32NextW"), "Process32NextW"))
        finally:
            close(handle)
        return payload(rows, errors, truncated=truncated,
                       checks=[{"operation": "CreateToolhelp32Snapshot", "status": "ok", "count": len(rows)}])

    def _services(self, cancel):
        import winreg
        library = dll("advapi32")
        open_manager = function(library, "OpenSCManagerW", [LPWSTR, LPWSTR, DWORD], HANDLE)
        enumerate_services = function(library, "EnumServicesStatusExW",
                                     [HANDLE, C.c_int, DWORD, DWORD, C.c_void_p, DWORD, LPDWORD, LPDWORD, LPDWORD, LPWSTR])
        close = function(library, "CloseServiceHandle", [HANDLE])
        manager = open_manager(None, None, 4)  # SC_MANAGER_ENUMERATE_SERVICE only
        if not manager:
            raise last_error("OpenSCManagerW")
        rows, errors, truncated = [], [], False
        resume = DWORD(0)
        states = {1: "Stopped", 2: "Start Pending", 3: "Stop Pending", 4: "Running", 5: "Continue Pending", 6: "Pause Pending", 7: "Paused"}
        modes = {0: "Boot", 1: "System", 2: "Auto", 3: "Manual", 4: "Disabled"}
        try:
            for _ in range(32):
                if self._cancelled(cancel):
                    return payload(rows, errors, status="cancelled")
                buffer = C.create_string_buffer(65536)
                needed, returned = DWORD(), DWORD()
                okay = enumerate_services(manager, 0, 0x30, 3, buffer, len(buffer), C.byref(needed), C.byref(returned), C.byref(resume), None)
                code = 0 if okay else C.get_last_error()
                if code not in (0, 234):
                    raise NativeError("EnumServicesStatusExW", code)
                if returned.value * C.sizeof(ENUM_SERVICE) > len(buffer):
                    raise NativeError("EnumServicesStatusExW", None, reason="invalid_table_size")
                for i in range(returned.value):
                    if self._cancelled(cancel):
                        return payload(rows, errors, status="cancelled")
                    if len(rows) >= LIMITS["services"]:
                        truncated = True
                        break
                    item = ENUM_SERVICE.from_buffer(buffer, i * C.sizeof(ENUM_SERVICE))
                    name = item.name
                    row = {"name": name, "state": states.get(item.service.state, "Unknown"), "start_mode": None, "status": "ok"}
                    # Query only the Start DWORD. QueryServiceConfig would also return binary command/account data.
                    try:
                        if not name or len(name) > 256 or any(c in name for c in "\\/\x00") or any(ord(c) < 32 for c in name):
                            raise NativeError("ServiceStartRegistry", None, "policy", reason="invalid_service_component")
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Services\\" + name,
                                            0, winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
                            value, kind = winreg.QueryValueEx(key, "Start")
                        if kind != winreg.REG_DWORD or value not in modes:
                            raise NativeError("ServiceStartRegistry", None, "field", reason="invalid_start_mode")
                        row["start_mode"] = modes[value]
                    except (OSError, NativeError) as error:
                        errors.append(self._failure(error, "ServiceStartRegistry", "field"))
                        row["status"] = "partial"
                    rows.append(row)
                if truncated or okay:
                    break
            else:
                truncated = True
        finally:
            close(manager)
        return payload(rows, errors, truncated=truncated,
                       checks=[{"operation": "EnumServicesStatusExW", "status": "ok", "count": len(rows)}])

    def _defender(self, cancel):
        import winreg
        rows, errors, checks = [], [], []
        fields = ("AMServiceEnabled", "AntivirusEnabled", "RealTimeProtectionEnabled", "BehaviorMonitorEnabled",
                  "IsTamperProtected", "AntivirusSignatureVersion", "AntivirusSignatureLastUpdated")
        # Registry and Security Center do not prove these effective Defender fields.
        rows.extend({"item": name, "value": None, "status": "unknown", "authority": "not_observed"} for name in fields)
        errors.append(evidence("field", "effective_defender_status_unavailable", exception_type="CoverageGap",
                               operation="DefenderNativeMetadata", status="unknown"))
        settings = (("", "DisableAntiSpyware"), ("", "DisableAntiVirus"),
                    ("Real-Time Protection", "DisableRealtimeMonitoring"),
                    ("Real-Time Protection", "DisableBehaviorMonitoring"), ("Features", "TamperProtection"))
        for suffix, name in settings:
            if self._cancelled(cancel):
                return payload(rows, errors, status="cancelled", checks=checks)
            operation = "Registry" + name
            try:
                path = "SOFTWARE\\Microsoft\\Windows Defender" + ("\\" + suffix if suffix else "")
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
                    value, kind = winreg.QueryValueEx(key, name)
                if kind != winreg.REG_DWORD or type(value) is not int:
                    raise NativeError(operation, None, "field", reason="invalid_setting_type")
                rows.append({"item": "Configured" + name, "value": value, "status": "ok", "authority": "configuration_only"})
                checks.append({"operation": operation, "status": "ok", "count": 1})
            except (OSError, NativeError) as error:
                record = self._failure(error, operation, "field")
                errors.append(record)
                checks.append({"operation": operation, "status": record["status"], "count": 0})
        try:
            health = DWORD()
            call = function(dll("wscapi"), "WscGetSecurityProviderHealth", [DWORD, LPDWORD], LONG)
            hr = call(4, C.byref(health))  # Aggregate antivirus, not Defender-specific state.
            if hr != 0:
                raise NativeError("WscGetSecurityProviderHealth", hr, "provider", hresult=True,
                                  reason="security_center_unavailable")
            value = {0: "good", 1: "not_monitored", 2: "poor", 3: "snoozed", 4: "unknown"}.get(health.value, "unknown")
            rows.append({"item": "SecurityCenterAntivirusHealth", "value": value,
                         "status": "ok" if value != "unknown" else "unknown", "authority": "aggregate_antivirus"})
            checks.append({"operation": "WscGetSecurityProviderHealth", "status": "ok", "count": 1})
        except (OSError, NativeError) as error:
            record = self._failure(error, "WscGetSecurityProviderHealth")
            errors.append(record)
            checks.append({"operation": "WscGetSecurityProviderHealth", "status": record["status"], "count": 0})
        return payload(rows, errors, status="partial" if any(c["status"] == "ok" for c in checks) else "unknown", checks=checks)

    @staticmethod
    def _startup_folder(identifier):
        shell, ole = dll("shell32"), dll("ole32")
        query = function(shell, "SHGetKnownFolderPath", [C.POINTER(GUID), DWORD, HANDLE, C.POINTER(C.c_void_p)], LONG)
        free = function(ole, "CoTaskMemFree", [C.c_void_p], None)
        value = C.c_void_p()
        guid = GUID.parse(identifier)
        hr = query(C.byref(guid), 0x4000, None, C.byref(value))  # DONT_VERIFY; no directory creation.
        if hr < 0:
            raise NativeError("SHGetKnownFolderPath", hr, "object", hresult=True)
        try:
            path = C.wstring_at(value)
            if len(path) > 32767:
                raise NativeError("SHGetKnownFolderPath", None, "policy", reason="folder_path_limit")
            return path
        finally:
            free(value)

    def _startup(self, cancel):
        import winreg
        rows, errors, checks = [], [], []
        truncated = False
        enum_name = function(dll("advapi32"), "RegEnumValueW",
                             [HANDLE, DWORD, C.c_wchar_p, LPDWORD, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p], LONG)
        for hive, label in ((winreg.HKEY_CURRENT_USER, "CurrentUser"), (winreg.HKEY_LOCAL_MACHINE, "LocalMachine")):
            for view, view_name in ((winreg.KEY_WOW64_32KEY, "Registry32"), (winreg.KEY_WOW64_64KEY, "Registry64")):
                for key_name in ("Run", "RunOnce"):
                    if self._cancelled(cancel):
                        return payload(rows, errors, status="cancelled", checks=checks)
                    source = label + "\\Software\\Microsoft\\Windows\\CurrentVersion\\" + key_name
                    common = {"source": source, "registry_view": view_name}
                    try:
                        with winreg.OpenKey(hive, "Software\\Microsoft\\Windows\\CurrentVersion\\" + key_name, 0, winreg.KEY_QUERY_VALUE | view) as key:
                            count = winreg.QueryInfoKey(key)[1]
                            if count == 0:
                                rows.append({**common, "name": "(empty)", "kind": "registry_empty", "status": "ok"})
                            available = max(0, LIMITS["startup"] - len(rows))
                            for index in range(min(count, available)):
                                if self._cancelled(cancel):
                                    return payload(rows, errors, status="cancelled", checks=checks)
                                name, length = C.create_unicode_buffer(16384), DWORD(16384)
                                # lpData=NULL and lpcbData=NULL: never fetch the command/value contents.
                                code = enum_name(HANDLE(int(key)), index, name, C.byref(length), None, None, None, None)
                                if code:
                                    raise NativeError("RegEnumValueW", code, "object")
                                rows.append({**common, "name": name.value, "kind": "registry", "status": "ok"})
                            truncated |= count > available
                        checks.append({"operation": label + view_name + key_name, "status": "ok", "count": count})
                    except FileNotFoundError:
                        rows.append({**common, "name": "(key absent)", "kind": "registry_missing", "status": "not_applicable"})
                        checks.append({"operation": label + view_name + key_name, "status": "not_applicable", "count": 0})
                    except (OSError, NativeError) as error:
                        record = self._failure(error, "StartupRegistry", "object")
                        errors.append(record)
                        rows.append({**common, "name": None, "kind": "registry", "status": record["status"]})
                        checks.append({"operation": label + view_name + key_name, "status": record["status"], "count": 0})
        for label, guid in (("Startup", "B97D20BB-F46A-4C97-BA10-5E3608430854"),
                            ("CommonStartup", "82A5EA35-D9CD-47C5-9629-E15D2F714E6E")):
            try:
                if self._cancelled(cancel):
                    return payload(rows, errors, status="cancelled", checks=checks)
                folder = fixed_local_path(self._startup_folder(guid))
                count = 0
                with os.scandir(folder) as entries:
                    for item in entries:
                        if self._cancelled(cancel):
                            return payload(rows, errors, status="cancelled", checks=checks)
                        count += 1
                        if len(rows) >= LIMITS["startup"]:
                            truncated = True
                            break
                        rows.append({"source": label, "name": item.name, "kind": "folder", "status": "ok"})
                if count == 0:
                    rows.append({"source": label, "name": "(empty)", "kind": "folder_empty", "status": "ok"})
                checks.append({"operation": label + "DirectoryNames", "status": "ok", "count": count})
            except (OSError, NativeError) as error:
                record = self._failure(error, "StartupDirectoryNames", "object")
                errors.append(record)
                rows.append({"source": label, "name": None, "kind": "folder", "status": record["status"]})
                checks.append({"operation": label + "DirectoryNames", "status": record["status"], "count": 0})
        return payload(rows, errors, truncated=truncated, checks=checks)

    def _tasks(self, cancel):
        from .taskcom import collect_tasks
        return collect_tasks(cancel, self._failure)

    def _versions(self, cancel):
        path = fixed_local_path(Path(sys.executable))
        library = dll("version")
        size_call = function(library, "GetFileVersionInfoSizeW", [LPWSTR, LPDWORD], DWORD)
        read = function(library, "GetFileVersionInfoW", [LPWSTR, DWORD, DWORD, C.c_void_p])
        query = function(library, "VerQueryValueW", [C.c_void_p, LPWSTR, C.POINTER(C.c_void_p), LPDWORD])
        ignored = DWORD()
        size = size_call(str(path), C.byref(ignored))
        if not size:
            raise last_error("GetFileVersionInfoSizeW", "object")
        if size > MAX_BUFFER:
            raise NativeError("GetFileVersionInfoW", None, "policy", reason="version_resource_limit")
        buffer = C.create_string_buffer(size)
        if not read(str(path), 0, size, buffer):
            raise last_error("GetFileVersionInfoW", "object")
        pointer, length = C.c_void_p(), DWORD()
        if not query(buffer, "\\", C.byref(pointer), C.byref(length)) or length.value < C.sizeof(FIXED_VERSION):
            raise last_error("VerQueryValueW", "field")
        value = C.cast(pointer, C.POINTER(FIXED_VERSION)).contents
        if value.signature != 0xFEEF04BD:
            raise NativeError("VerQueryValueW", None, "field", reason="invalid_version_resource")
        version = ".".join(str(n) for n in (value.product_ms >> 16, value.product_ms & 65535,
                                           value.product_ls >> 16, value.product_ls & 65535))
        # Match FileVersionInfo.ProductVersion's product string, not the Windows build tuple.
        translations, translation_size = C.c_void_p(), DWORD()
        if query(buffer, "\\VarFileInfo\\Translation", C.byref(translations), C.byref(translation_size)) and translation_size.value >= 4:
            language, codepage = (C.c_uint16 * 2).from_address(translations.value)
            product, product_length = C.c_void_p(), DWORD()
            key = "\\StringFileInfo\\%04x%04x\\ProductVersion" % (language, codepage)
            if query(buffer, key, C.byref(product), C.byref(product_length)) and 1 <= product_length.value <= 256:
                version = C.wstring_at(product, product_length.value).rstrip("\0")
        return payload([{"product": "python_runtime", "version": version, "path": str(path), "status": "ok"}],
                       checks=[{"operation": "GetFileVersionInfoW", "status": "ok", "count": 1}])
