"""Append-only history import primitive; never delete, ACK, or commit."""
import json

from .disposition_history_backup import verify_snapshot
from .disposition_history_store import record_attempt
from .schema import validate_event
from .store import event_payload_hash


def restore_suffix(db, value, *, namespace, available_bytes):
    """Import only an exact missing suffix inside the caller's transaction.

    The caller must independently establish source provenance, reserve ACK
    space, verify actual database use before commit, and handle rollback.
    Hashes are integrity checks, not authentication or restore authorization.
    """
    if not db.in_transaction or db.execute("PRAGMA query_only").fetchone()[0]:
        raise ValueError("history_restore_write_transaction_required")
    checked = verify_snapshot(value)
    if namespace not in ("live", "test") or checked["namespace"] != namespace:
        raise ValueError("history_restore_namespace_unverified")
    if type(available_bytes) is not int or available_bytes < 0:
        raise ValueError("history_restore_available_bytes_invalid")
    records = value["data"]["records"]
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_disposition_operations'").fetchone()
    if exists:
        columns = {row[1] for row in db.execute("PRAGMA table_info(event_disposition_operations)")}
        column = "payload_hash" if "payload_hash" in columns else "NULL"
        rows = db.execute("SELECT event_id,operation_id,previous_status,status,source,at,changed," + column +
                          " FROM event_disposition_operations ORDER BY rowid LIMIT ?", (len(records) + 1,)).fetchall()
    else:
        rows = []
    fields = ("event_id", "operation_id", "previous_status", "status", "source", "at", "changed", "payload_hash")
    if len(rows) > len(records) or any(tuple(row) != tuple(item[k] for k in fields) for row, item in zip(rows, records)):
        raise ValueError("history_restore_not_exact_prefix")
    checked_events = {}
    for item in records:
        if item["payload_hash"] is None:
            raise ValueError("history_restore_unbound_event")
        event_id = item["event_id"]
        if event_id not in checked_events:
            row = db.execute("SELECT payload,payload_hash FROM events WHERE event_id=?", (event_id,)).fetchone()
            try:
                event = validate_event(json.loads(row[0])) if row is not None else None
                digest = event_payload_hash(event) if event is not None and event["event_id"] == event_id else None
                checked_events[event_id] = digest if row is not None and row[1] == digest else None
            except (ValueError, TypeError, KeyError, OverflowError):
                checked_events[event_id] = None
        if checked_events[event_id] != item["payload_hash"]:
            raise ValueError("history_restore_event_identity_unverified")
    pending = records[len(rows):]
    db.execute("SAVEPOINT eventguard_history_restore")
    try:
        for item in pending:
            record = {key: item[key] for key in fields[:6]}
            result = record_attempt(db, record, available_bytes=available_bytes, payload_hash=item["payload_hash"])
            if result["replayed"] or result["changed"] != item["changed"]:
                raise ValueError("history_restore_operation_conflict")
        db.execute("RELEASE eventguard_history_restore")
    except Exception:
        db.execute("ROLLBACK TO eventguard_history_restore")
        db.execute("RELEASE eventguard_history_restore")
        raise
    return {"already_present": len(rows), "appended": len(pending), "source_history_removed": False,
            "ack_performed": False, "caller_commit_required": True}
