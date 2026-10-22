"""Pure MCP Events metadata and synthetic stored-evidence projections.

No native collector, model, filesystem, service, or network is invoked here.
Reference: https://developers.openai.com/plugins/build/mcp-events
and https://developers.openai.com/plugins/build/mcp-server .
"""
from __future__ import annotations

import json
import re

from eventguard.events.schema import STATUS_VALUES
from eventguard.events.projection import (ProtocolValidationError, project_event, EVENT_NAME,
    EVENT_TYPES, MAX_ENVELOPE_BYTES, _BINDINGS, _SOURCES)

PROTOCOL_VERSION = "2026-07-28"
OPERATIONS = ("health", "query_listener", "query_defender", "query_persistence")
DECISIONS = ("needs_more_evidence", "benign_change", "requires_user_approval")
REASON_CODES = ("synthetic_evidence_reviewed", "coverage_incomplete", "no_matching_evidence")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")




def _identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ProtocolValidationError("invalid_identifier")
    return value


def _object(value, required, optional=()):
    if not isinstance(value, dict):
        raise ProtocolValidationError("arguments_must_be_object")
    if not set(required).issubset(value) or set(value) - set(required) - set(optional):
        raise ProtocolValidationError("invalid_argument_keys")
    return value


def _max_rows(value):
    if type(value) is not int or not 1 <= value <= 20:
        raise ProtocolValidationError("invalid_max_rows")
    return value


def _enum(value, values):
    if not isinstance(value, str) or value not in values:
        raise ProtocolValidationError("invalid_enum")
    return value


def _id_schema():
    return {"type": "string", "minLength": 1, "maxLength": 160,
            "pattern": r"^[A-Za-z0-9_.:-]{1,160}$"}


def _object_schema(properties, required):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


def _evidence_schema():
    return _object_schema({
        "protocol": {"type": "string", "enum": ["TCP", "UDP"]},
        "port": {"type": "integer", "minimum": 0, "maximum": 65535},
        "binding_scope": {"type": "string", "enum": list(_BINDINGS)},
        "source": {"type": "string", "enum": list(_SOURCES)},
        "status": {"type": "string", "enum": sorted(STATUS_VALUES)},
        "current": {"type": "boolean"},
    }, [])


def _payload_schema():
    return _object_schema({
        "schema_version": {"type": "string", "const": "2.0"},
        "host_ref": _id_schema(), "episode_id": _id_schema(),
        "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
        "transition": {"type": "string", "enum": ["new", "escalated", "resolved"]},
        "severity": {"type": "string", "enum": ["info", "warning", "high", "critical"]},
        "evidence": _evidence_schema(),
        "coverage_status": {"type": "string", "enum": sorted(STATUS_VALUES)},
        "synthetic": {"type": "boolean", "const": True},
    }, ["schema_version", "host_ref", "episode_id", "event_type", "transition",
        "severity", "evidence", "coverage_status", "synthetic"])


def event_definition():
    """One fresh event definition for result.events in events/list.

    payloadSchema describes only the envelope's data object. Empty event_types
    means all supported types, scoped to the required opaque host_ref.
    """
    return {
        "name": EVENT_NAME,
        "description": "Stored synthetic EventGuard security-change summaries for one opaque host reference. No current system query or remediation.",
        "delivery": ["webhook"],
        "inputSchema": _object_schema({
            "host_ref": _id_schema(),
            "event_types": {"type": "array", "items": {"type": "string", "enum": list(EVENT_TYPES)},
                            "maxItems": len(EVENT_TYPES), "uniqueItems": True, "default": []},
        }, ["host_ref"]),
        "payloadSchema": _payload_schema(),
    }


def validate_arguments(args):
    """Validate subscription arguments without coercion or unknown fields."""
    args = _object(args, ("host_ref",), ("event_types",))
    types = args.get("event_types", [])
    if not isinstance(types, list) or len(types) > len(EVENT_TYPES):
        raise ProtocolValidationError("invalid_event_types")
    for value in types:
        _enum(value, EVENT_TYPES)
    if len(set(types)) != len(types):
        raise ProtocolValidationError("duplicate_event_types")
    return {"host_ref": _identifier(args["host_ref"]), "event_types": sorted(types)}






