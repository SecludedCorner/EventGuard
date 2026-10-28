"""Bounded read-only disposition history backup payload; no file writes."""
from __future__ import annotations

import hashlib
import hmac
import json
import re

from .disposition_history import MAX_HISTORY_ENTRIES, MAX_HISTORY_PER_EVENT, validate_record, transition_order

MAX_EXPORT_BYTES = 4 * 1024 * 1024


def snapshot(db, *, namespace):
    """Capture a stable query-only transaction without inferring legacy identity.

    Returned metadata contains event and operation identifiers. It is local
    sensitive runtime data, not a log or an authenticated forensic record.
    """
    if namespace not in ("live", "test"):
        raise ValueError("history_snapshot_namespace_invalid")
    if not db.in_transaction or db.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise ValueError("history_snapshot_read_transaction_required")
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_disposition_operations'").fetchone()
    records = []
    if exists:
        columns = {row[1] for row in db.execute("PRAGMA table_info(event_disposition_operations)")}
        hash_column = "payload_hash" if "payload_hash" in columns else "NULL"
        rows = db.execute("SELECT event_id,operation_id,previous_status,status,source,at,changed," + hash_column +
                          " FROM event_disposition_operations ORDER BY rowid LIMIT ?", (MAX_HISTORY_ENTRIES + 1,)).fetchall()
        if len(rows) > MAX_HISTORY_ENTRIES:
            raise ValueError("history_snapshot_count_limit")
        seen = set()
        for row in rows:
            value = dict(zip(("event_id", "operation_id", "previous_status", "status", "source", "at"), row[:6]))
            validate_record(value, allow_unchanged=True)
            if value["operation_id"] in seen or row[6] not in (0, 1) or bool(row[6]) != (value["previous_status"] != value["status"]):
                raise ValueError("history_snapshot_invalid")
            if row[7] is not None and (type(row[7]) is not str or re.fullmatch(r"[a-f0-9]{64}", row[7]) is None):
                raise ValueError("history_snapshot_invalid")
            seen.add(value["operation_id"])
            records.append({**value, "changed": bool(row[6]), "payload_hash": row[7]})
    data = {"schema_version": "1.1", "namespace": namespace, "state": "available" if exists else "not_recorded", "records": records}
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    if len(encoded) > MAX_EXPORT_BYTES:
        raise ValueError("history_snapshot_bytes_limit")
    result = {"data": data, "sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}
    verify_snapshot(result)
    return result


def verify_snapshot(value):
    """Verify bounded metadata and content hash; a hash is not a signature."""
    if type(value) is not dict or set(value) != {"data", "sha256", "bytes"}:
        raise ValueError("history_backup_invalid")
    data = value["data"]
    if type(data) is not dict:
        raise ValueError("history_backup_invalid")
    version = data.get("schema_version")
    legacy = version == "1.0" and set(data) == {"schema_version", "state", "records"}
    scoped = version == "1.1" and set(data) == {"schema_version", "namespace", "state", "records"} and data.get("namespace") in ("live", "test")
    if (not (legacy or scoped) or type(data["state"]) is not str or data["state"] not in {"available", "not_recorded"} or
            type(data["records"]) is not list or len(data["records"]) > MAX_HISTORY_ENTRIES or
            data["state"] == "not_recorded" and data["records"]):
        raise ValueError("history_backup_invalid")
    seen, counts = set(), {}
    for item in data["records"]:
        if type(item) is not dict or set(item) != {"event_id", "operation_id", "previous_status", "status", "source", "at", "changed", "payload_hash"}:
            raise ValueError("history_backup_invalid")
        record = {key: item[key] for key in ("event_id", "operation_id", "previous_status", "status", "source", "at")}
        validate_record(record, allow_unchanged=True)
        if (item["operation_id"] in seen or type(item["changed"]) is not bool or
                item["changed"] != (item["previous_status"] != item["status"]) or
                item["payload_hash"] is not None and (type(item["payload_hash"]) is not str or re.fullmatch(r"[a-f0-9]{64}", item["payload_hash"]) is None)):
            raise ValueError("history_backup_invalid")
        seen.add(item["operation_id"])
        counts[item["event_id"]] = counts.get(item["event_id"], 0) + 1
        if counts[item["event_id"]] > MAX_HISTORY_PER_EVENT:
            raise ValueError("history_backup_invalid")
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    digest = hashlib.sha256(encoded).hexdigest()
    if (len(encoded) > MAX_EXPORT_BYTES or type(value["bytes"]) is not int or value["bytes"] != len(encoded) or
            type(value["sha256"]) is not str or re.fullmatch(r"[a-f0-9]{64}", value["sha256"]) is None or
            not hmac.compare_digest(value["sha256"], digest)):
        raise ValueError("history_backup_integrity_failed")
    return {"records": len(data["records"]), "sha256": digest, "bytes": len(encoded),
            "namespace": data["namespace"] if scoped else "unknown"}


def preview_identity(db, value, *, namespace):
    """Compare identities only; never authorize or perform a restore.

    Counts do not prove archive authenticity, capacity, complete history,
    target provenance or recoverability. Both snapshots use one read transaction.
    """
    from .schema import validate_event
    from .store import event_payload_hash

    verified = verify_snapshot(value)
    if namespace not in ("live", "test") or verified["namespace"] != namespace:
        raise ValueError("history_backup_namespace_unverified")
    current = snapshot(db, namespace=namespace)
    operations = {item["operation_id"]: item for item in current["data"]["records"]}
    counts = {"unbound": 0, "event_missing": 0, "event_mismatch": 0,
              "operation_conflict": 0, "already_present": 0, "absent_operation": 0}
    event_checks = {}
    for item in value["data"]["records"]:
        event_id = item["event_id"]
        if item["payload_hash"] is None:
            counts["unbound"] += 1
            continue
        if event_id not in event_checks:
            row = db.execute("SELECT payload,payload_hash FROM events WHERE event_id=?", (event_id,)).fetchone()
            if row is None:
                event_checks[event_id] = ("event_missing", None)
            else:
                try:
                    event = validate_event(json.loads(row[0]))
                    digest = event_payload_hash(event)
                    valid = event["event_id"] == event_id and row[1] == digest
                except (TypeError, ValueError, KeyError, OverflowError):
                    valid, digest = False, None
                event_checks[event_id] = (None if valid else "event_mismatch", digest)
        failure, digest = event_checks[event_id]
        if failure or digest != item["payload_hash"]:
            counts[failure or "event_mismatch"] += 1
        elif item["operation_id"] not in operations:
            counts["absent_operation"] += 1
        elif item == operations[item["operation_id"]]:
            counts["already_present"] += 1
        else:
            counts["operation_conflict"] += 1
    existing = current["data"]["records"]
    backed_up = value["data"]["records"]
    exact_prefix = len(existing) <= len(backed_up) and existing == backed_up[:len(existing)]
    return {"counts": counts, "identity_conflicts": sum(counts[k] for k in
            ("unbound", "event_missing", "event_mismatch", "operation_conflict")),
            "history_order": "exact_prefix" if exact_prefix else "diverged",
            "transition_order": transition_order(backed_up),
            "target_records": len(existing), "backup_records": len(backed_up),
            "provenance_status": "unknown", "history_completeness": "unknown",
            "capacity_status": "unknown", "recoverability_status": "unknown",
            "restore_performed": False, "restore_authorized": False}
