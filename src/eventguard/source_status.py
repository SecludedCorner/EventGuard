"""Read saved source health. Page refreshes never collect operating-system data."""
from __future__ import annotations

from datetime import datetime, timezone
import re

from .collectors.contract import SECTION_IDS, STATUSES, clean_errors, verified_error_classifications
from .runtime import Runtime

SOURCE_NAMES = {
    "defender": "Defender", "listeners": "監聽連接埠", "processes": "程序",
    "startup": "啟動項目", "services": "服務", "tasks": "排程工作", "versions": "版本",
}


def _now():
    return datetime.now(timezone.utc)


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 80:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            return None
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _reason(code, status="unknown"):
    return clean_errors([{"stage": "policy", "reason_code": code,
                          "exception_type": "SourceStatus", "status": status}])[0]


def _reasons(coverage, status):
    result = clean_errors(coverage.get("errors"))
    if not result and status not in {"ok", "not_applicable", "not_requested"}:
        code = coverage.get("reason")
        code = code if isinstance(code, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]{0,95}", code) else "source_reason_not_recorded"
        result = [_reason(code, status)]
    unique = {}
    for item in result:
        item["hresult_hex"] = ("0x%08X" % (item["hresult"] & 0xFFFFFFFF)
                               if item["hresult"] is not None else None)
        key = tuple(item.values())
        unique[key] = item
    return list(unique.values())


def _suggestion(source_id, status, reasons):
    if status == "stale":
        return "資料已過期。確認 EventGuard 仍在執行。等待下一輪採集。"
    if status == "not_collected":
        return "尚無採集資料。執行 eventguard run，再查看此頁。"
    if status == "ok":
        return "最後一輪採集成功。這不代表主機安全。"
    if status == "not_applicable":
        return "此來源不適用。確認是否預期如此。不要視為安全證據。"
    if source_id == "defender" and status == "denied":
        return ("開啟 Windows 安全性，查看病毒與威脅防護。確認是否由組織管理。"
                "若仍拒讀，將原因碼交給管理者。")
    if source_id == "tasks":
        missing_folder = any(item.get("hresult_hex") == "0x80070003" for item in reasons)
        prefix = "0x80070003 表示路徑不存在；不能判為拒絕存取。" if missing_folder else ""
        return prefix + "開啟工作排程器，確認工作清單是否可讀。若仍失敗，將原因碼交給管理者。"
    if status == "partial":
        return "只有部分資料可讀。查看階段與錯誤碼。不要把缺漏資料視為安全。"
    if status == "denied":
        return "目前查詢被拒絕。查看階段與錯誤碼。請管理者確認讀取政策。"
    if status in {"timeout", "busy", "cancelled"}:
        return "本輪採集未完成。確認 EventGuard 狀態，並等待下一輪。"
    return "目前結果未知。查看階段與錯誤碼。若持續失敗，將原因碼交給管理者。"


def effective_collection_status(status, coverage):
    """Keep old metadata readable without promoting contradictory success.

    Missing optional legacy fields are supported. Explicit malformed fields or
    conflicting coverage status cannot establish success. No evidence is rewritten.
    """
    if not isinstance(status, str) or status not in STATUSES:
        return 'unknown'
    if status != 'ok':
        return status
    if not isinstance(coverage, dict) or coverage.get('status', 'ok') != 'ok':
        return 'unknown'
    if 'errors' in coverage and not isinstance(coverage['errors'], list):
        return 'unknown'
    if 'error_count' in coverage and (type(coverage['error_count']) is not int or not 0 <= coverage['error_count'] <= 2**31-1):
        return 'unknown'
    if any(key in coverage and type(coverage[key]) is not bool for key in ('truncated', 'errors_truncated')):
        return 'unknown'
    if coverage.get('errors') or coverage.get('error_count') or coverage.get('truncated') or coverage.get('errors_truncated'):
        return 'partial'
    return 'ok'


