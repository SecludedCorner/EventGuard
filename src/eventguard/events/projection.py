"""Pure legacy synthetic projection shared with the optional contrib bridge."""
import json
from .schema import STATUS_VALUES, validate_event

EVENT_NAME = "eventguard.security_change"
MAX_ENVELOPE_BYTES = 8192
EVENT_TYPES = (
    "coverage.degraded", "listener.changed", "persistence.changed", "protection.changed", "monitor_gap",
)
_BINDINGS = ("localhost", "loopback", "lan", "LAN", "link_local", "all_interfaces",
             "global_address", "other_reserved", "unknown")
_SOURCES = ("defender", "antivirus", "listeners", "startup", "services", "tasks",
            "processes", "versions", "coverage", "synthetic", "fixture")


class ProtocolValidationError(ValueError):
    """Fixed reason codes only; no untrusted argument echoed into errors."""


def _enum(value, values):
    if not isinstance(value, str) or value not in values:
        raise ProtocolValidationError("invalid_enum")
    return value


def _safe_evidence(evidence):
    """No arbitrary text survives: field names AND scalar values are allowlisted."""
    result = {}
    if not isinstance(evidence, dict):
        return result
    if evidence.get("protocol") in ("TCP", "UDP"):
        result["protocol"] = evidence["protocol"]
    if type(evidence.get("port")) is int and 0 <= evidence["port"] <= 65535:
        result["port"] = evidence["port"]
    binding = evidence.get("binding_scope", evidence.get("scope"))
    if isinstance(binding, str) and binding in _BINDINGS:
        result["binding_scope"] = binding
    for field, values in (("source", _SOURCES), ("status", STATUS_VALUES)):
        value = evidence.get(field)
        if isinstance(value, str) and value in values:
            result[field] = value
    if type(evidence.get("current")) is bool:
        result["current"] = evidence["current"]
    return result


def project_event(core):
    """Validate core 2.0, reject live data, and minimize for MCP webhook delivery.

    This does not deliver an event. It returns a bounded pure data object.
    Identity is preserved across retries; UTC time is canonicalized by core.
    """
    event = validate_event(core)
    if event["synthetic"] is not True:
        raise ProtocolValidationError("synthetic_only")
    _enum(event["event_type"], EVENT_TYPES)
    envelope = {
        "eventId": event["event_id"], "name": EVENT_NAME,
        "timestamp": event["observed_at"],
        "data": {
            "schema_version": "2.0", "host_ref": event["host_id"],
            "episode_id": event["episode_id"], "event_type": event["event_type"],
            "transition": event["transition"], "severity": event["severity"],
            "evidence": _safe_evidence(event["evidence"]),
            "coverage_status": event["coverage"]["status"], "synthetic": True,
        },
        "cursor": None,
    }
    encoded = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_ENVELOPE_BYTES:
        raise ProtocolValidationError("envelope_size_limit")
    return envelope

