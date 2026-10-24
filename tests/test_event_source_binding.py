"""Application event scope bound to an explicit synthetic source. Offline only.

No collector, notification, model or agent delivery is started. The bound
source is a temporary EventStore created by the test.
"""
from contextlib import redirect_stdout
import http.client
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from eventguard import agent_service
from eventguard.application import Application
from eventguard.application_mcp import call_application_tool
from eventguard.cli import main
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = str(ROOT / "tests/fixtures/normal.json")


class EventSourceBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default.json", self.root / "config/default.json")
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("no child, collector or model")))
        self.source = self.root / "reports/acceptance-fixture/source"
        self.event = make_synthetic("listener")
        EventStore(self.source).enqueue(self.event)
        self.default_event = make_synthetic("coverage")
        EventStore(self.root / "data/test").enqueue(self.default_event)

    def application(self, **options):
        values = {"port": 0, "fixture": FIXTURE, "auto_start": False, "notifications": False,
                  "mcp_enabled": False, "event_source": self.source}
        values.update(options)
        app = Application(self.root, **values)
        self.addCleanup(app.web.close)
        return app

    @staticmethod
    def get(app, route):
        connection = http.client.HTTPConnection("127.0.0.1", app.web.server.server_port, timeout=5)
        try:
            connection.request("GET", route)
            reply = connection.getresponse()
            return reply.status, reply.read()
        finally:
            connection.close()

    @staticmethod
    def ids(listing):
        return [item["event_id"] for item in listing["events"]]

    def test_catalog_reads_only_the_bound_test_source(self):
        bound = EventCatalog(self.root, "test", directory=self.source)
        self.assertEqual(self.ids(bound.list()), [self.event["event_id"]])
        self.assertEqual(self.ids(EventCatalog(self.root, "test").list()), [self.default_event["event_id"]])
        for namespace, directory, reason in (
                ("live", self.source, "event_source_requires_test_namespace"),
                ("test", self.root.parent / "outside", "event_source_outside_root"),
                ("test", self.root, "event_source_scope_refused"),
                ("test", self.root / "data/live", "event_source_scope_refused")):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                EventCatalog(self.root, namespace, directory=directory)

    def test_application_list_detail_and_status_share_the_bound_source(self):
        app = self.application()
        self.assertEqual(self.ids(app.list_events()), [self.event["event_id"]])
        self.assertEqual(app.event_detail(self.event["event_id"])["event_id"], self.event["event_id"])
        with self.assertRaises(Exception):
            app.event_detail(self.default_event["event_id"])
        scope = {"namespace": "test", "binding": "custom", "path": "reports/acceptance-fixture/source",
                 "collection": "disabled_for_bound_source"}
        self.assertEqual(app.status()["event_scope"], scope)
        self.assertEqual(app.capabilities()["event_scope"], scope)
        self.assertFalse(app.status()["monitor_controls"]["can_start"])
        for action in ("start", "resume"):
            self.assertEqual(app._monitor_action(action),
                             {"state": "blocked", "reason": "monitor_outside_bound_event_source"})

    def test_set_status_writes_only_the_bound_source(self):
        app = self.application()
        default_before = (self.root / "data/test/eventguard.sqlite3").read_bytes()
        result = app.set_event_status(self.event["event_id"], "handled", source="gui")
        self.assertEqual(result["state"], "event_status_updated")
        bound = EventCatalog(self.root, "test", directory=self.source)
        self.assertEqual(bound.detail(self.event["event_id"])["status"], "handled")
        self.assertEqual((self.root / "data/test/eventguard.sqlite3").read_bytes(), default_before)
        self.assertEqual(EventStore(self.source).get_event(self.event["event_id"])["delivery_status"], "pending",
                         "Handling state is not an ACK")

    def test_mcp_tools_and_web_page_use_the_same_bound_source(self):
        app = self.application()
        listed = json.dumps(call_application_tool(app, "list_events", {}, source="mcp"))
        inspected = json.dumps(call_application_tool(app, "inspect_event", {"event_id": self.event["event_id"]}, source="mcp"))
        self.assertIn(self.event["event_id"], listed)
        self.assertNotIn(self.default_event["event_id"], listed)
        self.assertIn(self.event["event_id"], inspected)
        app.web.start()
        status, body = self.get(app, "/api/events")
        self.assertEqual(status, 200)
        self.assertEqual(self.ids(json.loads(body)), [self.event["event_id"]])
        status, body = self.get(app, "/api/events/" + self.event["event_id"])
        self.assertEqual((status, json.loads(body)["event_id"]), (200, self.event["event_id"]))
        status, body = self.get(app, "/")
        self.assertIn("reports/acceptance-fixture/source", body.decode("utf-8"))
        status, body = self.get(app, "/api/events/" + self.event["event_id"] + "/delivery")
        self.assertEqual(json.loads(body)["reason"], "delivery_state_not_bound_to_event_source")
        status, body = self.get(app, "/api/status")
        self.assertEqual(json.loads(body)["event_scope"]["binding"], "custom")

    def test_agent_status_reports_whether_its_queue_matches_the_event_list(self):
        def control(source):
            agent_service._write(self.root, "control.json", {
                "kind": agent_service.KIND, "run_id": "a" * 32, "job_name": "Global\\EventGuard-" + "b" * 32,
                "enabled": False, "paused": False, "allow_live": False, "updated_at": agent_service._stamp(),
                "source_dir": str(source), "state_dir": str(self.root / "reports/acceptance-fixture/inbox"),
                "codex_executable": str(self.root / "fixture-never-run.exe")})
        control(self.source)
        self.assertIs(self.application().status()["agent_service"]["event_source_matches_application"], True)
        self.assertIs(self.application(event_source=None).status()["agent_service"]["event_source_matches_application"], False)
        control(self.root / "data/test")
        self.assertIs(self.application(event_source=None).status()["agent_service"]["event_source_matches_application"], True)

    def test_invalid_bindings_are_refused_before_any_listener(self):
        for options, reason in (({"fixture": None}, "event_source_requires_idle_test_without_notifications"),
                                ({"auto_start": True}, "event_source_requires_idle_test_without_notifications"),
                                ({"notifications": True}, "event_source_requires_idle_test_without_notifications"),
                                ({"event_source": self.root / "reports/missing"}, "existing_event_source_required")):
            values = {"port": 0, "fixture": FIXTURE, "auto_start": False, "notifications": False,
                      "mcp_enabled": False, "event_source": self.source, **options}
            with self.subTest(reason=reason, options=list(options)), self.assertRaisesRegex(ValueError, reason):
                Application(self.root, **values)
        self.assertFalse((self.root / "reports/missing").exists())

    def test_default_scope_is_unchanged(self):
        app = self.application(event_source=None)
        self.assertEqual(self.ids(app.list_events()), [self.default_event["event_id"]])
        self.assertEqual(app.status()["event_scope"], {"namespace": "test", "binding": "default",
                                                       "path": "data/test", "collection": "same_scope"})

    def test_cli_event_commands_accept_the_same_bound_source(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["events", "list", "--namespace", "test", "--event-source", str(self.source),
                                   "--format", "json"], root=self.root), 0)
        self.assertEqual(self.ids(json.loads(output.getvalue())), [self.event["event_id"]])
        with redirect_stdout(io.StringIO()):
            self.assertNotEqual(main(["events", "list", "--namespace", "live", "--event-source", str(self.source),
                                      "--format", "json"], root=self.root), 0)


if __name__ == "__main__":
    unittest.main()