def source_status(root, namespace="live"):
    """Return seven bounded status rows from this namespace's persisted evidence.

    success is tri-state: True for a fresh successful collection, False for a
    fresh explicit failure, and None for partial, unknown, stale or inapplicable.
    Raw exceptions, row contents and system queries are excluded.
    """
    runtime = Runtime(root)
    runtime.data_dir(namespace, create=False)  # Validate without creating files.
    now = _now()
    try:
        config = runtime.config()
        intervals, timeout = config["interval_seconds"], config["query_timeout_seconds"]
    except (OSError, ValueError, TypeError, KeyError):
        intervals, timeout = {}, None
    try:
        health = runtime.health()
        health = health if isinstance(health, dict) and health.get("namespace") == namespace else {}
        coverage_by_source = health.get("coverage", {})
        coverage_by_source = coverage_by_source if isinstance(coverage_by_source, dict) else {}
    except (OSError, ValueError, TypeError):
        coverage_by_source = {}
    rows = []
    for source_id in SECTION_IDS:
        section, saved_at, row_count, read_error = {}, None, None, False
        success_at, success_reason = None, "source_success_not_recorded"
        try:
            observation = runtime.observation(source_id, namespace, limit=1)
            if observation is not None:
                section = observation["section"]
                saved_at, row_count = observation.get("saved_at"), observation.get("total")
                success_at = _timestamp(observation.get("last_success_at"))
                success_reason = observation.get("last_success_reason", "source_success_not_recorded")
                if success_at is not None and success_at > now:
                    success_at, success_reason = None, "source_success_timestamp_invalid"
        except (OSError, ValueError, TypeError, KeyError):
            read_error = True
        health_item = coverage_by_source.get(source_id, {})
        health_item = health_item if isinstance(health_item, dict) else {}
        observed = _timestamp(section.get("observed_at"))
        health_observed = _timestamp(health_item.get("observed_at"))
        # A failed persistence attempt can be newer than the last saved rows.
        # Show that failed attempt, rather than hiding it behind older success.
        if health_observed is not None and (observed is None or health_observed > observed):
            section = {"status": health_item.get("status"), "coverage": health_item,
                       "observed_at": health_item.get("observed_at")}
            observed = health_observed
            row_count = health_item.get("row_count")
        coverage = section.get("coverage", {})
        coverage = coverage if isinstance(coverage, dict) else {}
        saved_status = section.get('status')
        saved_status = saved_status if isinstance(saved_status, str) and saved_status in STATUSES else 'unknown'
        evidence_status = effective_collection_status(saved_status, section.get('coverage', {}))
        reasons = _reasons(coverage, evidence_status) if section else []
        if saved_status == 'ok' and evidence_status != 'ok':
            reasons.append(_reason('source_success_evidence_inconsistent', evidence_status))
        age = (now - observed).total_seconds() if observed is not None else None
        interval = intervals.get(source_id)
        max_age = (interval + timeout if type(interval) in (int, float) and
                   type(timeout) in (int, float) and interval > 0 and timeout > 0 else None)
        freshness = "unknown" if age is None or age < 0 or max_age is None else "fresh" if age <= max_age else "stale"
        status = evidence_status if freshness == "fresh" else "stale" if freshness == "stale" else "unknown"
        if not section and not read_error:
            status = "not_collected"
        if read_error:
            reasons.append(_reason("saved_observation_unreadable"))
            status = "unknown"
        if success_reason == "source_success_timestamp_invalid":
            reasons.append(_reason("source_success_timestamp_invalid"))
        if section and freshness == "unknown":
            reasons.append(_reason("source_timestamp_or_freshness_unknown"))
        persistence_failed = health_item.get("observation_error") == "observation_persistence_failed"
        if persistence_failed and health_observed == observed:
            reasons.append(_reason("observation_persistence_failed", "error"))
            if freshness == "fresh":
                status = "error"
        success = True if status == "ok" else False if status in {"denied", "error", "timeout", "cancelled"} else None
        rows.append({"source_id": source_id, "name": SOURCE_NAMES[source_id],
                     "last_collected_at": observed.isoformat(timespec="seconds") if observed else None,
                     "last_success_at": success_at.isoformat(timespec="seconds") if success_at is not None else None,
                     "last_success_state": "known" if success_at is not None else "unknown",
                     "last_saved_at": saved_at if _timestamp(saved_at) is not None else None,
                     "saved_status": saved_status, "evidence_status": evidence_status, "status": status, "success": success,
                     "freshness": freshness, "age_seconds": round(age, 3) if age is not None and age >= 0 else None,
                     "max_age_seconds": max_age, "row_count": row_count if type(row_count) is int and row_count >= 0 else None,
                     "reasons": reasons, "suggestion": (
                         _suggestion(source_id, "stale", reasons) + " " + _suggestion(source_id, saved_status, reasons)
                         if status == "stale" and saved_status in {"denied", "unknown"}
                         else _suggestion(source_id, status, reasons))})
        count = coverage.get('error_count')
        count = count if type(count) is int and 0 <= count <= 2**31-1 else None
        retained = clean_errors(coverage.get('errors'))
        rows[-1].update(error_count=count, retained_error_count=len(retained),
            error_classifications=verified_error_classifications(coverage.get('error_classifications'), count, retained))
    return {"schema_version": "1.0", "namespace": namespace, "sources": rows,
            "read_only": True, "system_query_executed": False, "model_calls": 0,
            "incident_conclusion": "not_assessed", "data_trust": "untrusted_data"}
