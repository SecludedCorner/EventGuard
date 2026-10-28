"""Prepare a single-source baseline check; --execute needs same-run approval.

No socket injection is implemented: the production rule deliberately excludes
loopback listeners. A complete baseline never means that this host is safe.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).absolute().parents[1] / "src"))
from eventguard.local_paths import LocalWaitError, _guard
from eventguard.runtime import safe_child


KIND = "eventguard-windows-listener-baseline-v1"
TIMEOUT_SEC = 30
QUERY_TIMEOUT_SEC = 5  # Reserve the remaining budget for owned-Job cleanup.
MAX_JSON_BYTES = 65536
OPERATIONS = (
    "GetExtendedTcpTableIPv4", "GetExtendedTcpTableIPv6",
    "GetExtendedUdpTableIPv4", "GetExtendedUdpTableIPv6",
)
# These are existing collector evidence codes, not inferred root causes. Never
# copy an arbitrary reason/operation/exception string into a saved baseline.
ERROR_STAGES = frozenset({"launch", "provider", "object", "field", "policy"})
ERROR_STATUSES = frozenset({"ok", "partial", "denied", "unknown", "timeout", "error",
                            "cancelled", "not_applicable", "busy", "not_requested"})
ERROR_OPERATIONS = frozenset({"ListenerOpenProcess", "ListenerGetProcessTimes", "ListenerProcessIdentity",
                             "OpenProcess", "GetProcessTimes", "GetExtendedTcpTable", "GetExtendedUdpTable",
                             "listeners", "collect"})
ERROR_REASONS = frozenset({"access_denied", "object_unavailable", "api_unavailable", "listener_pid_reused",
                          "query_failed", "native_budget_exceeded", "cancelled_before_query",
                          "backend_reason_unavailable", "invalid_collector_output"})
MAX_ERROR_RECORDS = 64  # Same retained-prefix limit as collectors.contract.MAX_ERRORS.
SOURCE_FILES = (
    "scripts/validate_windows_listener.py", "scripts/eventguard_collect.py",
    "src/eventguard/collectors/windows.py", "src/eventguard/collectors/worker.py",
    "src/eventguard/collectors/runner.py", "src/eventguard/collectors/native.py",
    "src/eventguard/collectors/contract.py", "src/eventguard/processes.py",
    "src/eventguard/collectors/winapi.py",
    "src/eventguard/rules/detector.py", "src/eventguard/local_paths.py", "src/eventguard/runtime.py",
)
SCOPE = {
    "profile": "baseline-only", "source": "listeners", "backend": "native",
    "timeout_sec": TIMEOUT_SEC, "query_timeout_sec": QUERY_TIMEOUT_SEC,
    "query_limit": 1, "owned_job_only": True, "native_collection": True,
    "save_raw_facts": False, "model_calls": 0, "socket_bind": False,
    "registry_write": False, "system_changes": False, "extra_sources": False,
}


class ValidationError(ValueError):
    """Only fixed reason codes may cross the command boundary."""


def utc_now():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _time(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is not None:
            return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        pass
    raise ValidationError("approval_time_invalid")


def _plain_path(path):
    """Reuse the project owned-data guard, also reject other reparse types."""
    try:
        path = _guard(path)
    except LocalWaitError:
        raise ValidationError("redirected_path_rejected") from None
    for part in [*reversed(path.parents), path]:
        if not part.exists() and not part.is_symlink():
            continue
        entry = part.lstat()
        if stat.S_ISLNK(entry.st_mode) or getattr(entry, "st_file_attributes", 0) & 0x400:
            raise ValidationError("redirected_path_rejected")
    return path


def _root(root, project):
    project = _plain_path(project)
    path = Path(root)
    if not path.is_absolute():
        path = project / path
    if ".." in path.parts:
        raise ValidationError("dedicated_root_required")
    path = _plain_path(path)
    if path.parent != project / "reports" or not re.fullmatch(r"windows-listener-[A-Za-z0-9-]{1,100}", path.name):
        raise ValidationError("dedicated_root_required")
    try:
        return safe_child(project, Path("reports") / path.name)
    except ValueError:
        raise ValidationError("redirected_path_rejected") from None


def _read(path):
    path = _plain_path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_JSON_BYTES:
        raise ValidationError("evidence_file_invalid")
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValidationError("evidence_file_invalid")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValidationError("evidence_json_invalid") from None
    if not isinstance(value, dict):
        raise ValidationError("evidence_json_invalid")
    return value


def _write(path, value):
    path = _plain_path(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _digest(path):
    path = _plain_path(path)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValidationError("source_file_invalid")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes(project):
    return {name: _digest(Path(project) / name) for name in SOURCE_FILES}


def prepare(root, project, *, now=None):
    root = _root(root, project)
    now = now or utc_now()
    manifest = {
        "kind": KIND, "run_id": uuid.uuid4().hex, "root": str(root),
        "prepared_at": stamp(now), "scope": dict(SCOPE),
        "source_sha256": _source_hashes(project),
        "loopback_lifecycle": {"status": "blocked", "reason": "listener_rule_excludes_loopback"},
    }
    root.mkdir(exist_ok=False)
    _write(root / "manifest.json", manifest)
    request = {
        "kind": KIND + "-approval", "approved": False,
        "run_id": manifest["run_id"], "root": str(root),
        "manifest_sha256": _digest(root / "manifest.json"), "scope": dict(SCOPE),
        "approved_at": None, "expires_at": None, "authorization_text": "",
    }
    _write(root / "human-approval.template.json", request)
    (root / "AUTHORIZATION_REQUEST.md").write_text(
        "# 單一 listeners baseline-only 批准請求\n\n"
        "本目錄只完成準備，沒有採集。需當次人類明確批准，將 template 填寫為 human-approval.json。\n"
        "範圍：一次 listeners 原生查核，總預算30秒、query 5秒，其餘預留自有 Job 收尾。\n"
        "只保存狀態／計數與自有 Job 退出摘要，不保存其他 listener facts。\n"
        "無 socket、registry、系統設定或模型操作；完整 loopback 流程仍 blocked：產品按設計不產生 loopback 候選。\n"
        "approved_at 不早於 prepared_at；expires_at 在批准後30分鐘內，且執行當下尚未到期。\n"
        "填入本次直接授權文字，檔案不能代替實際使用者授權。查核成功不代表主機安全或完整 OS 流程通過。\n",
        encoding="utf-8",
    )
    return {"status": "prepared", "reason": "explicit_approval_required", "root": str(root),
            "query_started": False, "full_lifecycle_verified": False}


def _same_scope(value):
    return (isinstance(value, dict) and value.keys() == SCOPE.keys()
            and all(type(value[key]) is type(expected) and value[key] == expected
                    for key, expected in SCOPE.items()))


def _check_approval(root, project, now):
    # Keep all admission checks before the native collector import/creation.
    manifest = _read(root / "manifest.json")
    if (manifest.get("kind") != KIND or manifest.get("root") != str(root)
            or not _same_scope(manifest.get("scope")) or not isinstance(manifest.get("run_id"), str)
            or not re.fullmatch(r"[a-f0-9]{32}", manifest["run_id"])):
        raise ValidationError("manifest_scope_mismatch")
    try:
        approval = _read(root / "human-approval.json")
    except FileNotFoundError:
        raise ValidationError("approval_missing") from None
    if (approval.get("kind") != KIND + "-approval" or approval.get("approved") is not True
            or approval.get("run_id") != manifest["run_id"] or approval.get("root") != str(root)
            or not _same_scope(approval.get("scope"))
            or approval.get("manifest_sha256") != _digest(root / "manifest.json")):
        raise ValidationError("approval_scope_mismatch")
    granted = _time(approval.get("approved_at"))
    expires = _time(approval.get("expires_at"))
    if not (_time(manifest.get("prepared_at")) <= granted <= now < expires <= granted + timedelta(minutes=30)):
        raise ValidationError("approval_not_current")
    text = approval.get("authorization_text")
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4096:
        raise ValidationError("authorization_text_required")
    if manifest.get("source_sha256") != _source_hashes(project):
        raise ValidationError("source_changed_since_prepare")
    return manifest


def _count(value):
    return value if type(value) is int and 0 <= value <= 2**31 - 1 else None


def summarize_errors(coverage):
    """Aggregate the existing bounded evidence prefix; no owner or row linkage.

    Missing/truncated evidence stays missing. In particular, object_unavailable
    does not prove process exit, and listener_pid_reused records only the
    collector's creation-after-capture check, not an observed process history.
    """
    coverage = coverage if isinstance(coverage, dict) else {}
    records = coverage.get("errors")
    available = isinstance(records, list)
    records = records if available else []
    reported = _count(coverage.get("error_count"))
    groups, unknown = {}, 0
    dimensions = (("stage", ERROR_STAGES), ("operation", ERROR_OPERATIONS),
                  ("reason_code", ERROR_REASONS), ("status", ERROR_STATUSES))
    for record in records[:MAX_ERROR_RECORDS]:
        record = record if isinstance(record, dict) else {}
        key = tuple(value if isinstance(value := record.get(name), str) and value in allowed
                    else "unknown" for name, allowed in dimensions)
        # status=unknown can be a precise observation (e.g. creation mismatch).
        unknown += not all(isinstance(record.get(name), str) and record[name] in allowed
                           for name, allowed in dimensions)
        groups[key] = groups.get(key, 0) + 1
    retained = min(len(records), MAX_ERROR_RECORDS)
    consistent = available and reported is not None and reported >= len(records)
    omitted = reported - retained if consistent else None
    truncated = coverage.get("errors_truncated") is True or len(records) > MAX_ERROR_RECORDS
    return {"kind": "eventguard-listener-error-counts-v1", "evidence_available": available,
            "reported_count": reported, "retained_count": retained,
            "classified_count": retained - unknown, "unknown_count": unknown,
            "unretained_count": omitted, "count_consistent": consistent,
            "truncated": truncated, "complete": bool(consistent and not truncated and omitted == 0 and unknown == 0),
            "count_unit": "error_records_not_endpoint_rows_or_unique_owners",
            "groups": [dict(zip((name for name, _ in dimensions), key), count=count)
                       for key, count in sorted(groups.items())]}


def project_baseline(section):
    """Project only fixed statuses and counts; never persist rows or raw errors."""
    section = section if isinstance(section, dict) else {}
    coverage = section.get("coverage") if isinstance(section.get("coverage"), dict) else {}
    rows = section.get("rows") if isinstance(section.get("rows"), list) else []
    statuses = {"ok", "partial", "denied", "unknown", "timeout", "error", "cancelled", "not_applicable", "busy"}
    status = section.get("status") if section.get("status") in statuses else "unknown"
    checks, valid_checks = [], True
    raw_checks = coverage.get("checks")
    raw_checks = raw_checks if isinstance(raw_checks, list) else []
    for operation in OPERATIONS:
        matching = [item for item in raw_checks if isinstance(item, dict) and item.get("operation") == operation]
        item = matching[0] if len(matching) == 1 else {}
        item_status = item.get("status") if item.get("status") in statuses else "unknown"
        count = _count(item.get("count"))
        valid_checks &= len(matching) == 1 and item_status == "ok" and count is not None
        checks.append({"operation": operation, "status": item_status, "count": count})
    valid_rows = isinstance(section.get("rows"), list) and len(rows) <= 1000
    families = (("TCP", 4), ("TCP", 6), ("UDP", 4), ("UDP", 6))
    observed_counts = dict.fromkeys(families, 0)
    for row in rows[:1000]:
        if not isinstance(row, dict):
            valid_rows = False
            continue
        try:
            address = ipaddress.ip_address(str(row.get("address", "")).split("%", 1)[0])
            if row.get("protocol") in ("TCP", "UDP"):
                observed_counts[(row["protocol"], address.version)] += 1
            valid_rows &= (row.get("status") == "ok" and row.get("protocol") in ("TCP", "UDP")
                           and type(row.get("port")) is int and 0 <= row["port"] <= 65535
                           and row.get("process_identity_status") == "ok"
                           and bool(row.get("process_instance_ref")))
        except (ValueError, TypeError):
            valid_rows = False
    # An ok table status alone cannot prove every row survived the envelope.
    # Reconcile each family, not just the grand total (which can hide swaps).
    table_counts_consistent = valid_checks and all(
        check["count"] == observed_counts[family] for check, family in zip(checks, families))
    errors = coverage.get("errors")
    error_count = max(_count(coverage.get("error_count")) or 0, len(errors) if isinstance(errors, list) else 1)
    complete = (section.get("id") == "listeners" and status == "ok" and coverage.get("status") == "ok"
                and coverage.get("backend") == "native" and coverage.get("truncated") is False
                and coverage.get("errors_truncated") is False and error_count == 0
                and type(coverage.get("error_count")) is int and coverage["error_count"] == 0
                and coverage.get("gaps", []) == [] and len(raw_checks) == 4 and valid_checks and valid_rows
                and table_counts_consistent
                and coverage.get("process_identity_status") == "ok"
                and type(coverage.get("process_identity_missing_count")) is int
                and coverage["process_identity_missing_count"] == 0)
    return {"source": "listeners", "status": status, "complete": bool(complete),
            "row_count": len(rows), "error_count": error_count,
            "table_counts_consistent": bool(table_counts_consistent),
            "error_summary": summarize_errors(coverage),
            "truncated": coverage.get("truncated") is True, "checks": checks,
            "process_identity_status": "ok" if coverage.get("process_identity_status") == "ok" else "unknown",
            "process_identity_missing_count": _count(coverage.get("process_identity_missing_count"))}


def _own_process(value):
    value = value if isinstance(value, dict) else {}
    pid = value.get("pid")
    try:
        created = stamp(_time(value.get("created_at")))
    except ValidationError:
        created = None
    return {"managed": value.get("managed") is True,
            "pid": pid if type(pid) is int and 0 < pid <= 2**32 - 1 else None,
            "created_at": created,
            "child_exited": value.get("child_exited") is True,
            "exit_code": value.get("exit_code") if type(value.get("exit_code")) is int else None,
            "remaining_owned_processes": _count(value.get("remaining_owned_processes")),
            "forcibly_terminated": value.get("forcibly_terminated") if type(value.get("forcibly_terminated")) is bool else None}


def _native_collector(project):
    if os.name != "nt":
        raise ValidationError("windows_required")
    sys.path.insert(0, str(Path(project) / "src"))
    from eventguard.collectors.windows import WindowsCollectors
    return WindowsCollectors(backend="native", timeout=QUERY_TIMEOUT_SEC, evidence_sink=None)


def execute(root, project, *, now=None, collector_factory=None, clock=time.monotonic):
    root = _root(root, project)
    now = now or utc_now()
    manifest = _check_approval(root, project, now)
    stop_path = _plain_path(root / "stop.request")
    if stop_path.exists():
        raise ValidationError("stop_requested_before_query")
    _write(root / "execution-intent.json", {"kind": KIND, "run_id": manifest["run_id"],
                                          "started_at": stamp(now), "scope": dict(SCOPE)})
    started, collector, process, baseline = clock(), None, {}, None
    reason, query_started = "baseline_query_failed", False
    cancel = threading.Event()
    stop_seen, watcher_stop, watcher_failed = threading.Event(), threading.Event(), threading.Event()

    def check_stop():
        try:
            if _plain_path(stop_path).exists():
                stop_seen.set()
                cancel.set()
                return True
        except Exception:
            watcher_failed.set()
            cancel.set()
            return True
        return False

    def watch_stop():
        while not watcher_stop.is_set():
            if check_stop():
                return
            watcher_stop.wait(.025)

    watcher = threading.Thread(target=watch_stop, name="eventguard-listener-stop-" + manifest["run_id"], daemon=True)
    watcher_started = False
    try:
        watcher.start()
        watcher_started = True
        if not check_stop():
            collector = (collector_factory or _native_collector)(project)
            if not check_stop():
                query_started = True
                baseline = project_baseline(collector.collect("listeners", cancel=cancel))
                reason = "baseline_incomplete" if not baseline["complete"] else "owned_query_exit_unconfirmed"
    except Exception:
        # Source/OS output is untrusted. Never serialize an exception or row.
        reason = "baseline_query_failed"
    finally:
        cancel.set()
        try:
            if collector is not None:
                process = _own_process(collector.runner.shutdown(grace=.2) if collector.runner.pending
                                       else collector.runner.last_process)
        except Exception:
            process = _own_process({})
        finally:
            watcher_stop.set()
            if watcher_started:
                watcher.join(timeout=1)
            check_stop()
    elapsed = clock() - started
    clean = (process.get("managed") is True and process.get("child_exited") is True
             and process.get("pid") is not None and process.get("created_at") is not None
             and type(process.get("exit_code")) is int and process["exit_code"] == 0
             and process.get("remaining_owned_processes") == 0 and process.get("forcibly_terminated") is False)
    watcher_exited = not watcher.is_alive()
    passed = (baseline is not None and baseline["complete"] and clean and 0 <= elapsed <= TIMEOUT_SEC
              and not stop_seen.is_set() and not watcher_failed.is_set() and watcher_exited)
    if passed:
        reason = "baseline_only_verified"
    elif watcher_failed.is_set() or not watcher_exited:
        reason = "stop_watcher_unconfirmed"
    elif stop_seen.is_set():
        reason = "stop_requested"
    elif elapsed > TIMEOUT_SEC:
        reason = "overall_deadline_exceeded"
    result = {"kind": KIND, "run_id": manifest["run_id"], "status": "passed" if passed else "blocked",
              "reason": reason, "scope": dict(SCOPE), "started_at": stamp(now), "finished_at": stamp(utc_now()),
              "elapsed_sec": round(max(0, elapsed), 6), "query_started": query_started,
              "stop_requested": stop_seen.is_set(), "stop_watcher_exited": watcher_exited,
              "baseline": baseline, "owned_query": process, "raw_facts_saved": False,
              "full_lifecycle_verified": False, "injection_performed": False,
              "host_safety_assessed": False, "model_calls": 0,
              "loopback_lifecycle": {"status": "blocked", "reason": "listener_rule_excludes_loopback"}}
    _write(root / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="New direct reports/windows-listener-* directory")
    parser.add_argument("--execute", action="store_true", help="One approved native baseline query; no injection")
    args = parser.parse_args(argv)
    project = Path(__file__).absolute().parents[1]
    try:
        result = execute(args.root, project) if args.execute else prepare(args.root, project)
    except ValidationError as error:
        reason = error.args[0]
        before_query = reason in {
            "approval_missing", "approval_scope_mismatch", "approval_not_current", "approval_time_invalid",
            "authorization_text_required", "manifest_scope_mismatch", "source_changed_since_prepare",
            "dedicated_root_required", "evidence_file_invalid", "evidence_json_invalid", "source_file_invalid",
            "stop_requested_before_query",
        }
        result = {"status": "blocked", "reason": reason,
                  "query_started": False if before_query or not args.execute else None}
    except Exception:
        result = {"status": "blocked", "reason": "validation_storage_or_admission_failed",
                  "query_started": None if args.execute else False}
    print(json.dumps({key: result[key] for key in ("status", "reason", "query_started")}, ensure_ascii=False))
    return 0 if result["status"] in ("prepared", "passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
