"""Reproducible synthetic unit suite and syntax checks. No machine scan."""
import ast
import contextlib
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"src"))
started=time.monotonic()
output=ROOT/"reports"
output.mkdir(exist_ok=True)
syntax=[]
sources=[p for directory in ("src","scripts","tests") for p in (ROOT/directory).rglob("*.py")]
for path in sources:
    try:
        ast.parse(path.read_text(encoding="utf-8"),filename=str(path.relative_to(ROOT)))
    except SyntaxError as error:
        syntax.append({"file":str(path.relative_to(ROOT)),"line":error.lineno})
stream=io.StringIO()
printed=io.StringIO()
with contextlib.redirect_stdout(printed):
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern="test_*.py")
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(output/"unit-tests.txt").write_text(stream.getvalue()+"\nFixed test progress output:\n"+printed.getvalue(),encoding="utf-8")
summary={"verified_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),"tests_run":result.testsRun,
         "failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
         "python_files":len(sources),"syntax_errors":syntax,"duration_seconds":round(time.monotonic()-started,3),
         "test_data":"synthetic/mocked only","machine_scan_executed":False,"real_agent_woken":False,"model_calls":0}
(output/"verification-summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary))
if syntax or not result.wasSuccessful():
    print(stream.getvalue())
    raise SystemExit(1)
