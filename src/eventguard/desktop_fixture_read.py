"""Strict, bounded, read-only reopening checks for generated synthetic scopes."""
from datetime import datetime, timezone
import json

from .events.catalog import EventCatalog
from .events.store import EventStore, StoreError
from .runtime import Runtime, read_json
from .storage_policy import limits

IDS = frozenset('synthetic-ux-'+kind for kind in ('listener', 'defender', 'startup', 'coverage'))


class SavedFixtureStore:
    """No initialization/migration/cleanup, even when a fixture is incomplete."""
    def __init__(self, root):
        try:
            runtime = Runtime(root)
            marker = read_json(runtime.path('fixture.json'), limit=8192)
            expected = {'schema_version', 'synthetic', 'prepared_at', 'event_count', 'participant_results',
                        'machine_scan_executed', 'model_calls', 'ack_performed'}
            if (not isinstance(marker, dict) or set(marker) != expected or marker['schema_version'] != '1.0'
                    or marker['synthetic'] is not True or type(marker['event_count']) is not int or marker['event_count'] != 4
                    or marker['participant_results'] is not None or marker['machine_scan_executed'] is not False
                    or type(marker['model_calls']) is not int or marker['model_calls'] != 0 or marker['ack_performed'] is not False
                    or not isinstance(marker['prepared_at'], str) or len(marker['prepared_at']) > 80):
                raise ValueError('desktop_fixture_scope_invalid')
            self.stamp = datetime.fromisoformat(marker['prepared_at'].replace('Z', '+00:00'))
            if self.stamp.utcoffset() is None or self.stamp > datetime.now(timezone.utc):
                raise ValueError('desktop_fixture_scope_invalid')
            self.path = runtime.path('data/live/eventguard.sqlite3')
            if not 0 < self.path.stat().st_size <= 8*1024*1024:
                raise ValueError('desktop_fixture_scope_invalid')
            self.catalog = EventCatalog(root, 'live')
            with self.catalog._read() as db:
                columns = EventStore._schema_columns(db)
                if (columns is None or 'payload_hash' not in columns['events']
                        or not {'payload_hash', 'pending_finalization'} <= columns['receipts']):
                    raise ValueError('desktop_fixture_scope_invalid')
                row = db.execute("SELECT value FROM meta WHERE key='storage_policy'").fetchone()
                policy = json.loads(row[0]) if row else None
                if not isinstance(policy, dict) or limits('outbox', policy) != policy:
                    raise ValueError('desktop_fixture_scope_invalid')
                self._rows(db)
            for event_id in IDS:
                detail = self.catalog.detail(event_id)
                if detail['handling_history']['state'] == 'unknown':
                    raise ValueError('desktop_fixture_scope_invalid')
        except (OSError, ValueError, TypeError, KeyError, StoreError):
            raise ValueError('desktop_fixture_scope_invalid') from None

    @staticmethod
    def _rows(db):
        events = [EventStore._row(row) for row in db.execute('SELECT * FROM events LIMIT 5')]
        if (len(events) != 4 or {e['event_id'] for e in events} != IDS
                or any(e['synthetic'] is not True or e['delivery_status'] != 'pending' or e['attempts'] != 0 for e in events)
                or db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0] != 0):
            raise ValueError('desktop_fixture_scope_invalid')
        return events

    def list_events(self, limit=100):
        with self.catalog._read() as db:
            events = self._rows(db)
            rows = db.execute('SELECT * FROM events ORDER BY created_at DESC,event_id LIMIT ?', (max(0, min(5, limit)),))
            return [EventStore._row(row) for row in rows]

    def stats(self):
        with self.catalog._read() as db:
            self._rows(db)
            return {'pending': 4, 'retry': 0, 'ack': 0, 'failed': 0, 'receipt_count': 0}
