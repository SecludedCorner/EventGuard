"""Actual Ctrl+C on an owned private console, never an external console."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from eventguard.processes import spawn, finish

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''import ctypes as C,json,os,signal,sys,threading,time
from pathlib import Path
from ctypes import wintypes as W
folder=Path(sys.argv[1])
api=C.WinDLL("kernel32.dll",use_last_error=True,winmode=0x800)
api.GetConsoleProcessList.argtypes=[C.POINTER(W.DWORD),W.DWORD]
api.GetConsoleProcessList.restype=W.DWORD
api.GenerateConsoleCtrlEvent.argtypes=[W.DWORD,W.DWORD]
api.GenerateConsoleCtrlEvent.restype=W.BOOL
api.SetConsoleCtrlHandler.argtypes=[C.c_void_p,W.BOOL]
api.SetConsoleCtrlHandler.restype=W.BOOL
if not api.SetConsoleCtrlHandler(None,False): raise SystemExit(3)
signal.signal(signal.SIGINT,signal.default_int_handler)
def cancel_self():
    time.sleep(.2)
    ids=(W.DWORD*8)()
    count=api.GetConsoleProcessList(ids,len(ids))
    own=0<count<=len(ids) and set(ids[:count])=={os.getpid()}
    sent=bool(api.GenerateConsoleCtrlEvent(0,0)) if own else False
    (folder/"signal.json").write_text(json.dumps({"owned_console":own,"signal_sent":sent}))
original=sys.stdin
class MarkedInput:
    @property
    def buffer(self): return self
    def fileno(self): return original.fileno()
    def isatty(self):
        (folder/"ready").touch()
        threading.Thread(target=cancel_self).start()
        return False
    def read(self,limit): return original.buffer.read(limit)
sys.stdin=MarkedInput()
from eventguard.diagnostics.api import DiagnosticAPI
def forbidden(*args,**kwargs): raise AssertionError("query must not dispatch")
DiagnosticAPI.query=forbidden
from eventguard.cli import main
raise SystemExit(main(["--format","json","query","health","--args","-"],root=folder/"runtime"))
'''


@unittest.skipUnless(os.name == "nt", "owned Windows console required")
class CommandQueryConsoleCancellationTests(unittest.TestCase):
    def test_real_control_event_cancels_before_producer_eof(self):
        for content in (b"", b'{"request_id":'):
            with self.subTest(partial=bool(content)), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                child = spawn([sys.executable, "-B", "-c", PROGRAM, temporary],
                    env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                exited_before_eof = False
                try:
                    child.stdin.write(content)
                    child.stdin.flush()
                    until = time.monotonic() + 5
                    while not (folder / "ready").exists() and child.poll() is None and time.monotonic() < until:
                        time.sleep(.02)
                    try:
                        child.wait(timeout=2)
                        exited_before_eof = True
                    except subprocess.TimeoutExpired:
                        pass
                finally:
                    child.stdin.close()  # Cooperative release even on regression.
                    child.stdin = None
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
                    receipt = finish(child, reason="test_teardown", grace=1)
                out, err = child.communicate()
                self.assertFalse(receipt["forcibly_terminated"])
                self.assertTrue(receipt["child_exited"])
                self.assertEqual(receipt["remaining_owned_processes"], 0)
                self.assertEqual(json.loads((folder / "signal.json").read_text()), {"owned_console": True, "signal_sent": True})
                self.assertFalse(bool(err), "unexpected_stderr_omitted")
                self.assertEqual(child.returncode, 130)
                result = json.loads(out)
                self.assertEqual((result["status"], result["error_code"]), ("cancelled", "query_input_cancelled"))
                self.assertFalse(result["system_query_executed"])
                self.assertEqual(result["model_calls"], 0)
                self.assertFalse((folder / "runtime").exists())
                self.assertTrue(exited_before_eof, "cancellation_waited_for_producer_eof")
