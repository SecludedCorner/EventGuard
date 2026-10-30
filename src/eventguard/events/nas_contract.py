"""Offline NAS fixture contract; no log reader, live ingress, model or actions."""
from datetime import datetime
import re

from .schema import _timestamp, stable_event_id

VERSION = 'nas-security-fixture-v1'
FIELDS = {'schema_version', 'synthetic', 'source', 'record_ref', 'subject_ref', 'outcome',
          'event_time', 'received_at', 'clock_uncertainty_seconds', 'evidence_ref',
          'evidence_sha256', 'truncated'}


def exact(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise ValueError('nas_contract_fields_invalid')


def reference(value):
    if type(value) is not str or len(value) != 64 or re.fullmatch('[a-f0-9]{64}', value) is None:
        raise ValueError('nas_opaque_reference_required')
    return value


def source(value):
    exact(value, {'device_ref', 'source_ref', 'epoch_ref', 'service', 'trust'})
    for key in ('device_ref', 'source_ref', 'epoch_ref'):
        reference(value[key])
    if value['service'] not in ('dsm', 'ssh', 'website', 'router') or value['trust'] != 'unverified':
        raise ValueError('nas_unverified_source_required')
    return dict(value)


def timestamp(value):
    if value is None:
        return None, None
    canonical = _timestamp(value)
    offset = datetime.fromisoformat(value.replace('Z', '+00:00')).utcoffset().total_seconds()
    return canonical, offset


def count(value, maximum=2**31-1):
    if value is not None and (type(value) is not int or not 0 <= value <= maximum):
        raise ValueError('nas_count_invalid')
    return value


def normalize(value):
    exact(value, FIELDS)
    if value['schema_version'] != VERSION or value['synthetic'] is not True:
        raise ValueError('nas_fixture_only')
    origin = source(value['source'])
    if origin['service'] != 'dsm' or value['outcome'] not in ('success', 'failure'):
        raise ValueError('nas_dsm_login_outcome_required')
    if type(value['truncated']) is not bool:
        raise ValueError('nas_truncated_flag_invalid')
    refs = {key: reference(value[key]) for key in ('record_ref', 'evidence_ref', 'evidence_sha256')}
    subject = reference(value['subject_ref']) if value['subject_ref'] is not None else None
    event_time, event_offset = timestamp(value['event_time'])
    received, received_offset = timestamp(value['received_at'])
    if received is None:
        raise ValueError('nas_received_time_required')
    uncertainty = count(value['clock_uncertainty_seconds'], 86400)
    gaps = [key for key, missing in (('event_time_unknown', event_time is None),
        ('subject_unknown', subject is None), ('clock_uncertainty_unknown', uncertainty is None),
        ('record_truncated', value['truncated'])) if missing]
    if event_time and uncertainty is not None and (datetime.fromisoformat(event_time)-datetime.fromisoformat(received)).total_seconds() > uncertainty:
        gaps.append('event_clock_ahead')
    body = dict(schema_version=VERSION, synthetic=True, source=origin, **refs, subject_ref=subject,
        event_type='dsm_login', outcome=value['outcome'], event_time=event_time,
        clock_uncertainty_seconds=uncertainty, truncated=value['truncated'])
    return dict(body, received_at=received, timezone_offsets_seconds=dict(event=event_offset, received=received_offset),
        dedup_key=stable_event_id(VERSION, origin, refs['record_ref']), content_hash=stable_event_id(body),
        data_status='partial' if gaps else 'complete', gaps=gaps,
        incident_conclusion='not_assessed', allowed_actions=[])


def reconcile(records):
    """Order-independent bounded dedup; a reused record identity cannot overwrite evidence."""
    if type(records) is not list or len(records) > 256:
        raise ValueError('nas_batch_capacity')
    unique = {}
    for raw in records:
        event = normalize(raw)
        key = event['dedup_key']
        previous = unique.get(key)
        if previous and previous['content_hash'] != event['content_hash']:
            raise ValueError('nas_record_identity_conflict')
        if previous is None or (event['received_at'], stable_event_id(event)) < (previous['received_at'], stable_event_id(previous)):
            unique[key] = event
    return dict(events=[unique[key] for key in sorted(unique)], duplicates=len(records)-len(unique))
