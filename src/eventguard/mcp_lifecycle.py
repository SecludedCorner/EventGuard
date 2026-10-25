"""Bounded evidence for one MCP process observed inside the owned CLI Job."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from . import processes
from .acceptance_control import read_json
from .capture_receipt import validate_receipt
from .local_paths import _guard

LIMIT = 2048
KIND = "eventguard-mcp-process-binding-v1"
MARKER_KIND = "eventguard-inbox-startup-evidence-v1"
TOKEN = re.compile(r"[a-f0-9]{32}\Z")
PROCESS_FIELDS = ("identity_verified", "owner_job_membership_verified", "handle_retained",
                  "owner_pid", "owner_created_at", "pid", "created_at", "child_exited", "exit_code")
BINDING_FIELDS = ("kind", "attempt_id", "server_instance", "pid", "created_at", "owner_pid", "owner_created_at")


class McpLifecycleError(RuntimeError):
    """Fixed codes only; this module never terminates an observed process."""


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _pid(value):
    return type(value) is int and 1 <= value <= 0xFFFFFFFF


def _time(value):
    if type(value) is not str or not 20 <= len(value) <= 64:
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is not None
    except (ValueError, OverflowError):
        return False


def _token(value):
    return type(value) is str and TOKEN.fullmatch(value) is not None


def _marker(value, phase):
    return (type(value) is dict and value.get("kind") == MARKER_KIND and value.get("phase") == phase
            and _token(value.get("instance_id")) and _pid(value.get("pid")) and _time(value.get("created_at")))


def _binding(value):
    return (type(value) is dict and value.get("kind") == KIND and _token(value.get("attempt_id"))
            and _token(value.get("server_instance")) and _pid(value.get("pid")) and _time(value.get("created_at"))
            and _pid(value.get("owner_pid")) and _time(value.get("owner_created_at"))
            and value["pid"] != value["owner_pid"])


def _snapshot(observation):
    value = observation.snapshot()
    if type(value) is not dict:
        raise McpLifecycleError("mcp_member_snapshot_unavailable")
    return {field: value.get(field) for field in PROCESS_FIELDS}


def _matches(snapshot, binding, *, exited):
    return (type(snapshot) is dict and _binding(binding)
            and _pid(snapshot.get("pid")) and _pid(snapshot.get("owner_pid"))
            and _time(snapshot.get("created_at")) and _time(snapshot.get("owner_created_at"))
            and all(snapshot.get(field) is True for field in
                    ("identity_verified", "owner_job_membership_verified", "handle_retained"))
            and all(snapshot.get(field) == binding[field] for field in
                    ("pid", "created_at", "owner_pid", "owner_created_at"))
            and snapshot.get("child_exited") is exited
            and (type(snapshot.get("exit_code")) is int and snapshot["exit_code"] == 0
                 if exited else snapshot.get("exit_code") is None))


def _write_new(path, value):
    encoded = json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    if len(encoded) > LIMIT:
        raise McpLifecycleError("mcp_member_evidence_capacity")
    # Exclusive creation also refuses a concurrent or incomplete prior write.
    with _guard(path).open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _close(observation):
    if observation is not None:
        try:
            observation.close()
        except (OSError, ValueError, RuntimeError, TypeError, AttributeError):
            raise McpLifecycleError("mcp_member_handle_close_unconfirmed") from None


def bind_mcp_member(child, directory, attempt_id):
    """Retain a query HANDLE only after the marker matches a live CLI Job member."""
    observation = None
    try:
        directory = _guard(directory)
        marker_path = _guard(directory / "mcp-server-started.json")
        if not marker_path.exists():
            return None, None
        if not _token(attempt_id):
            raise McpLifecycleError("invalid_mcp_attempt")
        if _guard(directory / "mcp-process-start.json").exists():
            raise McpLifecycleError("mcp_member_binding_already_used")
        marker = read_json(marker_path, limit=LIMIT)
        if not _marker(marker, "server-started"):
            raise McpLifecycleError("mcp_started_marker_invalid")
        binding = {"kind": KIND, "attempt_id": attempt_id, "server_instance": marker["instance_id"],
                   "pid": marker["pid"], "created_at": marker["created_at"],
                   "owner_pid": child.pid, "owner_created_at": child.created_at}
        if not _binding(binding):
            raise McpLifecycleError("mcp_member_binding_invalid")
        observation = processes.observe_owned_member(child, marker["pid"], marker["created_at"])
        initial = _snapshot(observation)
        if not _matches(initial, binding, exited=False):
            raise McpLifecycleError("mcp_live_member_handle_required")
        _write_new(directory / "mcp-process-start.json",
                   {**binding, "phase": "start", "observed_at": _utc(), "process": initial})
        return observation, binding
    except McpLifecycleError:
        _close(observation)
        raise
    except (OSError, ValueError, RuntimeError, TypeError, AttributeError, KeyError):
        _close(observation)
        raise McpLifecycleError("mcp_member_binding_unconfirmed") from None


def finish_mcp_observation(observation, binding, directory):
    """Save the held HANDLE snapshot, including unknown/failed exits, then close it."""
    try:
        if not _binding(binding):
            raise McpLifecycleError("mcp_member_binding_invalid")
        snapshot = _snapshot(observation)
        _write_new(_guard(directory) / "mcp-process-exit.json",
                   {**binding, "phase": "exit", "observed_at": _utc(), "process": snapshot})
        return snapshot
    except McpLifecycleError:
        raise
    except (OSError, ValueError, RuntimeError, TypeError, AttributeError, KeyError):
        raise McpLifecycleError("mcp_member_exit_evidence_unconfirmed") from None
    finally:
        _close(observation)


def assess_mcp_exit(directory, attempt_id):
    """Pure read of raw capture/marker/HANDLE proof; missing legacy proof stays false."""
    errors = []
    result = {"passed": False, "mcp_natural_exit_verified": False, "evidence_errors": errors,
              "scope": "saved owned CLI Job member HANDLE and flushed-ACK lifecycle evidence"}
    if not _token(attempt_id):
        errors.append("invalid_mcp_attempt")
        return result
    try:
        directory = _guard(directory)
        capture_start = read_json(directory / "capture-start.json")
        capture_exit = read_json(directory / "capture-exit.json")
        started = read_json(directory / "mcp-server-started.json", limit=LIMIT)
        listed = read_json(directory / "mcp-tools-listed.json", limit=LIMIT)
        ended = read_json(directory / "mcp-stdio-exit.json", limit=LIMIT)
        process_start = read_json(directory / "mcp-process-start.json", limit=LIMIT)
        process_exit = read_json(directory / "mcp-process-exit.json", limit=LIMIT)
        if validate_receipt(capture_exit, capture_start, attempt_id, require_success=True):
            errors.append("natural_successful_cli_capture_required")
        if not all(_marker(marker, phase) for marker, phase in
                   ((started, "server-started"), (listed, "tools-listed"), (ended, "stdio-exit"))):
            errors.append("mcp_phase_markers_invalid")
        if any(any(marker.get(field) != started.get(field) for field in ("instance_id", "pid", "created_at"))
               for marker in (listed, ended)):
            errors.append("mcp_phase_identity_mismatch")
        names = listed.get("tool_names")
        if (type(names) is not list or len(names) != 3 or any(type(name) is not str for name in names)
                or set(names) != {"receive_event", "query_evidence", "ack_event"}
                or type(listed.get("tool_count")) is not int or listed["tool_count"] != 3
                or listed.get("response_prepared") is not True):
            errors.append("exact_inbox_tools_required")
        if (type(ended.get("return_code")) is not int or ended["return_code"] != 0
                or ended.get("stdio_entered") is not True or ended.get("ack_response_flushed") is not True
                or ended.get("os_exit_verified") is not False):
            errors.append("successful_flushed_ack_stdio_exit_required")
        expected = {"kind": KIND, "attempt_id": attempt_id, "server_instance": started.get("instance_id"),
                    "pid": started.get("pid"), "created_at": started.get("created_at"),
                    "owner_pid": capture_start.get("codex_pid"), "owner_created_at": capture_start.get("created_at")}
        if not _binding(expected) or any(any(record.get(field) != expected[field] for field in BINDING_FIELDS)
                                       for record in (process_start, process_exit)):
            errors.append("mcp_capture_owner_binding_mismatch")
        if process_start.get("phase") != "start" or not _matches(process_start.get("process"), expected, exited=False):
            errors.append("mcp_live_original_handle_required")
        if process_exit.get("phase") != "exit" or not _matches(process_exit.get("process"), expected, exited=True):
            errors.append("mcp_natural_zero_exit_unconfirmed")
        code = (process_exit.get("process") or {}).get("exit_code")
        result.update(attempt_id=attempt_id, ack_response_flushed=ended.get("ack_response_flushed") is True,
                      mcp_exit_code=code if type(code) is int and -(2**31) <= code <= 0xFFFFFFFF else None)
    except (OSError, ValueError, RuntimeError, TypeError, AttributeError, KeyError, OverflowError):
        errors.append("mcp_lifecycle_evidence_missing_or_invalid")
    result["passed"] = result["mcp_natural_exit_verified"] = not errors
    return result
