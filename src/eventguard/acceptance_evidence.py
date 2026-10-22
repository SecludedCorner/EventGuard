"""Pure, bounded validation of one CLI attempt against durable synthetic evidence.

This module performs no I/O and never treats agent prose or a stored ACK alone as
proof of model execution. Callers must supply this attempt's real CLI JSONL and
validate filesystem/process ownership separately.
"""
from __future__ import annotations

from datetime import datetime
import json
import math
import re

MAX_TRACE_ROWS = 4096
MAX_RESULT_CHARS = 65536
MAX_EVENTS = 64
MAX_WAITS = 128
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_KIND = "eventguard-single-synthetic-local-wait-experiment"
_TOOLS = ("wait_for_event", "query_evidence", "ack_event")
_RESULT_KEYS = {"status", "event_id", "query_id", "decision", "result_id", "recorded_at",
                "incident_conclusion", "real_agent_wake_verified", "experiment_only"}


def _identifier(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _stamp(value):
    if type(value) is not str or len(value) > 64:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp if stamp.tzinfo is not None and stamp.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _wait(value):
    if not isinstance(value, dict) or not _identifier(value.get("wait_id")):
        return False
    if set(value) - {"wait_id", "status", "started_at", "finished_at", "duration_seconds"}:
        return False
    if value.get("status") not in {"waiting", "event_available", "wait_expired", "cancelled", "error"}:
        return False
    started = _stamp(value.get("started_at"))
    if started is None:
        return False
    if value["status"] == "waiting":
        return set(value) == {"wait_id", "status", "started_at"}
    finished = _stamp(value.get("finished_at"))
    duration = value.get("duration_seconds")
    return (finished is not None and finished >= started and type(duration) in (int, float)
            and math.isfinite(duration) and 0 <= duration < 86400)


def _stored_result(value, identity, query_id):
    return (isinstance(value, dict) and set(value) == _RESULT_KEYS
            and value.get("status") == "synthetic_result_recorded"
            and value.get("event_id") == identity and value.get("query_id") == query_id
            and value.get("decision") in {"reviewed_synthetic", "needs_more_evidence"}
            and _identifier(value.get("result_id")) and _stamp(value.get("recorded_at")) is not None
            and value.get("incident_conclusion") == "not_assessed"
            and value.get("real_agent_wake_verified") is False and value.get("experiment_only") is True)


def _event_record(value, identity):
    if not isinstance(value, dict) or set(value) - {"event", "delivered_at", "query_id", "queried_at", "result"}:
        return False
    envelope = value.get("event")
    if (not isinstance(envelope, dict) or envelope.get("eventId") != identity
            or not isinstance(envelope.get("data"), dict) or envelope["data"].get("synthetic") is not True
            or _stamp(value.get("delivered_at")) is None):
        return False
    if "query_id" in value and (not _identifier(value["query_id"]) or _stamp(value.get("queried_at")) is None):
        return False
    if "queried_at" in value and "query_id" not in value:
        return False
    return "result" not in value or (_identifier(value.get("query_id"))
                                    and _stored_result(value["result"], identity, value["query_id"]))


def _tool_result(item):
    result = item.get("result")
    if not isinstance(result, dict):
        return None
    structured = result.get("structured_content", result.get("structuredContent"))
    if structured is not None and not isinstance(structured, dict):
        return None
    content = result.get("content")
    parsed = None
    if content is not None:
        if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
            return None
        block = content[0]
        raw = block.get("text")
        if block.get("type") != "text" or type(raw) is not str or len(raw) > MAX_RESULT_CHARS:
            return None
        try:
            parsed = json.loads(raw)
        except (ValueError, RecursionError):
            return None
        if not isinstance(parsed, dict):
            return None
    if structured is not None and parsed is not None and structured != parsed:
        return None
    return structured if structured is not None else parsed


def _assess(trace, ledger, event_id, exit_code, acknowledged, *, wait_ids_before=()):
    """Fail closed on malformed/partial evidence; return only current attempt waits.

    ``wait_ids_before`` is the caller's persisted baseline before starting a retry.
    Historic waits remain in the ledger but cannot satisfy this attempt's proof.
    """
    errors = []
    calls = []
    waits = []
    record = {}
    result = {}
    if not _identifier(event_id):
        errors.append("event_id_missing_or_invalid")
    if type(exit_code) is not int or exit_code != 0:
        errors.append("cli_not_completed_successfully")
    if acknowledged is not True:
        errors.append("durable_ack_missing")
    before_valid = (isinstance(wait_ids_before, (list, tuple, set, frozenset))
                    and len(wait_ids_before) <= MAX_WAITS
                    and all(_identifier(value) for value in wait_ids_before))
    if not before_valid:
        errors.append("invalid_wait_baseline")
    before = set(wait_ids_before) if before_valid else set()
    ledger_valid = (isinstance(ledger, dict)
                    and ledger.get("schema_version") == "1.0" and ledger.get("kind") == _KIND
                    and _identifier(ledger.get("experiment_id"))
                    and isinstance(ledger.get("events"), dict) and len(ledger["events"]) <= MAX_EVENTS
                    and isinstance(ledger.get("waits"), list) and len(ledger["waits"]) <= MAX_WAITS)
    if ledger_valid:
        ledger_valid = (all(_identifier(key) and _event_record(value, key) for key, value in ledger["events"].items())
                        and all(_wait(value) for value in ledger["waits"]))
    if ledger_valid:
        all_wait_ids = [value["wait_id"] for value in ledger["waits"]]
        ledger_valid = len(set(all_wait_ids)) == len(all_wait_ids)
    if ledger_valid:
        waits = [value for value in ledger["waits"] if value["wait_id"] not in before]
        record = ledger["events"].get(event_id, {})
        result = record.get("result", {})
        if len(waits) != 1 or waits[0].get("status") != "event_available":
            errors.append("one_new_completed_wait_required")
        if (not record or not result or result.get("decision") != "reviewed_synthetic"):
            errors.append("durable_review_result_missing")
    else:
        errors.append("invalid_durable_ledger")
    if not isinstance(trace, list) or len(trace) > MAX_TRACE_ROWS:
        errors.append("invalid_or_oversized_cli_trace")
    else:
        turns = 0
        started_ids = []
        for row in trace:
            if not isinstance(row, dict):
                errors.append("invalid_cli_trace_row")
                continue
            event_type = row.get("type")
            if event_type in {"turn.failed", "error"}:
                errors.append("cli_reported_failure")
            if event_type == "turn.completed":
                turns += 1
            if event_type in {"item.started", "item.completed", "item.updated"}:
                item = row.get("item")
                if not isinstance(item, dict):
                    errors.append("invalid_cli_item")
                    continue
                if item.get("type") not in {"mcp_tool_call", "agent_message", "reasoning", "todo_list"}:
                    errors.append("unexpected_cli_action")
                if item.get("type") == "mcp_tool_call":
                    if item.get("server") != "eventguard_local" or item.get("tool") not in _TOOLS:
                        errors.append("unexpected_mcp_tool")
                    if event_type == "item.started":
                        started_ids.append(item.get("id"))
                    if event_type == "item.completed":
                        calls.append(item)
        if turns != 1:
            errors.append("one_completed_cli_turn_required")
        if len(calls) != 3 or [value.get("tool") for value in calls] != list(_TOOLS):
            errors.append("wait_query_ack_sequence_required")
        if started_ids and (len(started_ids) != 3 or not all(_identifier(value) for value in started_ids)
                            or len(set(started_ids)) != 3
                            or started_ids != [value.get("id") for value in calls]):
            errors.append("incomplete_or_repeated_mcp_call")
        replies = []
        for call in calls:
            if call.get("status") != "completed" or call.get("error") is not None:
                errors.append("mcp_call_failed")
            replies.append(_tool_result(call))
        if len(calls) == 3:
            arguments = [value.get("arguments") for value in calls]
            expected_args = [{"timeout_seconds": 30}, {"event_id": event_id},
                             {"event_id": event_id, "query_id": record.get("query_id"), "decision": "reviewed_synthetic"}]
            if arguments != expected_args:
                errors.append("mcp_arguments_mismatch")
            if not all(isinstance(value, dict) for value in replies):
                errors.append("mcp_returned_evidence_missing")
            else:
                waited, queried, acked = replies
                if (len(waits) != 1 or waited.get("status") != "event_available"
                        or waited.get("event_id") != event_id or waited.get("event") != record.get("event")
                        or any(waited.get(key) != waits[0].get(key) for key in
                               ("wait_id", "started_at", "finished_at", "duration_seconds"))):
                    errors.append("wait_return_does_not_match_ledger")
                if (queried.get("status") != "synthetic_snapshot" or queried.get("event_id") != event_id
                        or queried.get("query_id") != record.get("query_id")
                        or queried.get("event") != record.get("event") or queried.get("snapshot_only") is not True
                        or queried.get("system_query_executed") is not False):
                    errors.append("query_return_does_not_match_ledger")
                if not result or acked != {**result, "outbox_acknowledged": True}:
                    errors.append("ack_return_does_not_match_ledger")
    return {"passed": not errors, "completed_tools": [value.get("tool") if value.get("tool") in _TOOLS
                                                       else "unexpected_tool" for value in calls],
            "waits": waits, "event_id": event_id if _identifier(event_id) else None,
            "query_id": record.get("query_id"), "result": result,
            "outbox_acknowledged": acknowledged is True, "codex_exit_code": exit_code if type(exit_code) is int else None,
            "idle_model_requests": "not_observable_from_cli_jsonl; no zero-usage claim",
            "desktop_task_resumed": False, "synthetic_only": True,
            "evidence_errors": list(dict.fromkeys(errors))}


def assess(trace, ledger, event_id, exit_code, acknowledged, *, wait_ids_before=()):
    """Public fail-closed boundary for untrusted decoded CLI and ledger objects."""
    try:
        return _assess(trace, ledger, event_id, exit_code, acknowledged,
                       wait_ids_before=wait_ids_before)
    except (AttributeError, TypeError, ValueError, OverflowError, RecursionError):
        return {"passed": False, "completed_tools": [], "waits": [],
                "event_id": event_id if _identifier(event_id) else None,
                "query_id": None, "result": {}, "outbox_acknowledged": acknowledged is True,
                "codex_exit_code": exit_code if type(exit_code) is int else None,
                "idle_model_requests": "not_observable_from_cli_jsonl; no zero-usage claim",
                "desktop_task_resumed": False, "synthetic_only": True,
                "evidence_errors": ["malformed_evidence"]}
