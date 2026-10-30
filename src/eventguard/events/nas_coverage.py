"""Pure synthetic source coverage; heartbeat health never establishes host safety."""
from datetime import datetime

from .nas_contract import count, exact, source, timestamp

VERSION = 'nas-source-fixture-v1'
FIELDS = {'schema_version', 'synthetic', 'source', 'window_start', 'observed_at',
          'heartbeat_at', 'last_success_at', 'parse_errors', 'dropped',
          'truncated', 'interrupted', 'storage_error'}


def assess(value, *, now, max_age_seconds):
    exact(value, FIELDS)
    if value['schema_version'] != VERSION or value['synthetic'] is not True:
        raise ValueError('nas_coverage_fixture_only')
    origin = source(value['source'])
    age_limit = count(max_age_seconds, 86400)
    current, _ = timestamp(now)
    if not age_limit or current is None:
        raise ValueError('nas_coverage_clock_required')
    times = {key: timestamp(value[key])[0] for key in ('window_start', 'observed_at', 'heartbeat_at', 'last_success_at')}
    counters = {key: count(value[key]) for key in ('parse_errors', 'dropped')}
    for key in ('truncated', 'interrupted'):
        if value[key] is not None and type(value[key]) is not bool:
            raise ValueError('nas_coverage_flag_invalid')
    storage = value['storage_error']
    if storage not in (None, 'none', 'disk_full', 'write_failed', 'unavailable'):
        raise ValueError('nas_storage_status_invalid')
    gaps = [key+'_unknown' for key, item in {**times, **counters,
        'truncated': value['truncated'], 'interrupted': value['interrupted'], 'storage': storage}.items() if item is None]
    observed = times['observed_at']
    if observed and (observed > current or any(item and item > observed for item in times.values())):
        gaps.append('clock_inconsistent')
    freshness = {}
    for key in ('heartbeat_at', 'last_success_at'):
        at = times[key]
        age = (datetime.fromisoformat(current)-datetime.fromisoformat(at)).total_seconds() if at else None
        freshness[key] = 'unknown' if age is None or age < 0 else 'fresh' if age <= age_limit else 'stale'
        if freshness[key] != 'fresh':
            gaps.append(key+'_'+freshness[key])
    for key, item in counters.items():
        if item:
            gaps.append(key)
    gaps.extend(key for key in ('truncated', 'interrupted') if value[key] is True)
    if storage not in (None, 'none'):
        gaps.append('storage_'+storage)
    unknown = any(item.endswith(('_unknown', '_stale')) or item == 'clock_inconsistent' for item in gaps)
    return dict(schema_version=VERSION, synthetic=True, source=origin, **times, **counters,
        truncated=value['truncated'], interrupted=value['interrupted'], storage_error=storage,
        counter_scope='window_start..observed_at within source epoch', assessed_at=current,
        freshness=freshness, freshness_basis='collector timestamps; not event clock verification',
        status='unknown' if unknown else 'partial' if gaps else 'ok', gaps=sorted(set(gaps)),
        incident_conclusion='not_assessed', allowed_actions=[])
