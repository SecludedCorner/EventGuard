"""One local application API for CLI users and optional agent tool adapters.

Core imports only the standard library and EventGuard; never imports an SDK or
launches a model. All live diagnostics are explicit event-bound operations.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import html
import json
import re
import sqlite3
import threading
import uuid

from . import __version__
from .runtime import Runtime, utc_now, read_json, atomic_json
from .events.store import EventStore, StoreError, event_payload_hash
from .events.schema import validate_event
from .diagnostics.review import event_view, review, validate_saved_review, row_view, event_guidance
from .collectors.windows import coverage_metadata

IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
SOURCES = ("defender", "listeners", "processes", "startup", "services", "tasks", "versions")
HEARTBEAT_MAX_AGE = 90


def store(runtime, namespace):
    limits = runtime.config().get("outbox", {})
    return EventStore(runtime.data_dir(namespace), **limits)


def read_events(runtime, namespace, limit=100, event_id=None):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("event_limit_out_of_bounds")
    if event_id is not None and (type(event_id) is not str or not IDENTIFIER.fullmatch(event_id)):
        raise ValueError("invalid_event_identifier")
    path = runtime.data_dir(namespace, create=False) / "eventguard.sqlite3"
    runtime.path(path.relative_to(runtime.root))
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        if event_id is None:
            rows = db.execute("SELECT * FROM events ORDER BY created_at DESC,event_id LIMIT ?", (limit,))
        else:
            rows = db.execute("SELECT * FROM events WHERE event_id=?", (event_id,))
        return [EventStore._row(row) for row in rows]


def saved_review(runtime, namespace, event):
    path = runtime.data_dir(namespace, create=False) / "eventguard.sqlite3"
    runtime.path(path.relative_to(runtime.root))
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_reviews'").fetchone():
            return None  # Earlier databases remain read-only until a write.
        row = db.execute("SELECT payload_hash,result FROM event_reviews WHERE event_id=?", (event["event_id"],)).fetchone()
    if row is None:
        return None
    expected = event_payload_hash(validate_event(event))
    if row[0] != expected or len(row[1]) > 65536:
        raise ValueError("saved_review_identity_conflict")
    value = json.loads(row[1])
    if not isinstance(value, dict) or value.get("payload_hash") != expected or value.get("incident_conclusion") != "not_assessed":
        raise ValueError("saved_review_invalid")
    return validate_saved_review(value, event)


def _now():
    return datetime.now(timezone.utc)


def _freshness(value, now, max_age):
    result = {"state": "unknown", "age_seconds": None, "max_age_seconds": max_age}
    if not isinstance(value, str):
        return dict(result, reason="timestamp_missing")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return dict(result, reason="timestamp_timezone_missing")
        age = (now - stamp).total_seconds()
    except (ValueError, TypeError, OverflowError):
        return dict(result, reason="timestamp_invalid")
    if age < 0:
        return dict(result, reason="timestamp_in_future")
    result["age_seconds"] = age
    if max_age is None:
        return dict(result, reason="freshness_policy_unavailable")
    return dict(result, state="fresh" if age <= max_age else "stale",
                reason="within_interval" if age <= max_age else "interval_exceeded")


def _owner_identity(pid):
    # A single PID from this root's matching owner record, never an enumeration.
    from .processes import identity
    return identity(pid)


def _current_monitor(runtime, health, heartbeat):
    result = {"state": "unknown", "reason": "owner_unverified", "owner_state": "unknown",
              "identity_matches": False, "heartbeat": heartbeat,
              "evidence_scope": "on_demand_owner_identity_and_saved_heartbeat; no independent watchdog"}
    try:
        path = runtime.path("data/monitor-owner.json")
        if not path.is_file():
            return dict(result, state="not_started" if health.get("state") == "not_started" else "unknown",
                        owner_state="not_recorded", reason="no_current_owner_record")
        owner = read_json(path)
        pid, created, instance = owner.get("pid"), owner.get("process_created_at"), owner.get("instance_id")
        if (type(pid) is not int or not 1 <= pid <= 2**32 - 1 or
                not isinstance(created, str) or not 1 <= len(created) <= 80 or
                not isinstance(instance, str) or not re.fullmatch(r"[a-f0-9]{32}", instance)):
            return dict(result, reason="owner_record_invalid")
        if (health.get("pid") != pid or health.get("process_created_at") != created or
                health.get("instance_id") != instance or health.get("namespace") not in {"live", "test"}):
            return dict(result, reason="owner_report_mismatch")
        observed = _owner_identity(pid)
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
        return dict(result, reason="owner_check_unavailable")
    state = observed.get("state") if isinstance(observed, dict) else "unknown"
    if state not in {"alive", "missing", "exited", "denied", "unknown"}:
        state = "unknown"
    result["owner_state"] = state
    if state in {"missing", "exited"}:
        return dict(result, reason="recorded_owner_not_alive")
    if state != "alive":
        return dict(result, reason="owner_identity_unverifiable")
    if observed.get("created_at") != created:
        return dict(result, owner_state="identity_mismatch", reason="owner_identity_changed")
    result["identity_matches"] = True
    if heartbeat["state"] != "fresh":
        return dict(result, reason="heartbeat_" + heartbeat["reason"])
    reported = health.get("state")
    if reported == "running" and health.get("monitoring") is True:
        return dict(result, state="running_verified", reason="owner_alive_with_recent_heartbeat")
    return dict(result, reason="last_report_not_running")


def _coverage_status(runtime, health, now):
    try:
        config = runtime.config()
        intervals, query_timeout = config["interval_seconds"], config["query_timeout_seconds"]
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        intervals, query_timeout = {}, 0
    saved = health.get("coverage")
    saved = saved if isinstance(saved, dict) else {}
    result = {}
    for source in SOURCES:
        item = saved.get(source, {})
        item = item if isinstance(item, dict) else {}
        interval = intervals.get(source)
        threshold = interval + query_timeout if type(interval) in (int, float) and interval > 0 else None
        freshness = _freshness(item.get("observed_at"), now, threshold)
        result[source] = {**coverage_metadata({"coverage": item}),
                          "status": item.get("status", "unknown"), "observed_at": item.get("observed_at"),
                          "last_success": item.get("last_success"), "freshness": freshness,
                          "freshness_basis": "configured_interval_plus_query_timeout",
                          "current_coverage": item.get("status", "unknown") if freshness["state"] == "fresh" else "unknown"}
        for key in ("row_count", "usable_row_count", "elapsed_ms"):
            value = item.get(key)
            result[source][key] = value if type(value) is int and 0 <= value <= 2**53 - 1 else None
        result[source]["observation_saved"] = item.get("observation_saved") is True
        result[source]["last_persisted_at"] = item.get("last_persisted_at")
        result[source]["evaluation_status"] = item.get("evaluation_status") if item.get("evaluation_status") in {"committed", "blocked", "not_evaluated"} else "unknown"
    return result


def _overview_coverage(coverage):
    """Group identical sanitized error samples only in the operator overview.

    sample_occurrences counts entries in the bounded saved sample, never all
    failures. The collector's error_count/errors_truncated and detailed saved
    observation remain authoritative and unchanged.
    """
    def grouped(errors):
        groups = {}
        for error in errors:
            key = json.dumps(error, sort_keys=True, separators=(",", ":"))
            if key not in groups:
                groups[key] = dict(error, sample_occurrences=0)
            groups[key]["sample_occurrences"] += 1
        return list(groups.values())

    result = {}
    for source, item in coverage.items():
        summary = dict(item)
        summary["errors"] = grouped(item.get("errors", []))
        summary["attempts"] = [dict(attempt, errors=grouped(attempt.get("errors", [])))
                               for attempt in item.get("attempts", [])]
        result[source] = summary
    return result


def _step(operation, explanation, **parameters):
    """Fixed local operation identifiers, never shell or untrusted instructions."""
    mutating = operation in {"monitor", "background_start", "background_stop", "stop", "diagnose_event", "report", "receive_event", "ack_event", "retry_event"}
    return {"operation": operation, "parameters": parameters, "explanation": explanation,
            "read_only": not mutating, "system_read_only": True, "local_state_mutation": mutating,
            "requires_model": False}


def _shutdown_status(health, namespace=None):
    """Saved gate state only; never disclose a different scope's job identity."""
    if namespace is not None and health.get("namespace") != namespace:
        return None
    saved = health.get("monitor_shutdown_gate")
    saved = saved if isinstance(saved, dict) else {}
    reported = health.get("state")
    blocked = saved.get("state") == "blocked" or type(reported) is str and reported in {"blocked_previous_query", "shutdown_unconfirmed"}
    if not saved and not blocked:
        return None
    reasons = {"previous_query_exit_unconfirmed", "previous_query_job_identity_unavailable",
               "previous_local_job_session_unverified",
               "previous_owned_job_still_active", "previous_query_exit_unverifiable",
               "previous_private_job_empty_or_destroyed", "no_unresolved_query"}
    reason = saved.get("reason")
    if type(reason) is not str or reason not in reasons:
        reason = "previous_query_exit_unverifiable" if blocked else "query_exit_state_unverifiable"
    state = "blocked" if blocked else saved.get("state")
    if type(state) is not str or state not in {"blocked", "clear", "confirmed_exited"}:
        state = "unknown"
    return {"state": state, "reason": reason,
            "evidence_scope": "saved_monitor_report; no new private_job_query",
            "process_identity_omitted": True}


