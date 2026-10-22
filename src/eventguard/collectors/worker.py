"""Native API calls run in a short-lived owned job, never in the monitor thread."""
from pathlib import Path
import sys

from .contract import SECTION_IDS
from .runner import Runner
from .progress import invoke_with_progress


class NativeWorker:
    name = "native"

    def __init__(self, timeout=15, evidence_sink=None, runner=None, entry=None):
        self.timeout = timeout
        self.runner = runner or Runner(evidence_sink=evidence_sink)
        self.entry = Path(entry) if entry else Path(__file__).resolve().parents[3] / "scripts/eventguard_collect.py"

    def collect(self, section_id, cancel=None, progress=None):
        if section_id not in SECTION_IDS:
            raise ValueError("unsupported_section")
        raw = invoke_with_progress(self.runner.run, "owned_native_worker", timeout=self.timeout, cancel=cancel,
                              progress=progress, source_id=section_id,
                              _argv=[sys.executable, "-B", str(self.entry), "--section", section_id, "--timeout", str(self.timeout)])
        data = raw.get("data") if raw["status"] == "ok" else {"status": raw["status"], "rows": [], "errors": raw["errors"]}
        data["process"] = raw.get("process", {})
        return data
