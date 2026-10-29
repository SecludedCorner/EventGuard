"""Shared, bounded collector contract. Error text and object names are not evidence codes."""
from __future__ import annotations

import re
from collections import Counter
from typing import Protocol


class CollectorBackend(Protocol):
    name: str

    def collect(self, section_id: str, cancel=None, progress=None) -> dict:
        """Return a backend payload; WindowsCollectors validates the shared envelope."""
        ...

SECTION_IDS = ("defender", "listeners", "processes", "startup", "services", "tasks", "versions")
STATUSES = frozenset({"ok", "partial", "denied", "unknown", "not_applicable", "error", "timeout", "cancelled", "busy", "not_requested"})
STAGES = frozenset({"launch", "provider", "object", "field", "policy"})
LIMITS = {"defender": 20, "listeners": 1000, "processes": 2000, "startup": 1000, "services": 500, "tasks": 300, "versions": 10}
FIELDS = {
    "defender": {"item", "value", "status", "authority"},
    "listeners": {"protocol", "address", "port", "pid", "scope", "status", "created_at", "process_instance_ref", "process_identity_status"},
    "processes": {"pid", "name", "path", "path_status", "created_at", "process_instance_ref", "status"},
    "startup": {"source", "name", "registry_view", "kind", "status"},
    "services": {"name", "state", "start_mode", "status"},
    "tasks": {"name", "task_path", "state", "status"},
    "versions": {"product", "version", "path", "status"},
}
MAX_ERRORS = 64
_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_.]{0,95}\Z")


def evidence(stage, reason_code, *, exception_type="UnknownError", win32_error=None,
             hresult=None, operation="collect", status="unknown", provider_code=None, category=None):
    """Copy only typed codes. No exception repr, message, path or username."""
    if stage not in STAGES or status not in STATUSES:
        raise ValueError("invalid_error_classification")
    def code(value):
        return value if isinstance(value, str) and _CODE.fullmatch(value) else "UnknownError"
    def number(value):
        return value if type(value) is int and -(2**31) <= value <= 2**32-1 else None
    provider_code = provider_code if type(provider_code) is int and 0 <= provider_code <= 2**31-1 or isinstance(provider_code, str) and _CODE.fullmatch(provider_code) else None
    category = category if category in ("PermissionDenied", "SecurityError", "ObjectNotFound", "InvalidOperation", "NotSpecified", "ResourceUnavailable", "NotImplemented", "InvalidArgument", "OperationStopped", "ParserError") else None
    return {"stage": stage, "reason_code": code(reason_code), "exception_type": code(exception_type),
            "win32_error": number(win32_error), "hresult": number(hresult),
            "operation": code(operation), "status": status, "provider_code": provider_code, "category": category}


def clean_errors(values):
    if not isinstance(values, list):
        return []
    return [evidence(item.get("stage") if isinstance(item.get("stage"), str) and item.get("stage") in STAGES else "provider",
                     item.get("reason_code", "unknown_failure"),
                     exception_type=item.get("exception_type", "UnknownError"),
                     win32_error=item.get("win32_error"), hresult=item.get("hresult"),
                     provider_code=item.get("provider_code"), category=item.get("category"),
                     operation=item.get("operation", "collect"),
                     status=item.get("status") if isinstance(item.get("status"), str) and item.get("status") in STATUSES else "unknown")
            for item in values[:MAX_ERRORS] if isinstance(item, dict)]


def error_from_exception(error, stage, operation, reason=None):
    win32 = getattr(error, "winerror", None)
    hr = getattr(error, "hresult", None)
    # POSIX errno is not a Win32 error number. Do not translate EACCES to Win32 13.
    denied = isinstance(error, PermissionError) or win32 in (5, 1314, 1260) or hr in (-2147024891, 0x80070005)
    missing = isinstance(error, (FileNotFoundError, NotImplementedError)) or win32 in (2, 3, 50, 126, 127)
    status = "denied" if denied else "not_applicable" if missing else "error"
    if win32 in (1260, 1314):
        stage = "policy"
    return evidence(stage, reason or ("access_denied" if denied else "api_unavailable" if missing else "query_failed"),
                    exception_type=type(error).__name__, win32_error=win32,
                    hresult=hr, operation=operation, status=status)


def error_classifications(errors):
    """Count every error using at most 60 fixed stage/status combinations.

    No operation, reason text, numeric identifier or object metadata is copied.
    Unknown classifications are counted, never inferred from the retained prefix.
    """
    groups, unclassified = Counter(), 0
    for error in errors:
        stage = error.get("stage") if isinstance(error, dict) else None
        status = error.get("status") if isinstance(error, dict) else None
        valid_stage = isinstance(stage, str) and stage in STAGES
        valid_status = isinstance(status, str) and status in STATUSES and status != "ok"
        unclassified += not (valid_stage and valid_status)
        groups[(stage if valid_stage else "unknown", status if valid_status else "unknown")] += 1
    return {"total_count": sum(groups.values()), "unclassified_count": unclassified,
            "groups": [dict(stage=stage, status=status, count=count)
                       for (stage, status), count in sorted(groups.items())]}


def payload(rows=None, errors=None, *, truncated=False, status=None, checks=None):
    rows, raw_errors = list(rows or []), list(errors or [])
    classifications = error_classifications(raw_errors)
    errors = clean_errors(raw_errors)
    if status is None:
        # Missing optional Run/RunOnce keys are a complete observation, not denial.
        states = [r.get("status", "unknown") for r in rows
                  if not (r.get("kind") == "registry_missing" and r.get("status") == "not_applicable")]
        states += [group["status"] for group in classifications["groups"]]
        bad = [s for s in states if s != "ok"]
        status = "ok" if not bad else bad[0] if len(set(bad)) == 1 and not any(s == "ok" for s in states) else "partial"
    if truncated and status == "ok":
        status = "partial"
    return {"status": status, "rows": rows, "truncated": bool(truncated),
            "errors": errors, "error_count": len(raw_errors), "errors_truncated": len(raw_errors) > MAX_ERRORS,
            "error_classifications": classifications,
            "checks": list(checks or [])[:64]}
