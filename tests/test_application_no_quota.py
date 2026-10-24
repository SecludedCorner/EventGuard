"""Application status has no daily model quota. Offline fixtures only.

These tests do not initialize or read a real quota authority, run a model,
start a collector, or prove a real agent was awakened.
"""
import http.client
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from eventguard.application import Application
from eventguard.operations import OperatorAPI
from eventguard.presentation import render
from eventguard.web import JS


ROOT = Path(__file__).resolve().parents[1]


class ApplicationNoQuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default.json", self.root / "config/default.json")
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("no child or model")))
        self.enterContext(patch("eventguard.operations._budget_status", side_effect=AssertionError("legacy quota status")))
        self.enterContext(patch("eventguard.agent_budget.public_status", side_effect=AssertionError("legacy public_status")))
        self.enterContext(patch("eventguard.agent_budget.BudgetAuthority.open_existing",
                                side_effect=AssertionError("legacy authority read")))
        self.enterContext(patch("eventguard.acceptance_process.open_authority",
                                side_effect=AssertionError("legacy open_authority"), create=True))
        self.enterContext(patch("eventguard.agent_dispatch.open_authority",
                                side_effect=AssertionError("legacy dispatch authority"), create=True))

    def assert_no_quota(self, value):
        if isinstance(value, dict):
            for key, item in value.items():
                self.assertNotIn(key, {"budget", "agent_budget", "daily_remaining", "daily_limit"})
                self.assert_no_quota(item)
        elif isinstance(value, list):
            for item in value:
                self.assert_no_quota(item)

    def application(self):
        app = Application(self.root, port=0, notifications=False, auto_start=False, mcp_enabled=False)
        self.addCleanup(app.web.close)
        return app

    @staticmethod
    def get(app, route):
        connection = http.client.HTTPConnection("127.0.0.1", app.web.server.server_port, timeout=5)
        try:
            connection.request("GET", route)
            reply = connection.getresponse()
            return reply.status, json.loads(reply.read())
        finally:
            connection.close()

    def test_operator_status_overview_and_capabilities_never_read_legacy_authority(self):
        api = OperatorAPI(self.root)
        for value in (api.status(), api.overview("test"), api.capabilities()):
            self.assert_no_quota(value)
        self.assertFalse((self.root / "data").exists())

    def test_application_status_does_not_depend_on_or_report_quota(self):
        app = self.application()
        result = app.status()
        self.assert_no_quota(result)
        self.assertEqual(result["namespace"], "live")
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(result["monitor_controls"]["available"])
        self.assertFalse((self.root / "data").exists())

    def test_existing_agent_service_status_has_no_quota_side_effect(self):
        from eventguard.agent_service import status
        result = status(self.root)
        self.assert_no_quota(result)
        self.assertIn("pending_events", result)
        self.assertEqual(result["pending_disposition"], "retained")
        self.assertIsNot(result.get("execution_verified"), True)
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse((self.root / "data").exists())

    def test_advisory_status_does_not_open_legacy_quota(self):
        from eventguard.intelligence.engine import status
        result = status(self.root)
        self.assert_no_quota(result)
        self.assertEqual(result["state"], "not_started")
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse((self.root / "data").exists())

    def test_desktop_saved_legacy_state_does_not_promise_daily_retry(self):
        from eventguard.gui import view_snapshot
        for state in ("waiting", "waiting_budget", "armed", "disabled"):
            with self.subTest(state=state):
                result = view_snapshot({"automatic_agent": {"state": state}})
                text = result["automatic_status"]
                self.assertNotIn("每日", text)
                self.assertNotIn("額度恢復", text)
                self.assertIn("明確授權", text)

    def test_web_status_and_existing_agent_route_do_not_read_quota(self):
        app = self.application()
        app.web.start()
        for route in ("/api/status", "/api/agent"):
            with self.subTest(route=route):
                code, result = self.get(app, route)
                self.assertEqual(code, 200)
                self.assert_no_quota(result)
                self.assertEqual(result["model_calls"], 0)
        self.assertFalse((self.root / "data").exists())

    def test_normal_text_and_web_rendering_omit_daily_quota_claims(self):
        legacy = {"state": "waiting", "host_liveness": "not_recorded", "pending_events": 3,
                  "last_progress": "waiting_for_event", "reason": "approval_required",
                  "budget": {"remaining": 5, "usage_known": True},
                  "agent_budget": {"state": "ready"}, "daily_remaining": 5}
        for command in ("agent", "advisories", "status"):
            text = render(legacy, command)
            self.assertNotIn("每日", text)
            self.assertNotIn("預算", text)
        agent = render(legacy, "agent")
        for expected in ("待收事件：3", "waiting_for_event", "approval_required"):
            self.assertIn(expected, agent)
        self.assertNotIn("每日剩餘", JS)
        self.assertNotIn("d.budget", JS)
        self.assertNotIn("d.agent_budget", JS)
        self.assertIn("d.last_progress", JS)


if __name__ == "__main__":
    unittest.main()
