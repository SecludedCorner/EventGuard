"""Local product flows. Synthetic SQLite and HTTP; no model or host inventory."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import quote

from eventguard.application import Application
from eventguard.cli import main
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.runtime import Runtime
from eventguard.synthetic import make_synthetic
from eventguard.web import LocalWeb

ROOT = Path(__file__).resolve().parents[1]


class ProductFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for relative in ("config/default.json", "config/rules.json", "playbooks/default.json", "tests/fixtures/normal.json"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, path)

    def event(self, event_id=None, severity="high"):
        event = make_synthetic("listener")
        event["severity"] = severity
        if event_id:
            event["event_id"] = event_id
        EventStore(self.root / "data/test").enqueue(event)
        return event


class LocalWebTests(ProductFixture):
    def setUp(self):
        super().setUp()
        self.web = LocalWeb(self.root, "test", port=0,
                            status_provider=lambda: {"monitor_state": "running", "model_calls": 0})
        self.web.start()
        self.addCleanup(self.close_web)

    def close_web(self):
        self.assertTrue(self.web.close()["web_thread_exited"])

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.web.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            raw = response.read()
            return response.status, dict(response.getheaders()), raw
        finally:
            connection.close()

    def test_empty_page_and_reads_do_not_create_data(self):
        for route in ("/", "/app.js", "/app.css", "/api/events", "/api/sources", "/api/rules", "/api/status"):
            with self.subTest(route=route):
                code, headers, body = self.request("GET", route)
                self.assertEqual(code, 200, body)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertFalse((self.root / "data").exists())

    def test_shared_filter_detail_status_and_reopen_without_ack(self):
        one = self.event("evt:local-one")
        self.event("evt:local-two", "warning")
        code, _, body = self.request("GET", "/api/events?severity=high&source=listeners&status=new&limit=1")
        data = json.loads(body)
        self.assertEqual(code, 200)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["events"][0]["event_id"], one["event_id"])
        encoded = quote(one["event_id"], safe="")
        code, _, body = self.request("GET", "/api/events/" + encoded)
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["status"], "new")
        code, _, body = self.request("POST", "/api/events/" + encoded + "/status",
            json.dumps({"status": "handled"}), {"Content-Type": "application/json", "Origin": self.web.url,
                                               "X-EventGuard-CSRF": self.web.token})
        self.assertEqual(code, 200, body)
        self.assertFalse(json.loads(body)["ack_performed"])
        detail = EventCatalog(self.root, "test").detail(one["event_id"])
        self.assertEqual(detail["status"], "handled")
        self.assertEqual(detail["delivery_status"], "pending")
        self.assertEqual(EventStore(self.root / "data/test").stats()["receipt_count"], 0)
        self.evidence = {"scope": "real loopback HTTP + synthetic SQLite; no Windows collection",
                         "handling_saved_after_new_catalog": True, "pending_preserved": True, "model_calls": 0}

    def test_foreign_host_and_cross_origin_writes_are_rejected(self):
        event = self.event()
        code, _, _ = self.request("GET", "/api/events", headers={"Host": "example.invalid"})
        self.assertEqual(code, 403)
        for headers in ({}, {"Origin": "http://evil.invalid", "X-EventGuard-CSRF": self.web.token},
                        {"Origin": self.web.url}, {"Origin": self.web.url, "X-EventGuard-CSRF": "wrong"}):
            with self.subTest(headers=headers):
                code, _, _ = self.request("POST", "/api/events/" + event["event_id"] + "/status",
                                          '{"status":"ignored"}', {"Content-Type": "application/json", **headers})
                self.assertEqual(code, 403)
        self.assertEqual(EventCatalog(self.root, "test").detail(event["event_id"])["status"], "new")

    def test_invalid_filters_paths_and_status_are_fixed_errors(self):
        for path in ("/api/events?severity=INVALID", "/api/events?limit=0", "/api/events?offset=-1",
                     "/api/events?source=listeners&source=tasks", "/api/events?sql=drop", "/api/events/..%2Fconfig"):
            with self.subTest(path=path):
                code, _, body = self.request("GET", path)
                self.assertEqual(code, 400, body)
        code, _, _ = self.request("GET", "/config/default.json")
        self.assertEqual(code, 404)
        event = self.event()
        for body in ('{"status":"ACK"}', '{"status":"read","command":"no"}', '[]'):
            code, _, _ = self.request("POST", "/api/events/" + event["event_id"] + "/status", body,
                {"Content-Type": "application/json", "Origin": self.web.url, "X-EventGuard-CSRF": self.web.token})
            self.assertEqual(code, 400)

    def test_web_sources_expose_denied_unknown_and_reasons_without_query(self):
        from eventguard.runtime import utc_now
        runtime = Runtime(self.root)
        for source, status, reason, hresult in (("defender", "denied", "access_denied", -2147024891),
                                                ("tasks", "unknown", "object_unavailable", -2147024893)):
            runtime.save_observation({"id": source, "status": status, "rows": [], "observed_at": utc_now(),
                "coverage": {"status": status, "errors": [{"stage": "provider" if source == "defender" else "object",
                    "reason_code": reason, "exception_type": "FixtureError", "hresult": hresult, "status": status}]}}, "test")
        with patch("eventguard.collectors.windows.WindowsCollectors.collect", side_effect=AssertionError("page cannot query OS")):
            code, _, raw = self.request("GET", "/api/sources")
        self.assertEqual(code, 200)
        rows = {s["source_id"]: s for s in json.loads(raw)["sources"]}
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows["defender"]["status"], "denied")
        self.assertIn("Windows 安全性", rows["defender"]["suggestion"])
        self.assertEqual(rows["tasks"]["reasons"][0]["hresult_hex"], "0x80070003")
        self.assertIn("工作排程器", rows["tasks"]["suggestion"])

    def test_page_uses_text_nodes_and_no_remote_assets(self):
        _, _, raw = self.request("GET", "/app.js")
        script = raw.decode()
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("eval(", script)
        self.assertNotIn("https://", script)
        self.assertIn("textContent", script)
        _, _, raw = self.request("GET", "/")
        self.assertNotIn("__TOKEN__", raw.decode())


class ProductCliTests(ProductFixture):
    def test_piped_chinese_text_uses_utf8(self):
        from eventguard.processes import spawn, finish
        entry = ("import sys;from pathlib import Path;sys.path.insert(0," + repr(str(ROOT / "src")) + ");"
                 "from eventguard.cli import main;raise SystemExit(main(['rules','validate','--format','text'],"
                 "root=Path(" + repr(str(self.root)) + ")))" )
        child = spawn([sys.executable, "-B", "-c", entry], stdin=subprocess.DEVNULL,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = child.communicate(timeout=10)
        finally:
            receipt = finish(child, "test_teardown", grace=2)
        self.assertEqual(child.returncode, 0, stderr.decode("utf-8",errors="replace"))
        self.assertIn("規則檔",stdout.decode("utf-8"))
        self.assertIn("兩項防護功能關閉",stdout.decode("utf-8"))
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(receipt["remaining_owned_processes"],0)

    def command(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(list(args), root=self.root)
        return code, out.getvalue()

    def test_cli_filter_detail_and_saved_handling(self):
        event = self.event()
        code, raw = self.command("events", "list", "--namespace", "test", "--severity", "high", "--source", "listeners", "--status", "new")
        self.assertEqual(code, 0, raw)
        self.assertEqual(json.loads(raw)["total"], 1)
        code, raw = self.command("events", "set-status", "--namespace", "test", "--event-id", event["event_id"], "--status", "read")
        self.assertEqual(code, 0, raw)
        code, raw = self.command("events", "detail", "--namespace", "test", "--event-id", event["event_id"])
        self.assertEqual(code, 0, raw)
        self.assertEqual(json.loads(raw)["status"], "read")
        code, text = self.command("events", "list", "--namespace", "test", "--format", "text")
        self.assertEqual(code, 0)
        for value in ("已讀", "listeners", "high", event["event_id"]):
            self.assertIn(value, text)

    def test_cli_lists_five_rules_and_reports_broken_file(self):
        code, raw = self.command("rules", "validate")
        self.assertEqual(code, 0, raw)
        self.assertEqual(len(json.loads(raw)["rules"]), 5)
        (self.root / "config/rules.json").write_text("{broken", encoding="utf-8")
        code, raw = self.command("rules", "validate")
        self.assertEqual(code, 2)
        self.assertTrue(json.loads(raw)["error_code"].startswith("rules_"))

    def test_cli_sources_show_seven_without_native_calls(self):
        with patch("eventguard.collectors.windows.WindowsCollectors.collect", side_effect=AssertionError("read-only")):
            code, raw = self.command("sources", "list")
        self.assertEqual(code, 0, raw)
        self.assertEqual(len(json.loads(raw)["sources"]), 7)

    def test_run_dispatches_one_local_application_and_no_models(self):
        with patch("eventguard.application.run", return_value={"state": "stopped", "model_calls": 0}) as run:
            code, raw = self.command("run", "--port", "8877", "--no-notifications")
        self.assertEqual(code, 0, raw)
        run.assert_called_once_with(self.root, port=8877, fixture=None, max_cycles=None, notifications=False, max_seconds=None)


class ApplicationTests(ProductFixture):
    @unittest.skipUnless(os.name == "nt", "Windows local notification API")
    def test_real_windows_synthetic_notification_request_closes_own_icon(self):
        from eventguard.notifications import _WindowsBalloon, NotificationError
        balloon = _WindowsBalloon()
        accepted = False
        try:
            try:
                accepted = balloon({"title": "EventGuard 合成通知測試", "body": "這是本機產品測試。沒有資安處置。",
                                    "severity": "high"})
            except NotificationError as error:
                self.skipTest(str(error))
            self.assertIs(accepted, True)
            balloon.pump()
        finally:
            closed = balloon.close()
            self.assertTrue(closed, "only this test's icon/window must close")
        self.evidence = {"scope": "real Windows Shell_NotifyIconW; fixed synthetic message only",
                         "os_accepted_notification_request": accepted, "own_window_and_icon_closed": closed,
                         "human_visibility_verified": False, "provider_queries": 0, "model_calls": 0}

    def test_port_conflict_starts_no_monitor(self):
        first = LocalWeb(self.root, "test", port=0)
        self.addCleanup(first.close)
        with patch("eventguard.background.start", side_effect=AssertionError("must not launch")) as start:
            with self.assertRaises(OSError):
                Application(self.root, port=first.server.server_port, notifications=False)
        start.assert_not_called()

    def test_stop_and_notification_close_failure_still_clean_only_owned_monitor(self):
        app = Application(self.root, port=0, notifications=False)
        app.notification_service = unittest.mock.Mock()
        app.notification_service.close.side_effect = OSError("fixture close failure")
        with patch("eventguard.background.start", return_value={"state": "started"}), \
             patch.object(app.owner, "close_owned_monitor", return_value={"child_exited": True}) as close:
            def announced(_):
                connection = http.client.HTTPConnection("127.0.0.1", app.web.server.server_port, timeout=5)
                connection.request("GET", "/api/status")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                connection.close()
                app.cancel.set()
            value = app.run(announce=announced)
        self.assertEqual(value["state"], "stopped")
        self.assertTrue(value["web"]["web_thread_exited"])
        close.assert_called_once()

    def test_broken_rule_file_starts_no_child_and_closes_port(self):
        app = Application(self.root, port=0, notifications=False)
        (self.root / "config/rules.json").write_text("bad", encoding="utf-8")
        with patch("eventguard.background.start", side_effect=AssertionError("invalid rules cannot launch")) as start:
            with self.assertRaises(ValueError):
                app.run(max_seconds=1)
        start.assert_not_called()
        self.assertEqual(app.web.server.fileno(), -1)

    @unittest.skipUnless(os.name == "nt", "Windows foreground product and owned monitor host")
    def test_real_foreground_fixture_server_and_owned_host_exit_without_model(self):
        from eventguard.processes import spawn, finish
        # The exact production command runs in its own private Job. Only the
        # fixture source is selected. It exits on its finite application limit.
        entry = ("import sys;from pathlib import Path;sys.path.insert(0," + repr(str(ROOT / "src")) + ");"
                 "from eventguard.cli import main;raise SystemExit(main(['run','--port','0','--fixture',"
                 "'tests/fixtures/normal.json','--max-cycles','1','--max-seconds','3','--no-notifications'],"
                 "root=Path(" + repr(str(self.root)) + ")))" )
        child = spawn([sys.executable, "-B", "-c", entry], stdin=subprocess.DEVNULL,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        receipt = None
        try:
            stdout, stderr = child.communicate(timeout=35)
        finally:
            receipt = finish(child, "test_teardown", grace=5)
        self.assertEqual(child.returncode, 0, stderr.decode(errors="replace"))
        result = json.loads(stdout)
        self.assertEqual(result["state"], "stopped")
        self.assertTrue(result["monitor"]["child_exited"])
        self.assertIn(b"http://127.0.0.1:", stderr)
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.assertEqual(result["model_calls"], 0)
        self.evidence = {"scope": "real foreground CLI + loopback server + Windows owned host; fixture only",
                         "application": result, "guardian_child": receipt, "model_calls": 0,
                         "inventory_executed": False}