def _operator_summary(document, namespace=None):
    current, coverage = document["current_monitor"], document["source_coverage"]
    namespaces = document["namespaces"]
    selected = {namespace: namespaces[namespace]} if namespace is not None else namespaces
    known = all(value.get("events") is not None for value in selected.values())
    pending = sum(value.get("counts", {}).get("pending", 0) + value.get("counts", {}).get("retry", 0)
                  for value in selected.values()) if known else None
    failed = sum(value.get("counts", {}).get("failed", 0) for value in selected.values()) if known else None
    fresh = sum(value["current_coverage"] == "ok" for value in coverage.values())
    observed = sum(value["row_count"] is not None for value in coverage.values())
    summary = {"monitor_state": current["state"], "coverage_ok_sources": fresh,
               "coverage_source_count": len(SOURCES), "observed_source_count": observed,
               "pending_events": pending, "failed_events": failed, "pending_count_complete": known,
               "model_calls": 0, "agent_required": False, "incident_conclusion": "not_assessed"}
    actions = []
    scope = namespace or "live"
    gate = _shutdown_status(document["last_report"], namespace)
    background = document.get("background") or {}
    background_state = background.get("state")
    summary["background_state"] = background_state
    if current.get("scope_matches") is False:
        summary.update(state="other_namespace", headline="目前監看屬於其他資料範圍；此處只顯示所選範圍的保存觀察。")
        actions.append(_step("status", "核對目前監看的 namespace；不把 fixture 觀察當成 live 採集。"))
    elif gate is not None and gate["state"] == "blocked":
        summary.update(state="blocked_previous_query", reason=gate["reason"], monitor_shutdown_gate=gate,
                       headline="前次本工具查詢尚未證明退出，新的採集被耐久閘道阻擋；這不是已停止或沒有事件。")
        actions.append(_step("overview", "查看此範圍保存的退出阻擋原因；不刪除閘道、不把鎖釋放當作退出。", namespace=scope, limit=20))
        monitor_args = {"fixture": "tests/fixtures/normal.json", "max_cycles": 1} if scope == "test" else {}
        actions.append(_step("monitor", "再次明確啟動時會先核對既有私有 Job 的退出證據；未確認前不開始新採集，也不停止其他程序。", **monitor_args))
    elif current["state"] != "running_verified" and background.get("namespace") in (None, scope) and (
            background.get("desired_enabled") is True or background_state in {"stopping", "shutdown_unconfirmed", "blocked"}):
        summary.update(state="background_" + (background_state if background_state in {
            "backoff", "stopping", "blocked", "shutdown_unconfirmed", "enabled_not_running", "running"} else "unknown"),
            headline="背景控制仍啟用；目前尚未證明採集正在運作，請核對等待、背壓或退出原因。")
        actions.append(_step("background_status", "核對背景心跳、退避與耐久啟停意圖；不要重建資料或反覆啟動。"))
    elif current["state"] == "not_started":
        summary.update(state="not_started", headline="尚未開始監看，尚無實際採集證據。")
        actions.append(_step("monitor", "明確啟動本機唯讀監看；不需要 agent。"))
    elif current["state"] == "running_verified":
        summary.update(state="observing" if fresh == len(SOURCES) else "coverage_incomplete",
                       headline="監看程序與近期心跳已核對。" if fresh == len(SOURCES) else "監看程序已核對；部分來源可見性不足或尚未完成。")
    elif document["last_report"].get("state") == "stopped" and current.get("owner_state") in {"missing", "exited", "not_recorded"}:
        summary.update(state="stopped", headline="監看已結束；目前顯示保存的歷史觀察。")
        actions.append(_step("monitor", "要取得後續變化，需再次明確啟動監看。"))
    else:
        summary.update(state="unknown", headline="目前無法證明監看仍在運作；保存的報告不能當作即時狀態。")
        actions.append(_step("status", "查看 owner、心跳及阻塞原因；不要只憑舊 running 字樣判斷。"))
    for source in SOURCES:
        item = coverage[source]
        if item["current_coverage"] != "ok":
            actions.append(_step("observation", "查看此來源已保存的筆數、時間、拒讀原因與未知；不會重新掃描。",
                                 source_id=source, namespace=scope, limit=20))
    for space, value in selected.items():
        if any(value.get("counts", {}).get(state, 0) for state in ("pending", "retry", "failed")):
            actions.append(_step("events", "有未確認接收或投遞失敗的事件；先查看保存觀察，ACK 不代表已修復。", namespace=space, limit=20))
    if not known:
        actions.append(_step("status", "至少一個事件資料庫無法讀取，事件數量未知；先處理本工具的儲存故障。"))
    summary["next_steps"] = actions
    return summary


