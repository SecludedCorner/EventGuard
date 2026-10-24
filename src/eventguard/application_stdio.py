"""Optional SDK stdio with cooperative Windows input shutdown.

Only this process's stdin pipe is observed. No stdin worker, handle mutation,
process signal, reader cancellation API or new service is used. Other platforms
retain the SDK fallback; that is not a claim of Linux monitoring support.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import ctypes as C
import os
import sys

MAX_LINE_BYTES = 2*1024*1024
MAX_OUTPUT_BYTES = 4*1024*1024
READ_BYTES = 65536
POLL_SECONDS = .05
_EOF_ERRORS = frozenset({109, 232, 233})  # Broken/closing/disconnected pipe.


class ApplicationStdioError(RuntimeError):
    """Fixed transport reason only; no input bytes, paths or raw OS errors."""


class _InputPipe:
    def __init__(self):
        import msvcrt
        try:
            self.fd = sys.stdin.fileno()
            if self.fd != 0:
                raise ValueError()
            self.handle = msvcrt.get_osfhandle(self.fd)
            if self.handle in {-1, 0}:
                raise ValueError()
            self.api = C.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
            self.api.GetFileType.restype = C.c_uint32
            self.api.GetFileType.argtypes = [C.c_void_p]
            self.api.PeekNamedPipe.restype = C.c_int
            self.api.PeekNamedPipe.argtypes = [C.c_void_p, C.c_void_p, C.c_uint32,
                C.POINTER(C.c_uint32), C.POINTER(C.c_uint32), C.POINTER(C.c_uint32)]
            if self.api.GetFileType(self.handle) != 3:  # FILE_TYPE_PIPE only.
                raise ValueError()
        except (OSError, ValueError, AttributeError, TypeError):
            raise ApplicationStdioError("application_stdio_own_stdin_pipe_required") from None

    def read_available(self):
        """None means real EOF; b'' means an open pipe currently has no bytes."""
        available = C.c_uint32()
        if not self.api.PeekNamedPipe(self.handle, None, 0, None, C.byref(available), None):
            if C.get_last_error() in _EOF_ERRORS:
                return None
            raise ApplicationStdioError("application_stdio_stdin_unavailable")
        if available.value == 0:
            return b""
        try:
            # This is the sole stdin reader. Positive Peek availability bounds
            # the synchronous read; no worker can be stranded in readline().
            chunk = os.read(self.fd, min(available.value, READ_BYTES))
            return chunk if chunk else None
        except OSError as error:
            if getattr(error, "winerror", None) in _EOF_ERRORS:
                return None
            raise ApplicationStdioError("application_stdio_stdin_unavailable") from None


def _output_buffer():
    try:
        return sys.stdout.buffer
    except AttributeError:
        raise ApplicationStdioError("application_stdio_stdout_unavailable") from None


@asynccontextmanager
async def application_stdio_server(stop_event=None):
    """SDK 1.6 JSONRPCMessage streams; optional Event ends an owned GUI scope."""
    if stop_event is not None and not callable(getattr(stop_event, "is_set", None)):
        raise ValueError("invalid_application_stdio_stop_event")
    if os.name != "nt":
        from mcp.server.stdio import stdio_server
        async with stdio_server() as streams:
            yield streams
        return

    import anyio
    import anyio.lowlevel
    import mcp.types as types

    pipe = _InputPipe()
    # Reuse the process-owned binary buffer. A temporary TextIOWrapper would
    # own/close that buffer; this adapter never closes standard process handles.
    stdout = anyio.wrap_file(_output_buffer())
    input_writer, incoming = anyio.create_memory_object_stream(0)
    outgoing, output_reader = anyio.create_memory_object_stream(0)

    def stopped():
        return stop_event is not None and stop_event.is_set()

    async def deliver(raw):
        if len(raw) > MAX_LINE_BYTES:
            await input_writer.send(ValueError("application_stdio_message_capacity"))
            return False
        try:
            message = types.JSONRPCMessage.model_validate_json(raw)
        except Exception:
            # Pydantic's original exception can include untrusted input values.
            # The SDK accepts Exception items; expose only this fixed code.
            message = ValueError("application_stdio_message_invalid")
        await input_writer.send(message)
        return True

    async def stdin_reader():
        pending = bytearray()
        try:
            async with input_writer:
                while not stopped():
                    chunk = pipe.read_available()
                    if chunk is None:
                        if pending:
                            await deliver(bytes(pending))
                        return
                    if not chunk:
                        await anyio.sleep(POLL_SECONDS)
                        continue
                    pending.extend(chunk)
                    while (end := pending.find(b"\n")) != -1:
                        if stopped():
                            return
                        line = bytes(pending[:end])
                        del pending[:end+1]
                        if not await deliver(line):
                            return
                    if len(pending) > MAX_LINE_BYTES:
                        await input_writer.send(ValueError("application_stdio_message_capacity"))
                        return
        except (anyio.ClosedResourceError, anyio.BrokenResourceError):
            await anyio.lowlevel.checkpoint()

    async def stdout_writer():
        try:
            async with output_reader:
                async for message in output_reader:
                    encoded = message.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8") + b"\n"
                    if len(encoded) > MAX_OUTPUT_BYTES:
                        raise ApplicationStdioError("application_stdio_output_capacity")
                    await stdout.write(encoded)
                    await stdout.flush()
        except (anyio.ClosedResourceError, anyio.BrokenResourceError, BrokenPipeError):
            await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(stdin_reader)
        tasks.start_soon(stdout_writer)
        if stop_event is not None:
            async def observe_owner_exit():
                while not stopped():
                    await anyio.sleep(POLL_SECONDS)
                tasks.cancel_scope.cancel()
            tasks.start_soon(observe_owner_exit)
        try:
            yield incoming, outgoing
        finally:
            tasks.cancel_scope.cancel()
