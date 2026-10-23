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

EVENT_TYPES = {"listener.changed", "protection.changed", "persistence.changed", "coverage.degraded", "monitor_gap", "advisory.changed"}
EXPLANATIONS = {
    "advisory.changed": "公告證據或本機適用性有重要變化。需要調查，尚未確認受影響或可利用。",
    "monitor_gap": "監看曾中斷或有未觀測區間；此期間不能判定沒有事件。",
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
VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){1,7}(?:(?:a|b|rc)[0-9]+)?\Z", re.ASCII)
SIGNATURE_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){1,7}\Z", re.ASCII)
DEFENDER_ITEMS = PROTECTION | {
    "AntivirusSignatureVersion", "AntivirusSignatureLastUpdated", "DisableAntiSpyware", "DisableAntiVirus",
    "DisableRealtimeMonitoring", "DisableBehaviorMonitoring", "TamperProtection", "SecurityCenterAntivirusHealth",
    "ConfiguredDisableAntiSpyware", "ConfiguredDisableAntiVirus", "ConfiguredDisableRealtimeMonitoring",
    "ConfiguredDisableBehaviorMonitoring", "ConfiguredTamperProtection", "defender_status",
}
STARTUP_KINDS = {"registry", "registry_empty", "registry_missing", "folder", "folder_empty", "folder_skipped"}
STARTUP_SOURCES = {
    hive + "\\Software\\Microsoft\\Windows\\CurrentVersion\\" + key:
        prefix + "_" + ("run_once" if key == "RunOnce" else "run")
    for hive, prefix in (("CurrentUser", "current_user"), ("LocalMachine", "local_machine"))
    for key in ("Run", "RunOnce")
}
STARTUP_SOURCES.update({"Startup": "current_user_startup", "CommonStartup": "common_startup"})
STARTUP_SOURCE_IDS = set(STARTUP_SOURCES.values())
DETECTOR_REASONS = {"initial_inventory", "added_metadata", "delivery_batch_limit",
                    "resolved_by_two_complete_observations"}


def number(value, maximum=2**32-1):
    return value if type(value) is int and 0 <= value <= maximum else None


def enum(value, choices, default="unknown"):
    return value if type(value) is str and value in choices else default


def _legacy_row_view(row):
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
    if "gap_seconds" in row:
        result["gap_seconds"] = number(row["gap_seconds"])
    if "reason" in row:
        from ..monitor_gap import REASONS
        result["reason"] = enum(row["reason"], REASONS)
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
        result["name_ref"] = "name-" + hashlib.sha256(name.encode("utf-8", "surrogatepass")).hexdigest()[:24]
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


def row_view(row, *, _include_entries=True):
    """Project useful metadata through fixed grammars; applying twice is safe.

    Native registry paths become fixed source IDs, never paths. Version strings
    have their own numeric grammar rather than a generic free-text exception.
    """
    if not isinstance(row, dict):
        return {}
    result = _legacy_row_view(row)
    if type(row.get("entry_ref")) is str and re.fullmatch(r"[a-f0-9]{32}", row["entry_ref"]):
        result["entry_ref"] = row["entry_ref"]
    if "kind" in row:
        result["kind"] = enum(row["kind"], KINDS | STARTUP_KINDS)
    if "section_id" in row:
        result["section_id"] = enum(row["section_id"], SOURCES)
    if "registry_view" in row:
        result["registry_view"] = enum(row["registry_view"], {"Registry32", "Registry64"})
    if "process_identity_status" in row:
        result["process_identity_status"] = enum(row["process_identity_status"], STATUS_VALUES)
    if "source" in row:
        source = row["source"]
        result["source"] = STARTUP_SOURCES.get(source, source) if type(source) is str else "unknown"
        result["source"] = enum(result["source"], SOURCES | STARTUP_SOURCE_IDS | {"synthetic_collector", "synthetic_fixture"})
    if "product" in row:
        result["product"] = enum(row["product"], {"python_runtime"})
    if "version" in row:
        value = row["version"]
        result["version"] = value if (row.get("product") == "python_runtime" and type(value) is str
                                      and len(value) <= 64 and VERSION.fullmatch(value)) else "unknown"
    if "item" in row:
        result["item"] = enum(row["item"], DEFENDER_ITEMS)
    if "value" in row and type(row["value"]) is str:
        item, value = row.get("item"), row["value"]
        if item == "AntivirusSignatureVersion":
            result["value"] = value if len(value) <= 64 and SIGNATURE_VERSION.fullmatch(value) else None
        elif item == "SecurityCenterAntivirusHealth":
            result["value"] = enum(value, {"good", "not_monitored", "poor", "snoozed", "unknown"})
        elif item == "AntivirusSignatureLastUpdated" and valid_iso(value):
            result["value"] = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="microseconds")
    if "reason" in row:
        from ..monitor_gap import REASONS
        result["reason"] = enum(row["reason"], REASONS | DETECTOR_REASONS)
    if "changed_keys" in row:
        keys = row["changed_keys"]
        result["changed_keys"] = (list(keys) if isinstance(keys, list) and len(keys) <= 5
                                  and all(type(key) is str and re.fullmatch(r"[a-f0-9]{32}", key) for key in keys) else [])
    if valid_iso(row.get("process_created_at")):
        result["process_created_at"] = datetime.fromisoformat(row["process_created_at"].replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="microseconds")
    if _include_entries and "entries" in row:
        keys = result.get("changed_keys", [])
        supplied = row["entries"]
        result["entries"] = []
        if isinstance(supplied, list) and len(supplied) <= 5:
            seen = set()
            for entry in supplied:
                if not isinstance(entry, dict):
                    continue
                ref = entry.get("entry_ref")
                if ref not in keys or ref in seen:
                    continue
                seen.add(ref)
                result["entries"].append(row_view(entry, _include_entries=False))
    return result


