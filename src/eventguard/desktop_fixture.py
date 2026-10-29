"""Disposable synthetic desktop scope; no collector, agent, ACK or settings API."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import re

from .desktop import DesktopController
from .diagnostics.review import review
from .events.catalog import EventCatalog
from .events.store import EventStore
from .runtime import Runtime, atomic_json
from .synthetic import make_synthetic


SAFE = frozenset({'inspect', 'investigate', 'set_status', 'backup_history', 'preview_history_backup'})
BLOCKED = frozenset({'start', 'pause', 'set_agent_delivery', 'set_automatic_agent', 'acknowledge', 'ack_event', 'collect', 'diagnose'})


class DesktopFixtureController:
    """Always create a new reports scope; never open installation live data.

    Internal data/live is a disposable synthetic copy for the existing desktop
    contract. Existing scopes are refused rather than guessed safe or reset.
    """
    synthetic_fixture = True

    def __init__(self, project_root, name, *, now=None):
        if not isinstance(name, str) or re.fullmatch(r'desktop-ux-[A-Za-z0-9_-]{1,64}', name) is None:
            raise ValueError('desktop_fixture_name_invalid')
        runtime = Runtime(project_root)
        reports = runtime.path('reports')
        reports.mkdir(exist_ok=True)
        self.root = runtime.path(Path('reports')/name)
        self.root.mkdir(exist_ok=False)
        self.closed = False
        stamp = now or datetime.now(timezone.utc)
        self.stamp = stamp.isoformat(timespec='seconds')
        self.store = EventStore(self.root/'data/live')
        for kind in ('listener', 'defender', 'startup', 'coverage'):
            event = make_synthetic(kind)
            event.update(event_id='synthetic-ux-'+kind, observed_at=self.stamp, persisted_at=self.stamp,
                         window={'start': self.stamp, 'end': self.stamp})
            self.store.enqueue(event)
        self.catalog = EventCatalog(self.root, 'live')
        self.catalog.set_status('synthetic-ux-defender', 'read', source='system', operation_id='fixture-read')
        self.catalog.set_status('synthetic-ux-defender', 'handled', source='system', operation_id='fixture-handled')
        event = self.store.get_event('synthetic-ux-listener')
        api = SimpleNamespace(query=lambda *a: {'status': 'denied', 'source': 'listeners', 'rows': [],
            'truncated': True, 'observed_at': self.stamp, 'coverage': {}})
        diagnosis = dict(review(event, api, refresh=True, now=self.stamp), namespace='live')
        self.store.save_review(event['event_id'], diagnosis['payload_hash'], diagnosis)
        states = ('denied', 'partial', 'unknown', 'ok', 'error', 'stale', 'not_applicable')
        sources = ('defender', 'listeners', 'processes', 'startup', 'services', 'tasks', 'versions')
        self.sources = [{'source_id': source, 'status': state, 'row_count': 1 if state in ('partial', 'ok') else None,
            'observed_at': self.stamp, 'freshness': {'state': 'stale' if state == 'stale' else 'fresh'},
            'last_success_at': (stamp-timedelta(minutes=5)).isoformat(), 'last_success_state': 'known',
            'reason': 'synthetic_fixture'} for source, state in zip(sources, states)]
        self._local = DesktopController(self.root)
        atomic_json(self.root/'fixture.json', {'schema_version': '1.0', 'synthetic': True,
            'prepared_at': self.stamp, 'event_count': 4, 'participant_results': None,
            'machine_scan_executed': False, 'model_calls': 0, 'ack_performed': False})

    def _blocked(self, *args, **kwargs):
        return {'state': 'blocked', 'reason': 'synthetic_fixture_operation_disabled', 'synthetic_fixture': True,
                'system_query_executed': False, 'model_calls': 0, 'ack_performed': False}

    def __getattr__(self, name):
        if name in BLOCKED:
            return self._blocked
        if name not in SAFE:
            raise AttributeError(name)
        def call(*args, **kwargs):
            if self.closed:
                return self._blocked()
            self._events()
            return getattr(self._local, name)(*args, **kwargs)
        return call

    def _events(self):
        events = self.store.list_events(limit=5)
        if len(events) != 4 or any(e.get('synthetic') is not True for e in events):
            raise ValueError('desktop_fixture_data_scope_changed')
        return events

    def snapshot(self):
        if self.closed:
            return self._blocked()
        events = self._events()
        counts = self.store.stats()
        handling = self.catalog.handling_states(events)
        return {'state': 'disabled', 'synthetic_fixture': True, 'monitoring': False, 'namespace': 'live',
            'updated_at': self.stamp, 'sources': deepcopy(self.sources),
            'events': [dict(e, handling_status=handling[e['event_id']]) for e in events],
            'events_total': len(events), 'events_truncated': False,
            'counts': {'pending': counts['pending']+counts['retry'], 'acked': counts['ack'], 'failed': counts['failed']},
            'agent_delivery': {'enabled': False}, 'automatic_agent': {'enabled': False, 'state': 'disabled'},
            'model_calls': 0, 'system_query_executed': False}

    def close(self):
        self.closed = True
        return {'state': 'closed', 'synthetic_fixture': True, 'can_close': True,
                'model_calls': 0, 'system_query_executed': False, 'ack_performed': False}