def _result_record_schema():
    return _object_schema({
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "evidence_request_ids": {"type": "array", "items": _id_schema(),
                                 "maxItems": 10, "uniqueItems": True},
        "reason_code": {"type": "string", "enum": list(REASON_CODES)},
        "run_ref": _id_schema(), "expected_result_id": _id_schema(),
    }, ["decision", "evidence_request_ids", "reason_code"])


def _query_result_schema():
    row = _evidence_schema()
    row["properties"].update({
        "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
        "transition": {"type": "string", "enum": ["new", "escalated", "resolved"]},
        "severity": {"type": "string", "enum": ["info", "warning", "high", "critical"]},
        "coverage_status": {"type": "string", "enum": sorted(STATUS_VALUES)},
    })
    row["required"] = ["event_type", "transition", "severity", "coverage_status"]
    properties = {
        "schema_version": {"type": "string", "const": "1.0"},
        "event_id": _id_schema(), "request_id": _id_schema(),
        "operation": {"type": "string", "enum": list(OPERATIONS)},
        "source": {"type": "string", "const": "eventguard_synthetic_evidence"},
        "status": {"type": "string", "enum": ["ok", "partial", "unknown"]},
        "observed_at": {"type": "string", "format": "date-time"},
        "coverage_status": {"type": "string", "enum": sorted(STATUS_VALUES)},
        "synthetic": {"type": "boolean", "const": True},
        "snapshot_only": {"type": "boolean", "const": True},
        "system_query_executed": {"type": "boolean", "const": False},
        "rows": {"type": "array", "items": row, "maxItems": 20},
        "truncated": {"type": "boolean"},
        "reason_code": {"type": "string", "enum": ["stored_synthetic_evidence", "coverage_incomplete",
                                                    "no_matching_evidence", "no_usable_evidence"]},
    }
    return _object_schema(properties, list(properties))


def _tool_output_schema(name):
    if name == "eventguard_get_event":
        return _object_schema({
            "event": _payload_schema(),
            "evidence_source": {"type": "string", "const": "persisted_synthetic_event"},
            "current_system_query": {"type": "boolean", "const": False},
        }, ["event", "evidence_source", "current_system_query"])
    if name == "eventguard_query_evidence":
        return _query_result_schema()
    properties = {
        "event_id": _id_schema(), "result_id": _id_schema(),
        "status": {"type": "string", "const": "agent_result_recorded"},
        "result": _result_record_schema(),
        "recorded_at": {"type": "number"},
        "platform_run_verified": {"type": "boolean", "const": False},
        "system_actions_performed": {"type": "boolean", "const": False},
    }
    result = _object_schema(properties, list(properties))
    # Store may add ledger metadata; the handler still minimizes its response.
    result["additionalProperties"] = True
    return result


def tool_definitions():
    """Exact bounded input schemas; annotations describe actual tool behavior.

    Recording a result is a write to EventGuard's own idempotent result ledger;
    it never authorizes or performs a host action.
    """
    specs = [
        ("eventguard_get_event", "Read stored synthetic event",
         "Read one stored synthetic event summary by ID. No current host query.",
         _object_schema({"event_id": _id_schema()}, ["event_id"]), True),
        ("eventguard_query_evidence", "Query stored synthetic evidence",
         "Read bounded evidence from the synthetic event snapshot only. Does not query the current host or assert safety.",
         _object_schema({
             "event_id": _id_schema(), "request_id": _id_schema(),
             "operation": {"type": "string", "enum": list(OPERATIONS)},
             "max_rows": {"type": "integer", "minimum": 1, "maximum": 20, "default": 20},
         }, ["event_id", "request_id", "operation"]), True),
        ("eventguard_record_result", "Record synthetic evidence review",
         "Record an idempotent decision in EventGuard's own ledger. Does not change host protection or grant permission for remediation.",
         _object_schema({
             "event_id": _id_schema(),
             "decision": {"type": "string", "enum": list(DECISIONS)},
             "evidence_request_ids": {"type": "array", "items": _id_schema(),
                                      "maxItems": 10, "uniqueItems": True},
             "reason_code": {"type": "string", "enum": list(REASON_CODES)},
             "run_ref": _id_schema(), "expected_result_id": _id_schema(),
         }, ["event_id", "decision", "evidence_request_ids", "reason_code"]), False),
    ]
    return [{"name": name, "title": title, "description": description,
             "inputSchema": schema,
             "outputSchema": _tool_output_schema(name),
             "annotations": {"readOnlyHint": readonly, "destructiveHint": False,
                             "openWorldHint": False, "idempotentHint": True}}
            for name, title, description, schema, readonly in specs]


