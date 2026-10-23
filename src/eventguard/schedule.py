"""Approval-bound, current-user logon recovery. Default invocations never mutate tasks."""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from .processes import finish, spawn
from .runtime import safe_child

NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
SOURCE = "EventGuard.BackgroundMonitor.v1"
MAX_XML = 262144
SID = re.compile(r"S-1-(?:\d+-){1,14}\d+\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
SOURCES = [
    "https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-schema",
    "https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-executiontimelimit",
    "https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-logontype",
    "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create",
    "https://learn.microsoft.com/en-us/windows/win32/api/taskschd/nf-taskschd-itaskfolder-gettask",
    "https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-tsch/528539ab-2678-4184-9573-cd624916ef9a",
]
ACTION_SOURCES = ("scripts/eventguard.py", "src/eventguard/background.py",
                  "src/eventguard/processes.py", "src/eventguard/monitor.py",
                  "src/eventguard/runtime.py", "src/eventguard/schedule.py",
                  "config/default.json")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _json(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")


def current_user_sid():
    """Token identity only; no password or credentials are read."""
    if os.name != "nt":
        raise OSError("windows_required")
    from ctypes import wintypes as W
    kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    advapi = ctypes.WinDLL("advapi32.dll", use_last_error=True, winmode=0x800)
    kernel.GetCurrentProcess.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.LocalFree.argtypes = [W.HLOCAL]
    advapi.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE)]
    advapi.GetTokenInformation.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(W.LPWSTR)]
    token = W.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise OSError("current_user_identity_unavailable")
    try:
        size = W.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not 1 <= size.value <= 65536:
            raise OSError("current_user_identity_unavailable")
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
            raise OSError("current_user_identity_unavailable")
        value = W.LPWSTR()
        if not advapi.ConvertSidToStringSidW(ctypes.c_void_p.from_buffer(buffer).value, ctypes.byref(value)):
            raise OSError("current_user_identity_unavailable")
        try:
            result = value.value
        finally:
            kernel.LocalFree(value)
        if not SID.fullmatch(result):
            raise OSError("invalid_current_user_sid")
        return result
    finally:
        kernel.CloseHandle(token)


def _root(root):
    root = Path(root).resolve(strict=True)
    if not (root / "scripts/eventguard.py").is_file():
        raise ValueError("eventguard_root_required")
    return root


def _python(executable=None):
    if sys.version_info[:2] != (3, 13):
        raise ValueError("python_3_13_required")
    executable = Path(executable or sys.executable).resolve(strict=True)
    if os.name == "nt" and executable.name.lower() not in {"python.exe", "pythonw.exe"}:
        raise ValueError("native_python_executable_required")
    windowless = executable.with_name("pythonw.exe")
    return windowless if windowless.is_file() else executable


def task_name(root, sid):
    return "EventGuard-Monitor-" + _hash(str(root).casefold().encode("utf-8"))[:12] + "-" + _hash(sid.encode("ascii"))[:8]


def action_source_hashes(root):
    """Bind the installed host, including imported core code and policy data."""
    root = _root(root)
    names = set(ACTION_SOURCES)
    for folder, pattern, recursive in (("src/eventguard", "*.py", True),
                                       ("config", "*.json", False),
                                       ("playbooks", "*.json", False)):
        base = safe_child(root, folder)
        if not base.exists():
            continue
        paths = base.rglob(pattern) if recursive else base.glob(pattern)
        for path in paths:
            checked = safe_child(root, path.relative_to(root))
            if checked.is_file():
                names.add(checked.relative_to(root).as_posix())
    return {name: _hash(safe_child(root, name).read_bytes()) if safe_child(root, name).is_file() else None
            for name in sorted(names)}