def _namespace_status(runtime, namespace):
    try:
        path = runtime.data_dir(namespace, create=False) / "eventguard.sqlite3"
        runtime.path(path.relative_to(runtime.root))
        if path.is_file():
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
                db.execute("PRAGMA query_only=ON")
                db.execute("BEGIN")
                counts = dict(db.execute("SELECT delivery_status,COUNT(*) FROM events GROUP BY delivery_status"))
                policy = db.execute("SELECT value FROM meta WHERE key='storage_policy'").fetchone()
                receipts = db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
                has_finalization = "pending_finalization" in {row[1] for row in db.execute("PRAGMA table_info(receipts)")}
                finalizations = db.execute("SELECT COUNT(*) FROM receipts WHERE pending_finalization=1").fetchone()[0] if has_finalization else None
                rotation = dict(db.execute("SELECT key,value FROM meta WHERE key IN ('rotated_ack','expired_receipts','pressure_rotated_receipts')"))
            return {"state": "available", "counts": counts, "events": sum(counts.values()),
                    "storage_bytes": path.stat().st_size, "receipt_count": receipts,
                    "pending_receiver_finalizations": finalizations,
                    "retention": json.loads(policy[0]) if policy else None, "rotation": rotation}
        return {"state": "not_created", "events": 0}
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return {"state": "unknown", "reason": "namespace_storage_unavailable", "events": None,
                "raw_error_omitted": True}


def _budget_status(runtime):
    # The installation-wide authority chooses its path. Status must never create
    # or reset a ledger, including when the operator uses a fixture root.
    try:
        from .agent_budget import public_status
        return public_status()
    except (ImportError, OSError, ValueError, TypeError, RuntimeError, sqlite3.Error):
        return {"state": "blocked", "reason": "budget_status_unavailable"}


def _background_status(runtime, namespace=None):
    try:
        from .background import status as background_status
        value = background_status(runtime.root)
        if namespace is not None and value.get("namespace") not in (None, namespace):
            return {"state": "not_applicable", "reason": "background_outside_launcher_namespace",
                    "namespace": namespace, "model_calls": 0}
        return value
    except (OSError, ValueError, TypeError, RuntimeError):
        return {"state": "unknown", "reason": "background_status_unavailable", "model_calls": 0}


def status(runtime):
    now = _now()
    try:
        health = runtime.health()
        if not isinstance(health, dict):
            raise ValueError("health_report_invalid")
    except (OSError, ValueError, TypeError):
        health = {"state": "unknown", "monitoring": None, "reason": "last_report_unavailable"}
    heartbeat = _freshness(health.get("heartbeat_at"), now, HEARTBEAT_MAX_AGE)
    result = {"tool_version": __version__, "health": health, "last_report": health,
            "heartbeat_age_seconds": heartbeat["age_seconds"],
            "liveness": "on_demand_owner_check; no independent watchdog",
            "current_monitor": _current_monitor(runtime, health, heartbeat),
            "monitor_shutdown_gate": _shutdown_status(health),
            "source_coverage": _coverage_status(runtime, health, now),
            "namespaces": {namespace: _namespace_status(runtime, namespace) for namespace in ("live", "test")},
            "agent_budget": _budget_status(runtime),
            "background": _background_status(runtime),
            "agent_ingress": "not_configured", "real_agent_woken": False}
    result["operator_summary"] = _operator_summary(result)
    return result


