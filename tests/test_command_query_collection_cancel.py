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
PROGRAM = '''import json,sys
from pathlib import Path
from eventguard.collectors.runner import Runner
from eventguard.diagnostics import api
folder=Path(sys.argv[1])
class SyntheticCollector:
    def __init__(self):
        self.runner=Runner()
        self.interrupted=False
    def interrupt(self,update):
        if update["phase"]==sys.argv[2] and not self.interrupted and self.runner.last_process.get("pid"):
            self.interrupted=True
            raise KeyboardInterrupt("SYNTHETIC_PRIVATE")
    def collect(self,section,cancel=None):
        try:
            value=self.runner.run("fixture only",_argv=[sys.executable,"-B","-c",
                "import sys,time;time.sleep(float(sys.argv[1]));print('{\\\"rows\\\":[]}')",sys.argv[3]],progress=self.interrupt)
            return {"status":value["status"],"rows":[],"coverage":{"process":value["process"]}}
        finally:
            receipt=self.runner.shutdown(grace=2)
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


class CommandQueryCollectionCancellationTests(unittest.TestCase):
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
            self.assertTrue(owned["managed"])
            self.assertTrue(owned["child_exited"])
            self.assertFalse(owned["forcibly_terminated"])
            self.assertEqual(owned["remaining_owned_processes"], 0)
            frames = Path(temporary) / "interrupt-frames.json"
            self.assertFalse(frames.exists(), frames.read_text() if frames.exists() else "")
            self.assertEqual(child.returncode, 130)
            self.assertFalse(bool(err), "unexpected_stderr_omitted")
            result = json.loads(out)
            self.assertEqual((result["status"], result["error_code"], result["rows"]), ("cancelled", "source_cancelled", []))
            self.assertTrue(result["coverage"]["process"]["child_exited"])
            self.assertFalse(result["coverage"]["process"]["forcibly_terminated"])
            self.assertEqual(result["coverage"]["process"]["remaining_owned_processes"], 0)
            self.assertNotIn("SYNTHETIC_PRIVATE", out.decode("utf-8"))
            self.assertEqual({p.name for p in Path(temporary).iterdir()}, {"collector-receipt.json"})
