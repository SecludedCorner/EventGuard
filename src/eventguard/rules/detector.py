"""Pure, local deterministic rules. No I/O, network, model or system actions.

The caller must persist the returned state and events in one transaction.  Never
persist only one side. Deferred events retain their original ID across restart.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import time

VERSION = "1.0.0"
SECTION_IDS = frozenset({"defender", "listeners", "processes", "startup", "services", "tasks", "versions"})
STATUSES = frozenset({"ok", "partial", "denied", "unknown", "not_applicable", "error", "timeout", "cancelled", "busy", "not_requested"})
SEVERITY = {"info": 0, "warning": 1, "high": 2, "critical": 3}
MAX_STATE_BYTES = 4 * 1024 * 1024
MAX_DEFERRED = 1000
MAX_EVENTS_PER_EVALUATION = 20
PROTECTION_FIELDS = ("AntivirusEnabled", "RealTimeProtectionEnabled")
RULE_IDS = {"protection.changed": "pb-protection-change", "listener.changed": "pb-listener-change", "persistence.changed": "pb-persistence-change", "coverage.degraded": "pb-monitor-fault"}
SUMMARY = {
    "protection.changed": "觀測到明確防護設定關閉；需要查證用途與狀態。",
    "listener.changed": "觀測到全介面本機端點變化；Internet 可達性未知。",
    "persistence.changed": "觀測到持久化 metadata 盤點或新增；不代表惡意。",
    "coverage.degraded": "觀測或事件處理覆蓋降級；不代表已入侵。",
}


class DetectorCapacityError(RuntimeError):
    """No state is returned when pending/state bounds would be exceeded."""


class StateValidationError(ValueError):
    """Caller must preserve corrupt state, report degraded coverage and stop."""


def _hash(value, size=40):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()[:size]


def _epoch(now):
    if now is None:
        return time.time()
    if isinstance(now, datetime):
        if now.tzinfo is None:
            raise ValueError("timezone_required")
        now = now.timestamp()
    if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
        raise ValueError("invalid_clock")
    return float(now)


def _stamp(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _initial(host_id, now):
    return {"schema_version": "1.0", "host_id": host_id,
            "baseline_version": "baseline-" + _hash([host_id, _stamp(now)], 24),
            "active": {}, "history": {}, "baselines": {}, "deferred": [],
            "last_evaluated_at": None, "metrics": {"deferred_count": 0, "suppression_count": 0}}


def _valid_state(state, host_id, now):
    if state is None:
        return _initial(host_id, now)
    if not isinstance(state, dict) or state.get("schema_version") != "1.0" or state.get("host_id") != host_id:
        raise StateValidationError("invalid_detector_state")
    if set(state) != {"schema_version", "host_id", "baseline_version", "active", "history", "baselines", "deferred", "last_evaluated_at", "metrics"} or not isinstance(state.get("baseline_version"), str):
        raise StateValidationError("invalid_detector_state")
    if any(not isinstance(state.get(key), dict) for key in ("active", "history", "baselines", "metrics")) or not isinstance(state.get("deferred"), list):
        raise StateValidationError("invalid_detector_state")
    try:
        encoded = json.dumps(state, allow_nan=False, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    except (ValueError, TypeError):
        raise StateValidationError("invalid_detector_state") from None
    if len(encoded) > MAX_STATE_BYTES or len(state["deferred"]) > MAX_DEFERRED:
        raise DetectorCapacityError("detector_state_capacity")
    for record in state["active"].values():
        if not isinstance(record, dict) or record.get("event_type") not in RULE_IDS or record.get("severity") not in SEVERITY or not isinstance(record.get("sequence"), int):
            raise StateValidationError("invalid_detector_record")
    for record in state["history"].values():
        if not isinstance(record, dict) or type(record.get("episode")) is not int or record["episode"] < 1:
            raise StateValidationError("invalid_detector_history")
        for field in ("last_emitted", "last_resolved"):
            if field in record and (type(record[field]) not in (int, float) or not math.isfinite(record[field])):
                raise StateValidationError("invalid_detector_history")
    for baseline in state["baselines"].values():
        if not isinstance(baseline, dict) or not isinstance(baseline.get("keys"), list) or any(not isinstance(key, str) or len(key) != 32 for key in baseline["keys"]):
            raise StateValidationError("invalid_persistence_baseline")
    for item in state["deferred"]:
        if not isinstance(item, dict) or not isinstance(item.get("event_id"), str):
            raise StateValidationError("invalid_deferred_event")
    return copy.deepcopy(state)


def _optional_missing(section_id, row):
    return section_id == "startup" and row.get("kind") == "registry_missing" and row.get("status") == "not_applicable"


def _effective_status(section_id, section):
    status = section.get("status", "unknown")
    if status not in STATUSES:
        return "unknown"
    rows = section.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return "unknown"
    coverage = section.get("coverage") if isinstance(section.get("coverage"), dict) else {}
    truncated = section.get("truncated") is True or coverage.get("truncated") is True
    incomplete = [row for row in rows if row.get("status", "unknown") != "ok" and not _optional_missing(section_id, row)]
    if status == "ok" and incomplete:
        return "partial"
    # Some collectors conservatively mark a mixed set partial. Confirmed absent
    # optional keys are complete observations; no other failure is relaxed.
    if truncated and status in ("ok", "partial"):
        return "partial"
    gaps = coverage.get("gaps", [])
    if section_id == "startup" and status == "partial" and rows and not incomplete and any(_optional_missing(section_id, row) for row in rows) and not truncated and not gaps:
        status = "ok"
    if status in ("ok", "partial"):
        for row in rows:
            if row.get("status") != "ok":
                continue
            if section_id == "listeners":
                try:
                    ipaddress.ip_address(str(row.get("address", "")).split("%", 1)[0])
                except ValueError:
                    return "partial"
                if row.get("protocol") not in ("TCP", "UDP") or type(row.get("port")) is not int or not 0 <= row["port"] <= 65535:
                    return "partial"
            if section_id in ("startup", "services", "tasks"):
                if row.get("kind") in ("registry_empty", "folder_empty"):
                    continue
                if not isinstance(row.get("name"), str) or not row["name"] or len(row["name"]) > 2048:
                    return "partial"
    return status


def _event(state, record, transition, now):
    record["sequence"] += 1
    sequence = record["sequence"]
    episode_id = record["episode_id"]
    evidence = copy.deepcopy(record["evidence"])
    summary = SUMMARY[record["event_type"]]
    if transition == "resolved":
        evidence = {"previous": evidence, "status": "resolved_by_two_complete_observations"}
        summary = "指定規則經兩次完整成功觀測已不再符合；這不是主機安全結論。"
    return {"schema_version": "2.0", "event_id": "evt-" + _hash([state["host_id"], episode_id, sequence, transition]),
            "host_id": state["host_id"], "episode_id": episode_id, "correlation_id": episode_id,
            "sequence": sequence, "event_type": record["event_type"],
            "detector": {"id": record["detector"], "version": VERSION},
            "rule_ref": {"rule_id": RULE_IDS[record["event_type"]], "version": VERSION},
            "transition": transition, "severity": record["severity"], "synthetic": False,
            "observed_at": _stamp(now), "persisted_at": _stamp(now),
            "window": {"start": _stamp(record["first_seen"]), "end": _stamp(now)},
            "baseline_version": state["baseline_version"], "evidence": evidence,
            "inference": {"summary": summary, "compromise_conclusion": "undetermined"},
            "coverage": {"status": record.get("coverage", "unknown"), "gaps": [] if record.get("coverage") == "ok" else [record.get("coverage", "unknown")]},
            "privacy": {"profile": "minimal-v1", "redacted": True}, "evidence_refs": []}


def _observe(state, identity, event_type, detector, severity, evidence, status, now, cooldown, generated, managed=True):
    active, history = state["active"], state["history"]
    record = active.get(identity)
    if record is None:
        previous = history.get(identity, {})
        episode = int(previous.get("episode", 0)) + 1
        record = {"identity": identity, "event_type": event_type, "detector": detector,
                  "episode_id": "ep-" + _hash([state["host_id"], identity, episode], 32),
                  "episode": episode, "severity": severity, "emitted_severity": None,
                  "evidence": evidence, "coverage": status, "first_seen": now, "last_seen": now,
                  "sequence": 0, "recovery_count": 0, "managed": managed}
        active[identity] = record
        last = max(previous.get("last_emitted", -math.inf), previous.get("last_resolved", -math.inf))
        previous_severity = previous.get("last_severity", "info")
        if now - last >= cooldown or SEVERITY[severity] > SEVERITY.get(previous_severity, 0):
            generated.append(_event(state, record, "new", now))
            record["emitted_severity"] = severity
            history[identity] = {"episode": episode, "last_emitted": now, "last_severity": severity}
        else:
            history[identity] = {"episode": episode, "last_emitted": last, "last_severity": previous_severity}
    else:
        record.update(severity=severity, evidence=evidence, coverage=status, last_seen=now, recovery_count=0)
        emitted = record.get("emitted_severity")
        if emitted is not None and SEVERITY[severity] > SEVERITY[emitted]:
            generated.append(_event(state, record, "escalated", now))
            record["emitted_severity"] = severity
            history[identity]["last_emitted"] = now
            history[identity]["last_severity"] = severity
        elif emitted is None and now - history[identity].get("last_emitted", -math.inf) >= cooldown:
            generated.append(_event(state, record, "new", now))
            record["emitted_severity"] = severity
            history[identity]["last_emitted"] = now
            history[identity]["last_severity"] = severity
    return identity


def _recover(state, identity, now, generated):
    record = state["active"].get(identity)
    if record is None:
        return
    record["recovery_count"] += 1
    if record["recovery_count"] < 2:
        return
    if record.get("emitted_severity") is not None:
        record["coverage"] = "ok"
        generated.append(_event(state, record, "resolved", now))
    state["history"][identity]["last_resolved"] = now
    del state["active"][identity]


def _persistence_key(section_id, row):
    metadata = [section_id, row.get("source", ""), row.get("registry_view", ""), row.get("kind", ""), row.get("name", "")]
    if section_id in ("services", "tasks"):
        metadata += [row.get("state", ""), row.get("start_mode", row.get("startmode", ""))]
    if section_id == "tasks":
        metadata.append(row.get("task_path", ""))
    return _hash(metadata, 32)


def evaluate(sections, state=None, now=None, host_id="local-host", cooldown=300):
    """Return new state/events without mutating inputs or doing any I/O.

    Missing sources do not recover risks. Each managed recovery needs two
    successful complete observations. Caller should pass subsets as collected.
    """
    instant = _epoch(now)
    if not isinstance(host_id, str) or not host_id or len(host_id) > 160 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-" for c in host_id):
        raise ValueError("invalid_host_id")
    if isinstance(cooldown, bool) or not isinstance(cooldown, (int, float)) or not math.isfinite(cooldown) or cooldown < 0:
        raise ValueError("invalid_cooldown")
    current = _valid_state(state, host_id, instant)
    if not isinstance(sections, list):
        raise ValueError("sections_must_be_list")
    chosen = {}
    for section in sections:
        if isinstance(section, dict) and section.get("id") in SECTION_IDS:
            if section["id"] in chosen:
                raise ValueError("duplicate_section")
            chosen[section["id"]] = section
    generated = []
    for section_id, section in chosen.items():
        status = _effective_status(section_id, section)
        rows = section.get("rows", []) if isinstance(section.get("rows"), list) else []
        coverage_id = "coverage:" + section_id
        if status != "ok":
            # A failed/incomplete observation breaks a recovery streak. Missing
            # unrequested sources are deliberately not visited by this loop.
            for identity, record in current["active"].items():
                belongs = ((section_id == "defender" and identity == "protection:settings") or
                           (section_id == "listeners" and identity.startswith("listener:")) or
                           identity.startswith("persistence:" + section_id + ":"))
                if belongs:
                    record["recovery_count"] = 0
        if status not in ("ok", "not_requested"):
            severity = "info" if status == "not_applicable" else ("high" if status in ("error", "timeout") else "warning")
            _observe(current, coverage_id, "coverage.degraded", "coverage", severity,
                     {"section": section_id, "status": status}, status, instant, cooldown, generated)
        elif status == "ok":
            _recover(current, coverage_id, instant, generated)
        if status not in ("ok", "partial"):
            continue
        if section_id == "defender":
            observed = {row.get("property", row.get("item")): row.get("value") for row in rows
                        if isinstance(row, dict) and row.get("status") == "ok" and row.get("property", row.get("item")) in PROTECTION_FIELDS and type(row.get("value")) is bool}
            disabled = [key for key in PROTECTION_FIELDS if observed.get(key) is False]
            if disabled:
                _observe(current, "protection:settings", "protection.changed", "defender-settings",
                         "high" if len(disabled) == 2 else "warning", {"current": disabled, "count": len(disabled)},
                         status, instant, cooldown, generated)
            elif status == "ok" and all(observed.get(key) is True for key in PROTECTION_FIELDS):
                _recover(current, "protection:settings", instant, generated)
        elif section_id == "listeners":
            present = set()
            for row in rows:
                if not isinstance(row, dict) or row.get("status") != "ok" or row.get("protocol") not in ("TCP", "UDP") or type(row.get("port")) is not int:
                    continue
                try:
                    address = ipaddress.ip_address(str(row.get("address", "")).split("%", 1)[0])
                    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                        address = address.ipv4_mapped
                except ValueError:
                    continue
                if not address.is_unspecified or not 0 <= row["port"] <= 65535:
                    continue
                pid = row.get("pid") if type(row.get("pid")) is int else None
                identity = "listener:" + _hash([row["protocol"], str(address), row["port"], pid], 32)
                present.add(identity)
                evidence = {"protocol": row["protocol"], "address": str(address), "port": row["port"], "scope": "all_interfaces"}
                if pid is not None:
                    evidence["pid"] = pid
                _observe(current, identity, "listener.changed", "listener-diff", "warning", evidence,
                         status, instant, cooldown, generated)
            if status == "ok":
                for identity in list(current["active"]):
                    if identity.startswith("listener:") and identity not in present:
                        _recover(current, identity, instant, generated)
        elif section_id in ("startup", "services", "tasks"):
            keys = {_persistence_key(section_id, row) for row in rows
                    if isinstance(row, dict) and row.get("status") == "ok" and row.get("kind") not in ("registry_empty", "folder_empty") and isinstance(row.get("name"), str) and row.get("name")}
            baseline = current["baselines"].get(section_id)
            if baseline is None:
                if status == "ok":
                    current["baselines"][section_id] = {"keys": sorted(keys)}
                    if keys:
                        _observe(current, "inventory:" + section_id, "persistence.changed", "persistence-inventory", "info",
                                 {"section": section_id, "count": len(keys), "changed_keys": sorted(keys)[:5], "reason": "initial_inventory"},
                                 status, instant, cooldown, generated, managed=False)
                continue
            previous = set(baseline["keys"])
            for key in sorted(keys - previous):
                _observe(current, "persistence:" + section_id + ":" + key, "persistence.changed", "persistence-diff", "warning",
                         {"section": section_id, "count": 1, "changed_keys": [key], "reason": "added_metadata"},
                         status, instant, cooldown, generated)
            if status == "ok":
                for identity in list(current["active"]):
                    prefix = "persistence:" + section_id + ":"
                    if identity.startswith(prefix) and identity[len(prefix):] not in keys:
                        _recover(current, identity, instant, generated)
                baseline["keys"] = sorted(keys)
            else:
                baseline["keys"] = sorted(previous | keys)

    pending = current["deferred"] + generated
    storm_id = "coverage:storm"
    if len(pending) > MAX_EVENTS_PER_EVALUATION:
        summaries = []
        _observe(current, storm_id, "coverage.degraded", "storm-control", "warning",
                 {"suppression_count": len(pending) - MAX_EVENTS_PER_EVALUATION, "reason": "delivery_batch_limit"},
                 "partial", instant, cooldown, summaries)
        pending = summaries + pending
    else:
        summaries = []
        _recover(current, storm_id, instant, summaries)
        pending += summaries
    # Every transition is either returned or retained with the same ID. If even
    # the bounded durable backlog cannot hold it, fail visibly and return no state.
    if len(pending) > MAX_DEFERRED:
        raise DetectorCapacityError("detector_pending_capacity")
    events = pending[:MAX_EVENTS_PER_EVALUATION]
    current["deferred"] = pending[MAX_EVENTS_PER_EVALUATION:]
    current["metrics"] = {"deferred_count": len(current["deferred"]), "suppression_count": len(current["deferred"])}
    # Keep episode counters forever only while needed to avoid ID reuse; bounded
    # state capacity is explicit rather than silently pruning dedup identities.
    current["last_evaluated_at"] = _stamp(instant)
    encoded = json.dumps(current, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
    if len(encoded) > MAX_STATE_BYTES:
        raise DetectorCapacityError("detector_state_capacity")
    return current, events


class RuleEngine:
    def evaluate(self, sections, state=None, now=None, host_id="local-host", cooldown=300):
        return evaluate(sections, state, now, host_id, cooldown)
