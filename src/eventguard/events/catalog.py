"""Local event browsing and handling states. No collection, ACK or model use."""
from __future__ import annotations

from contextlib import contextmanager, closing
import json
import sqlite3
import stat

from ..runtime import Runtime
from ..diagnostics.review import event_view, event_guidance, review, validate_saved_review
from .schema import IDENTIFIER, validate_event
from .store import EventStore, StoreError, event_payload_hash, _disposition_timestamp


STATUSES = frozenset({"new", "read", "handled", "ignored"})
SEVERITIES = frozenset({"info", "warning", "high", "critical"})
SOURCES = ("defender", "listeners", "processes", "startup", "services", "tasks", "versions")
SOURCE_FILTERS = frozenset((*SOURCES, "monitor", "advisories", "unknown"))

# Only fixed paths and fixed enum constants enter this SQL. User filters are
# bound parameters. Filter the whole database before applying LIMIT/OFFSET.
_SOURCE_CHOICES = "(" + ",".join("'" + source + "'" for source in SOURCES) + ")"
_SOURCE_PATHS = ("$.evidence.section", "$.evidence.source", "$.evidence.section_id", "$.evidence.kind",
                 "$.evidence.previous.section", "$.evidence.previous.source", "$.evidence.previous.kind",
                 "$.coverage.source")
_SOURCE_SQL = "CASE " + " ".join(
    "WHEN json_extract(e.payload,'" + path + "') IN " + _SOURCE_CHOICES
    + " THEN json_extract(e.payload,'" + path + "')" for path in _SOURCE_PATHS
) + """ WHEN json_extract(e.payload,'$.event_type')='listener.changed' THEN 'listeners'
    WHEN json_extract(e.payload,'$.event_type')='protection.changed' THEN 'defender'
    WHEN json_extract(e.payload,'$.event_type')='monitor_gap' THEN 'monitor'
    WHEN json_extract(e.payload,'$.event_type')='advisory.changed' THEN 'advisories'
    ELSE 'unknown' END"""


def _identifier(event_id):
    if type(event_id) is not str or not IDENTIFIER.fullmatch(event_id):
        raise ValueError("invalid_event_identifier")


