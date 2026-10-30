"""Synthetic CSVs only; structure success never means DSM compatibility."""
import contextlib
import io
import json
import unittest

from eventguard.events.nas_sample_probe import inspect_structure
from test_nas_csv import encoded


class NasSampleProbeTests(unittest.TestCase):
    def test_logical_rows_and_multiline_bom_have_no_source_claim(self):
        raw = b'\xef\xbb\xbf'+encoded([['quoted,\nfixture', 'success']], ('actor', 'result'))
        got = inspect_structure(raw)
        self.assertEqual((got['status'], got['rows'], got['columns']), ('structure_valid', 1, 2))
        self.assertTrue(got['bom'] and got['multiline'] and got['input_complete'])
        self.assertEqual(got['semantic_status'], 'not_assessed')
        self.assertFalse(got['source_format_verified'])

    def test_explicit_dialect_is_not_guessed(self):
        for name, delim in [('semicolon', ';'), ('tab', '\t')]:
            got = inspect_structure(f'a{delim}b\n1{delim}2'.encode(), delimiter=name)
            self.assertEqual(got['columns'], 2)
        self.assertEqual(inspect_structure(b'a;b\n1;2')['columns'], 1)
        self.assertEqual(inspect_structure(b'', delimiter=[])['error'], 'delimiter_invalid')

    def test_invalid_shape_encoding_and_empty_input_fail_closed(self):
        cases = [(b'', 'header_capacity_or_missing'), (b'a,a\n1,2', 'header_invalid'),
                 (b'a, \n1,2', 'header_invalid'), (b'a,b\n1', 'row_shape_invalid'),
                 (b'a\n"unterminated', 'csv_invalid'), (b'\xff', 'encoding_invalid'),
                 (b'a\n\x00', 'control_invalid'), (b'a\n', 'rows_missing')]
        for raw, code in cases:
            with self.subTest(code=code):
                got = inspect_structure(raw)
                self.assertEqual((got['status'], got['error']), ('rejected', code))

    def test_exact_capacities_and_overflow(self):
        self.assertEqual(inspect_structure(b'h\n'+b'x'*65534)['status'], 'structure_valid')
        self.assertEqual(inspect_structure(b'h\n'+b'x'*65535)['error'], 'input_capacity_or_type')
        self.assertEqual(inspect_structure(b'h\n'+b'x\n'*10)['rows'], 10)
        got = inspect_structure(b'h\n'+b'x\n'*11)
        self.assertEqual((got['error'], got['rows'], got['input_complete']), ('row_capacity', 10, False))
        for count in (32, 33):
            got = inspect_structure(encoded([['x']*count], [str(n) for n in range(count)]))
            self.assertEqual(got['status'], 'structure_valid' if count == 32 else 'rejected')

    def test_values_headers_and_failure_text_never_escape(self):
        canary = 'PRIVATE_FIXTURE_do_not_execute=cmd()'
        outputs = []
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            for raw in (encoded([[canary]], [canary]), (canary+'\n"'+canary).encode(),
                        encoded([[canary, canary]], ['h']), canary):
                outputs.append(inspect_structure(raw))
        self.assertEqual(capture.getvalue(), '')
        self.assertNotIn(canary, json.dumps(outputs))
        expected = {'version', 'status', 'error', 'encoding', 'delimiter', 'bom',
                    'columns', 'rows', 'multiline', 'input_complete',
                    'semantic_status', 'source_format_verified'}
        self.assertTrue(all(set(row) == expected for row in outputs))
