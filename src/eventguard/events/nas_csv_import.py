"""Combine candidate parsing, conflict exclusion and independent fixture coverage."""
from .nas_contract import timestamp
from .nas_coverage import VERSION as COVERAGE_VERSION, assess
from .nas_csv import parse_fixture_csv
from .schema import stable_event_id


def inspect_fixture_csv(raw, context, *, profile, now, max_age_seconds, coverage=None):
    parsed = parse_fixture_csv(raw, context, profile=profile)
    groups = {}
    for event in parsed['events']:
        groups.setdefault(event['dedup_key'], []).append(event)
    accepted, duplicates, conflict_rows = [], 0, 0
    errors = dict(parsed['errors'])
    for key in sorted(groups):
        members = groups[key]
        if len({event['content_hash'] for event in members}) != 1:
            conflict_rows += len(members)
            continue
        accepted.append(min(members, key=lambda event: (event['received_at'], stable_event_id(event))))
        duplicates += len(members)-1
    if conflict_rows:
        errors['identity_conflict_rows'] = conflict_rows
    gaps = []
    if not parsed['input_complete']:
        gaps.append('input_incomplete')
    if errors:
        gaps.append('parser_errors')
    if any(event['data_status'] != 'complete' for event in accepted):
        gaps.append('event_evidence_partial')
    parser_status = 'unknown' if not parsed['input_complete'] else 'partial' if gaps else 'ok'
    if coverage is None:
        gaps.append('transport_coverage_not_supplied')
        coverage = dict(schema_version=COVERAGE_VERSION, synthetic=True, source=parsed['source'],
            window_start=None, observed_at=None, heartbeat_at=None, last_success_at=None,
            parse_errors=None, dropped=None, truncated=None, interrupted=None, storage_error=None)
    elif type(coverage) is not dict or coverage.get('source') != parsed['source']:
        raise ValueError('nas_csv_coverage_source_mismatch')
    transport = assess(coverage, now=now, max_age_seconds=max_age_seconds)
    current, _ = timestamp(now)
    received = parsed['received_at']
    window = transport['window_start'], transport['observed_at']
    outside = received > current or any(window) and not (all(window) and window[0] <= received <= window[1])
    if outside:
        gaps.append('transport_window_does_not_cover_import')
    statuses = (parser_status, transport['status'])
    status = 'unknown' if outside or 'unknown' in statuses else 'partial' if 'partial' in statuses else 'ok'
    return dict(profile=profile, synthetic=True, source=parsed['source'], events=accepted,
        rows_seen=parsed['rows_seen'], parsed_rows=len(parsed['events']), duplicate_rows=duplicates,
        parser_errors=errors, parser_status=parser_status, input_complete=parsed['input_complete'],
        transport_coverage=transport, status=status, gaps=gaps,
        evidence_hash_scope=parsed['evidence_hash_scope'], incident_conclusion='not_assessed', allowed_actions=[])
