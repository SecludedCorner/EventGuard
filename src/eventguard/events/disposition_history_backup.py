"""Bounded read-only disposition history backup payload; no file writes."""
from __future__ import annotations

import hashlib
import json
import re

from .disposition_history import MAX_HISTORY_ENTRIES, validate_record

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
    return {"data": data, "sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}