class OperatorAPI:
    def __init__(self, root, diagnostic_api=None, *, background_lifetime_owner="independent"):
        if type(background_lifetime_owner) is not str or background_lifetime_owner not in {"independent", "application"}:
            raise ValueError("invalid_operator_background_lifetime")
        self.runtime = Runtime(root)
        # Explicit test injection only; synthetic input never instantiates a
        # native diagnostic implementation by itself.
        self.diagnostic_api = diagnostic_api
        # An adapter may own the existing application-lifetime host. The CLI
        # retains its independent launch contract. No desktop/agent automation
        # controller is constructed or resumed by this application API.
        self._background_lifetime_owner = background_lifetime_owner
        self._background_owner_lock = threading.RLock()
        self._background_owner_closed = threading.Event()
        self._background_children = []
        self._background_receipts = []
        self._background_shutdown_result = None

    def call(self, operation, *args, **kwargs):
        """Shared public error envelope: never forward an OS exception/path."""
        if operation not in {"capabilities", "status", "overview", "activity", "observation", "stop", "monitor", "events", "inspect_event", "diagnose_event", "receive_event", "ack_event", "retry_event", "report", "background_start", "background_status", "background_stop"}:
            return {"status": "invalid_request", "error_code": "input_or_config_validation_failed", "raw_error_omitted": True}
        try:
            return getattr(self, operation)(*args, **kwargs)
        except (ValueError, TypeError, json.JSONDecodeError):
            return {"status": "invalid_request", "error_code": "input_or_config_validation_failed", "raw_error_omitted": True}
        except Exception as error:
            if (type(error).__module__ in {"eventguard.queue_inbox", "eventguard.local_paths"}
                    and error.args and type(error.args[0]) is str
                    and re.fullmatch(r"[a-z][a-z0-9_]{0,95}", error.args[0])):
                return {"status": "blocked", "reason": error.args[0], "error_code": "event_delivery_blocked",
                        "raw_error_omitted": True, "model_started": False}
            return {"status": "error", "error_code": "capacity_or_storage_failure" if type(error).__name__ in {"CapacityError", "StoreError"} else "operation_failed", "raw_error_omitted": True}

    def capabilities(self):
        from .diagnostics.api import DiagnosticAPI
        return {"tool_version": __version__, "diagnostics": DiagnosticAPI().capabilities(),
                "monitor": "foreground or background, durable stop, singleton", "transport": ["disabled", "synthetic-only local mock"],
                "remediation": [], "gui": True, "model_calls": 0, "real_agent_ingress": "not_configured",
                "operator_operations": ["capabilities", "status", "overview", "activity", "observation", "stop", "events", "inspect_event", "diagnose_event", "receive_event", "ack_event", "retry_event", "report", "monitor", "background_start", "background_status", "background_stop"],
                "agent_required": False, "data_trust": "untrusted_data",
                "background": {"entry": "scripts/eventguard.py background", "model_required": False,
                    "daily_monitor_limit": None, "duration_limit": None,
                    "start_lifetime_owner": self._background_lifetime_owner,
                    "lifetime_limited": True if self._background_lifetime_owner == "application" else None,
                    "lifetime_scope": "owning_application_process" if self._background_lifetime_owner == "application" else "independent_host_if_verified",
                    "owner_exit_stops_monitor": self._background_lifetime_owner == "application",
                    "scheduler_installation_requires_separate_approval": True,
                    "automatic_resume": "current_user_logon_after_approved_task_install",
                    "manual_stop_is_durable": True, "before_logon_monitoring": False},
                "optional_agent_ingress": {"entry": "scripts/eventguard_inbox_mcp.py",
                    "arguments": ["--operator-root", "<project-root>", "--namespace", "test"],
                    "live_scope_arguments": ["--namespace", "live", "--allow-live"],
                    "mode": "local_stdio_shared_operator_api", "needs_existing_sdk": True,
                    "launches_model": False, "permanent_registration_performed": False,
                    "client_configuration": "required_in_the_calling_client; not_performed_by_EventGuard",
                    "state": "not_configured", "connected": False, "real_client_verified": False,
                    "default_enabled": False},
                "bounded_dispatch": {"entry": "scripts/eventguard_watch.py", "mode": "explicit_bounded_foreground",
                    "default_enabled": False, "requires_separate_model_authorization": True,
                    "projection": "fixed-minimal-v1"}}

    def status(self):
        return status(self.runtime)

    def activity(self, namespace="live", limit=100):
        from .activity import snapshot
        return snapshot(self.runtime.root, namespace, limit)

    def overview(self, namespace="live", limit=20):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("event_limit_out_of_bounds")
        self.runtime.data_dir(namespace, create=False)
        document = self.status()
        monitor_namespace = document["last_report"].get("namespace")
        current = dict(document["current_monitor"], namespace=monitor_namespace,
                       scope_matches=monitor_namespace in (None, namespace))
        scoped = dict(document, current_monitor=current)
        if monitor_namespace != namespace:
            coverage = {}
            for source in SOURCES:
                try:
                    item = self.observation(source, namespace, 1)
                    observed = item["status"] != "not_observed"
                    coverage[source] = {**item.get("coverage", {}),
                        "status": item["status"] if observed else "not_requested",
                        "observed_at": item.get("observed_at"), "last_success": None,
                        "freshness": item["freshness"], "freshness_basis": "configured_interval_plus_query_timeout",
                        "current_coverage": item.get("current_coverage", "unknown"),
                        "row_count": item.get("row_count"),
                        "usable_row_count": item.get("coverage", {}).get("usable_row_count"),
                        "elapsed_ms": item.get("elapsed_ms"), "observation_saved": observed,
                        "last_persisted_at": item.get("saved_at"), "evaluation_status": "unknown"}
                except (OSError, ValueError, TypeError, KeyError):
                    coverage[source] = {"status": "unknown", "current_coverage": "unknown", "row_count": None,
                        "usable_row_count": None, "elapsed_ms": None, "freshness": _freshness(None, _now(), None),
                        "reason": "saved_observation_unavailable", "observation_saved": False,
                        "evaluation_status": "unknown", "observed_at": None, "last_success": None}
            scoped["source_coverage"] = coverage
        try:
            listing = self.events(namespace, limit)
        except (OSError, ValueError, TypeError, KeyError, StoreError, sqlite3.Error):
            listing = {"namespace": namespace, "events": [], "total": None, "exported": 0,
                       "truncated": None, "status": "unknown", "reason": "namespace_storage_unavailable"}
        gate = _shutdown_status(document["last_report"], namespace)
        blocked_reason = gate["reason"] if gate is not None and gate["state"] == "blocked" else None
        last_error = document["last_report"].get("last_error") if monitor_namespace == namespace else None
        if type(last_error) is not str or last_error not in {
            "observation_persistence_failed", "monitor_gap_persistence_failed", "progress_persistence_failed",
            "queue_capacity_or_storage_failure", "event_evaluation_failed", "owned_query_shutdown_failed"}:
            last_error = blocked_reason
        return {"tool_version": __version__, "namespace": namespace,
                "operator_summary": _operator_summary(scoped, namespace),
                "current_monitor": current, "monitor_namespace": monitor_namespace,
                "source_coverage": _overview_coverage(scoped["source_coverage"]),
                "source_coverage_namespace": namespace,
                "event_storage": document["namespaces"][namespace], "event_list": listing,
                "agent_budget": document["agent_budget"],
                "background": _background_status(self.runtime, namespace),
                "progress": document["last_report"].get("progress") if monitor_namespace == namespace else None,
                "monitor_gap": document["last_report"].get("monitor_gap") if monitor_namespace == namespace else None,
                "monitor_shutdown_gate": gate, "reason": blocked_reason, "last_error": last_error,
                "agent_required": False, "model_calls": 0, "incident_conclusion": "not_assessed"}

    def observation(self, source_id, namespace="live", limit=20):
        if type(source_id) is not str or source_id not in SOURCES or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("invalid_observation_request")
        self.runtime.data_dir(namespace, create=False)
        value = self.runtime.observation(source_id, namespace, limit)
        if value is None:
            return {"namespace": namespace, "source_id": source_id, "status": "not_observed",
                    "row_count": None, "exported": 0, "truncated": False, "rows": [],
                    "coverage": {"status": "unknown"}, "observed_at": None,
                    "freshness": _freshness(None, _now(), None),
                    "explanation": "此來源尚無保存觀察，不能解讀為成功讀取零筆或沒有風險。",
                    "system_query_executed": False, "model_calls": 0}
        section = value["section"]
        status_value = section.get("status")
        if status_value not in {"ok", "partial", "denied", "unknown", "not_applicable", "error", "timeout", "cancelled", "busy", "not_requested"}:
            status_value = "unknown"
        try:
            config = self.runtime.config()
            max_age = config["interval_seconds"][source_id] + config["query_timeout_seconds"]
        except (OSError, ValueError, TypeError, KeyError):
            max_age = None
        fresh = _freshness(section.get("observed_at"), _now(), max_age)
        rows = [row_view(row) for row in section.get("rows", [])[:limit] if isinstance(row, dict)]
        total = value.get("total")
        total = total if type(total) is int and total >= len(rows) else None
        return {"namespace": namespace, "source_id": source_id, "status": status_value,
                "current_coverage": status_value if fresh["state"] == "fresh" else "unknown",
                "row_count": total, "exported": len(rows),
                "truncated": value.get("truncated") is True or total is not None and total > len(rows),
                "rows": rows, "coverage": coverage_metadata(section),
                "observed_at": section.get("observed_at"), "saved_at": value.get("saved_at"),
                "freshness": fresh, "elapsed_ms": section.get("elapsed_ms"),
                "explanation": "這是最後保存的唯讀來源觀察；時間、可見性與截斷限制均保留，不能證明主機安全。",
                "system_query_executed": False, "model_calls": 0, "data_trust": "untrusted_data"}

    def stop(self, namespace=None):
        background_result = None
        background_path = self.runtime.path("data/background/control.json")
        if background_path.is_file():
            current = _background_status(self.runtime)
            if namespace is None or current.get("namespace") == namespace:
                background_result = (self.background_stop() if namespace is None else
                                     self.background_stop(expected_namespace=namespace))
        if namespace is not None:
            self.runtime.data_dir(namespace, create=False)  # Validate scope.
            owner_path = self.runtime.path("data/monitor-owner.json")
            if not owner_path.is_file():
                return background_result or {"status": "not_running", "reason": "no_current_owner_record", "process_terminated": False}
            owner, health = read_json(owner_path), self.runtime.health()
            instance_id = owner.get("instance_id") if isinstance(owner, dict) else None
            if not isinstance(health, dict) or type(instance_id) is not str or re.fullmatch(r"[a-f0-9]{32}", instance_id) is None:
                return background_result or {"status": "blocked", "reason": "monitor_scope_unverifiable", "process_terminated": False}
            if health.get("namespace") != namespace or health.get("instance_id") != owner.get("instance_id"):
                return background_result or {"status": "not_applicable", "reason": "monitor_outside_launcher_namespace", "process_terminated": False}
            result = self.runtime.request_stop(expected_instance_id=instance_id)
        else:
            result = self.runtime.request_stop()
        if background_result is not None:
            return {**background_result, "monitor_stop": result,
                    "note": ("Background remains disabled until an explicit start; ACK and pending events are unchanged."
                             if background_result.get("desired_enabled") is False else
                             "Background state may have changed; inspect status. ACK and pending events are unchanged.")}
        return result

    def background_start(self):
        from .background import start
        if self._background_lifetime_owner == "independent":
            return start(self.runtime.root)
        if self._background_owner_closed.is_set():
            return {"state": "blocked", "reason": "operator_monitor_owner_closed", "model_calls": 0}
        with self._background_owner_lock:
            if self._background_owner_closed.is_set():
                return {"state": "blocked", "reason": "operator_monitor_owner_closed", "model_calls": 0}
            self._release_exited_monitor_children()
            return start(self.runtime.root, lifetime_owner="application", child_owner=self._own_monitor_child)

    def _own_monitor_child(self, child):
        """Capture only a child created by our start, never a saved existing host."""
        scope = getattr(child, "_eventguard_background_scope", None)
        if (not isinstance(scope, dict) or scope.get("kind") != "eventguard-background-owned-launch-v1"
                or type(scope.get("run_id")) is not str or re.fullmatch(r"[a-f0-9]{32}", scope["run_id"]) is None
                or type(scope.get("control_generation")) is not str
                or re.fullmatch(r"[a-f0-9]{32}", scope["control_generation"]) is None
                or type(scope.get("job_name")) is not str
                or re.fullmatch(r"Global\\EventGuard-[a-f0-9]{32}", scope["job_name"]) is None
                or scope["job_name"] != getattr(getattr(child, "job", None), "name", None)
                or scope.get("namespace") not in {"live", "test"}
                or scope.get("pid") != child.pid or scope.get("created_at") != child.created_at):
            # Retain the actual fresh child even if its launch evidence cannot
            # be used to change shared intent. Cleanup still owns its Job.
            scope = None
        with self._background_owner_lock:
            self._background_children.append({"child": child, "scope": dict(scope) if scope is not None else None})

    @staticmethod
    def _monitor_child_exited(receipt):
        return (isinstance(receipt, dict) and receipt.get("child_exited") is True
                and type(receipt.get("remaining_owned_processes")) is int
                and receipt["remaining_owned_processes"] == 0)

    def _release_exited_monitor_children(self):
        """Release handles only after both process and private Job are empty."""
        from . import processes
        remaining = []
        for record in self._background_children:
            child = record["child"]
            try:
                if child.poll() is None or child.job.active() != 0:
                    remaining.append(record)
                    continue
                receipt = processes.finish(child, "cancelled", grace=0, request_stop=False)
                if self._monitor_child_exited(receipt):
                    self._background_receipts.append(receipt)
                else:
                    remaining.append(record)
            except (OSError, ValueError, TypeError, RuntimeError):
                remaining.append(record)
        self._background_children = remaining
        self._background_receipts = self._background_receipts[-32:]

    def close_owned_monitor(self, grace_seconds=5):
        """EOF cleanup: fence admission, then stop only this API's captured hosts.

        This is adapter lifecycle, deliberately absent from public operations.
        A different client's newer intent is never disabled. The retained real
        child/Job remains our only force-cleanup authority after the grace.
        """
        if type(grace_seconds) not in (int, float) or not 0 <= grace_seconds <= 30:
            raise ValueError("invalid_operator_monitor_close_grace")
        from . import background, processes
        # Fence even callers waiting for the ownership lock. An already
        # accepted Start completes under that lock and is included below.
        self._background_owner_closed.set()
        with self._background_owner_lock:
            if not self._background_children and self._background_shutdown_result is not None:
                return self._background_shutdown_result
            results, remaining = [], []
            for record in self._background_children:
                child, scope = record["child"], record["scope"]
                stopped = None
                if scope is not None:
                    try:
                        stopped = background.stop(self.runtime.root, grace_seconds=grace_seconds,
                            expected_namespace=scope["namespace"], expected_run_id=scope["run_id"],
                            expected_control_generation=scope["control_generation"], expected_job_name=scope["job_name"])
                    except (OSError, ValueError, TypeError, RuntimeError):
                        stopped = {"state": "shutdown_unconfirmed", "reason": "operator_owned_stop_unconfirmed",
                                   "raw_error_omitted": True}
                if ((stopped or {}).get("process") or {}).get("forcibly_terminated") is True:
                    record["forced_process"] = stopped["process"]
                try:
                    receipt = processes.finish(child, "cancelled", grace=grace_seconds, request_stop=False)
                    if receipt.get("forcibly_terminated") is True:
                        record["forced_process"] = receipt
                    confirmed = self._monitor_child_exited(receipt)
                    results.append({"scope": scope, "stop": stopped, "process": receipt,
                                    "forced_process": record.get("forced_process")})
                    if confirmed:
                        self._background_receipts.append(receipt)
                    else:
                        remaining.append(record)
                except (OSError, ValueError, TypeError, RuntimeError):
                    remaining.append(record)
                    results.append({"scope": scope, "stop": stopped, "child_exited": None,
                                    "forced_process": record.get("forced_process"),
                                    "reason": "operator_owned_monitor_cleanup_unconfirmed", "raw_error_omitted": True})
            self._background_children = remaining
            self._background_receipts = self._background_receipts[-32:]
            forced = any((item.get("process") or {}).get("forcibly_terminated") is True
                         or ((item.get("stop") or {}).get("process") or {}).get("forcibly_terminated") is True
                         or item.get("forced_process") is not None
                         for item in results)
            evidence_saved = None
            if results:
                # One bounded last receipt for this installation, never one
                # file per MCP connection and never the new host's control or
                # stop receipt. Empty observers cannot overwrite this proof.
                entries = []
                for item in results[-32:]:
                    stopped = item.get("stop") or {}
                    entries.append({"scope": item["scope"], "process": item.get("process"),
                        "forced_process": item.get("forced_process"),
                        "stop": {key: stopped[key] for key in ("state", "reason", "desired_enabled", "disabled_persisted", "process") if key in stopped},
                        "reason": item.get("reason"), "child_exited": item.get("child_exited")})
                try:
                    atomic_json(self.runtime.path("data/background/operator-stop-receipt.json"),
                        {"kind": "eventguard-operator-monitor-shutdown-v1", "recorded_at": utc_now(),
                         "child_exited": not remaining, "forcibly_terminated": forced,
                         "results": entries, "truncated": len(results) > len(entries)}, 128 * 1024)
                    evidence_saved = True
                except (OSError, ValueError, TypeError, RuntimeError):
                    evidence_saved = False
            self._background_shutdown_result = {"state": "shutdown_unconfirmed" if remaining else "closed", "child_exited": not remaining,
                    "owned_monitors_remaining": len(remaining), "owned_monitor_results": results,
                    "forcibly_terminated": forced, "evidence_saved": evidence_saved,
                    "evidence_write_failed": evidence_saved is False,
                    "lifetime_owner": self._background_lifetime_owner,
                    "lifetime_limited": self._background_lifetime_owner == "application", "model_calls": 0}
            return self._background_shutdown_result

    def background_status(self):
        return _background_status(self.runtime)

    def background_stop(self, grace_seconds=10, *, expected_namespace=None):
        from .background import stop
        result = stop(self.runtime.root, grace_seconds=grace_seconds, expected_namespace=expected_namespace)
        if self._background_lifetime_owner == "application":
            with self._background_owner_lock:
                process = result.get("process") or {}
                if process.get("forcibly_terminated") is True:
                    for record in self._background_children:
                        child = record["child"]
                        if (process.get("job_name") == child.job.name and process.get("pid") == child.pid
                                and process.get("created_at") == child.created_at):
                            record["forced_process"] = process
                self._release_exited_monitor_children()
        return result

    def monitor(self, **kwargs):
        from .monitor import Monitor
        return Monitor(self.runtime.root).run(**kwargs)

    def events(self, namespace="live", limit=100):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("event_limit_out_of_bounds")
        events, total = _report_events(self.runtime, namespace, limit)
        return {"namespace": namespace, "events": [event_view(e) for e in events], "total": total,
                "exported": len(events), "truncated": total > len(events), "limit": limit,
                "ack_meaning": "received_only_not_case_closed"}

    def _event(self, event_id, namespace):
        rows = read_events(self.runtime, namespace, event_id=event_id)
        if not rows:
            raise ValueError("event_not_found")
        return rows[0]

    def inspect_event(self, event_id, namespace="live"):
        event = self._event(event_id, namespace)
        return {**review(event), "guidance": event_guidance(event),
                "latest_diagnosis": saved_review(self.runtime, namespace, event), "latest_diagnosis_is_saved": True, "namespace": namespace}

    def diagnose_event(self, event_id, namespace="live"):
        event = self._event(event_id, namespace)
        diagnostic_api = self.diagnostic_api
        if diagnostic_api is None and event["synthetic"] is False:
            from .diagnostics.api import DiagnosticAPI
            from .collectors.windows import WindowsCollectors
            diagnostic_api = DiagnosticAPI(WindowsCollectors(timeout=self.runtime.config().get("query_timeout_seconds", 15)))
        result = review(event, diagnostic_api, refresh=True)
        # Native synthetic queries are denied, rather than persisted as if a
        # diagnosis happened. Fixture-injected tests are labelled in review().
        if result["status"] == "not_applicable":
            return dict(result, namespace=namespace, saved=False)
        result["namespace"] = namespace
        store(self.runtime, namespace).save_review(event_id, result["payload_hash"], result)
        return dict(result, saved=True)

    @staticmethod
    def _already_received(event, namespace):
        return {"status": "already_received", "event_id": event["event_id"], "namespace": namespace,
                "outbox_acknowledged": True, "new_receipt_created": False,
                "ack_semantics": "received_only_not_case_closed", "incident_conclusion": "not_assessed",
                "model_calls": 0, "real_agent_woken": False}

    def _operator_inbox(self, event_id, namespace):
        from .agent_dispatch import _bind_channel
        from .queue_inbox import QueueInbox
        source = self.runtime.data_dir(namespace, create=False)
        state = self.runtime.path("data/agent-delivery" if namespace == "live" else "data/agent-delivery-test")
        _bind_channel(source, state)
        return QueueInbox(source, state, event_id=event_id, allow_live=namespace == "live",
                          limits=self.runtime.config().get("inbox"))

    def receive_event(self, event_id, namespace="live"):
        event = self._event(event_id, namespace)
        if event["delivery_status"] == "ack":
            return self._already_received(event, namespace)
        if event["delivery_status"] == "failed":
            return {"status": "blocked", "reason": "failed_event_requires_explicit_retry",
                    "event_id": event_id, "namespace": namespace, "outbox_acknowledged": False,
                    "next_steps": [_step("retry_event", "明確重試此單一失敗事件；不重設每日預算，也不啟動模型。", event_id=event_id, namespace=namespace)]}
        inbox = self._operator_inbox(event_id, namespace)
        received = inbox.receive_event()
        query = inbox.query_evidence(event_id)
        return {**received, "namespace": namespace, "query_id": query["query_id"],
                "query": query, "outbox_acknowledged": False,
                "ack_semantics": "received_only_not_case_closed", "model_calls": 0,
                "next_steps": [_step("inspect_event", "查看此事件的具體保存觀察與查證計畫。", event_id=event_id, namespace=namespace),
                               _step("ack_event", "明確確認已收到；保留查證未知，不代表事件已修復或結案。",
                                     event_id=event_id, query_id=query["query_id"], decision="reviewed_metadata", namespace=namespace)]}

    def ack_event(self, event_id, query_id, decision="reviewed_metadata", namespace="live"):
        if type(query_id) is not str or not IDENTIFIER.fullmatch(query_id) or type(decision) is not str or decision not in {"reviewed_metadata", "needs_more_evidence"}:
            raise ValueError("invalid_event_receipt_request")
        event = self._event(event_id, namespace)
        if event["delivery_status"] == "ack":
            # An existing source ACK proves receipt, not that this caller's
            # query/decision is its retained receipt. Never reconstruct missing
            # inbox evidence or write a second receipt while checking a replay.
            from .queue_inbox import QueueInbox, QueueInboxError
            source = self.runtime.data_dir(namespace, create=False)
            state = self.runtime.path("data/agent-delivery" if namespace == "live" else "data/agent-delivery-test")
            try:
                inbox = QueueInbox.open_readonly(source, state, event_id, allow_live=namespace == "live")
            except QueueInboxError as error:
                if error.args and error.args[0] in {"existing_inbox_state_required", "existing_inbox_policy_required"}:
                    raise QueueInboxError("ack_replay_evidence_unavailable") from None
                raise
            evidence = inbox.evidence(event_id)
            if evidence is None or "query_id" not in evidence or "result" not in evidence:
                raise QueueInboxError("ack_replay_evidence_unavailable")
            if evidence["query_id"] != query_id:
                raise QueueInboxError("same_event_query_required")
            if evidence["result"]["decision"] != decision:
                raise QueueInboxError("inbox_result_decision_conflict")
            if not inbox.acknowledged(event_id):
                raise QueueInboxError("ack_replay_evidence_unavailable")
            return {**self._already_received(event, namespace), "query_id": query_id,
                    "decision": decision, "result_id": evidence["result"]["result_id"],
                    "ack_replay_verified": True}
        inbox = self._operator_inbox(event_id, namespace)
        result = inbox.ack_event(event_id, query_id, decision)
        return {**result, "namespace": namespace, "ack_semantics": "received_only_not_case_closed",
                "model_calls": 0, "real_agent_woken": False}

    def retry_event(self, event_id, namespace="live"):
        event = self._event(event_id, namespace)
        if event["delivery_status"] == "ack":
            return self._already_received(event, namespace)
        if event["delivery_status"] != "failed":
            return {"status": "not_applicable", "reason": "only_failed_event_can_be_retried",
                    "event_id": event_id, "namespace": namespace, "model_calls": 0}
        try:
            changed = store(self.runtime, namespace).retry_failed(event_id)
        except StoreError as error:
            if error.args == ("replay_requires_receipt_check",):
                return {"status": "blocked", "reason": "dedup_window_expired_requires_receipt_review",
                        "event_id": event_id, "namespace": namespace, "budget_reset": False,
                        "agent_attempts_reset": False, "model_started": False, "model_calls": 0}
            raise
        return {"status": "retry_requested" if changed else "not_applicable", "event_id": event_id,
                "namespace": namespace, "pending": bool(changed), "budget_reset": False,
                "agent_attempts_reset": False, "model_started": False, "model_calls": 0,
                "ack_semantics": "received_only_not_case_closed"}

    def report(self, namespace="live"):
        return export_report(self.runtime, namespace)


