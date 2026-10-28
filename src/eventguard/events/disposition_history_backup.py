"""Bounded read-only disposition history backup payload; no file writes."""
from __future__ import annotations

import hashlib
import hmac
import json
import re

from .disposition_history import MAX_HISTORY_ENTRIES, MAX_HISTORY_PER_EVENT, validate_record

MAX_EXPORT_BYTES = 4 * 1024 * 1024


def snapshot(db):
    """Capture a stable query-only transaction without inferring legacy identity.

    Returned metadata contains event and operation identifiers. It is local
    sensitive runtime data, not a log or an authenticated forensic record.
    """
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
    data = {"schema_version": "1.0", "state": "available" if exists else "not_recorded", "records": records}
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
    if (type(data) is not dict or set(data) != {"schema_version", "state", "records"} or
            data["schema_version"] != "1.0" or type(data["state"]) is not str or data["state"] not in {"available", "not_recorded"} or
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
    return {"records": len(data["records"]), "sha256": digest, "bytes": len(encoded)}
