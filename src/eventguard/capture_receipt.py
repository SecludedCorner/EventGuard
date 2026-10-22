"""Validate saved Windows capture proof without reading files or trusting claims.

The default policy proves only that the identified owned process tree exited.
It deliberately permits a failed/truncated/forced capture so a known failed task
can release an active-task gate. ``require_success=True`` additionally requires
complete, untruncated evidence and a natural successful CLI exit. Neither policy
proves tool delivery, an ACK, model execution, or the truth of mutable local files.
"""
from __future__ import annotations

from datetime import datetime
import re


_ATTEMPT = re.compile(r"[a-f0-9]{32}\Z")
_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")


def _pid(value):
    return type(value) is int and 1 <= value <= 0xFFFFFFFF


def _exit_code(value):
    # Accept signed and unsigned 32-bit representations, never bool or unknown.
    return type(value) is int and -(2**31) <= value <= 0xFFFFFFFF


def _created_at(value):
    if type(value) is not str or not 20 <= len(value) <= 64 or not _TIME.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.utcoffset() is not None
    except (ValueError, OverflowError):
        return False


def validate_receipt(receipt, started, attempt_id, *, require_success=False) -> list[str]:
    """Return fixed error codes; only an empty list is valid under the policy.

    ``started`` is capture-start.json, ``receipt`` is capture-exit.json. Creation
    identity lives in started.created_at and receipt.process.created_at in the
    actual writer schema. Missing legacy fields remain unknown; do not invent
    them to upgrade an old receipt. Inputs must be ordinary JSON dictionaries.
    """
    if type(require_success) is not bool:
        return ["invalid_capture_receipt_policy"]
    if type(receipt) is not dict or type(started) is not dict:
        return ["capture_receipt_or_start_missing"]
    errors = []
    if type(attempt_id) is not str or not _ATTEMPT.fullmatch(attempt_id):
        errors.append("invalid_expected_capture_attempt")
    if (type(receipt.get("attempt_id")) is not str or receipt.get("attempt_id") != attempt_id
            or type(started.get("attempt_id")) is not str or started.get("attempt_id") != attempt_id):
        errors.append("capture_attempt_mismatch")
    pid = started.get("codex_pid")
    if (not _pid(pid) or not _pid(receipt.get("codex_pid")) or receipt.get("codex_pid") != pid):
        errors.append("capture_pid_mismatch")
    created = started.get("created_at")
    if not _created_at(created):
        errors.append("capture_creation_time_missing")
    process = receipt.get("process")
    if type(process) is not dict:
        errors.append("owned_process_receipt_missing")
        process = {}
    if process.get("managed") is not True:
        errors.append("owned_job_not_verified")
    if not _pid(process.get("pid")) or process.get("pid") != pid:
        errors.append("owned_process_pid_mismatch")
    if not _created_at(process.get("created_at")) or process.get("created_at") != created:
        errors.append("owned_process_creation_time_mismatch")
    if receipt.get("child_exited") is not True or process.get("child_exited") is not True:
        errors.append("owned_child_exit_unconfirmed")
    if (type(process.get("remaining_owned_processes")) is not int
            or process.get("remaining_owned_processes") != 0):
        errors.append("owned_tree_exit_unconfirmed")
    code, process_code = receipt.get("codex_exit_code"), process.get("exit_code")
    if not _exit_code(code) or not _exit_code(process_code) or process_code != code:
        errors.append("owned_root_exit_code_unconfirmed")
    if require_success:
        if receipt.get("capture_complete") is not True:
            errors.append("capture_incomplete")
        if receipt.get("stdout_truncated") is not False or receipt.get("stderr_truncated") is not False:
            errors.append("capture_truncated_or_unknown")
        if receipt.get("forcibly_terminated") is not False or process.get("forcibly_terminated") is not False:
            errors.append("owned_tree_forced_or_unknown")
        if (receipt.get("stop_reason") != "descendants_remaining" or process.get("reason") != "natural_exit"
                or process.get("shutdown_requested_reason") != "descendants_remaining"):
            errors.append("natural_capture_exit_not_verified")
        if type(code) is not int or code != 0:
            errors.append("cli_not_completed_successfully")
    return errors