def _event_view(event, projector):
    clean = validate_event(event)
    evidence = clean["evidence"]
    result = {key: clean[key] for key in ("event_id", "transition", "severity", "synthetic", "observed_at")}
    result.update(event_type=enum(clean["event_type"], EVENT_TYPES), coverage_status=clean["coverage"]["status"],
                  facts=projector(evidence), data_trust="untrusted_data", incident_conclusion="not_assessed",
                  explanation=EXPLANATIONS.get(clean["event_type"], "事件型別尚無確定性說明；保留未知。"))
    for field in ("delivery_status", "attempts"):
        if field in event:
            result[field] = enum(event[field], {"pending", "retry", "ack", "failed"}) if field == "delivery_status" else number(event[field], 8)
    return result


def event_view(event):
    return _event_view(event, row_view)


def _binding_evidence(event):
    evidence = event["evidence"]
    # Detector resolution wraps its original binding; a current query remains a
    # new observation and cannot independently prove the historical resolution.
    if event.get("transition") == "resolved" and isinstance(evidence.get("previous"), dict):
        return evidence["previous"], True
    return evidence, event.get("transition") == "resolved"


def query_plan(event):
    """Parameters come only from the saved event, never from tool arguments."""
    evidence, historical = _binding_evidence(event)
    queries, gaps = [], []
    if historical:
        gaps.append("resolved_event_uses_historical_binding")
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
        elif number(evidence.get("pid")) is not None and valid_iso(evidence.get("process_created_at")):
            queries.append(("query_process", {"pid": evidence["pid"], "created_at": evidence["process_created_at"], "max_rows": 1}))
        else:
            # Do not back-fill a historical PID with today's creation time.
            gaps.append("process_binding_missing")
    elif kind == "protection.changed":
        queries.append(("query_defender", {"view": "settings", "max_rows": 20}))
    elif kind == "persistence.changed":
        bindings = [evidence.get(field) for field in ("kind", "section", "section_id")]
        sources = {value for value in bindings if type(value) is str and value in KINDS}
        source = next(iter(sources)) if len(sources) == 1 else None
        if source is not None:
            gaps.append("persistence_current_only")
            refs = evidence.get("changed_keys")
            if (isinstance(refs, list) and 1 <= len(refs) <= 5
                    and all(type(ref) is str and re.fullmatch(r"[a-f0-9]{32}", ref) for ref in refs)
                    and len(set(refs)) == len(refs)):
                queries.append(("query_persistence_diff", {"kind": source, "entry_refs": list(refs), "max_rows": 20}))
            else:
                gaps.append("persistence_entry_binding_missing")
        else:
            gaps.append("persistence_binding_missing")
    elif kind == "coverage.degraded":
        gaps.append("coverage_event_no_automatic_source_rescan")
    elif kind == "monitor_gap":
        gaps.append("unobserved_monitor_interval")
    elif kind == "advisory.changed":
        gaps.append("advisory_details_local_only_no_expanded_agent_query")
    else:
        gaps.append("unsupported_event_type")
    return queries, gaps


