"""Bounded pending human intents; no dispatch, authorization, ACK, or commit."""
import re

from .events.disposition_history import IDENTIFIER, OPERATION, STATUSES
from .events.store import EventStore

FIELDS = ('namespace', 'event_id', 'status', 'operation_id', 'payload_hash')
MAX_PENDING = 128


def _valid(value):
    if (type(value) is not dict or set(value) != set(FIELDS)
            or type(value['namespace']) is not str or value['namespace'] not in ('live', 'test')
            or type(value['event_id']) is not str or not IDENTIFIER.fullmatch(value['event_id'])
            or type(value['operation_id']) is not str or not OPERATION.fullmatch(value['operation_id'])
            or type(value['status']) is not str or value['status'] not in STATUSES
            or type(value['payload_hash']) is not str or not re.fullmatch(r'[a-f0-9]{64}', value['payload_hash'])):
        raise ValueError('desktop_request_invalid')
    return dict(value)


def pending(db, *, namespace):
    """Missing table is empty; malformed or overfull evidence is never reset."""
    if type(namespace) is not str or namespace not in ('live', 'test'):
        raise ValueError('desktop_request_namespace_invalid')
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='desktop_status_requests'").fetchone()
    if not exists:
        return []
    if {row[1] for row in db.execute('PRAGMA table_info(desktop_status_requests)')} != set(FIELDS):
        raise ValueError('desktop_request_schema_invalid')
    rows = db.execute('SELECT namespace,event_id,status,operation_id,payload_hash FROM desktop_status_requests ORDER BY operation_id LIMIT ?',
                      (MAX_PENDING+1,)).fetchall()
    if len(rows) > MAX_PENDING:
        raise ValueError('desktop_request_capacity')
    values = [_valid(dict(zip(FIELDS, row))) for row in rows]
    if any(v['namespace'] != namespace for v in values):
        raise ValueError('desktop_request_namespace_mismatch')
    if (len({v['operation_id'] for v in values}) != len(values)
            or len({(v['event_id'], v['status']) for v in values}) != len(values)):
        raise ValueError('desktop_request_conflict')
    return values


def begin(db, value, *, available_bytes):
    """Caller owns the write transaction, outbox reserve and final size check.

    Persist before dispatch. A different ID for an unresolved event/status is
    refused; reading the original ID never executes it automatically.
    """
    if not db.in_transaction or db.execute('PRAGMA query_only').fetchone()[0]:
        raise ValueError('desktop_request_transaction_required')
    value = _valid(value)
    if type(available_bytes) is not int or available_bytes < 0:
        raise ValueError('desktop_request_bytes_invalid')
    row = db.execute('SELECT * FROM events WHERE event_id=?', (value['event_id'],)).fetchone()
    event = EventStore._row(row) if row is not None else None
    if event is None or row['payload_hash'] != value['payload_hash']:
        raise ValueError('desktop_request_event_unverified')
    values = pending(db, namespace=value['namespace'])
    for old in values:
        if old['operation_id'] == value['operation_id'] or (old['event_id'], old['status']) == (value['event_id'], value['status']):
            if old != value:
                raise ValueError('desktop_request_pending_conflict')
            return {'persisted': True, 'replayed': True, 'caller_commit_required': True}
    if len(values) >= MAX_PENDING or available_bytes < db.execute('PRAGMA page_size').fetchone()[0]*8:
        raise ValueError('desktop_request_capacity')
    db.execute('''CREATE TABLE IF NOT EXISTS desktop_status_requests(
        namespace TEXT NOT NULL, event_id TEXT NOT NULL, status TEXT NOT NULL, operation_id TEXT PRIMARY KEY,
        payload_hash TEXT NOT NULL, UNIQUE(event_id,status))''')
    db.execute('INSERT INTO desktop_status_requests(namespace,event_id,status,operation_id,payload_hash) VALUES(?,?,?,?,?)',
               tuple(value[key] for key in FIELDS))
    return {'persisted': True, 'replayed': False, 'caller_commit_required': True}


def complete(db, value):
    """Forget only an exact intent with independently stored GUI operation proof."""
    if not db.in_transaction or db.execute('PRAGMA query_only').fetchone()[0]:
        raise ValueError('desktop_request_transaction_required')
    value = _valid(value)
    if value not in pending(db, namespace=value['namespace']):
        raise ValueError('desktop_request_completion_unverified')
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_disposition_operations'").fetchone()
    row = db.execute('SELECT event_id,status,source,payload_hash FROM event_disposition_operations WHERE operation_id=?',
                     (value['operation_id'],)).fetchone() if exists else None
    if row is None or tuple(row) != (value['event_id'], value['status'], 'gui', value['payload_hash']):
        raise ValueError('desktop_request_completion_unverified')
    db.execute('DELETE FROM desktop_status_requests WHERE namespace=? AND event_id=? AND status=? AND operation_id=? AND payload_hash=?',
               tuple(value[key] for key in FIELDS))
    return {'resolved': True, 'caller_commit_required': True, 'ack_performed': False}


def retention_guard(db, table):
    """Keep both evidence and ACK receipts while human confirmation is pending.

    The namespace is validated, not interpreted as authorization. Any malformed
    journal blocks rotation rather than silently treating it as empty.
    """
    if table not in ('events', 'receipts'):
        raise ValueError('desktop_request_retention_table_invalid')
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='desktop_status_requests'").fetchone()
    if not exists:
        return ''
    row = db.execute('SELECT namespace FROM desktop_status_requests LIMIT 1').fetchone()
    pending(db, namespace=row[0] if row else 'live')
    return ' AND NOT EXISTS (SELECT 1 FROM desktop_status_requests q WHERE q.event_id='+table+'.event_id)'
