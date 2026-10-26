"""Local event browsing and handling states. No collection, ACK or model use."""
from __future__ import annotations

from contextlib import contextmanager, closing
import json
from pathlib import Path
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

    def __init__(self, root, namespace="live", directory=None):
        self.runtime = Runtime(root)
        self.namespace = namespace
        if directory is None:
            self.directory = self.runtime.data_dir(namespace, create=False)
        else:
            # An explicit synthetic source inside this root. Never the live scope.
            if namespace != "test":
                raise ValueError("event_source_requires_test_namespace")
            try:
                relative = Path(directory).absolute().relative_to(self.runtime.root)
            except ValueError:
                raise ValueError("event_source_outside_root") from None
            self.directory = self.runtime.path(relative)
            if self.directory in (self.runtime.root, self.runtime.data_dir("live", create=False)):
                raise ValueError("event_source_scope_refused")
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
            result = {**self._summary(row, event), "namespace": self.namespace, "event": event_view(event),
                    "interpretation": review(event), "guidance": event_guidance(event),
                    "latest_diagnosis": self._saved_diagnosis(db, event), "latest_diagnosis_is_saved": True,
                    "data_trust": "untrusted_data", "incident_conclusion": "not_assessed", "model_calls": 0,
                    "investigation": self._saved_investigation(db, event, row["catalog_source"])}
            if event["event_type"] == "advisory.changed":
                from ..intelligence.views import public_advisories
                result["advisory_context"] = public_advisories(self.runtime.root, self.namespace,
                                                               limit=1, event_id=event_id)
            return result

    @staticmethod
    def _saved_investigation(db, event, source):
        from .investigation import validate_saved
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_investigations'").fetchone():
            return None
        row = db.execute("SELECT payload_hash,result FROM event_investigations WHERE event_id=?", (event["event_id"],)).fetchone()
        if row is None:
            return None
        if (row["payload_hash"] != event_payload_hash(validate_event(event)) or type(row["result"]) is not str
                or len(row["result"].encode("utf-8")) > 65536):
            raise ValueError("saved_investigation_identity_conflict")
        try:
            case = validate_saved(json.loads(row["result"]), event)
        except (ValueError, TypeError):
            raise ValueError("saved_investigation_invalid") from None
        anchor = next(item for item in case["timeline"] if item["event_id"] == event["event_id"])
        if anchor["source"] != source:
            raise ValueError("saved_investigation_identity_conflict")
        missing, changed = [], []
        for member in case["timeline"]:
            current = db.execute("SELECT * FROM events WHERE event_id=?", (member["event_id"],)).fetchone()
            if current is None:
                missing.append(member["event_id"])
            else:
                try:
                    current_hash = event_payload_hash(validate_event(EventStore._row(current)))
                except (ValueError, TypeError, StoreError):
                    current_hash = None
                if current_hash != member["payload_hash"]:
                    changed.append(member["event_id"])
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(case["as_of"])).total_seconds()
        return {"case": case, "evidence_status": "unknown" if missing or changed else "saved_snapshot",
                "snapshot_freshness": "unknown" if age < -60 else "stale" if age > 900 else "ok",
                "missing_event_ids": missing, "changed_event_ids": changed,
                "ack_performed": False, "model_calls": 0, "native_queries": 0}

    def investigate(self, event_id, *, now=None):
        """Explicitly save a snapshot of existing metadata, never refresh OS facts."""
        from .investigation import MAX_CANDIDATES, build, project
        _identifier(event_id)
        with self._read() as db:
            if db is None:
                raise ValueError("event_not_found")
            selection = "e.*," + _SOURCE_SQL + " AS catalog_source"
            row = db.execute("SELECT " + selection + " FROM events e WHERE e.event_id=?", (event_id,)).fetchone()
            if row is None:
                raise ValueError("event_not_found")
            event = EventStore._row(row)
            anchor = project(event, row["catalog_source"])
            rows = db.execute("SELECT " + selection + " FROM events e ORDER BY "
                              "ABS(julianday(json_extract(e.payload,'$.observed_at'))-julianday(?)),e.event_id LIMIT ?",
                              (event["observed_at"], MAX_CANDIDATES+1)).fetchall()
            candidates = [project(EventStore._row(item), item["catalog_source"]) for item in rows[:MAX_CANDIDATES]]
            case = build(anchor, candidates, as_of=now, truncated=len(rows) > MAX_CANDIDATES)
        EventStore(self.directory).save_investigation(event_id, anchor["payload_hash"], case)
        return self.detail(event_id)["investigation"]

    def set_status(self, event_id, status):
        _identifier(event_id)
        if type(status) is not str or status not in STATUSES:
            raise ValueError("invalid_event_status")
        # Check existence and payload identity without initializing an empty DB.
        # The write transaction checks existence again against concurrent prune.
        self.detail(event_id)
        result = EventStore(self.directory).set_disposition(event_id, status)
        return dict(result, namespace=self.namespace, ack_performed=False, model_calls=0)