class EventCatalog:
    """One saved-event interface shared by CLI and the loopback Web page.

    Reads never initialize a store, table or directory. Old events have handling
    state ``new``. Delivery state and handling state are separate properties.
    """

    def __init__(self, root, namespace="live"):
        self.runtime = Runtime(root)
        self.namespace = namespace
        self.directory = self.runtime.data_dir(namespace, create=False)
        self.path = self.runtime.path(self.directory.relative_to(self.runtime.root) / "eventguard.sqlite3")

    @contextmanager
    def _read(self):
        # Recheck redirects for each request. A caller can retain this object.
        path = self.runtime.path(self.path.relative_to(self.runtime.root))
        try:
            mode = path.stat().st_mode
        except FileNotFoundError:
            yield None
            return
        except OSError:
            raise StoreError("event_catalog_read_failed") from None
        if not stat.S_ISREG(mode):
            raise StoreError("event_catalog_read_failed")
        try:
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA query_only=ON")
                db.execute("BEGIN")
                yield db
        except sqlite3.Error as error:
            raise StoreError("event_catalog_read_failed") from error

    @staticmethod
    def _selection(db):
        dispositions = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_dispositions'").fetchone()
        if dispositions:
            return ("e.*," + _SOURCE_SQL + " AS catalog_source,COALESCE(d.status,'new') AS catalog_status,d.updated_at AS disposition_updated_at",
                    "events e LEFT JOIN event_dispositions d ON d.event_id=e.event_id")
        return ("e.*," + _SOURCE_SQL + " AS catalog_source,'new' AS catalog_status,NULL AS disposition_updated_at", "events e")

    @staticmethod
    def _summary(row, event=None):
        event = EventStore._row(row) if event is None else event
        if row["catalog_status"] not in STATUSES:
            raise StoreError("stored_event_disposition_invalid")
        return {"id": event["event_id"], "event_id": event["event_id"], "event_type": event["event_type"],
                "severity": event["severity"], "source": row["catalog_source"], "observed_at": event["observed_at"],
                "status": row["catalog_status"], "delivery_status": event["delivery_status"],
                "synthetic": event["synthetic"],
                "status_updated_at": _disposition_timestamp(row["disposition_updated_at"]) if row["disposition_updated_at"] is not None else None}

    def list(self, *, severity=None, source=None, status=None, limit=100, offset=0):
        if severity is not None and (type(severity) is not str or severity not in SEVERITIES):
            raise ValueError("invalid_event_severity_filter")
        if source is not None and (type(source) is not str or source not in SOURCE_FILTERS):
            raise ValueError("invalid_event_source_filter")
        if status is not None and (type(status) is not str or status not in STATUSES):
            raise ValueError("invalid_event_status")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("event_limit_out_of_bounds")
        if type(offset) is not int or not 0 <= offset <= 2**31 - 1:
            raise ValueError("event_offset_out_of_bounds")
        result = {"namespace": self.namespace, "events": [], "total": 0, "limit": limit, "offset": offset,
                  "has_more": False, "filters": {"severity": severity, "source": source, "status": status},
                  "ack_meaning": "received_only_not_case_closed", "model_calls": 0}
        with self._read() as db:
            if db is None:
                return result
            selection, table = self._selection(db)
            conditions, values = [], []
            for field, value in (("json_extract(e.payload,'$.severity')", severity), (_SOURCE_SQL, source)):
                if value is not None:
                    conditions.append(field + "=?")
                    values.append(value)
            if status is not None:
                status_sql = "COALESCE(d.status,'new')" if " LEFT JOIN " in table else "'new'"
                conditions.append(status_sql + "=?")
                values.append(status)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            total = db.execute("SELECT COUNT(*) FROM " + table + where, values).fetchone()[0]
            rows = db.execute("SELECT " + selection + " FROM " + table + where
                              + " ORDER BY e.created_at DESC,e.event_id LIMIT ? OFFSET ?", (*values, limit, offset))
            result.update(events=[self._summary(row) for row in rows], total=total, has_more=offset + limit < total)
            return result

    @staticmethod
    def _saved_diagnosis(db, event):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_reviews'").fetchone():
            return None
        row = db.execute("SELECT payload_hash,result FROM event_reviews WHERE event_id=?", (event["event_id"],)).fetchone()
        if row is None:
            return None
        expected = event_payload_hash(validate_event(event))
        if row["payload_hash"] != expected or len(row["result"]) > 65536:
            raise ValueError("saved_review_identity_conflict")
        try:
            value = json.loads(row["result"])
        except (ValueError, TypeError):
            raise ValueError("saved_review_invalid") from None
        if not isinstance(value, dict) or value.get("payload_hash") != expected or value.get("incident_conclusion") != "not_assessed":
            raise ValueError("saved_review_invalid")
        return validate_saved_review(value, event)

    def detail(self, event_id):
        _identifier(event_id)
        with self._read() as db:
            if db is None:
                raise ValueError("event_not_found")
            selection, table = self._selection(db)
            row = db.execute("SELECT " + selection + " FROM " + table + " WHERE e.event_id=?", (event_id,)).fetchone()
            if row is None:
                raise ValueError("event_not_found")
            event = EventStore._row(row)
            return {**self._summary(row, event), "namespace": self.namespace, "event": event_view(event),
                    "interpretation": review(event), "guidance": event_guidance(event),
                    "latest_diagnosis": self._saved_diagnosis(db, event), "latest_diagnosis_is_saved": True,
                    "data_trust": "untrusted_data", "incident_conclusion": "not_assessed", "model_calls": 0}

    def set_status(self, event_id, status):
        _identifier(event_id)
        if type(status) is not str or status not in STATUSES:
            raise ValueError("invalid_event_status")
        # Check existence and payload identity without initializing an empty DB.
        # The write transaction checks existence again against concurrent prune.
        self.detail(event_id)
        result = EventStore(self.directory).set_disposition(event_id, status)
        return dict(result, namespace=self.namespace, ack_performed=False, model_calls=0)
