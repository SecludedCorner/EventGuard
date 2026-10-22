"""Durable evidence of an unobserved interval; never a security conclusion."""
from datetime import datetime, timezone
import hashlib
import json

from .runtime import read_json, atomic_json
from .events.schema import validate_event
from .processes import identity

REASONS = {"planned_monitor_interval", "previous_monitor_interrupted", "heartbeat_stale", "heartbeat_clock_anomaly",
           "owner_identity_changed", "owner_identity_unverifiable", "checkpoint_unreadable"}


def prepare(runtime, namespace, host_id, now=None, inspect=None):
    now = now or datetime.now(timezone.utc)
    inspect = inspect or identity
    marker = runtime.path("data/" + namespace + "/monitor-gap-pending.json")
    if marker.exists():
        value = read_json(marker, 16384)
        event = validate_event(value.get("event"))
        if value.get("kind") != "monitor-gap-pending-v1" or event["event_type"] != "monitor_gap" or event["host_id"] != host_id or event["synthetic"] is not (namespace == "test"):
            raise ValueError("monitor_gap_marker_invalid")
        return event
    checkpoint = runtime.path("data/" + namespace + "/monitor-checkpoint.json")
    reason, previous = None, {}
    try:
        previous = read_json(checkpoint) if checkpoint.exists() else runtime.health()
        if previous.get("namespace") != namespace:
            if checkpoint.exists():
                raise ValueError("checkpoint_namespace_mismatch")
            return None
        if previous.get("state") == "not_started":
            return None
        if not isinstance(previous, dict) or not previous.get("heartbeat_at"):
            raise ValueError("invalid_monitor_checkpoint")
        heartbeat = datetime.fromisoformat(previous["heartbeat_at"].replace("Z", "+00:00"))
        if heartbeat.tzinfo is None:
            raise ValueError("invalid_monitor_checkpoint")
    except (ValueError, TypeError, AttributeError, OSError):
        if not checkpoint.exists():
            # A malformed legacy health file still represents unknown coverage.
            if not runtime.path("data/health.json").exists():
                return None
        previous, heartbeat, reason = {}, now, "checkpoint_unreadable"
    elapsed = (now - heartbeat).total_seconds()
    owner = inspect(previous.get("pid")) if type(previous.get("pid")) is int else {"state": "unknown", "created_at": None}
    expected = previous.get("process_created_at")
    matches = isinstance(expected, str) and expected == owner.get("created_at")
    if reason is None:
        if elapsed < 0:
            reason = "heartbeat_clock_anomaly"
        elif expected and owner.get("created_at") and not matches:
            reason = "owner_identity_changed"
        elif not expected or owner.get("state") in {"denied", "unknown"}:
            reason = "owner_identity_unverifiable"
        elif previous.get("state") == "stopped":
            reason = "planned_monitor_interval"
        elif elapsed > 90:
            reason = "heartbeat_stale"
        else:
            reason = "previous_monitor_interrupted"
    stamp = now.astimezone(timezone.utc).isoformat(timespec="microseconds")
    start = min(heartbeat, now).astimezone(timezone.utc).isoformat(timespec="microseconds")
    key = hashlib.sha256(json.dumps([namespace, previous.get("instance_id"), previous.get("heartbeat_at"), stamp, reason]).encode()).hexdigest()[:40]
    event = validate_event({"schema_version": "2.0", "event_id": "evt-gap-" + key, "host_id": host_id,
        "episode_id": "gap-" + key, "correlation_id": "gap-" + key, "sequence": 1,
        "event_type": "monitor_gap", "transition": "new", "severity": "warning", "synthetic": namespace == "test",
        "observed_at": stamp, "persisted_at": stamp, "window": {"start": start, "end": stamp},
        "detector": {"id": "monitor-lifecycle", "version": "1.0"}, "rule_ref": {"rule_id": "monitor-gap", "version": "1.0"},
        "baseline_version": "monitor-lifecycle-v1", "evidence": {"reason": reason, "gap_seconds": max(0, int(elapsed)),
            "pid": previous.get("pid"), "process_created_at": expected, "observed_at": previous.get("heartbeat_at"),
            "source_status": owner.get("state", "unknown"), "status": "unknown"},
        "coverage": {"status": "unknown", "gaps": ["unobserved_monitor_interval"]},
        "inference": {"summary": "Monitoring interval was not observed; no-event and host safety conclusions are unavailable.", "compromise_conclusion": "undetermined"},
        "privacy": {"profile": "minimal-v1", "redacted": True}})
    atomic_json(marker, {"kind": "monitor-gap-pending-v1", "event": event}, 16384)
    return event


def persist(runtime, namespace, host_id, store):
    event = prepare(runtime, namespace, host_id)
    if event is None:
        return None
    store.enqueue(event)  # Failure preserves marker and all existing pending data.
    runtime.path("data/" + namespace + "/monitor-gap-pending.json").unlink()
    return {"event_id": event["event_id"], "reason": event["evidence"]["reason"], "gap_seconds": event["evidence"]["gap_seconds"]}
