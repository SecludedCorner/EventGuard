"""Read original human-operation results separately from the current state."""
import sqlite3

from .disposition_history import validate_record
from .store import EventStore, StoreError, _disposition_timestamp


def read_result(catalog, event_id, operation_id):
    result = {"schema_version": "1.0", "state": "unknown", "namespace": catalog.namespace,
              "event_id": event_id, "operation_id": operation_id, "operation": None, "current": None,
              "ack_performed": False, "model_calls": 0, "data_trust": "untrusted_data"}
    try:
        with catalog._read() as db:
            if db is None:
                return result
            columns = EventStore._schema_columns(db)
            if columns is None or "payload_hash" not in columns["events"]:
                return result
            selection, table = catalog._selection(db)
            anchor = db.execute("SELECT " + selection + " FROM " + table + " WHERE e.event_id=?", (event_id,)).fetchone()
            if anchor is None:
                return result
            summary = catalog._summary(anchor)
            current = {"status": summary["status"], "status_updated_at": summary["status_updated_at"]}
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_disposition_operations'").fetchone()
            if not exists:
                return dict(result, state="not_recorded", current=current)
            # Bound the read even if a damaged/replaced table lost its PK.
            rows = db.execute("SELECT event_id,operation_id,previous_status,status,source,at,changed,payload_hash "
                              "FROM event_disposition_operations WHERE operation_id=? LIMIT 2", (operation_id,)).fetchall()
            if not rows:
                return dict(result, state="not_recorded", current=current)
            if len(rows) != 1:
                return result
            row = rows[0]
            if row["event_id"] != event_id:
                return dict(result, state="not_recorded", current=current)
            record = validate_record({key: row[key] for key in ("event_id", "operation_id", "previous_status", "status", "source", "at")},
                                     allow_unchanged=True)
            if (row["payload_hash"] != anchor["payload_hash"] or row["changed"] not in (0, 1)
                    or bool(row["changed"]) != (record["previous_status"] != record["status"])):
                return result
            operation = {key: record[key] for key in ("previous_status", "status", "source")}
            operation.update(at=_disposition_timestamp(record["at"]), changed=bool(row["changed"]), payload_hash=row["payload_hash"])
            return dict(result, state="available", operation=operation, current=current)
    except (OSError, sqlite3.Error, StoreError, ValueError, TypeError, KeyError, IndexError, OverflowError):
        return result
