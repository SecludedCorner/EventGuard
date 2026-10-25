"""Bounded transport contracts. Mocks are separate from real stdio processes."""
from __future__ import annotations

import builtins
from contextlib import ExitStack, asynccontextmanager
import ctypes as C
import importlib.util
import io
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from eventguard import application_stdio as transport

SDK_AVAILABLE = importlib.util.find_spec("mcp") is not None


class OptionalTransportImportTests(unittest.TestCase):
    def test_import_does_not_require_or_load_sdk(self):
        original_import = builtins.__import__
        def no_sdk(name, *args, **kwargs):
            if name in {"anyio", "mcp"} or name.startswith("mcp."):
                raise AssertionError("Optional transport imported SDK eagerly")
            return original_import(name, *args, **kwargs)
        path = Path(transport.__file__)
        spec = importlib.util.spec_from_file_location("fixture_optional_application_stdio", path)
        module = importlib.util.module_from_spec(spec)
        with patch("builtins.__import__", side_effect=no_sdk):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.application_stdio_server))


class OptionalResponseCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_windows_callback_is_unsupported_without_loading_sdk(self):
        original_import = builtins.__import__
        def no_sdk(name, *args, **kwargs):
            if name == "mcp" or name.startswith("mcp."):
                raise AssertionError("Unsupported callback loaded SDK")
            return original_import(name, *args, **kwargs)
        with patch.object(transport.os, "name", "posix"), patch("builtins.__import__", side_effect=no_sdk):
            with self.assertRaisesRegex(transport.ApplicationStdioError, "^application_stdio_response_flushed_unsupported$"):
                async with transport.application_stdio_server(response_flushed=lambda message: None):
                    self.fail("Unsupported callback entered transport")

    @unittest.skipUnless(SDK_AVAILABLE, "optional installed SDK fallback")
    async def test_non_windows_default_preserves_sdk_fallback(self):
        streams = (object(), object())
        entered = []
        @asynccontextmanager
        async def fallback():
            entered.append(True)
            yield streams
        with patch("mcp.server.stdio.stdio_server", fallback), patch.object(transport.os, "name", "posix"):
            async with transport.application_stdio_server() as actual:
                self.assertIs(actual, streams)
        self.assertEqual(entered, [True])


@unittest.skipUnless(os.name == "nt", "Mock Win32 pipe contracts; no Linux runtime claim")
class InputPipeContracts(unittest.TestCase):
    def pipe(self, peek):
        value = object.__new__(transport._InputPipe)
        value.fd, value.handle = 0, 123
        value.api = SimpleNamespace(PeekNamedPipe=peek)
        return value

    def test_no_available_bytes_does_not_read_and_positive_peek_bounds_read(self):
        def peek(_handle, _buffer, _size, _read, available, _remaining):
            C.cast(available, C.POINTER(C.c_uint32)).contents.value = 0
            return 1
        pipe = self.pipe(peek)
        with patch.object(transport.os, "read") as read:
            self.assertEqual(pipe.read_available(), b"")
        read.assert_not_called()
        def much_available(_handle, _buffer, _size, _read, available, _remaining):
            C.cast(available, C.POINTER(C.c_uint32)).contents.value = transport.READ_BYTES*10
            return 1
        pipe = self.pipe(much_available)
        with patch.object(transport.os, "read", return_value=b"bounded") as read:
            self.assertEqual(pipe.read_available(), b"bounded")
        read.assert_called_once_with(0, transport.READ_BYTES)

    def test_only_known_pipe_disconnect_is_eof_and_denial_is_not_empty(self):
        pipe = self.pipe(Mock(return_value=0))
        for code in (109, 232, 233):
            with self.subTest(code=code), patch.object(transport.C, "get_last_error", return_value=code), \
                 patch.object(transport.os, "read") as read:
                self.assertIsNone(pipe.read_available())
            read.assert_not_called()
        with patch.object(transport.C, "get_last_error", return_value=5), \
             self.assertRaisesRegex(transport.ApplicationStdioError, "^application_stdio_stdin_unavailable$"):
            pipe.read_available()


