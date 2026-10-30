"""Bounded in-memory CSV structure probe; no schema, provenance, or safety claim."""
import csv
import io

MAX_BYTES, MAX_ROWS, MAX_COLUMNS = 65536, 10, 32
DELIMITERS = {'comma': ',', 'semicolon': ';', 'tab': '\t'}


def inspect_structure(raw, *, delimiter='comma'):
    """Return only fixed enums/counts. Callers own authorization and local I/O."""
    result = dict(version='nas-sample-structure-v1', status='rejected', error=None,
        encoding='unknown', delimiter='unknown', bom=False, columns=0, rows=0,
        multiline=False, input_complete=False, semantic_status='not_assessed',
        source_format_verified=False)

    def reject(code):
        result['error'] = code
        return result

    if type(delimiter) is not str or delimiter not in DELIMITERS:
        return reject('delimiter_invalid')
    result['delimiter'] = delimiter
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        return reject('input_capacity_or_type')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError:
        return reject('encoding_invalid')
    result.update(encoding='utf8', bom=raw.startswith(b'\xef\xbb\xbf'))
    if any(ord(c) < 32 and c not in '\t\r\n' for c in text):
        return reject('control_invalid')
    reader = csv.reader(io.StringIO(text, newline=''),
                        delimiter=DELIMITERS[delimiter], strict=True)
    try:
        header = next(reader, None)
        if not header or len(header) > MAX_COLUMNS:
            return reject('header_capacity_or_missing')
        if any(not cell.strip() for cell in header) or len(set(header)) != len(header):
            return reject('header_invalid')
        result['columns'] = len(header)
        result['multiline'] = any('\n' in c or '\r' in c for c in header)
        for row in reader:
            if result['rows'] >= MAX_ROWS:
                return reject('row_capacity')
            if len(row) != len(header):
                return reject('row_shape_invalid')
            result['rows'] += 1
            result['multiline'] |= any('\n' in c or '\r' in c for c in row)
        result['input_complete'] = True
        if not result['rows']:
            return reject('rows_missing')
    except csv.Error:
        return reject('csv_invalid')
    result['status'] = 'structure_valid'
    return result