def build_task_xml(root, executable, sid):
    root, executable = _root(root), Path(executable).resolve(strict=True)
    if not SID.fullmatch(sid):
        raise ValueError("invalid_current_user_sid")
    name = task_name(root, sid)
    ET.register_namespace("", NS)
    task = ET.Element(f"{{{NS}}}Task", {"version": "1.2"})

    def element(parent, tag, text=None, **attributes):
        node = ET.SubElement(parent, f"{{{NS}}}{tag}", attributes)
        if text is not None:
            node.text = text
        return node

    info = element(task, "RegistrationInfo")
    element(info, "Source", SOURCE)
    element(info, "Author", sid)
    element(info, "URI", "\\" + name)
    element(info, "Description", "EventGuard read-only monitor; root=" + str(root))
    triggers = element(task, "Triggers")
    trigger = element(triggers, "LogonTrigger")
    element(trigger, "Enabled", "true")
    element(trigger, "UserId", sid)
    principals = element(task, "Principals")
    principal = element(principals, "Principal", id="EventGuardUser")
    element(principal, "UserId", sid)
    element(principal, "LogonType", "InteractiveToken")
    element(principal, "RunLevel", "LeastPrivilege")
    settings = element(task, "Settings")
    for key, value in [
        ("MultipleInstancesPolicy", "IgnoreNew"), ("DisallowStartIfOnBatteries", "false"),
        ("StopIfGoingOnBatteries", "false"), ("AllowHardTerminate", "false"),
        ("StartWhenAvailable", "true"), ("RunOnlyIfNetworkAvailable", "false"),
        ("AllowStartOnDemand", "true"), ("Enabled", "true"), ("Hidden", "false"),
        ("RunOnlyIfIdle", "false"), ("WakeToRun", "false"),
        ("ExecutionTimeLimit", "PT0S"), ("Priority", "7"),
    ]:
        element(settings, key, value)
    idle = element(settings, "IdleSettings")
    element(idle, "StopOnIdleEnd", "false")
    element(idle, "RestartOnIdle", "false")
    restart = element(settings, "RestartOnFailure")
    element(restart, "Interval", "PT1M")
    element(restart, "Count", "3")
    actions = element(task, "Actions", Context="EventGuardUser")
    action = element(actions, "Exec")
    element(action, "Command", str(executable))
    element(action, "Arguments", subprocess.list2cmdline(["-B", str(root / "scripts/eventguard.py"), "--format", "json", "background", "serve"]))
    element(action, "WorkingDirectory", str(root))
    ET.indent(task, space="  ")
    return ET.tostring(task, encoding="utf-16", xml_declaration=True)


