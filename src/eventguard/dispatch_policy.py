"""Deterministic, read-only admission filtering over the existing outbox.

Policy contains only fixed enums. It cannot supply commands, prompts, paths,
tools, recipients or permissions. No event is received, ACKed, reclassified or
removed by this module. Deduplication/cooldown remain producer responsibilities.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time

from .events.schema import MAX_EVENT_BYTES
from .queue_inbox import QueueInbox, QueueInboxError, EVENT_TYPES, _guard, _identifier

MAX_POLICY_BYTES = 8192
PAGE_SIZE = 100
MAX_CANDIDATES = 1000
_FIELDS = frozenset({"severities", "event_types", "human_statuses"})
_VALUES = {"severities": frozenset({"info", "warning", "high", "critical"}),
           "event_types": EVENT_TYPES, "human_statuses": frozenset({"new", "read"})}
DEFAULT_POLICY = {"severities": ["high", "critical"],
                  "event_types": sorted(EVENT_TYPES), "human_statuses": ["new", "read"]}


class DispatchPolicyError(ValueError):
    """Fixed reason codes; never repeat untrusted configuration or raw SQL."""


def validate_policy(value):
    """Return a detached validated policy. Handled/ignored are never admitted."""
    if type(value) is not dict or set(value) != _FIELDS:
        raise DispatchPolicyError("dispatch_policy_fields_invalid")
    result = {}
    for field, allowed in _VALUES.items():
        items = value[field]
        if (type(items) is not list or not 1 <= len(items) <= len(allowed)
                or any(type(item) is not str or item not in allowed for item in items)
                or len(set(items)) != len(items)):
            raise DispatchPolicyError("dispatch_policy_condition_invalid")
        result[field] = list(items)
    return result


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DispatchPolicyError("dispatch_policy_duplicate_key")
        result[key] = value
    return result


def load_policy(path=None):
    """Read an explicit local JSON file, or return detached safe defaults."""
    if path is None:
        return validate_policy(DEFAULT_POLICY)
    try:
        target = _guard(Path(path))
        with target.open("rb") as stream:
            raw = stream.read(MAX_POLICY_BYTES + 1)
        if len(raw) > MAX_POLICY_BYTES:
            raise DispatchPolicyError("dispatch_policy_capacity")
        return validate_policy(json.loads(raw, object_pairs_hook=_pairs))
    except DispatchPolicyError:
        raise
    except (OSError, ValueError, TypeError, RecursionError, QueueInboxError):
        raise DispatchPolicyError("dispatch_policy_read_failed") from None


def _value(field):
    # SQLite may reorder WHERE predicates. CASE makes malformed/oversized JSON
    # safe independently of query planning, before any json_extract operation.
    return ("CASE WHEN typeof(e.payload)='text' AND length(CAST(e.payload AS BLOB))<="
            + str(MAX_EVENT_BYTES) + " AND json_valid(e.payload) THEN json_extract(e.payload,'$."
            + field + "') END")


def select_pending(inbox, policy=None):
    """Select one due permitted ID without head-of-line low-severity blocking.

    Critical precedes high, warning and info; ties use persisted time and ID.
    SQL filters before pagination, so any number of low-severity rows cannot
    hide a later high-severity candidate. Bounded pages avoid loading a queue.
    Every selected candidate is independently validated against its stored hash
    using QueueInbox's existing source reader. Corrupt matching candidates fail
    visibly rather than being silently ACKed/skipped. A scan limit is an error,
    never an empty-queue assertion. Selection is not a launch authorization.
    """
    if not isinstance(inbox, QueueInbox):
        raise DispatchPolicyError("dispatch_policy_inbox_required")
    checked = load_policy() if policy is None else validate_policy(policy)
    severity, kind = _value("severity"), _value("event_type")
    priority = "CASE " + severity + " WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END"
    now = time.time()
    with inbox._readonly() as db:
        # One local read transaction bounds the observation. It reserves no
        # events and grants no right to ignore later pause/budget/launch gates.
        db.execute("BEGIN")
        disposition_exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_dispositions'").fetchone()
        join = " LEFT JOIN event_dispositions d ON d.event_id=e.event_id" if disposition_exists else ""
        human = "COALESCE(d.status,'new')" if disposition_exists else "'new'"
        placeholders = lambda values: ",".join("?" for _ in values)
        sql = ("SELECT e.event_id FROM events e" + join +
               " WHERE e.delivery_status IN ('pending','retry')"
               " AND (e.next_retry_at IS NULL OR e.next_retry_at<=?)"
               " AND (e.lease_until IS NULL OR e.lease_until<=?)"
               " AND " + severity + " IN (" + placeholders(checked["severities"]) + ")"
               " AND " + kind + " IN (" + placeholders(checked["event_types"]) + ")"
               " AND " + human + " IN (" + placeholders(checked["human_statuses"]) + ")")
        parameters = [now, now, *checked["severities"], *checked["event_types"], *checked["human_statuses"]]
        if not inbox.allow_live:
            sql += " AND " + _value("synthetic") + "=1"
        sql += " ORDER BY " + priority + ",e.created_at,e.event_id LIMIT ? OFFSET ?"
        for offset in range(0, MAX_CANDIDATES, PAGE_SIZE):
            rows = db.execute(sql, [*parameters, PAGE_SIZE, offset]).fetchall()
            for row in rows:
                identity = _identifier(row["event_id"])
                source = inbox._source_record(identity)
                snapshot = source.get("snapshot")
                if source.get("delivery_status") not in {"pending", "retry"} or snapshot is None:
                    continue
                if (snapshot["severity"] in checked["severities"]
                        and snapshot["event_type"] in checked["event_types"]
                        and (inbox.allow_live or snapshot["synthetic"] is True)):
                    return identity
            if len(rows) < PAGE_SIZE:
                return None
    raise DispatchPolicyError("dispatch_policy_scan_limit_pending_preserved")