def validate_tool_arguments(name, args):
    """Validate the selected typed operation, never shell text or free-form reason."""
    if name == "eventguard_get_event":
        args = _object(args, ("event_id",))
        return {"event_id": _identifier(args["event_id"])}
    if name == "eventguard_query_evidence":
        args = _object(args, ("event_id", "request_id", "operation"), ("max_rows",))
        return {"event_id": _identifier(args["event_id"]),
                "request_id": _identifier(args["request_id"]),
                "operation": _enum(args["operation"], OPERATIONS),
                "max_rows": _max_rows(args.get("max_rows", 20))}
    if name == "eventguard_record_result":
        args = _object(args, ("event_id", "decision", "evidence_request_ids", "reason_code"), ("run_ref", "expected_result_id"))
        references = args["evidence_request_ids"]
        if not isinstance(references, list) or len(references) > 10:
            raise ProtocolValidationError("invalid_evidence_request_ids")
        clean_refs = [_identifier(value) for value in references]
        if len(set(clean_refs)) != len(clean_refs):
            raise ProtocolValidationError("duplicate_evidence_request_ids")
        if args["decision"] == "benign_change" and not clean_refs:
            raise ProtocolValidationError("benign_change_requires_evidence")
        result = {"event_id": _identifier(args["event_id"]),
                  "decision": _enum(args["decision"], DECISIONS),
                  "evidence_request_ids": sorted(clean_refs),
                  "reason_code": _enum(args["reason_code"], REASON_CODES)}
        if "run_ref" in args:
            result["run_ref"] = _identifier(args["run_ref"])
        if "expected_result_id" in args:
            result["expected_result_id"] = _identifier(args["expected_result_id"])
        return result
    raise ProtocolValidationError("unknown_tool")


def query_snapshot(event, operation, max_rows=20):
    """Diagnostic-result 1.0 using only the stored, synthetic event snapshot.

    health describes that event's coverage only, never whole-machine health.
    The caller may add its already validated request_id before persistence.
    No matching type or no usable typed evidence yields unknown, not safe.
    """
    operation = _enum(operation, OPERATIONS)
    _max_rows(max_rows)
    envelope = project_event(event)
    data = envelope["data"]
    expected = {"query_listener": "listener.changed", "query_defender": "protection.changed",
                "query_persistence": "persistence.changed"}
    rows = []
    status = "unknown"
    reason = "no_matching_evidence"
    if operation == "health" or expected.get(operation) == data["event_type"]:
        evidence = data["evidence"]
        if operation == "health" or evidence:
            row = {"event_type": data["event_type"], "transition": data["transition"],
                   "severity": data["severity"], "coverage_status": data["coverage_status"]}
            row.update(evidence)
            rows = [row]
            status = "ok" if data["coverage_status"] == "ok" else "partial"
            reason = "stored_synthetic_evidence" if status == "ok" else "coverage_incomplete"
        else:
            reason = "no_usable_evidence"
    return {
        "schema_version": "1.0", "event_id": envelope["eventId"],
        "operation": operation, "source": "eventguard_synthetic_evidence",
        "status": status, "observed_at": envelope["timestamp"],
        "coverage_status": data["coverage_status"], "synthetic": True,
        "snapshot_only": True, "system_query_executed": False,
        "rows": rows[:max_rows], "truncated": len(rows) > max_rows,
        "reason_code": reason,
    }
