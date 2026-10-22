"""Bounded event 2.0 validation and minimization; no I/O or network activity."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import re

MAX_EVENT_BYTES = 8192
EVENT_FIELDS = frozenset({
    "schema_version", "event_id", "host_id", "episode_id", "correlation_id",
    "sequence", "event_type", "detector", "rule_ref", "transition", "severity",
    "synthetic", "observed_at", "window", "persisted_at", "baseline_version",
    "evidence", "inference", "coverage", "privacy", "evidence_refs",
})
META_FIELDS = frozenset({
    "id", "version", "rule_id", "protocol", "address", "local_address",
    "local_port", "port", "pid", "process_instance_ref", "instance_ref",
    "path", "path_status", "name", "source", "source_name", "item", "property", "value",
    "status", "reason", "summary", "internet_reachability",
    "compromise_conclusion", "gaps", "profile", "redacted", "start", "end",
    "count", "previous", "current", "changed_fields", "detector", "section_id",
    "error_code", "rows", "observed_at", "signature_status", "result_code",
    "query_id", "baseline_ref", "expected", "actual", "enabled", "active",
    "level", "event_id", "provider", "kind", "recovered", "unavailable_fields",
    "truncated", "first_seen", "last_seen", "operation", "data_status",
    "failure_count", "coverage_status", "process_name", "binding_scope",
    "scope", "source_status", "change", "entry_ref", "changed_count",
    "section", "changed_keys", "suppression_count", "expected_count",
    "missing_count",
    "gap_seconds", "process_created_at",
})
FORBIDDEN_PARTS = ("command", "message", "xml", "password", "token", "secret",
                   "credential", "authorization", "username", "user_id",
                   "account", "stderr", "traceback")
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
STATUS_VALUES = frozenset({"ok", "partial", "denied", "unknown", "not_applicable",
                          "error", "timeout", "cancelled", "busy", "not_requested",
                          "stale", "limit_exceeded"})


class EventValidationError(ValueError):
    """Only fixed reason codes are returned; no untrusted values in errors."""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_event_id(*parts):
    """Stable identity helper; callers supply episode/transition identity parts."""
    encoded = json.dumps(parts, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def redact_text(value, limit=512):
    text = str(value)
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    text = re.sub(r"(?i)[a-z]:[\\/]Users[\\/][^\\/\"<>|]+", "%USER_HOME%", text)
    text = re.sub(r"(?i)/(?:Users|home)/[^/\"<>|]+", "%USER_HOME%", text)
    text = re.sub(r"(?i)\b(?:api[_-]?key|password|secret|token|authorization)\s*[:=]\s*[^\s;,]+",
                  "<REDACTED>", text)
    return text[:limit]


def _identifier(value, name):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise EventValidationError("invalid_" + name)
    return value


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        raise EventValidationError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, OverflowError, TypeError):
        raise EventValidationError("invalid_timestamp") from None


def _metadata(value, depth=0):
    if depth > 3:
        raise EventValidationError("metadata_depth_limit")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > 2**63 - 1:
            raise EventValidationError("metadata_number_limit")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EventValidationError("metadata_number_limit")
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (list, tuple)):
        if len(value) > 32:
            raise EventValidationError("metadata_list_limit")
        return [_metadata(item, depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > 32:
            raise EventValidationError("metadata_field_limit")
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            lowered = key.casefold()
            if key not in META_FIELDS or any(part in lowered for part in FORBIDDEN_PARTS):
                continue
            result[key] = _metadata(item, depth + 1)
        return result
    raise EventValidationError("unsupported_metadata_type")


def _reference(value, id_name):
    if not isinstance(value, dict):
        raise EventValidationError("invalid_reference")
    identity = _identifier(value.get(id_name), id_name)
    version = value.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}", version):
        raise EventValidationError("invalid_reference_version")
    return {id_name: identity, "version": version}


def validate_event(event):
    """Return an allowlisted event, rejecting invalid identity and large payloads.

    Unknown top-level/metadata fields are dropped. Immutable identifiers are not
    truncated or rewritten. Message/command/secret fields never cross this API.
    This validator minimizes metadata; it is not an authority or a malware test.
    """
    if not isinstance(event, dict) or len(event) > 64:
        raise EventValidationError("event_must_be_bounded_dictionary")
    if event.get("schema_version") != "2.0":
        raise EventValidationError("unsupported_event_schema")
    clean = {"schema_version": "2.0"}
    for field in ("event_id", "host_id", "episode_id", "correlation_id", "event_type"):
        clean[field] = _identifier(event.get(field), field)
    sequence = event.get("sequence")
    if type(sequence) is not int or not 1 <= sequence <= 2**53 - 1:
        raise EventValidationError("invalid_sequence")
    clean["sequence"] = sequence
    if not isinstance(event.get("transition"), str) or event["transition"] not in {"new", "escalated", "resolved"}:
        raise EventValidationError("invalid_transition")
    clean["transition"] = event["transition"]
    if not isinstance(event.get("severity"), str) or event["severity"] not in {"info", "warning", "high", "critical"}:
        raise EventValidationError("invalid_severity")
    clean["severity"] = event["severity"]
    if type(event.get("synthetic")) is not bool:
        raise EventValidationError("invalid_synthetic_flag")
    clean["synthetic"] = event["synthetic"]
    clean["observed_at"] = _timestamp(event.get("observed_at"))
    clean["persisted_at"] = _timestamp(event.get("persisted_at"))
    clean["detector"] = _reference(event.get("detector", {"id":"unspecified", "version":"0"}), "id")
    clean["rule_ref"] = _reference(event.get("rule_ref", {"rule_id":"unassigned", "version":"0"}), "rule_id")
    window = event.get("window", {"start":clean["observed_at"], "end":clean["observed_at"]})
    if not isinstance(window, dict):
        raise EventValidationError("invalid_window")
    start, end = _timestamp(window.get("start")), _timestamp(window.get("end"))
    if start > end:
        raise EventValidationError("invalid_window_order")
    clean["window"] = {"start":start, "end":end}
    baseline = event.get("baseline_version", "uninitialized")
    clean["baseline_version"] = _identifier(baseline, "baseline_version")
    evidence = event.get("evidence", {})
    if not isinstance(evidence, dict):
        raise EventValidationError("invalid_evidence")
    clean["evidence"] = _metadata(evidence)
    inference = event.get("inference", {"summary":"Observation only; compromise is undetermined.", "compromise_conclusion":"undetermined"})
    if not isinstance(inference, (str, dict)):
        raise EventValidationError("invalid_inference")
    clean["inference"] = _metadata(inference)
    coverage = event.get("coverage", {"status":"unknown", "gaps":[]})
    if not isinstance(coverage, dict) or not isinstance(coverage.get("status"), str) or coverage["status"] not in STATUS_VALUES:
        raise EventValidationError("invalid_coverage")
    clean["coverage"] = _metadata(coverage)
    privacy = event.get("privacy", {"profile":"minimal-v1", "redacted":True})
    if not isinstance(privacy, dict) or privacy.get("redacted") is not True:
        raise EventValidationError("invalid_privacy_profile")
    clean["privacy"] = {"profile":redact_text(privacy.get("profile", "minimal-v1"), 64), "redacted":True}
    refs = event.get("evidence_refs", [])
    if not isinstance(refs, list) or len(refs) > 16:
        raise EventValidationError("invalid_evidence_refs")
    clean["evidence_refs"] = [_identifier(ref, "evidence_ref") for ref in refs]
    encoded = json.dumps(clean, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_EVENT_BYTES:
        raise EventValidationError("event_size_limit")
    return clean