def definition_digest(xml):
    """Compare all behavior, allowing only known Scheduler export bookkeeping."""
    if not isinstance(xml, (str, bytes)) or len(xml) > MAX_XML:
        raise ValueError("invalid_task_definition")
    try:
        decoded = xml if isinstance(xml, str) else xml.decode("utf-16" if xml.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    except UnicodeError:
        raise ValueError("invalid_task_definition") from None
    if "\x00" in decoded or "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
        raise ValueError("invalid_task_definition")
    # COM returns a Unicode XML string whose declaration can still say UTF-16.
    # Parse Unicode content without asking a byte parser to reinterpret that text.
    decoded = re.sub(r"\A\ufeff?<\?xml[^?]*\?>", "", decoded, count=1)
    try:
        root = ET.fromstring(decoded)
    except ET.ParseError:
        raise ValueError("invalid_task_definition") from None
    if root.tag != f"{{{NS}}}Task":
        raise ValueError("invalid_task_definition")
    generated = {
        "Task/Settings/UseUnifiedSchedulingEngine": "false",
        "Task/Settings/DisallowStartOnRemoteAppSession": "false",
        "Task/Settings/Volatile": "false",
        "Task/Settings/IdleSettings/Duration": "PT10M",
        "Task/Settings/IdleSettings/WaitTimeout": "PT1H",
    }

    def canonical(node, path=""):
        if not node.tag.startswith("{" + NS + "}"):
            raise ValueError("invalid_task_definition")
        tag = node.tag.split("}", 1)[1]
        path = path + "/" + tag if path else tag
        value = (node.text or "").strip()
        if path == "Task/RegistrationInfo/Date" or generated.get(path) == value:
            return None
        attrs = dict(node.attrib)
        if path == "Task":
            attrs.pop("version", None)
        children = [item for child in node if (item := canonical(child, path)) is not None]
        children.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return [tag, sorted(attrs.items()), value, children]

    return _hash(_json(canonical(root)))


def _owned_run(argv, timeout=15):
    child = spawn(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        output, _ = child.communicate(timeout=timeout)
        receipt = finish(child, "owner_exception", grace=0, request_stop=False)
        if receipt.get("managed") and (not receipt.get("child_exited") or receipt.get("remaining_owned_processes") != 0):
            return {"status": "unknown", "reason": "scheduler_child_exit_unconfirmed", "shutdown": receipt}
        if len(output or b"") > 2 * MAX_XML:
            return {"status": "unknown", "reason": "scheduler_output_limit", "shutdown": receipt}
        return {"status": "completed", "exit_code": child.returncode, "stdout": output or b"", "shutdown": receipt}
    except subprocess.TimeoutExpired:
        return {"status": "unknown", "reason": "scheduler_timeout", "shutdown": finish(child, "timeout", grace=1)}
    except BaseException:
        finish(child, "owner_exception", grace=1)
        raise


def _ps_literal(value):
    return "'" + value.replace("'", "''") + "'"


QUERY_STAGES = {"com_create", "connect", "get_folder", "get_task", "definition", "xml"}


def _query_error(stage, hresult, parent_folder_confirmed):
    """Missing a task is distinct from failing to access its parent folder."""
    if stage not in QUERY_STAGES or not isinstance(hresult, str) or not re.fullmatch(r"[A-F0-9]{8}", hresult) or type(parent_folder_confirmed) is not bool:
        raise ValueError("invalid_scheduler_response")
    # MS-TSCH SchRpcRetrieveTask defines missing path/task (03/02) separately
    # from E_ACCESSDENIED. Only interpret them after GetFolder succeeded.
    absent = stage == "get_task" and parent_folder_confirmed and hresult in {"80070002", "80070003"}
    return {"status": "absent" if absent else "denied" if hresult == "80070005" else "unknown",
            "reason": "task_not_found_in_confirmed_folder" if absent else "scheduler_access_denied" if hresult == "80070005" else "scheduler_query_failed",
            "stage": stage, "hresult": hresult, "parent_folder_confirmed": parent_folder_confirmed}


def query_task(name, *, root=None, sid=None):
    """Only the deterministic task, with HRESULT rather than translated messages."""
    if os.name != "nt":
        return {"status": "unknown", "reason": "windows_required"}
    if not re.fullmatch(r"EventGuard-Monitor-[a-f0-9]{12}-[a-f0-9]{8}", name):
        raise ValueError("invalid_task_name")
    if root is None or not isinstance(sid, str) or not SID.fullmatch(sid):
        return {"status": "unknown", "reason": "expected_task_identity_required"}
    root = _root(root)
    if name != task_name(root, sid):
        raise ValueError("task_name_does_not_match_installation")
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not powershell.is_file():
        return {"status": "unknown", "reason": "scheduler_query_unavailable"}
    script = ("$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
              "$stage='com_create';$folderKnown=$false;"
              "try{$s=New-Object -ComObject Schedule.Service;$stage='connect';$s.Connect();"
              "$stage='get_folder';$f=$s.GetFolder('\\');if($null -eq $f){throw 'scheduler_folder_unavailable'};"
              "$folderKnown=$true;$stage='get_task';$t=$f.GetTask('" + name + "');"
              "$stage='definition';$d=$t.Definition;$r=$d.RegistrationInfo;$p=$d.Principal;"
              "if(([string]$r.Source -cne " + _ps_literal(SOURCE) + ") -or "
              "([string]$r.URI -cne " + _ps_literal("\\" + name) + ") -or "
              "([string]$r.Description -cne " + _ps_literal("EventGuard read-only monitor; root=" + str(root)) + ") -or "
              "([string]$p.UserId -cne " + _ps_literal(sid) + ")){"
              "@{status='present';ownership='foreign_or_changed_identity';stage=$stage;parent_folder_confirmed=$folderKnown}|ConvertTo-Json -Compress}"
              "else{$stage='xml';$x=[string]$t.Xml;"
              "if($x.Length -gt 262144){@{status='unknown';reason='scheduler_output_limit';stage=$stage;parent_folder_confirmed=$folderKnown}|ConvertTo-Json -Compress}"
              "else{@{status='present';ownership='matching_eventguard_identity';xml=$x;stage=$stage;parent_folder_confirmed=$folderKnown}|ConvertTo-Json -Compress}}}"
              "catch{$e=$_.Exception;while($e.InnerException){$e=$e.InnerException};"
              "$c='{0:X8}' -f ($e.HResult -band 0xffffffffL);"
              "@{status='error';stage=$stage;hresult=$c;parent_folder_confirmed=$folderKnown}|ConvertTo-Json -Compress}")
    result = _owned_run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", script])
    if result["status"] != "completed":
        return result
    if result["exit_code"] != 0:
        return {"status": "unknown", "reason": "scheduler_query_failed", "exit_code": result["exit_code"]}
    try:
        value = json.loads(result["stdout"].decode("utf-8-sig"))
        if value.get("status") == "error":
            return _query_error(value.get("stage"), value.get("hresult"), value.get("parent_folder_confirmed"))
        if value.get("status") not in {"present", "unknown"} or value.get("stage") not in QUERY_STAGES or type(value.get("parent_folder_confirmed")) is not bool:
            raise ValueError
        if value["status"] == "present":
            if value.get("ownership") == "foreign_or_changed_identity":
                return {"status": "present", "ownership": "foreign_or_changed_identity", "stage": value["stage"], "parent_folder_confirmed": value["parent_folder_confirmed"]}
            if value.get("ownership") != "matching_eventguard_identity" or type(value.get("xml")) is not str or len(value["xml"]) > MAX_XML:
                raise ValueError
        return value
    except (ValueError, UnicodeError, AttributeError):
        return {"status": "unknown", "reason": "invalid_scheduler_response"}


def make_plan(root, action="install", *, executable=None, sid=None, observed=None, start_now=False):
    root = _root(root)
    if action not in {"install", "uninstall"} or type(start_now) is not bool or (action == "uninstall" and start_now):
        raise ValueError("invalid_schedule_action")
    sid, executable = sid or current_user_sid(), _python(executable)
    xml = build_task_xml(root, executable, sid)
    expected = definition_digest(xml)
    name = task_name(root, sid)
    observed = query_task(name, root=root, sid=sid) if observed is None else observed
    state = {key: observed[key] for key in ("status", "reason", "hresult", "exit_code", "stage", "parent_folder_confirmed") if key in observed}
    owned = False
    if state.get("status") == "present":
        if observed.get("ownership") == "foreign_or_changed_identity":
            state["reason"] = "task_identity_not_owned"
        else:
            try:
                state["definition_sha256"] = definition_digest(observed.get("xml", ""))
                owned = state["definition_sha256"] == expected
            except ValueError:
                state["reason"] = "invalid_task_definition"
        state["ownership"] = "matching_eventguard_definition" if owned else "foreign_or_changed_definition"
    source_hashes = action_source_hashes(root)
    missing_sources = [name for name, value in source_hashes.items() if value is None]
    blocked_reason = "monitor_installation_incomplete" if missing_sources else None
    if not blocked_reason and state.get("status") not in {"absent", "present"}:
        blocked_reason = state.get("reason") or "scheduler_query_not_verified"
    if not blocked_reason and state.get("status") == "present" and not owned:
        blocked_reason = state.get("reason") or "scheduler_ownership_not_verified"
    plan = {
        "schema_version": "1.0", "action": action, "task_name": name,
        "root": str(root), "user_sid": sid, "python_executable": str(executable),
        "task_xml_sha256": _hash(xml), "definition_sha256": expected,
        "action_source_sha256": source_hashes,
        "installation_status": "incomplete" if missing_sources else "complete",
        "missing_action_sources": missing_sources,
        "blocked_reason": blocked_reason,
        "observed": state, "model_calls": 0, "start_now": start_now,
        "recovery_scope": "current_user_logon_after_reboot_not_before_login",
        "approval_scope": "register_and_start_one_task" if start_now else "register_one_task_without_starting_it" if action == "install" else "remove_one_matching_registration_without_stopping_monitor",
        "limits": ["No service or pre-logon monitoring", "Interactive session required", "Restart on failure: three retries, one minute apart", "No task replacement or privilege escalation"],
        "sources": SOURCES,
    }
    plan["plan_sha256"] = _hash(_json(plan))
    blocked = bool(missing_sources) or state.get("status") not in {"absent", "present"} or (state.get("status") == "present" and not owned)
    return plan, xml, blocked


def write_plan(root, plan, xml, plan_dir=None):
    root = _root(root)
    reports = safe_child(root, "reports")
    directory = Path(plan_dir) if plan_dir else reports / ("schedule-" + plan["action"] + "-" + plan["plan_sha256"][:12])
    directory = directory if directory.is_absolute() else root / directory
    try:
        relative = directory.relative_to(root)
    except ValueError:
        raise ValueError("plan_directory_must_be_inside_reports") from None
    directory = safe_child(root, relative)
    directory = directory.resolve()
    if directory == reports or reports not in directory.parents:
        raise ValueError("plan_directory_must_be_inside_reports")
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in (("plan.json", _json(plan)), ("task.xml", xml)):
        path = safe_child(root, directory.relative_to(root) / name)
        if path.is_symlink() or (path.exists() and (path.stat().st_size != len(content) or path.read_bytes() != content)):
            raise ValueError("plan_artifact_already_exists_with_different_content")
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
    return directory


def _scheduler_executable():
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/schtasks.exe"


def execute_plan(root, action, approved, *, executable=None, sid=None, plan_dir=None, start_now=False):
    """Regenerate trusted fields. Edited artifact JSON/XML never supplies commands."""
    if not isinstance(approved, str) or not DIGEST.fullmatch(approved):
        return {"status": "approval_required", "reason": "approved_plan_sha256_required", "executed": False}
    plan, xml, blocked = make_plan(root, action, executable=executable, sid=sid, start_now=start_now)
    if plan["plan_sha256"] != approved:
        return {"status": "approval_required", "reason": "plan_changed_or_digest_mismatch", "executed": False, "plan": plan}
    if blocked:
        return {"status": "blocked", "reason": plan.get("blocked_reason") or "scheduler_ownership_or_query_not_verified", "executed": False, "plan": plan}
    present = plan["observed"]["status"] == "present"
    if (action == "install" and present and not start_now) or (action == "uninstall" and not present):
        return {"status": "already_installed" if present else "already_absent", "executed": False, "plan": plan}
    directory = write_plan(root, plan, xml, plan_dir)
    receipt_path = directory / "execution.json"
    started_path = directory / "execution-start.json"
    if any(path.exists() or path.is_symlink() for path in (receipt_path, started_path)):
        return {"status": "blocked", "reason": "execution_receipt_already_exists", "executed": False, "plan": plan}
    scheduler = _scheduler_executable()
    if not scheduler.is_file():
        return {"status": "blocked", "reason": "scheduler_command_unavailable", "executed": False, "plan": plan}
    # No /F on create: even a task-name race cannot overwrite another registration.
    argv = [str(scheduler), "/Create", "/TN", plan["task_name"], "/XML", str(directory / "task.xml")]
    if action == "uninstall":
        # /F suppresses this exact-name delete confirmation; it does not stop a process.
        argv = [str(scheduler), "/Delete", "/TN", plan["task_name"], "/F"]
    # An interrupted mutation cannot be silently replayed from the same plan.
    with started_path.open("xb") as handle:
        handle.write(_json({"schema_version": "1.0", "plan_sha256": approved,
                            "action": action, "start_now": start_now,
                            "status": "execution_started_not_yet_confirmed"}))
        handle.flush()
        os.fsync(handle.fileno())
    result = {"status": "completed", "exit_code": 0}
    try:
        if not (action == "install" and present):
            result = _owned_run(argv)
    except (OSError, ValueError):
        result = {"status": "unknown", "reason": "scheduler_mutation_exit_unconfirmed"}
    # Never launch another query while this mutation's own exit is unconfirmed.
    after, after_blocked = {"observed": {"status": "unknown", "reason": "mutation_not_confirmed"}}, True
    if result.get("status") == "completed":
        try:
            after, _, after_blocked = make_plan(root, action, executable=executable, sid=sid, start_now=start_now)
        except (OSError, ValueError):
            pass
    expected_state = "present" if action == "install" else "absent"
    passed = result.get("status") == "completed" and result.get("exit_code") == 0 and not after_blocked and after["observed"]["status"] == expected_state
    run = None
    if passed and start_now:
        try:
            run = _owned_run([str(scheduler), "/Run", "/TN", plan["task_name"]])
        except (OSError, ValueError):
            run = {"status": "unknown", "reason": "scheduler_run_exit_unconfirmed"}
    receipt = {"status": "installed" if passed and action == "install" else "uninstalled" if passed else "unconfirmed",
               "executed": True, "exit_code": result.get("exit_code"), "shutdown": result.get("shutdown"),
               "reason": result.get("reason"),
               "plan_sha256": approved, "plan_directory": str(directory), "observed_after": after["observed"],
               "task_start_requested": start_now, "task_started": False,
               "start_request_accepted": bool(run and run.get("status") == "completed" and run.get("exit_code") == 0),
               "start_receipt": {key: run.get(key) for key in ("status", "reason", "exit_code", "shutdown")} if run else None,
               "model_calls": 0}
    if run and not receipt["start_request_accepted"]:
        receipt["status"] = "installed_start_unconfirmed"
    # Run acceptance is not proof the monitor acquired its lease or is healthy.
    receipt["receipt_persisted"] = True
    try:
        with receipt_path.open("xb") as handle:
            handle.write(_json(receipt))
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        receipt["receipt_persisted"] = False
        receipt["status"] = "unconfirmed"
        receipt["reason"] = "execution_receipt_persistence_failed"
    return receipt


def main(argv=None, *, root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall", "status"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Default: query one task and write a review plan.")
    mode.add_argument("--execute", action="store_true", help="Requires explicit approval of the current plan digest.")
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--plan-dir", help="New directory inside this project's reports directory.")
    parser.add_argument("--start-now", action="store_true", help="Install plan also approves one immediate Run request.")
    args = parser.parse_args(argv)
    root = Path(root or Path(__file__).resolve().parents[2])
    try:
        if args.action == "status":
            if args.execute or args.approved_plan_sha256 or args.plan_dir or args.start_now:
                raise ValueError("status_is_read_only")
            plan, _, blocked = make_plan(root)
            result = {"status": "blocked" if blocked else "present" if plan["observed"]["status"] == "present" else "absent",
                      "reason": plan.get("blocked_reason"),
                      "observed": plan["observed"], "task_name": plan["task_name"], "executed": False,
                      "model_calls": 0, "recovery_scope": plan["recovery_scope"]}
        elif args.execute:
            result = execute_plan(root, args.action, args.approved_plan_sha256, plan_dir=args.plan_dir, start_now=args.start_now)
        else:
            plan, xml, blocked = make_plan(root, args.action, start_now=args.start_now)
            directory = write_plan(root, plan, xml, args.plan_dir)
            result = {"status": "blocked" if blocked else "dry_run", "executed": False, "requires_approval": True,
                      "reason": plan.get("blocked_reason"),
                      "plan": plan, "plan_directory": str(directory), "model_calls": 0}
    except (OSError, ValueError) as error:
        result = {"status": "blocked", "reason": str(error) if type(error) is ValueError else "scheduler_or_identity_unavailable",
                  "executed": False, "model_calls": 0}
    result["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 2 if result["status"] in {"approval_required", "blocked", "unconfirmed", "installed_start_unconfirmed"} else 0