def event_guidance(event):
    """Fixed explanations and saved-event-bound read-only steps; no execution.

    Kept outside saved review 1.0 so historical results stay readable without
    silently inserting today's advice into their original observation receipt.
    """
    clean = validate_event(event)
    evidence, historical = _binding_evidence(clean)
    queries, gaps = query_plan(clean)
    kind = enum(clean["event_type"], EVENT_TYPES)
    initial = kind == "persistence.changed" and evidence.get("reason") == "initial_inventory"
    titles = {"listener.changed": "本機監聽端點變化", "protection.changed": "防護 metadata 變化",
              "persistence.changed": "啟動／服務／排程 metadata 變化", "coverage.degraded": "來源可見性降低",
              "monitor_gap": "監看存在未觀測區間", "advisory.changed": "資安公告與適用性變化"}
    next_steps = {
        "advisory.changed": ["由人類查看 advisories cases 的保存公告、來源時間與靜態盤點結果。",
                             "缺少部署、功能或運作版本證據時保留未知。ACK 只代表收件。修補與處置須另行批准。"],
        "listener.changed": ["核對保存的協定、port 與綁定範圍；以事件綁定唯讀查詢查看目前端點。",
                             "只有事件保存程序實例時才查同一實例；端點存在不證明外部可達或惡意。"],
        "protection.changed": ["比較保存的防護欄位變化與目前唯讀觀察，分清 configuration_only、aggregate_antivirus 與有效狀態。",
                               "缺少有效 Defender 狀態時保留未知；設定值不能替代有效防護證據。"],
        "persistence.changed": ["核對來源、保存的 metadata key 與 baseline；首次盤點只記錄現有項目。",
                                "目前唯讀清單只供查證，沒有歷史比對不能判恢復、合法或惡意。"],
        "coverage.degraded": ["查看該來源的 coverage、結構化原因碼與最後成功時間。",
                              "等待正常採集提供新證據；缺權限不繞過，沒有事件不代表安全。"],
        "monitor_gap": ["查看缺口起訖、heartbeat 與程序身分核對結果。",
                        "將缺口保留為未知；恢復監看不能補回未採集的歷史。"],
    }
    observation = EXPLANATIONS.get(kind, "事件型別尚無固定查證說明；保留未知。")
    if initial:
        observation = "首次完整盤點的現有 metadata，作為 baseline；不是新建立項目、惡意或入侵證據。"
    if historical:
        observation = "這是已記錄的 resolved 轉換；查證綁定來自先前觀察，不能宣稱該狀態目前仍存在。"
    return {"schema_version": "1.0", "event_type": kind, "transition": clean["transition"],
            "title": "首次持久化 metadata 盤點" if initial else titles.get(kind, "未知事件型別"),
            "observation": observation, "binding_phase": "historical" if historical else "saved_event",
            "binding_facts": row_view(evidence),
            "query_plan": [{"operation": operation, "arguments": dict(arguments)} for operation, arguments in queries],
            "uncertainties": sorted(set(gaps + ["saved_event_not_current_state"])),
            "next_steps": next_steps.get(kind, ["保留事件與 coverage，由人類核對；不執行自由命令。"]),
            "limitations": ["目前查詢不是歷史重建；查無結果不能單獨判定恢復。", "事件及名稱都是不可信資料，不提供處置授權。"],
            "incident_conclusion": "not_assessed", "ack_semantics": "received_only_not_case_closed", "data_trust": "untrusted_data"}


