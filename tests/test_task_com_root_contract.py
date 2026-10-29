"""Exercise actual Dispatch marshalling with fake COM functions, never Task COM."""
import ctypes as C
import unittest
from unittest.mock import patch

from eventguard.collectors import taskcom
from eventguard.collectors.winapi import LONG, NativeError


class TaskRootContractTests(unittest.TestCase):
    def call_root(self, *, failure=False, argument='\\'):
        buffer = C.create_unicode_buffer('\\')
        calls, clears, releases = [], [], []
        def allocate(value):
            calls.append(('allocate', value))
            return C.addressof(buffer)
        def clear(pointer):
            value = C.cast(pointer, C.POINTER(taskcom.VARIANT)).contents
            clears.append((value.vt, value.value.pointer))
            value.vt = 0
            return 0
        functions = {'SysAllocString': allocate, 'VariantClear': clear,
                     'SysFreeString': lambda value: self.fail('no exception BSTR in fixture'),
                     'SysStringLen': lambda value: 1}
        def get_ids(pointer, iid, names, count, locale, identity):
            self.assertEqual((names[0], count, locale), ('GetFolder', 1, 0))
            C.cast(identity, C.POINTER(LONG))[0] = 42
            return 0
        def invoke(pointer, identity, iid, locale, flags, parameters, result, exception, argerror):
            params = C.cast(parameters, C.POINTER(taskcom.PARAMETERS)).contents
            self.assertEqual((identity.value, flags, params.count, params.named_count), (42, 1, 1, 0))
            self.assertEqual(params.args[0].vt, 8)
            self.assertEqual(C.wstring_at(params.args[0].value.pointer), '\\')
            calls.append(('invoke',))
            if failure:
                return -2147024893  # HRESULT_FROM_WIN32(ERROR_PATH_NOT_FOUND).
            returned = C.cast(result, C.POINTER(taskcom.VARIANT)).contents
            returned.vt, returned.value.pointer = 9, 456
            return 0
        def method(dispatch, index, *signature):
            if index == 5:
                return get_ids
            if index == 6:
                return invoke
            self.assertEqual(index, 2)
            return lambda pointer: releases.append(pointer.value) or 0
        with patch.object(taskcom, 'function', side_effect=lambda library, name, *a: functions[name]), \
             patch.object(taskcom.Dispatch, '_method', method):
            service = taskcom.Dispatch(123, object())
            if failure:
                with self.assertRaises(NativeError) as caught:
                    service.get('GetFolder', argument, method=True, stage='object')
                self.assertEqual(caught.exception.evidence()['reason_code'], 'object_unavailable')
                returned = None
            elif argument != '\\':
                with self.assertRaisesRegex(ValueError, 'unallowlisted_com_argument'):
                    service.get('GetFolder', argument, method=True, stage='object')
                returned = None
            else:
                returned = service.get('GetFolder', argument, method=True, stage='object')
                self.assertEqual(returned.pointer.value, 456)
                self.assertEqual(clears[0][0], 0, 'returned dispatch reference must be detached before VariantClear')
            if returned:
                returned.close()
            service.close()
        return calls, clears, releases

    def test_root_bstr_method_and_owned_reference_transfer(self):
        calls, clears, releases = self.call_root()
        self.assertEqual(calls, [('allocate', '\\'), ('invoke',)])
        self.assertEqual([value[0] for value in clears], [0, 8])
        self.assertEqual(releases, [456, 123])

    def test_root_failure_preserves_unknown_and_clears_allocated_argument(self):
        calls, clears, releases = self.call_root(failure=True)
        self.assertEqual([value[0] for value in clears], [0, 8])
        self.assertEqual(releases, [123])

    def test_unallowlisted_path_never_reaches_invoke(self):
        calls, clears, releases = self.call_root(argument='..')
        self.assertEqual(calls, [])
        self.assertEqual(releases, [123])
