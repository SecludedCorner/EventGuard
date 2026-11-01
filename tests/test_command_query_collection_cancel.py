"""Injected Ctrl+C exception during a real owned synthetic query process."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from eventguard.processes import spawn, finish

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''import json,sys,threading
from pathlib import Path
from eventguard.collectors.runner import Runner
from eventguard.diagnostics import api
folder=Path(sys.argv[1])
if sys.argv[2]=="decode":
    import eventguard.collectors.runner as runner_module
    def interrupt_decode(_content):
        raise KeyboardInterrupt("SYNTHETIC_PRIVATE")
    runner_module.loads=interrupt_decode
if sys.argv[2]=="creation":
    from eventguard import processes
    def interrupt_creation(_thread_handle):
        raise KeyboardInterrupt("SYNTHETIC_PRIVATE")
    processes.kernel().ResumeThread=interrupt_creation
if sys.argv[2].startswith("signal_"):
    import ctypes as C,os,signal
    from ctypes import wintypes as W
    kernel=C.WinDLL("kernel32.dll",use_last_error=True,winmode=0x800)
    kernel.GetConsoleProcessList.argtypes=[C.POINTER(W.DWORD),W.DWORD]
    kernel.GetConsoleProcessList.restype=W.DWORD
    kernel.GenerateConsoleCtrlEvent.argtypes=[W.DWORD,W.DWORD]
    kernel.GenerateConsoleCtrlEvent.restype=W.BOOL
    kernel.SetConsoleCtrlHandler.argtypes=[C.c_void_p,W.BOOL]
    kernel.SetConsoleCtrlHandler.restype=W.BOOL
    if not kernel.SetConsoleCtrlHandler(None,False): raise SystemExit(3)
    signal.signal(signal.SIGINT,signal.default_int_handler)
    def signal_self():
        import time
        time.sleep(.05)
        ids=(W.DWORD*8)()
        count=kernel.GetConsoleProcessList(ids,len(ids))
        own=0<count<=len(ids) and set(ids[:count])=={os.getpid()}
        sent=bool(kernel.GenerateConsoleCtrlEvent(0,0)) if own else False
        (folder/"console-signal.json").write_text(json.dumps({"owned_console":own,"signals_sent":int(sent)}))
class SyntheticCollector:
    def __init__(self):
        self.runner=Runner()
        self.interrupted=False
        self.signaller=None
    def interrupt(self,update):
        if update["phase"]==sys.argv[2].removeprefix("signal_") and not self.interrupted:
            self.interrupted=True
            if sys.argv[2].startswith("signal_"):
                self.signaller=threading.Thread(target=signal_self)
                self.signaller.start()
                if update["phase"]=="launch":
                    import time
                    time.sleep(.15)  # Keep the launch callback before OS creation.
                return
            raise KeyboardInterrupt("SYNTHETIC_PRIVATE")
    def collect(self,section,cancel=None):
        try:
            value=self.runner.run("fixture only",_argv=[sys.executable,"-B","-c",
                "import sys,time;time.sleep(float(sys.argv[1]));print('{\\\"rows\\\":[]}')",sys.argv[3]],progress=self.interrupt)
            return {"status":value["status"],"rows":[],"coverage":{"process":value["process"]}}
        finally:
            receipt=self.runner.shutdown(grace=2)
            if self.signaller is not None:
                self.signaller.join(timeout=2)
            (folder/"collector-receipt.json").write_text(json.dumps(receipt))
collector=SyntheticCollector()
original=api.DiagnosticAPI
api.DiagnosticAPI=lambda **kwargs: original(collectors=collector)
from eventguard.cli import main
try:
    code=main(["--format","json","query","query_version"],root=folder)
except KeyboardInterrupt as error:
    import traceback
    frames=[{"file":Path(f.filename).name,"function":f.name,"line":f.lineno} for f in traceback.extract_tb(error.__traceback__)]
    (folder/"interrupt-frames.json").write_text(json.dumps(frames))
    raise
raise SystemExit(code)
'''


@unittest.skipUnless(os.name == "nt", "actual Windows owned Job required")
class CommandQueryCollectionCancellationTests(unittest.TestCase):
    def test_creation_interrupt_returns_cancelled_and_preserves_forced_launch_failure(self):
        self.check_interrupt("creation", ".1")

    def test_interrupt_during_output_decode_returns_cancelled_with_original_exit_evidence(self):
        self.check_interrupt("decode", ".1")

    def test_interrupted_owned_query_returns_cancelled_with_exit_evidence(self):
        for phase, seconds in (("waiting", "1.6"), ("completed", ".6")):
            with self.subTest(phase=phase):
                self.check_interrupt(phase, seconds)

    def check_interrupt(self, phase, seconds):
        with tempfile.TemporaryDirectory() as temporary:
            child = spawn([sys.executable, "-B", "-c", PROGRAM, temporary, phase, seconds],
                env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                out, err = child.communicate(timeout=12)
            finally:
                receipt = finish(child, reason="test_teardown", grace=1)
            self.assertTrue(receipt["child_exited"])
            self.assertFalse(receipt["forcibly_terminated"])
            self.assertEqual(receipt["remaining_owned_processes"], 0)
            owned = json.loads((Path(temporary) / "collector-receipt.json").read_text())
            launched = phase.removeprefix("signal_") != "launch"
            self.assertEqual(owned["managed"], launched)
            self.assertTrue(owned["child_exited"])
            self.assertEqual(owned["forcibly_terminated"], phase == "creation")
            if launched:
                self.assertEqual(owned["remaining_owned_processes"], 0)
            else:
                self.assertNotIn("pid", owned)
            frames = Path(temporary) / "interrupt-frames.json"
            self.assertFalse(frames.exists(), frames.read_text() if frames.exists() else "")
            self.assertEqual(child.returncode, 130)
            self.assertFalse(bool(err), "unexpected_stderr_omitted")
            result = json.loads(out)
            self.assertEqual((result["status"], result["error_code"], result["rows"]), ("cancelled", "source_cancelled", []))
            if launched:
                self.assertTrue(result["coverage"]["process"]["child_exited"])
                self.assertEqual(result["coverage"]["process"]["forcibly_terminated"], phase == "creation")
                self.assertEqual(result["coverage"]["process"]["remaining_owned_processes"], 0)
                self.assertEqual(result["coverage"]["process"]["exit_code"], 1460 if phase == "creation" else 0)
            else:
                self.assertNotIn("process", result["coverage"])
            self.assertNotIn("SYNTHETIC_PRIVATE", out.decode("utf-8"))
            expected = {"collector-receipt.json"}
            if phase.startswith("signal_"):
                expected.add("console-signal.json")
                value = json.loads((Path(temporary) / "console-signal.json").read_text())
                self.assertEqual(value, {"owned_console": True, "signals_sent": 1})
            self.assertEqual({p.name for p in Path(temporary).iterdir()}, expected)
            if phase in {"decode", "creation"}:
                self.evidence = dict(scope="real CLI and owned synthetic collector; injected interrupt, no native query/model",
                    phase=phase, cli_process=receipt, collector_process=owned, result=result, model_calls=0)

    def test_native_control_event_while_waiting_has_owned_exit_evidence(self):
        self.check_interrupt("signal_waiting", "1.6")

    def test_launch_interrupt_never_creates_a_collector_process(self):
        for phase in ("launch", "signal_launch"):
            with self.subTest(phase=phase):
                self.check_interrupt(phase, ".6")
