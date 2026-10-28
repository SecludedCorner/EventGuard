"""Transactional storage primitive for bounded investigation revisions."""
from __future__ import annotations

import json

from .investigation_revision import has_revision_capacity, validate_revision


class RevisionCapacityError(ValueError):
    pass


def append_revision(db, revision, anchor_event, *, available_bytes):
    """Append inside the caller's write transaction; never commit or evict.

    The caller must include current-case replacement in this same transaction,
    verify actual database use after insertion, and roll back on any error.
    """
    if not db.in_transaction or db.execute("PRAGMA query_only").fetchone()[0]:
        raise ValueError("investigation_revision_write_transaction_required")
    if type(available_bytes) is not int or available_bytes < 0:
        raise ValueError("investigation_revision_available_bytes_invalid")
    validate_revision(revision, anchor_event)
    encoded = json.dumps(revision["case"], sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='investigation_revisions'").fetchone()
    if exists:
        total = db.execute("SELECT COUNT(*) FROM investigation_revisions").fetchone()[0]
        per_event = db.execute("SELECT COUNT(*) FROM investigation_revisions WHERE event_id=?", (revision["event_id"],)).fetchone()[0]
    else:
        total = per_event = 0
    if not has_revision_capacity(total, per_event):
        raise RevisionCapacityError("investigation_revision_count_capacity")
    page = db.execute("PRAGMA page_size").fetchone()[0]
    if available_bytes < len(encoded) + page * (8 if not exists else 4):
        raise RevisionCapacityError("investigation_revision_bytes_capacity")
    db.execute("""CREATE TABLE IF NOT EXISTS investigation_revisions(
        revision_id INTEGER PRIMARY KEY, event_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
        case_hash TEXT NOT NULL, saved_at REAL NOT NULL, case_json TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS investigation_revisions_event ON investigation_revisions(event_id,revision_id)")
    db.execute("INSERT INTO investigation_revisions(event_id,payload_hash,case_hash,saved_at,case_json) VALUES(?,?,?,?,?)",
               (revision["event_id"], revision["payload_hash"], revision["case_hash"], revision["saved_at"], encoded))
