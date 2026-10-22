"""Deterministic event-bound observations shared by people and optional tools.

No model, command, action, ACK or implicit live query. Names are data; paths and
unrestricted text are never projected into this interface.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import re

from .api import DiagnosticAPI, valid_iso
from ..collectors.windows import coverage_metadata
from ..events.schema import validate_event, STATUS_VALUES
from ..events.store import event_payload_hash

EVENT_TYPES = {"listener.changed", "protection.changed", "persistence.changed", "coverage.degraded"}
EXPLANATIONS = {
    "listener.changed": "觀測到本機端點變化；全介面綁定不代表 Internet 可達。",
    "protection.changed": "觀測到防護 metadata 變化；需區分設定與實際有效狀態。",
    "persistence.changed": "觀測到啟動／服務／排程 metadata 變化；不能單憑新增判惡意。",
    "coverage.degraded": "監看可見性降低；沒有事件不能視為沒有風險。",
}
KINDS = {"startup", "services", "tasks"}
NAME = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")
REF = re.compile(r"proc-[a-f0-9]{24}\Z")
PROTECTION = {"AntivirusEnabled", "RealTimeProtectionEnabled", "AMServiceEnabled", "BehaviorMonitorEnabled", "IsTamperProtected"}
SOURCES = {"listeners", "processes", "defender", "startup", "services", "tasks", "versions"}


def number(value, maximum=2**32-1):
    return value if type(value) is int and 0 <= value <= maximum else None


def enum(value, choices, default="unknown"):
    return value if type(value) is str and value in choices else default


def row_view(row):
    """Fixed scalar vocabulary, not a generic redact-and-forward operation."""
    result = {}
    for key, choices in {
        "protocol": {"TCP", "UDP"}, "scope": {"all_interfaces", "localhost", "lan", "global", "link_local", "other_reserved"},
        "binding_scope": {"all_interfaces", "localhost", "lan", "global", "link_local", "other_reserved"},
        "status": STATUS_VALUES, "kind": KINDS,
        "section": SOURCES, "source": SOURCES | {"synthetic_collector", "synthetic_fixture"}, "property": PROTECTION,
        "state": {"running", "stopped", "paused", "start_pending", "stop_pending", "continue_pending", "pause_pending", "ready", "disabled", "queued", "unknown"},
        "authority": {"configuration_only", "aggregate_antivirus", "not_observed"},
        "item": {"AntivirusEnabled", "RealTimeProtectionEnabled", "AMServiceEnabled", "BehaviorMonitorEnabled", "IsTamperProtected", "AntivirusSignatureVersion", "AntivirusSignatureLastUpdated", "DisableAntiSpyware", "DisableAntiVirus", "DisableRealtimeMonitoring", "DisableBehaviorMonitoring", "TamperProtection", "SecurityCenterAntivirusHealth"},
    }.items():
        if key in row:
            value = row[key]
            if key == "state" and type(value) is str:
                value = value.lower().replace(" ", "_")
            result[key] = enum(value, choices)
    if "start_mode" in row:
        value = row["start_mode"]
        result["start_mode"] = enum(value.lower() if type(value) is str else value, {"boot", "system", "auto", "automatic", "manual", "disabled"})
    for key, maximum in (("port", 65535), ("pid", 2**32-1), ("count", 2**31-1), ("changed_count", 2**31-1)):
        if key in row:
            result[key] = number(row[key], maximum)
    if "value" in row:
        value = row["value"]
        result["value"] = value if value is None or type(value) is bool else number(value)
    for field in ("current", "previous"):
        value = row.get(field)
        if type(value) is bool or type(value) is int and number(value) is not None:
            result[field] = value
        elif isinstance(value, list) and len(value) <= 5 and all(type(item) is str and item in PROTECTION for item in value):
            result[field] = value
    if isinstance(row.get("address"), str):
        try:
            result["address"] = str(ipaddress.ip_address(row["address"].split("%", 1)[0]))
        except ValueError:
            pass
    if valid_iso(row.get("created_at")):
        result["created_at"] = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="microseconds")
    if isinstance(row.get("process_instance_ref"), str) and REF.fullmatch(row["process_instance_ref"]):
        result["process_instance_ref"] = row["process_instance_ref"]
    if isinstance(row.get("name"), str):
        # Hash all names as an opaque reference. Show only a small display-name
        # grammar; this is still explicitly untrusted data, never authority.
        name = row["name"]
        result["name_ref"] = "name-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]
        if NAME.fullmatch(name):
            result["display_name"] = name
        else:
            result["name_omitted"] = True
    elif isinstance(row.get("name_ref"), str) and re.fullmatch(r"name-[a-f0-9]{24}", row["name_ref"]):
        result["name_ref"] = row["name_ref"]
        if isinstance(row.get("display_name"), str) and NAME.fullmatch(row["display_name"]):
            result["display_name"] = row["display_name"]
        elif row.get("name_omitted") is True:
            result["name_omitted"] = True
    return result


def event_view(event):
    clean = validate_event(event)
    evidence = clean["evidence"]
    result = {key: clean[key] for key in ("event_id", "transition", "severity", "synthetic", "observed_at")}
    result.update(event_type=enum(clean["event_type"], EVENT_TYPES), coverage_status=clean["coverage"]["status"],
                  facts=row_view(evidence), data_trust="untrusted_data", incident_conclusion="not_assessed",
                  explanation=EXPLANATIONS.get(clean["event_type"], "事件型別尚無確定性說明；保留未知。"))
    for field in ("delivery_status", "attempts"):
        if field in event:
            result[field] = enum(event[field], {"pending", "retry", "ack", "failed"}) if field == "delivery_status" else number(event[field], 8)
    return result


def query_plan(event):
    """Parameters come only from the saved event, never from tool arguments."""
    evidence = event["evidence"]
    queries, gaps = [], []
    kind = event["event_type"]
    if kind == "listener.changed":
        protocol, port = evidence.get("protocol"), evidence.get("port")
        if protocol in ("TCP", "UDP") and type(port) is int and 1 <= port <= 65535:
            queries.append(("query_listener", {"protocol": protocol, "port": port, "max_rows": 20}))
        else:
            gaps.append("listener_binding_missing")
        ref = evidence.get("process_instance_ref", evidence.get("instance_ref"))
        if isinstance(ref, str) and REF.fullmatch(ref):
            queries.append(("query_process", {"process_instance_ref": ref, "max_rows": 1}))
        else:
            # Do not back-fill a historical PID with today's creation time.
            gaps.append("process_binding_missing")
    elif kind == "protection.changed":
        queries.append(("query_defender", {"view": "settings", "max_rows": 20}))
    elif kind == "persistence.changed":
        source = evidence.get("kind")
        if type(source) is str and source in KINDS:
            queries.append(("query_persistence_diff", {"kind": source, "max_rows": 20}))
            gaps.append("persistence_current_only")
        else:
            gaps.append("persistence_binding_missing")
    elif kind == "coverage.degraded":
        gaps.append("coverage_event_no_automatic_source_rescan")
    else:
        gaps.append("unsupported_event_type")
    return queries, gaps


def review(event, api=None, *, refresh=False, now=None):
    clean = validate_event(event)
    queries, gaps = query_plan(clean)
    result = {"schema_version": "1.0", "event": event_view(event), "payload_hash": event_payload_hash(clean),
              "mode": "current_read_only" if refresh else "stored_observation", "observations": [],
              "coverage": {"event_status": clean["coverage"]["status"]}, "uncertainties": list(gaps),
              "incident_conclusion": "not_assessed", "model_calls": 0, "actions_executed": [],
              "ack_performed": False, "data_trust": "untrusted_data", "system_query_executed": False,
              "observed_at": clean["observed_at"]}
    if not refresh:
        result["uncertainties"].append("saved_event_not_current_state")
        return dict(result, status="stored_observation")
    if clean["synthetic"]:
        # Synthetic event contents can never cause an actual Windows query.
        if api is None:
            return dict(result, status="not_applicable", uncertainties=result["uncertainties"] + ["synthetic_native_query_blocked"])
    api = api or DiagnosticAPI()
    result["observed_at"] = now or datetime.now(timezone.utc).isoformat(timespec="microseconds")
    for operation, args in queries:
        raw = api.query(operation, args)
        status = enum(raw.get("status"), STATUS_VALUES)
        record = {"operation": operation, "status": status, "source": enum(raw.get("source"), {"listeners", "processes", "defender", *KINDS}),
                  "coverage": coverage_metadata({"coverage": raw.get("coverage", {})}), "rows": [],
                  "truncated": raw.get("truncated") is True,
                  "observed_at": raw["observed_at"] if valid_iso(raw.get("observed_at")) else None}
        if raw.get("coverage", {}).get("mode") == "current_only":
            record["coverage"]["mode"] = "current_only"
        if isinstance(raw.get("rows"), list):
            record["rows"] = [row_view(row) for row in raw["rows"][:20] if isinstance(row, dict)]
        code = raw.get("error_code")
        if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,95}", code):
            record["error_code"] = code
        if status != "ok":
            result["uncertainties"].append("diagnostic_" + status)
        if raw.get("truncated"):
            result["uncertainties"].append("diagnostic_truncated")
        if status == "ok" and not record["rows"]:
            result["uncertainties"].append("not_observed_is_not_recovery")
        result["observations"].append(record)
    result["system_query_executed"] = bool(queries) and not clean["synthetic"]
    result["fixture_queries_executed"] = bool(queries) and clean["synthetic"]
    result["uncertainties"] = sorted(set(result["uncertainties"]))
    return dict(result, status="partial" if result["uncertainties"] else "observed")


def validate_saved_review(value, event):
    """Local SQLite/config are mutable; do not trust cached result strings."""
    required = {"schema_version", "event", "payload_hash", "mode", "observations", "coverage", "uncertainties",
                "incident_conclusion", "model_calls", "actions_executed", "ack_performed", "data_trust",
                "system_query_executed", "observed_at", "fixture_queries_executed", "status", "namespace"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("saved_review_invalid")
    expected = event_view(event)
    saved = value["event"]
    if not isinstance(saved, dict) or set(saved) != set(expected):
        raise ValueError("saved_review_invalid")
    for key in expected:
        if key not in {"delivery_status", "attempts"} and saved[key] != expected[key]:
            raise ValueError("saved_review_invalid")
    if (saved.get("delivery_status") not in {"pending", "retry", "ack", "failed"} or type(saved.get("attempts")) is not int
            or not 0 <= saved["attempts"] <= 8 or value["schema_version"] != "1.0" or value["mode"] != "current_read_only"
            or value["incident_conclusion"] != "not_assessed" or type(value["model_calls"]) is not int or value["model_calls"] != 0
            or value["actions_executed"] != [] or value["ack_performed"] is not False or value["data_trust"] != "untrusted_data"
            or type(value["system_query_executed"]) is not bool or type(value["fixture_queries_executed"]) is not bool
            or value["status"] not in {"partial", "observed"} or value["namespace"] not in {"test", "live"}
            or value["coverage"] != {"event_status": event["coverage"]["status"]} or not valid_iso(value["observed_at"])):
        raise ValueError("saved_review_invalid")
    if not isinstance(value["uncertainties"], list) or len(value["uncertainties"]) > 16 or any(type(x) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,95}", x) for x in value["uncertainties"]):
        raise ValueError("saved_review_invalid")
    if not isinstance(value["observations"], list) or len(value["observations"]) > 2:
        raise ValueError("saved_review_invalid")
    for row in value["observations"]:
        if (not isinstance(row, dict) or set(row) - {"operation", "status", "source", "coverage", "rows", "truncated", "observed_at", "error_code"}
                or row.get("operation") not in {"query_listener", "query_process", "query_defender", "query_persistence_diff"}
                or row.get("status") not in STATUS_VALUES or row.get("source") not in {"listeners", "processes", "defender", *KINDS, "unknown"}
                or type(row.get("truncated")) is not bool or row.get("observed_at") is not None and not valid_iso(row["observed_at"])
                or not isinstance(row.get("rows"), list) or len(row["rows"]) > 20
                or any(not isinstance(item, dict) or row_view(item) != item for item in row["rows"])):
            raise ValueError("saved_review_invalid")
        coverage = row.get("coverage")
        if not isinstance(coverage, dict):
            raise ValueError("saved_review_invalid")
        safe = coverage_metadata({"coverage": coverage})
        if coverage.get("mode") == "current_only":
            safe["mode"] = "current_only"
        if coverage != safe or "error_code" in row and (type(row["error_code"]) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,95}", row["error_code"])):
            raise ValueError("saved_review_invalid")
    return value
