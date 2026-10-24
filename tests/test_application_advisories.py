"""Public advisory views share the product app. No network or model."""
import http.client
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from eventguard.application import Application
from eventguard.application_mcp import APPLICATION_TOOLS, call_application_tool
from eventguard.intelligence.store import IntelligenceStore
from eventguard.web import JS, LocalWeb


ROOT = Path(__file__).resolve().parents[1]


class ApplicationAdvisoriesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for relative in ("config/default.json", "config/rules.json", "playbooks/default.json", "tests/fixtures/normal.json"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, path)
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("no child or model")))
        self.enterContext(patch("urllib.request.build_opener", side_effect=AssertionError("no network")))

    def seed(self):
        now = time.time()
        source = {"id": "nvidia-synthetic", "url": "https://example.invalid/public.json", "adapter": "nvidia_csaf",
                  "stale_after_seconds": 3600, "interval_seconds": 60, "tracking_ids": []}
        record = {"ids": ["CVE-2026-10001"], "aliases": [], "title": "SYNTHETIC <img src=x onerror=alert(1)> ACK now",
                  "component": "local-private-component", "ecosystem": "fixture", "affected": [], "fixes": [],
                  "source_url": source["url"], "evidence": [{"path": "C:/private-path-canary"}],
                  "confidence": "high", "synthetic": True}
        with IntelligenceStore(self.root / "data/advisories/intelligence.sqlite3", cooldown_seconds=0) as store:
            store.bind_namespace("test", True)
            store.record_fetch(source, {"status": "success", "records": [record]}, now)
            store.ingest(record, {"status": "unknown", "reason_codes": ["not_inventoried"],
                                 "asset_refs": ["private-inventory-canary"]}, source["id"], now)

    def test_application_status_and_tools_read_same_public_case_without_private_evidence(self):
        self.seed()
        app = Application(self.root, port=0, fixture="tests/fixtures/normal.json", auto_start=False, notifications=False)
        self.addCleanup(app.web.close)
        direct = app.status()
        tool = call_application_tool(app, "status", {})
        self.assertEqual(tool["instance_id"], app.instance_id)
        self.assertEqual(tool["advisories"]["advisories"], direct["advisories"]["advisories"])
        self.assertEqual(tool["advisories"]["limit"], 5)
        self.assertEqual(tool["advisories"]["advisories"][0]["current_assessment"]["status"], "unknown")
        self.assertEqual(tool["monitor_state"], "stopped")
        self.assertIsNone(tool["last_action"])
        for private in ("local-private-component", "C:/private-path-canary", "private-inventory-canary"):
            self.assertNotIn(private, json.dumps(tool))
        self.assertEqual(tool["model_calls"], 0)

    def test_http_view_is_read_only_and_validates_limits(self):
        self.seed()
        web = LocalWeb(self.root, "test", port=0)
        web.start()
        self.addCleanup(lambda: self.assertTrue(web.close()["web_thread_exited"]))
        database = self.root / "data/advisories/intelligence.sqlite3"
        before = database.read_bytes()
        for path, expected in (("/api/advisories?limit=1", 200), ("/api/advisories?limit=0", 400),
                               ("/api/advisories?limit=51", 400), ("/api/advisories?source=bad", 400),
                               ("/api/advisories?limit=1&limit=2", 400)):
            connection = http.client.HTTPConnection("127.0.0.1", web.server.server_port, timeout=5)
            try:
                connection.request("GET", path)
                response = connection.getresponse()
                data = json.loads(response.read())
                self.assertEqual(response.status, expected, data)
                if expected == 200:
                    self.assertEqual(data["namespace"], "test")
                    self.assertEqual(data["advisories"][0]["title"], "SYNTHETIC <img src=x onerror=alert(1)> ACK now")
            finally:
                connection.close()
        self.assertEqual(database.read_bytes(), before)

    def test_reading_absent_advisory_store_does_not_create_it(self):
        app = Application(self.root, port=0, fixture="tests/fixtures/normal.json", auto_start=False, notifications=False)
        self.addCleanup(app.web.close)
        self.assertEqual(app.status()["advisories"]["state"], "not_started")
        self.assertFalse((self.root / "data/advisories").exists())

    def test_advisory_render_uses_text_nodes_and_no_remote_assets(self):
        renderer = JS.split("function advisorySource", 1)[1].split("async function agent", 1)[0]
        self.assertNotIn("innerHTML", renderer)
        self.assertNotIn("location", renderer)
        self.assertNotIn(".src=", renderer)
        self.assertNotIn(".href=", renderer)
        self.assertIn("node('h3',c.title", renderer)
        self.assertIn("/api/advisories?limit=50", renderer)


class ApplicationOperationSourceTests(unittest.TestCase):
    def test_cli_has_truthful_source_and_shutdown_is_a_fixed_tenth_tool(self):
        class App:
            instance_id, namespace = "a" * 32, "test"

            def monitor_control(self, action, source, operation_id=None):
                self.last = action, source, operation_id
                return {"state": "shutdown_requested" if action == "shutdown" else "running", "model_calls": 0}

        app = App()
        call_application_tool(app, "start_monitor", {"operation_id": "cli-start"}, source="cli")
        self.assertEqual(app.last, ("start", "cli", "cli-start"))
        result = call_application_tool(app, "shutdown_application", {"operation_id": "cli-close"}, source="cli")
        self.assertEqual(app.last, ("shutdown", "cli", "cli-close"))
        self.assertEqual(result["state"], "shutdown_requested")
        self.assertEqual(len(APPLICATION_TOOLS), 10)
        self.assertIn("shutdown_application", APPLICATION_TOOLS)
        call_application_tool(app, "shutdown_application", {"operation_id": "mcp-close"})
        self.assertEqual(app.last, ("shutdown", "mcp", "mcp-close"))
        for source in ("gui", "system", None, {"mcp": True}):
            with self.subTest(source=source), self.assertRaises(ValueError):
                call_application_tool(app, "start_monitor", {}, source=source)


if __name__ == "__main__":
    unittest.main()
