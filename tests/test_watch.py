"""Bounded watch ownership and cooperative lifecycle; no native scans/models."""
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from eventguard.acceptance_control import read_json
from eventguard import watch


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "reports/watch"

    def test_preflight_and_missing_explicit_live_scope_never_collect(self):
        with patch.object(watch, "Monitor") as monitor:
            result = watch.run(self.directory, root=self.root)
            self.assertEqual(result["model_calls"], 0)
            self.assertFalse(self.directory.exists())
            with self.assertRaisesRegex(ValueError, "explicit_live_scope_required"):
                watch.run(self.directory, root=self.root, execute=True)
            monitor.assert_not_called()
        for seconds, tasks in ((0, 1), (3601, 1), (1, 6), (True, 1)):
            with self.assertRaises(ValueError):
                watch.run(self.directory, root=self.root, max_seconds=seconds, max_tasks=tasks)

    def test_agent_failure_cooperatively_stops_owned_monitor(self):
        monitors = []
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
                monitors.append(self)
            def run(self, max_seconds, on_cycle, deadline_monotonic=None):
                on_cycle({"instance_id": "owned", "coverage": {}, "cycles": 1})
                self.cancel.wait(3)
                return {"state": "stopped", "cycles": 1, "coverage": {"tasks": {"status": "denied"}}}
        with patch.object(watch, "_native", return_value="fixture.exe"), patch.object(watch, "Monitor", FakeMonitor), \
             patch("eventguard.agent_dispatch.run", return_value=1) as dispatch:
            result = watch.run(self.directory, root=self.root, execute=True, allow_live=True, max_seconds=3, max_tasks=2)
        self.assertEqual(result["state"], "delivery_blocked")
        self.assertTrue(monitors[0].cancel.is_set())
        self.assertTrue(result["monitor_exited"])
        self.assertEqual(result["coverage"], {"tasks": "denied"})
        self.assertEqual(dispatch.call_args.kwargs["max_tasks"], 2)
        self.assertTrue(dispatch.call_args.kwargs["allow_live"])

    def test_busy_monitor_never_starts_agent(self):
        class BusyMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
            def run(self, **kwargs):
                return {"status": "busy", "cycles": 0}
        with patch.object(watch, "_native", return_value="fixture.exe"), patch.object(watch, "Monitor", BusyMonitor), \
             patch("eventguard.agent_dispatch.run") as dispatch:
            result = watch.run(self.directory, root=self.root, execute=True, allow_live=True)
        self.assertEqual(result["state"], "monitor_busy")
        dispatch.assert_not_called()

    def test_stop_only_targets_foreground_watch_and_its_agent(self):
        self.directory.mkdir(parents=True)
        watch.write_json(self.directory / "watch.json", {"kind": watch.KIND, "watch_id": "owned"})
        with patch("eventguard.agent_dispatch.stop") as stop:
            result = watch.stop(self.directory)
        stop.assert_not_called()
        self.assertFalse(result["process_signal_sent"])
        self.assertEqual(read_json(self.directory / "stop.request")["watch_id"], "owned")
        self.assertFalse((self.root / "data/stop-request.json").exists())

    def test_stop_before_agent_status_reaches_shared_preflight_cancellation(self):
        entered = threading.Event()
        monitors = []
        results = []
        class FakeMonitor:
            def __init__(self, root):
                self.cancel = threading.Event()
                monitors.append(self)
            def run(self, max_seconds, on_cycle, deadline_monotonic=None):
                on_cycle({"instance_id": "owned", "coverage": {}, "cycles": 1})
                self.cancel.wait(4)
                return {"state": "stopped", "cycles": 1, "coverage": {}}
        def preflight(*args, cancel=None, **kwargs):
            entered.set()
            self.assertTrue(cancel.wait(3), "Watch stop must reach an agent without status yet")
            return 0
        with patch.object(watch, "_native", return_value="fixture.exe"), patch.object(watch, "Monitor", FakeMonitor), \
             patch("eventguard.agent_dispatch.run", side_effect=preflight):
            worker = threading.Thread(target=lambda: results.append(watch.run(
                self.directory, root=self.root, execute=True, allow_live=True, max_seconds=4)))
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse((self.directory / "agent/status.json").exists())
                watch.stop(self.directory)
            finally:
                worker.join(5)
                if worker.is_alive():
                    monitors[0].cancel.set()
                    worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertTrue(results[0]["monitor_exited"])
