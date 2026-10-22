"""Minimal local Task Scheduler IDispatch reader; never reads Definition/XML/Actions."""
from __future__ import annotations

import ctypes as C

from .contract import LIMITS, payload
from .winapi import DWORD, LONG, GUID, NativeError, dll, function


class VALUE(C.Union):
    _fields_ = [("integer", LONG), ("pointer", C.c_void_p), ("pair", C.c_void_p * 2), ("number", C.c_double)]


class VARIANT(C.Structure):
    _fields_ = [("vt", C.c_uint16), ("r1", C.c_uint16), ("r2", C.c_uint16), ("r3", C.c_uint16), ("value", VALUE)]


class PARAMETERS(C.Structure):
    _fields_ = [("args", C.POINTER(VARIANT)), ("named", C.POINTER(LONG)), ("count", DWORD), ("named_count", DWORD)]


class EXCEPTION(C.Structure):
    _fields_ = [("code", C.c_uint16), ("reserved", C.c_uint16), ("source", C.c_void_p),
                ("description", C.c_void_p), ("help", C.c_void_p), ("context", DWORD),
                ("reserved_pointer", C.c_void_p), ("deferred", C.c_void_p), ("scode", LONG)]


class Dispatch:
    def __init__(self, pointer, automation):
        self.pointer, self.automation = C.c_void_p(pointer), automation

    def _method(self, index, result, *args):
        address = C.cast(self.pointer, C.POINTER(C.POINTER(C.c_void_p))).contents[index]
        return C.WINFUNCTYPE(result, C.c_void_p, *args)(address)

    def close(self):
        if self.pointer:
            self._method(2, DWORD)(self.pointer)  # Release only this owned reference.
            self.pointer = C.c_void_p()

    def get(self, name, *arguments, method=False, stage="field"):
        # All names and string arguments are fixed literals in collect_tasks.
        empty, dispatch_id = GUID(), LONG()
        names = (C.c_wchar_p * 1)(name)
        hr = self._method(5, LONG, C.POINTER(GUID), C.POINTER(C.c_wchar_p), DWORD, DWORD, C.POINTER(LONG))(
            self.pointer, C.byref(empty), names, 1, 0, C.byref(dispatch_id))
        if hr < 0:
            raise NativeError("Task" + name, hr, stage, hresult=True)
        values = (VARIANT * len(arguments))()
        allocate = function(self.automation, "SysAllocString", [C.c_wchar_p], C.c_void_p)
        clear = function(self.automation, "VariantClear", [C.POINTER(VARIANT)], LONG)
        free_string = function(self.automation, "SysFreeString", [C.c_void_p], None)
        string_length = function(self.automation, "SysStringLen", [C.c_void_p], DWORD)
        result, exception, argument_error = VARIANT(), EXCEPTION(), DWORD()
        try:
            for value, argument in zip(values, reversed(arguments)):
                if type(argument) is int:
                    value.vt, value.value.integer = 3, argument
                elif type(argument) is str and argument == "\\":
                    value.vt, value.value.pointer = 8, allocate(argument)
                    if not value.value.pointer:
                        raise MemoryError()
                else:
                    raise ValueError("unallowlisted_com_argument")
            params = PARAMETERS(values if arguments else None, None, len(arguments), 0)
            hr = self._method(6, LONG, LONG, C.POINTER(GUID), DWORD, C.c_uint16,
                              C.POINTER(PARAMETERS), C.POINTER(VARIANT), C.POINTER(EXCEPTION), C.POINTER(DWORD))(
                self.pointer, dispatch_id, C.byref(empty), 0, 1 if method else 2,
                C.byref(params), C.byref(result), C.byref(exception), C.byref(argument_error))
            if hr < 0:
                raise NativeError("Task" + name, exception.scode or hr, stage, hresult=True)
            if result.vt == 9:  # Detach the returned IDispatch's owned reference.
                pointer = result.value.pointer
                result.vt = 0
                if not pointer:
                    raise NativeError("Task" + name, None, stage, reason="null_dispatch_result")
                return Dispatch(pointer, self.automation)
            if result.vt == 8:
                length = string_length(result.value.pointer)
                if length > 2048:
                    raise NativeError("Task" + name, None, "field", reason="com_string_limit")
                return C.wstring_at(result.value.pointer, length) if length else ""
            if result.vt in (3, 19, 22, 23):
                return int(result.value.integer)
            if result.vt in (0, 1):
                return None
            raise NativeError("Task" + name, None, stage, reason="unexpected_com_type")
        finally:
            clear(C.byref(result))
            for value in values:
                clear(C.byref(value))
            # Never decode provider error descriptions, paths or account names.
            for value in (exception.source, exception.description, exception.help):
                if value:
                    free_string(value)


