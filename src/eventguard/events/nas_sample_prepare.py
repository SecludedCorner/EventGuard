"""Fixture CSV -> local private derivatives plus a separate value-free summary."""
import csv
from dataclasses import dataclass, field
import io
import json

from .nas_sample_minimize import minimize_fixture_row
from .nas_sample_probe import MAX_BYTES, inspect_structure

COLUMNS = ('record_id', 'subject', 'origin', 'event_time', 'outcome')


@dataclass
class PreparedFixture:
    summary: dict
    private_rows: list = field(default_factory=list, repr=False)


def prepare_fixture_csv(raw, *, profile, package_ref, source_ref, key, shift_days):
    """No I/O or delivery; only explicitly declared, generated fixtures may enter."""
    structure = inspect_structure(raw)
    summary = dict(version='nas-sample-preview-v1', status='rejected',
        error=structure['error'], structure=structure, transformed_rows=0,
        success=0, failure=0, field_gaps=0, missing_outcomes=[],
        semantic_status='not_assessed', source_format_verified=False,
        collection_authorized=False, allowed_actions=[])
    if structure['status'] != 'structure_valid':
        return PreparedFixture(summary)
    reader = csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    if next(reader) != list(COLUMNS):
        summary['error'] = 'fixture_schema_unknown'
        return PreparedFixture(summary)
    rows = []
    try:
        for values in reader:
            rows.append(minimize_fixture_row(dict(zip(COLUMNS, values)), profile=profile,
                package_ref=package_ref, source_ref=source_ref, key=key, shift_days=shift_days))
    except ValueError:
        summary['error'] = 'record_or_scope_invalid'
        return PreparedFixture(summary)  # Never release a partially transformed batch.
    if len(json.dumps(rows, ensure_ascii=True).encode()) > MAX_BYTES:
        summary['error'] = 'output_capacity'
        return PreparedFixture(summary)
    summary['transformed_rows'] = len(rows)
    for row in rows:
        summary[row['outcome']] += 1
        summary['field_gaps'] += len(row['gaps'])
    summary['missing_outcomes'] = [name for name in ('success', 'failure') if not summary[name]]
    summary['status'] = 'partial' if summary['missing_outcomes'] or summary['field_gaps'] else 'prepared'
    return PreparedFixture(summary, rows)
