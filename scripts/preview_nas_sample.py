"""Run an in-memory, generated example; accepts no file, device or model input."""
import csv
import io
import json
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from eventguard.events.nas_sample_minimize import PROFILE
from eventguard.events.nas_sample_prepare import COLUMNS, prepare_fixture_csv


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args != ['--synthetic']:
        print(json.dumps({'error': 'synthetic_flag_required', 'collection_authorized': False}))
        return 2
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(COLUMNS)
    for index, outcome in enumerate(('failure', 'success')):
        writer.writerow([f'fixture-{index}', 'fixture-user', '192.0.2.1',
                         f'2026-10-30T08:00:0{index}+08:00', outcome])
    prepared = prepare_fixture_csv(stream.getvalue().encode(), profile=PROFILE,
        package_ref=secrets.token_hex(32), source_ref=secrets.token_hex(32),
        key=secrets.token_bytes(32), shift_days=7)
    print(json.dumps(prepared.summary, sort_keys=True))
    return 0 if prepared.summary['status'] == 'prepared' else 1


if __name__ == '__main__':
    raise SystemExit(main())