@unittest.skipUnless(os.name == "nt" and SDK_AVAILABLE, "Windows transport with installed optional SDK; input is mocked")
class AsyncTransportContracts(unittest.IsolatedAsyncioTestCase):
    def mocked_streams(self, pipe):
        stack = ExitStack()
        output = io.BytesIO()
        stack.enter_context(patch.object(transport, "_InputPipe", return_value=pipe))
        stack.enter_context(patch.object(transport, "_output_buffer", return_value=output))
        return stack, output

    async def test_fragmented_utf8_sdk_message_eof_and_utf8_output(self):
        import anyio
        import mcp.types as types
        raw = '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"label":"合成"}}\n'.encode("utf-8")
        split = raw.index("合".encode("utf-8"))+1
        pipe = Mock()
        pipe.read_available.side_effect = [raw[:split], raw[split:], None]
        stack, output = self.mocked_streams(pipe)
        with stack:
            async with transport.application_stdio_server() as (incoming, outgoing):
                message = await incoming.receive()
                self.assertIsInstance(message, types.JSONRPCMessage)
                self.assertEqual(message.model_dump()["params"]["label"], "合成")
                with self.assertRaises(anyio.EndOfStream):
                    await incoming.receive()
                reply = types.JSONRPCMessage.model_validate_json(
                    '{"jsonrpc":"2.0","id":1,"result":{"label":"合成"}}')
                await outgoing.send(reply)
                with anyio.fail_after(2):
                    while not output.getvalue().endswith(b"\n"):
                        await anyio.sleep(.01)
        self.assertFalse(output.closed, "The adapter does not close process-owned stdout")
        self.assertEqual(json.loads(output.getvalue().decode("utf-8"))["result"]["label"], "合成")

    async def test_idle_owner_exit_cancels_poll_without_a_stdin_worker(self):
        import anyio
        pipe = Mock()
        pipe.read_available.return_value = b""
        event = threading.Event()
        stack, _output = self.mocked_streams(pipe)
        began = time.monotonic()
        with stack:
            async with transport.application_stdio_server(event):
                event.set()
                await anyio.sleep(10)  # The transport must cancel this owner scope promptly.
        self.assertLess(time.monotonic()-began, 2)
        self.assertLess(pipe.read_available.call_count, 10)

    async def test_response_callback_waits_for_write_and_flush_completion(self):
        import anyio
        import mcp.types as types
        order = []
        flush_entered, release_flush, callback_done = anyio.Event(), anyio.Event(), anyio.Event()
        class Output:
            async def write(self, encoded):
                order.append("write_completed")
                return len(encoded)
            async def flush(self):
                order.append("flush_started")
                flush_entered.set()
                await release_flush.wait()
                order.append("flush_completed")
        pipe = Mock()
        pipe.read_available.return_value = b""
        stack, _output = self.mocked_streams(pipe)
        reply = types.JSONRPCMessage.model_validate_json('{"jsonrpc":"2.0","id":7,"result":{"ok":true}}')
        received = []
        def flushed(message):
            received.append(message)
            order.append("callback")
            callback_done.set()
        with stack, patch.object(anyio, "wrap_file", return_value=Output()):
            async with transport.application_stdio_server(response_flushed=flushed) as (_incoming, outgoing):
                await outgoing.send(reply)
                with anyio.fail_after(2):
                    await flush_entered.wait()
                self.assertEqual(received, [])
                self.assertEqual(order, ["write_completed", "flush_started"])
                release_flush.set()
                with anyio.fail_after(2):
                    await callback_done.wait()
        self.assertEqual(received, [reply])
        self.assertEqual(order, ["write_completed", "flush_started", "flush_completed", "callback"])

    async def test_write_or_flush_failure_never_calls_response_callback(self):
        import anyio
        import mcp.types as types
        reply = types.JSONRPCMessage.model_validate_json('{"jsonrpc":"2.0","id":8,"result":{}}')
        for failed_phase in ("write", "flush"):
            with self.subTest(failed_phase=failed_phase):
                class Output:
                    async def write(self, encoded):
                        if failed_phase == "write":
                            raise OSError("synthetic_write_failure")
                        return len(encoded)
                    async def flush(self):
                        if failed_phase == "flush":
                            raise OSError("synthetic_flush_failure")
                pipe = Mock()
                pipe.read_available.return_value = b""
                callback = Mock()
                stack, _output = self.mocked_streams(pipe)
                with stack, patch.object(anyio, "wrap_file", return_value=Output()):
                    with self.assertRaises(BaseExceptionGroup):
                        with anyio.fail_after(2):
                            async with transport.application_stdio_server(response_flushed=callback) as (_incoming, outgoing):
                                await outgoing.send(reply)
                                await anyio.sleep_forever()
                callback.assert_not_called()

    async def test_callback_failure_exposes_only_fixed_reason(self):
        import anyio
        import mcp.types as types
        reply = types.JSONRPCMessage.model_validate_json('{"jsonrpc":"2.0","id":9,"result":{}}')
        pipe = Mock()
        pipe.read_available.return_value = b""
        callback = Mock(side_effect=RuntimeError("PRIVATE_CALLBACK_FAILURE"))
        stack, _output = self.mocked_streams(pipe)
        with stack:
            with self.assertRaises(BaseExceptionGroup) as raised:
                with anyio.fail_after(2):
                    async with transport.application_stdio_server(response_flushed=callback) as (_incoming, outgoing):
                        await outgoing.send(reply)
                        await anyio.sleep_forever()
        pending, leaves = [raised.exception], []
        while pending:
            value = pending.pop()
            if isinstance(value, BaseExceptionGroup):
                pending.extend(value.exceptions)
            else:
                leaves.append(value)
        self.assertEqual(len(leaves), 1)
        self.assertIsInstance(leaves[0], transport.ApplicationStdioError)
        self.assertEqual(str(leaves[0]), "application_stdio_response_flushed_callback_failed")
        self.assertTrue(leaves[0].__suppress_context__)
        callback.assert_called_once_with(reply)

    async def test_partial_write_never_calls_response_callback(self):
        import anyio
        import mcp.types as types
        class Output:
            async def write(self, encoded):
                return len(encoded)-1
            async def flush(self):
                pass
        pipe = Mock()
        pipe.read_available.return_value = b""
        callback = Mock()
        stack, _output = self.mocked_streams(pipe)
        reply = types.JSONRPCMessage.model_validate_json('{"jsonrpc":"2.0","id":10,"result":{}}')
        with stack, patch.object(anyio, "wrap_file", return_value=Output()):
            with self.assertRaises(BaseExceptionGroup):
                with anyio.fail_after(2):
                    async with transport.application_stdio_server(response_flushed=callback) as (_incoming, outgoing):
                        await outgoing.send(reply)
                        await anyio.sleep_forever()
        callback.assert_not_called()

    async def test_invalid_and_oversized_input_have_fixed_errors_without_original_values(self):
        import anyio
        cases = ((b'{"PRIVATE-CANARY":[] }\n', "application_stdio_message_invalid", 128),
                 (b"x"*129, "application_stdio_message_capacity", 128))
        for raw, reason, capacity in cases:
            pipe = Mock()
            pipe.read_available.side_effect = [raw, None]
            stack, _output = self.mocked_streams(pipe)
            with self.subTest(reason=reason), stack, patch.object(transport, "MAX_LINE_BYTES", capacity):
                async with transport.application_stdio_server() as (incoming, _outgoing):
                    value = await incoming.receive()
                    self.assertIsInstance(value, ValueError)
                    self.assertEqual(str(value), reason)
                    self.assertNotIn("PRIVATE-CANARY", str(value))
                    with self.assertRaises(anyio.EndOfStream):
                        await incoming.receive()


if __name__ == "__main__":
    unittest.main()