def collect_tasks(cancel, failure):
    ole, automation = dll("ole32"), dll("oleaut32")
    initialize = function(ole, "CoInitializeEx", [C.c_void_p, DWORD], LONG)
    uninitialize = function(ole, "CoUninitialize", [], None)
    create = function(ole, "CoCreateInstance", [C.POINTER(GUID), C.c_void_p, DWORD, C.POINTER(GUID), C.POINTER(C.c_void_p)], LONG)
    hr = initialize(None, 0)
    initialized = hr in (0, 1)
    if hr < 0 and (hr & 0xffffffff) != 0x80010106:  # Existing apartment is usable.
        raise NativeError("CoInitializeEx", hr, "launch", hresult=True)
    rows, errors, checks, truncated = [], [], [], False
    service, root = None, None
    visited = 0
    states = {0: "Unknown", 1: "Disabled", 2: "Queued", 3: "Ready", 4: "Running"}

    def scan(folder, depth):
        nonlocal visited, truncated
        visited += 1
        if visited > 4096 or depth > 32:
            truncated = True
            return
        if cancel is not None and cancel.is_set():
            return
        tasks = children = None
        try:
            tasks = folder.get("GetTasks", 1, method=True, stage="object")  # Include visible hidden tasks.
            count = tasks.get("Count", stage="object")
            if type(count) is not int or not 0 <= count <= 100000:
                raise NativeError("TaskCount", None, "object", reason="invalid_collection_count")
            for index in range(1, count + 1):
                if len(rows) >= LIMITS["tasks"]:
                    truncated = True
                    return
                if cancel is not None and cancel.is_set():
                    return
                item = None
                try:
                    item = tasks.get("Item", index, stage="object")
                    row = {"status": "ok"}
                    for property_name, field in (("Name", "name"), ("Path", "task_path"), ("State", "state")):
                        try:
                            value = item.get(property_name)
                            if field == "task_path" and isinstance(value, str):
                                value = value[:value.rfind("\\") + 1]
                            row[field] = states.get(value, "Unknown") if field == "state" else value
                            if value is None or field == "state" and value not in states:
                                raise NativeError("Task" + property_name, None, "field", reason="invalid_task_field")
                        except NativeError as error:
                            errors.append(failure(error, "Task" + property_name))
                            row["status"] = "partial"
                    rows.append(row)
                except NativeError as error:
                    errors.append(failure(error, "TaskItem"))
                finally:
                    if item:
                        item.close()
        except NativeError as error:
            errors.append(failure(error, "TaskGetTasks"))
        finally:
            if tasks:
                tasks.close()
        try:
            children = folder.get("GetFolders", 0, method=True, stage="object")
            count = children.get("Count", stage="object")
            if type(count) is not int or not 0 <= count <= 100000:
                raise NativeError("TaskFolderCount", None, "object", reason="invalid_collection_count")
            for index in range(1, count + 1):
                if len(rows) >= LIMITS["tasks"] or visited >= 4096 or depth >= 32:
                    truncated = True
                    break
                if cancel is not None and cancel.is_set():
                    break
                child = None
                try:
                    child = children.get("Item", index, stage="object")
                    scan(child, depth + 1)
                except NativeError as error:
                    errors.append(failure(error, "TaskFolderItem"))
                finally:
                    if child:
                        child.close()
        except NativeError as error:
            errors.append(failure(error, "TaskGetFolders"))
        finally:
            if children:
                children.close()

    try:
        clsid = GUID.parse("0f87369f-a4e5-4cfc-bd3e-73e6154572dd")
        iid = GUID.parse("00020400-0000-0000-c000-000000000046")
        pointer = C.c_void_p()
        hr = create(C.byref(clsid), None, 1, C.byref(iid), C.byref(pointer))
        if hr < 0:
            raise NativeError("TaskCoCreateInstance", hr, "launch", hresult=True)
        service = Dispatch(pointer.value, automation)
        service.get("Connect", method=True, stage="provider")  # No server/account/password arguments.
        root = service.get("GetFolder", "\\", method=True, stage="object")
        scan(root, 0)
        checks.append({"operation": "TaskSchedulerLocalCOM", "status": "ok", "count": len(rows)})
    finally:
        if root:
            root.close()
        if service:
            service.close()
        if initialized:
            uninitialize()
    return payload(rows, errors, truncated=truncated,
                   status="cancelled" if cancel is not None and cancel.is_set() else None, checks=checks)
