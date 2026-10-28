"""Transactional building block for bounded disposition operation records."""
from .disposition_history import has_capacity, validate_record


class HistoryCapacityError(ValueError):
    pass


class HistoryConflictError(ValueError):
    pass


def record_attempt(db, value, *, available_bytes):
    """Record once within the caller's transaction; never commit or ACK here.

    available_bytes excludes the outbox ACK reserve. An unchanged request is
    kept for durable idempotency but is not a transition in displayed history.
    """
    if not db.in_transaction:
        raise ValueError("history_transaction_required")
    record = validate_record(value, allow_unchanged=True)
    if type(available_bytes) is not int or available_bytes < 0:
        raise ValueError("invalid_history_available_bytes")
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_disposition_operations'").fetchone()
    if exists:
        old = db.execute("SELECT event_id,operation_id,previous_status,status,source,at,changed FROM event_disposition_operations WHERE operation_id=?", (record["operation_id"],)).fetchone()
        if old:
            if (old[0], old[3], old[4]) != (record["event_id"], record["status"], record["source"]):
                raise HistoryConflictError("history_operation_conflict")
            return {"replayed": True, "changed": bool(old[6]), "previous_status": old[2], "status": old[3]}
        total = db.execute("SELECT COUNT(*) FROM event_disposition_operations").fetchone()[0]
        per_event = db.execute("SELECT COUNT(*) FROM event_disposition_operations WHERE event_id=?", (record["event_id"],)).fetchone()[0]
    else:
        total = per_event = 0
    if not has_capacity(total, per_event):
        raise HistoryCapacityError("history_count_capacity")
    page = db.execute("PRAGMA page_size").fetchone()[0]
    if available_bytes < page * (8 if not exists else 4):
        raise HistoryCapacityError("history_bytes_capacity")
    db.execute("""CREATE TABLE IF NOT EXISTS event_disposition_operations(
        operation_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
        previous_status TEXT NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL,
        at REAL NOT NULL, changed INTEGER NOT NULL CHECK(changed IN(0,1)))""")
    db.execute("CREATE INDEX IF NOT EXISTS event_disposition_operations_event ON event_disposition_operations(event_id)")
    changed = record["previous_status"] != record["status"]
    db.execute("INSERT INTO event_disposition_operations VALUES(?,?,?,?,?,?,?)",
               (record["operation_id"], record["event_id"], record["previous_status"],
                record["status"], record["source"], record["at"], int(changed)))
    return {"replayed": False, "changed": changed, "previous_status": record["previous_status"], "status": record["status"]}
