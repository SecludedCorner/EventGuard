"""Bounded command input; the CLI is the sole reader of fresh stdin."""
import os
import sys
import time


def read_bounded_stdin(stream, limit):
    if os.name != "nt" or stream is not getattr(sys.stdin, "buffer", None):
        return stream.read(limit)
    import _winapi
    import msvcrt
    if _winapi.GetFileType(msvcrt.get_osfhandle(stream.fileno())) != 3:
        return stream.read(limit)  # Regular redirected file, not a waiting pipe.
    from .application_stdio import _InputPipe, READ_BYTES, POLL_SECONDS
    pipe = _InputPipe()
    content = bytearray()
    while len(content) < limit:
        chunk = pipe.read_available(min(limit - len(content), READ_BYTES))
        if chunk is None:
            break
        if chunk:
            content.extend(chunk)
        else:
            time.sleep(POLL_SECONDS)  # Let Python process pending Ctrl+C.
    return bytes(content)
