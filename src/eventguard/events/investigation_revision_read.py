"""Read bounded saved investigation revisions without modifying the database."""
import json
import sqlite3

from .investigation_revision import MAX_CASE_BYTES, MAX_REVISIONS, MAX_REVISIONS_PER_EVENT, validate_revision
from .schema import validate_event
from .store import EventStore, StoreError, event_payload_hash


_UNOBSERVED = object()


def read_revisions(db, event, *, diagnosis=_UNOBSERVED):
    """Only current matching event identities are considered known.

    Older, unrecorded revisions remain unknown; a hash is not a signature.
    """
    if not db.in_transaction or db.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise ValueError("investigation_revision_read_transaction_required")
    unknown = {"state": "unknown", "revisions": [], "prior_history": "unknown", "count_capacity": "unknown"}
    try:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='investigation_revisions'").fetchone()
        if not exists:
            return {"state": "not_recorded", "revisions": [], "prior_history": "unknown", "count_capacity": "available"}
        total = db.execute("SELECT COUNT(*) FROM investigation_revisions").fetchone()[0]
        rows = db.execute("SELECT event_id,payload_hash,case_hash,saved_at,case_json,revision_id FROM investigation_revisions WHERE event_id=? ORDER BY revision_id DESC LIMIT ?",
                          (event["event_id"], MAX_REVISIONS_PER_EVENT + 1)).fetchall()
        if total > MAX_REVISIONS or len(rows) > MAX_REVISIONS_PER_EVENT:
            return unknown
        from .investigation import diagnostic_summary
        current_diagnostic = None if diagnosis is _UNOBSERVED else diagnostic_summary(diagnosis)
        results = []
        for row in rows:
            if (type(row[4]) is not str or len(row[4].encode("utf-8")) > MAX_CASE_BYTES
                    or type(row[5]) is not int or not 1 <= row[5] <= 2**53-1):
                return unknown
            revision = {"schema_version": "1.0", "event_id": row[0], "payload_hash": row[1],
                        "case_hash": row[2], "saved_at": row[3], "case": json.loads(row[4])}
            validate_revision(revision, event)
            missing, changed = [], []
            for member in revision["case"]["timeline"]:
                current = db.execute("SELECT * FROM events WHERE event_id=?", (member["event_id"],)).fetchone()
                if current is None:
                    missing.append(member["event_id"])
                else:
                    try:
                        digest = event_payload_hash(validate_event(EventStore._row(current)))
                    except (ValueError, TypeError, StoreError):
                        digest = None
                    if digest != member["payload_hash"]:
                        changed.append(member["event_id"])
            context = revision["case"].get("diagnostic_context")
            diagnostic_status = ("not_bound" if context is None else
                                 "unknown" if current_diagnostic is None else
                                 "missing" if current_diagnostic["state"] == "missing" else
                                 "matched" if current_diagnostic["review_hash"] == context["review_hash"] else "changed")
            results.append({**revision, "revision_id": row[5], "evidence_status": "unknown" if missing or changed else "saved_snapshot",
                            "diagnostic_evidence_status": diagnostic_status,
                            "missing_event_ids": missing, "changed_event_ids": changed})
        full = total >= MAX_REVISIONS or len(rows) >= MAX_REVISIONS_PER_EVENT
        return {"state": "available" if results else "not_recorded", "revisions": results,
                "prior_history": "unknown", "count_capacity": "full" if full else "available"}
    except (sqlite3.Error, ValueError, TypeError, KeyError, OverflowError, StoreError):
        return unknown
