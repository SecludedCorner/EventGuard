"""Offline candidate CSV exchange parser; NOT a verified DSM export format."""
import csv
import io

from .nas_contract import VERSION, count, exact, normalize, source, timestamp
from .schema import stable_event_id

PROFILE = 'nas-csv-fixture-v1'
COLUMNS = ('record_ref', 'subject_ref', 'event_time', 'outcome', 'evidence_ref')
MAX_BYTES, MAX_ROWS = 65536, 256


def parse_fixture_csv(raw, context, *, profile):
    exact(context, {'synthetic', 'source', 'received_at', 'clock_uncertainty_seconds'})
    if profile != PROFILE or context['synthetic'] is not True:
        raise ValueError('nas_csv_fixture_profile_required')
    origin = source(context['source'])
    received, _ = timestamp(context['received_at'])
    uncertainty = count(context['clock_uncertainty_seconds'], 86400)
    if received is None or origin['service'] != 'dsm':
        raise ValueError('nas_csv_context_invalid')
    result = dict(profile=PROFILE, synthetic=True, source=origin, received_at=received,
        events=[], errors={}, rows_seen=0, input_complete=False,
        evidence_hash_scope='canonical minimized CSV projection; not raw bytes',
        incident_conclusion='not_assessed', allowed_actions=[])

    def reject(code):
        result['errors'][code] = result['errors'].get(code, 0)+1
        return result

    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        return reject('input_capacity_or_type')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError:
        return reject('invalid_utf8')
    if any(ord(char) < 32 and char not in '\t\r\n' for char in text):
        return reject('invalid_control_character')
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    try:
        if next(reader, None) != list(COLUMNS):
            return reject('unknown_columns')
        for row in reader:
            if result['rows_seen'] == MAX_ROWS:
                return reject('row_capacity')
            result['rows_seen'] += 1
            if len(row) != len(COLUMNS) or sum(map(len, row)) > 1024:
                reject('row_shape_invalid')
                continue
            values = dict(zip(COLUMNS, row))
            draft = dict(schema_version=VERSION, synthetic=True, source=origin,
                **values, received_at=context['received_at'], clock_uncertainty_seconds=uncertainty,
                evidence_sha256='0'*64, truncated=False)
            draft['subject_ref'] = values['subject_ref'] or None
            draft['event_time'] = values['event_time'] or None
            try:
                canonical = normalize(draft)
                projection = {key: canonical[key] for key in COLUMNS}
                draft['evidence_sha256'] = stable_event_id(PROFILE, projection)
                result['events'].append(normalize(draft))
            except ValueError:
                reject('record_invalid')
        result['input_complete'] = True
    except csv.Error:
        reject('csv_syntax_invalid')
    return result