def _report_events(runtime, namespace, limit=1000):
    """Count and page from one read-only SQLite snapshot, without OS queries."""
    path = runtime.data_dir(namespace, create=False) / "eventguard.sqlite3"
    runtime.path(path.relative_to(runtime.root))
    if not path.is_file():
        return [], 0
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        total = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        rows = db.execute("SELECT * FROM events ORDER BY created_at DESC,event_id LIMIT ?", (limit,))
        return [EventStore._row(row) for row in rows], total


def export_report(runtime, namespace):
    events, total = _report_events(runtime, namespace)
    # Export saved source evidence only. Never invoke owner identity, a live
    # collector, a budget initialization, or a model as a reporting side effect.
    api = OperatorAPI(runtime.root)
    source_observations = {}
    for source in SOURCES:
        try:
            source_observations[source] = api.observation(source, namespace, 20)
        except (OSError, ValueError, TypeError, KeyError):
            source_observations[source] = {"source_id": source, "status": "unknown", "row_count": None,
                                           "rows": [], "reason": "saved_observation_unavailable",
                                           "system_query_executed": False}
    completeness = {"total": total, "exported": len(events), "truncated": total > len(events), "limit": 1000}
    document = {"schema_version": "1.0", "tool_version": __version__, "exported_at": utc_now(), "namespace": namespace,
                "real_agent_connected": False, "agent_required": False,
                "note": "本機事件與投遞狀態；ACK 不代表診斷、結案或主機安全。文字皆為不可信資料。",
                **completeness,
                "source_observations": source_observations,
                "events": events,
                "reviews": [{**review(e), "guidance": event_guidance(e), "latest_diagnosis": saved_review(runtime, namespace, e)} for e in events]}
    runtime.ensure()
    prefix = "eventguard-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    json_path = runtime.path("reports/" + prefix + ".json")
    html_path = runtime.path("reports/" + prefix + ".html")
    with json_path.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
    escaped = html.escape(json.dumps(document, ensure_ascii=False, indent=2), quote=True)
    event_rows = []
    for item in document["reviews"]:
        guidance, diagnosis = item["guidance"], item["latest_diagnosis"]
        diagnosis_text = "尚未執行目前狀態查證"
        if diagnosis:
            diagnosis_text = diagnosis["status"] + "；" + "；".join(
                row["operation"] + ":" + row["status"] + "，" + str(len(row["rows"])) + " 筆，" + (row["observed_at"] or "時間未知")
                for row in diagnosis["observations"])
        event_rows.append("<tr>" + "".join("<td>" + html.escape(str(value), quote=True) + "</td>" for value in (
            item["event"]["event_id"], item["event"]["severity"], guidance["observation"],
            json.dumps(guidance["binding_facts"], ensure_ascii=False), item["event"]["coverage_status"],
            diagnosis_text, "；".join(guidance["next_steps"]))) + "</tr>")
    rows = "".join(event_rows)
    completeness_note = '<p>保存資料快照：共 ' + str(total) + ' 件，匯出 ' + str(len(events)) + ' 件；' + ('已截斷，這不是完整清單。' if completeness['truncated'] else '清單未截斷。') + ' 匯出不代表目前仍在監看或資料仍新鮮。</p>'
    source_rows = "".join("<tr>" + "".join("<td>" + html.escape(str(value), quote=True) + "</td>" for value in (
        source, item["status"], "未知" if item.get("row_count") is None else item["row_count"],
        item.get("observed_at") or "尚無觀察時間", item.get("freshness", {}).get("state", "unknown"),
        json.dumps(item.get("coverage", {}), ensure_ascii=False))) + "</tr>" for source, item in source_observations.items())
    source_table = '<h2>逐來源保存觀察</h2><p>筆數是上次保存的來源範圍，不是風險計數；未知不等於零。完整觀察與拒讀原因見下方結構化證據。</p><table><tr><th>來源</th><th>可見性</th><th>筆數</th><th>觀察時間</th><th>新鮮度</th><th>原因／限制</th></tr>' + source_rows + '</table>'
    page = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>EventGuard 本機報告</title><style>body{font:15px sans-serif;max-width:1100px;margin:32px auto;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}td,th{padding:8px;border:1px solid #aaa;overflow-wrap:anywhere}table{border-collapse:collapse}</style><h1>EventGuard 本機事件與查證報告</h1><p>事件及名稱皆為不可信資料。ACK 不代表診斷、結案或主機安全。</p>' + completeness_note + source_table + '<h2>事件與查證</h2><table><tr><th>事件</th><th>嚴重度</th><th>觀測說明</th><th>具體觀測</th><th>可見性</th><th>查證</th><th>下一步唯讀查證</th></tr>' + rows + '</table><details><summary>結構化證據</summary><pre>' + escaped + '</pre></details></html>'
    with html_path.open("x", encoding="utf-8") as stream:
        stream.write(page)
    return {"json": str(json_path), "html": str(html_path), "event_count": len(events), **completeness}
