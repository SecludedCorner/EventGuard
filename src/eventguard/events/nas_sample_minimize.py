"""Local-only fixture transformation; outputs are private derivatives, not events."""
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import re

PROFILE = 'nas-login-local-fixture-v1'
FIELDS = {'record_id', 'subject', 'origin', 'event_time', 'outcome'}


def minimize_fixture_row(values, *, profile, package_ref, source_ref, key, shift_days):
    """Explicit fixture schema only; caller must keep refs/key/output local."""
    if type(profile) is not str or profile != PROFILE:
        raise ValueError('fixture_profile_required')
    if type(key) is not bytes or len(key) != 32:
        raise ValueError('package_key_invalid')
    if any(type(v) is not str or re.fullmatch('[0-9a-f]{64}', v) is None
           for v in (package_ref, source_ref)):
        raise ValueError('scope_invalid')
    if type(shift_days) is not int or not 1 <= abs(shift_days) <= 3650:
        raise ValueError('time_shift_invalid')
    if type(values) is not dict or set(values) != FIELDS:
        raise ValueError('fixture_fields_invalid')
    if any(v is not None and (type(v) is not str or len(v) > 1024)
           for v in values.values()):
        raise ValueError('fixture_value_invalid')
    if values['outcome'] not in ('success', 'failure'):
        raise ValueError('outcome_unknown')
    gaps, refs = [], {}
    for field, target in (('record_id', 'record_ref'), ('subject', 'subject_ref'),
                          ('origin', 'origin_ref')):
        value = values[field]
        if not value:
            refs[target] = None
            gaps.append(field+'_unknown')
        else:
            binding = json.dumps([PROFILE, package_ref, source_ref, field, value],
                                 ensure_ascii=True, separators=(',', ':')).encode()
            refs[target] = hmac.new(key, binding, hashlib.sha256).hexdigest()
    event_time = values['event_time']
    shifted = None
    offset_seconds = None
    if not event_time:
        gaps.append('event_time_unknown')
    else:
        invalid = False
        try:
            stamp = datetime.fromisoformat(event_time)
            if stamp.utcoffset() is None:
                gaps.append('event_time_offset_unknown')
            elif stamp.utcoffset().microseconds:
                invalid = True
            else:
                offset_seconds = int(stamp.utcoffset().total_seconds())
                shifted = (stamp+timedelta(days=shift_days)).isoformat()
        except (ValueError, OverflowError):
            invalid = True
        if invalid:
            raise ValueError('event_time_invalid')
    return dict(profile=PROFILE, **refs, event_time=shifted, offset_seconds=offset_seconds,
        outcome=values['outcome'], gaps=gaps, time_basis='artificial_shifted',
        artifact_scope='private_transformed_fixture', semantic_status='not_assessed',
        source_format_verified=False)
