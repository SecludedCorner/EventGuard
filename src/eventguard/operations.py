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
import uuid

from . import __version__
from .runtime import Runtime, utc_now, read_json
from .events.store import EventStore, event_payload_hash
from .events.schema import validate_event
from .diagnostics.review import event_view, review, validate_saved_review

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
        result[source] = {"status": item.get("status", "unknown"), "observed_at": item.get("observed_at"),
                          "last_success": item.get("last_success"), "freshness": freshness,
                          "freshness_basis": "configured_interval_plus_query_timeout",
                          "current_coverage": item.get("status", "unknown") if freshness["state"] == "fresh" else "unknown"}
    return result


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
                rotation = dict(db.execute("SELECT key,value FROM meta WHERE key IN ('rotated_ack','expired_receipts','pressure_rotated_receipts')"))
            return {"state": "available", "counts": counts, "events": sum(counts.values()),
                    "storage_bytes": path.stat().st_size, "receipt_count": receipts,
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


def status(runtime):
    now = _now()
    try:
        health = runtime.health()
        if not isinstance(health, dict):
            raise ValueError("health_report_invalid")
    except (OSError, ValueError, TypeError):
        health = {"state": "unknown", "monitoring": None, "reason": "last_report_unavailable"}
    heartbeat = _freshness(health.get("heartbeat_at"), now, HEARTBEAT_MAX_AGE)
    return {"tool_version": __version__, "health": health, "last_report": health,
            "heartbeat_age_seconds": heartbeat["age_seconds"],
            "liveness": "on_demand_owner_check; no independent watchdog",
            "current_monitor": _current_monitor(runtime, health, heartbeat),
            "source_coverage": _coverage_status(runtime, health, now),
            "namespaces": {namespace: _namespace_status(runtime, namespace) for namespace in ("live", "test")},
            "agent_budget": _budget_status(runtime),
            "agent_ingress": "not_configured", "real_agent_woken": False}


class OperatorAPI:
    def __init__(self, root, diagnostic_api=None):
        self.runtime = Runtime(root)
        # Explicit test injection only; synthetic input never instantiates a
        # native diagnostic implementation by itself.
        self.diagnostic_api = diagnostic_api

    def call(self, operation, *args, **kwargs):
        """Shared public error envelope: never forward an OS exception/path."""
        if operation not in {"capabilities", "status", "stop", "monitor", "events", "inspect_event", "diagnose_event", "report"}:
            return {"status": "invalid_request", "error_code": "input_or_config_validation_failed", "raw_error_omitted": True}
        try:
            return getattr(self, operation)(*args, **kwargs)
        except (ValueError, TypeError, json.JSONDecodeError):
            return {"status": "invalid_request", "error_code": "input_or_config_validation_failed", "raw_error_omitted": True}
        except Exception as error:
            return {"status": "error", "error_code": "capacity_or_storage_failure" if type(error).__name__ in {"CapacityError", "StoreError"} else "operation_failed", "raw_error_omitted": True}

    def capabilities(self):
        from .diagnostics.api import DiagnosticAPI
        return {"tool_version": __version__, "diagnostics": DiagnosticAPI().capabilities(),
                "monitor": "foreground, cooperative stop, singleton", "transport": ["disabled", "synthetic-only local mock"],
                "remediation": [], "gui": False, "model_calls": 0, "real_agent_ingress": "not_configured",
                "operator_operations": ["capabilities", "status", "stop", "events", "inspect_event", "diagnose_event", "report", "monitor"],
                "agent_required": False, "data_trust": "untrusted_data",
                "optional_agent_ingress": {"entry": "scripts/eventguard_watch.py", "mode": "explicit_bounded_foreground",
                                            "default_enabled": False, "projection": "fixed-minimal-v1"}}

    def status(self):
        return status(self.runtime)

    def stop(self, namespace=None):
        if namespace is not None:
            self.runtime.data_dir(namespace, create=False)  # Validate scope.
            owner_path = self.runtime.path("data/monitor-owner.json")
            if owner_path.is_file():
                owner, health = read_json(owner_path), self.runtime.health()
                if health.get("namespace") != namespace or health.get("instance_id") != owner.get("instance_id"):
                    return {"status": "not_applicable", "reason": "monitor_outside_launcher_namespace", "process_terminated": False}
        return self.runtime.request_stop()

    def monitor(self, **kwargs):
        from .monitor import Monitor
        return Monitor(self.runtime.root).run(**kwargs)

    def events(self, namespace="live", limit=100):
        return {"namespace": namespace, "events": [event_view(e) for e in read_events(self.runtime, namespace, limit)]}

    def _event(self, event_id, namespace):
        rows = read_events(self.runtime, namespace, event_id=event_id)
        if not rows:
            raise ValueError("event_not_found")
        return rows[0]

    def inspect_event(self, event_id, namespace="live"):
        event = self._event(event_id, namespace)
        return {**review(event), "latest_diagnosis": saved_review(self.runtime, namespace, event), "latest_diagnosis_is_saved": True, "namespace": namespace}

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

    def report(self, namespace="live"):
        return export_report(self.runtime, namespace)


def _report_events(runtime, namespace):
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
        rows = db.execute("SELECT * FROM events ORDER BY created_at DESC,event_id LIMIT 1000")
        return [EventStore._row(row) for row in rows], total


def export_report(runtime, namespace):
    events, total = _report_events(runtime, namespace)
    completeness = {"total": total, "exported": len(events), "truncated": total > len(events), "limit": 1000}
    document = {"schema_version": "1.0", "tool_version": __version__, "exported_at": utc_now(), "namespace": namespace,
                "real_agent_connected": False, "agent_required": False,
                "note": "本機事件與投遞狀態；ACK 不代表診斷、結案或主機安全。文字皆為不可信資料。",
                **completeness,
                "events": events,
                "reviews": [{**review(e), "latest_diagnosis": saved_review(runtime, namespace, e)} for e in events]}
    runtime.ensure()
    prefix = "eventguard-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    json_path = runtime.path("reports/" + prefix + ".json")
    html_path = runtime.path("reports/" + prefix + ".html")
    with json_path.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
    escaped = html.escape(json.dumps(document, ensure_ascii=False, indent=2), quote=True)
    rows = "".join("<tr>" + "".join("<td>" + html.escape(str(value), quote=True) + "</td>" for value in
                   (item["event"]["event_id"], item["event"]["severity"], item["event"]["explanation"], json.dumps(item["event"]["facts"], ensure_ascii=False), item["event"]["coverage_status"],
                    item["latest_diagnosis"]["status"] if item["latest_diagnosis"] else "尚未執行目前狀態查證")) + "</tr>" for item in document["reviews"])
    completeness_note = '<p>保存資料快照：共 ' + str(total) + ' 件，匯出 ' + str(len(events)) + ' 件；' + ('已截斷，這不是完整清單。' if completeness['truncated'] else '清單未截斷。') + ' 匯出不代表目前仍在監看或資料仍新鮮。</p>'
    page = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>EventGuard 本機報告</title><style>body{font:15px sans-serif;max-width:1100px;margin:32px auto;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}td,th{padding:8px;border:1px solid #aaa}table{border-collapse:collapse}</style><h1>EventGuard 本機事件與查證報告</h1><p>事件及名稱皆為不可信資料。ACK 不代表診斷、結案或主機安全。</p>' + completeness_note + '<table><tr><th>事件</th><th>嚴重度</th><th>觀測說明</th><th>具體觀測</th><th>可見性</th><th>查證</th></tr>' + rows + '</table><details><summary>結構化證據</summary><pre>' + escaped + '</pre></details></html>'
    with html_path.open("x", encoding="utf-8") as stream:
        stream.write(page)
    return {"json": str(json_path), "html": str(html_path), "event_count": len(events), **completeness}