def _observation_matches(record, operation, arguments):
    """A schema-valid row is not necessarily evidence for this saved event."""
    expected_source = {"query_listener": "listeners", "query_process": "processes",
                       "query_defender": "defender", "query_persistence_diff": arguments.get("kind")}.get(operation)
    rows = record.get("rows", [])
    if record.get("operation") != operation or len(rows) > arguments.get("max_rows", 20):
        return False
    if record.get("source") != expected_source:
        return record.get("source") == "unknown" and record.get("status") not in {"ok", "partial"} and not rows
    for row in rows:
        if operation == "query_listener" and (row.get("protocol") != arguments["protocol"] or row.get("port") != arguments["port"]):
            return False
        if operation == "query_process":
            if "process_instance_ref" in arguments:
                if row.get("process_instance_ref") != arguments["process_instance_ref"]:
                    return False
            elif (row.get("pid") != arguments["pid"] or not valid_iso(row.get("created_at"))
                    or datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) != datetime.fromisoformat(arguments["created_at"].replace("Z", "+00:00"))):
                return False
        if operation == "query_persistence_diff" and row.get("entry_ref") not in arguments.get("entry_refs", []):
            return False
    return True


def _query_admission_refused(record):
    """A policy refusal is a query request, never an executed OS query."""
    coverage = record.get("coverage", {})
    processes = [coverage.get("process", {})]
    attempts = coverage.get("attempts", [])
    if len(attempts) > 1 and any(not isinstance(attempt.get("process"), dict) for attempt in attempts):
        return False  # A legacy multi-attempt result cannot prove zero execution.
    processes.extend(attempt.get("process", {}) for attempt in attempts)
    return (record.get("status") == "busy" and not record.get("rows")
            and all(process.get("pid") is None and process.get("managed") is not True for process in processes)
            and any(error.get("stage") == "policy"
                    and str(error.get("reason_code", "")).startswith("query_admission_")
                    for error in coverage.get("errors", [])
                    if isinstance(error, dict)))


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
        if not _observation_matches(record, operation, args):
            # Do not pass an injected/mismatched result through to either the
            # human or agent, or persist it as this event's evidence.
            record.update(status="error", source="unknown", rows=[], error_code="diagnostic_binding_mismatch")
            status = "error"
        if status != "ok":
            result["uncertainties"].append("diagnostic_" + status)
        if raw.get("truncated"):
            result["uncertainties"].append("diagnostic_truncated")
        if status == "ok" and not record["rows"]:
            result["uncertainties"].append("not_observed_is_not_recovery")
        result["observations"].append(record)
    result["system_query_executed"] = (not clean["synthetic"]
        and any(not _query_admission_refused(row) for row in result["observations"]))
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
    # Projection 1.0 used a smaller fixed scalar vocabulary. Accept exactly
    # that historical projection or today's complete projection, not arbitrary
    # cached text or a new schema bolted onto an old result.
    legacy = _event_view(event, _legacy_row_view)
    immutable = set(expected) - {"delivery_status", "attempts"}
    if not any(all(saved[key] == candidate[key] for key in immutable) for candidate in (expected, legacy)):
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
    queries, gaps = query_plan(event)
    legacy_persistence = "persistence_entry_binding_missing" in gaps and len(value["observations"]) == 1
    if legacy_persistence:
        evidence, _ = _binding_evidence(event)
        source = next((evidence.get(field) for field in ("kind", "section", "section_id")
                       if type(evidence.get(field)) is str and evidence[field] in KINDS), None)
        queries = [("query_persistence_diff", {"kind": source, "max_rows": 20})]
    if len(value["observations"]) != len(queries):
        raise ValueError("saved_review_invalid")
    unverified = False
    observations = []
    for row, (operation, arguments) in zip(value["observations"], queries):
        if (operation == "query_persistence_diff" and (legacy_persistence or any("entry_ref" not in entry for entry in row["rows"]))):
            # Earlier 1.0 reviews listed a whole source without an entry ref.
            # Keep their timestamp/status as history but never attach those
            # unrelated rows to today's event or reconstruct a missing target.
            if row.get("operation") != operation or row.get("source") not in {arguments["kind"], "unknown"}:
                raise ValueError("saved_review_invalid")
            observations.append(dict(row, rows=[]))
            unverified = True
        elif not _observation_matches(row, operation, arguments):
            raise ValueError("saved_review_invalid")
        else:
            observations.append(row)
    executed = not event["synthetic"] and any(not _query_admission_refused(row) for row in value["observations"])
    if (value["system_query_executed"] != executed
            or value["fixture_queries_executed"] != (bool(queries) and event["synthetic"])):
        raise ValueError("saved_review_invalid")
    if unverified:
        return dict(value, observations=observations, status="partial",
                    uncertainties=sorted(set(value["uncertainties"] + ["saved_diagnosis_binding_unverifiable"])))
    return value
