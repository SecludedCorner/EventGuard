"""Application rendezvous fixtures. No HTTP sockets, SDK, OS query or model."""
from contextlib import contextmanager
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request

from eventguard import application_host as host
from eventguard.application_mcp import call_application_tool
from eventguard.runtime import Runtime, atomic_json

INSTANCE = "a" * 32
OTHER_INSTANCE = "b" * 32
TOKEN = "c" * 64  # Public synthetic capability. Not an account credential.
PID = 4242
CREATED = "2026-10-24T00:00:00+00:00"
URL = "http://127.0.0.1:18765"


class ResponseFixture:
    def __init__(self, value, *, code=200, url=URL + "/api/operator", raw=None):
        self.raw = json.dumps(value).encode() if raw is None else raw
        self.status, self.url = code, url
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.raw[:limit]

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url


class ApplicationHostFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runtime = Runtime(self.root)
        self.path = self.runtime.path(host.DESCRIPTOR)
        self.identity = self.enterContext(patch("eventguard.processes.identity", return_value={
            "pid": PID, "created_at": CREATED, "state": "alive"}))

    def descriptor(self, **overrides):
        value = {"kind": "eventguard-application-connection-v1", "state": "ready",
                 "root_scope": host._scope(self.runtime), "instance_id": INSTANCE, "namespace": "test",
                 "pid": PID, "created_at": CREATED, "url": URL, "control_token": TOKEN,
                 "mcp": {"state": "ready", "transport": "sse"}, "model_calls": 0}
        value.update(overrides)
        atomic_json(self.path, value)
        return value

    @contextmanager
    def opener(self, response):
        instance = Mock()
        instance.open.return_value = response
        with patch("eventguard.application_host.build_opener", return_value=instance) as factory:
            yield factory, instance


class ConnectionDescriptorTests(ApplicationHostFixture):
    def test_absence_is_read_only_and_does_not_create_runtime(self):
        self.assertIsNone(host.connection(self.runtime, "test"))
        self.assertFalse((self.root / "data").exists())
        self.identity.assert_not_called()

    def test_valid_descriptor_checks_only_recorded_owner_and_does_not_change_bytes(self):
        expected = self.descriptor()
        before = self.path.read_bytes()
        self.assertEqual(host.connection(Runtime(self.root), "test"), expected)
        self.identity.assert_called_once_with(PID)
        self.assertEqual(self.path.read_bytes(), before)

    def test_scope_shape_host_token_and_state_rejections_have_fixed_errors(self):
        cases = (("kind", "unknown"), ("root_scope", "0" * 64), ("namespace", "live"),
                 ("instance_id", "not-an-instance"), ("instance_id", []), ("pid", True),
                 ("state", "closed"), ("control_token", "bad\n"), ("control_token", []),
                 ("url", "https://127.0.0.1:18765"), ("url", "http://localhost:18765"),
                 ("url", "http://127.0.0.1:0"), ("url", "http://127.0.0.1:65536"),
                 ("url", URL + "/private"), ("url", "http://user@127.0.0.1:18765"))
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.descriptor(**{field: value})
                before = self.path.read_bytes()
                with self.assertRaises(host.ApplicationHostError) as error:
                    host.connection(self.runtime, "test")
                self.assertRegex(str(error.exception), r"^application_connection_[a-z_]+$")
                self.assertNotIn(TOKEN, str(error.exception))
                self.assertEqual(self.path.read_bytes(), before)

    def test_bad_json_scalar_and_oversized_descriptor_do_not_leak_content(self):
        self.path.parent.mkdir(parents=True)
        for raw in (b"{PRIVATE-CANARY", b"[]", b"null", b"PRIVATE-CANARY" * 2000):
            with self.subTest(length=len(raw)):
                self.path.write_bytes(raw)
                with self.assertRaises(host.ApplicationHostError) as error:
                    host.connection(self.runtime, "test")
                self.assertNotIn("PRIVATE-CANARY", str(error.exception))
                self.assertEqual(self.path.read_bytes(), raw)

    def test_exited_reused_or_unverifiable_owner_never_becomes_ready(self):
        self.descriptor()
        for state in ("missing", "exited"):
            self.identity.return_value = {"pid": PID, "created_at": CREATED, "state": state}
            self.assertIsNone(host.connection(self.runtime, "test"))
        self.identity.return_value = {"pid": PID, "created_at": "2026-10-24T00:00:01+00:00", "state": "alive"}
        self.assertIsNone(host.connection(self.runtime, "test"))
        self.identity.return_value = {"pid": PID, "created_at": None, "state": "denied"}
        with self.assertRaises(host.ApplicationHostError):
            host.connection(self.runtime, "test")


class RemoteApplicationTests(ApplicationHostFixture):
    def test_fixed_post_rpc_uses_pinned_instance_and_never_puts_token_in_body(self):
        self.descriptor()
        response = ResponseFixture({"instance_id": INSTANCE, "namespace": "test", "state": "running", "model_calls": 0})
        with self.opener(response) as (factory, opener):
            proxy = host.RemoteApplication(self.root, "test", expected_instance_id=INSTANCE)
            value = proxy.monitor_control("start", operation_id="fixture-operation")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, URL + "/api/operator")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertEqual(json.loads(request.data), {"instance_id": INSTANCE, "name": "start_monitor",
                         "arguments": {"operation_id": "fixture-operation"}})
        self.assertNotIn(TOKEN.encode(), request.data)
        self.assertEqual(value["instance_id"], INSTANCE)
        self.assertNotIn(TOKEN, json.dumps(value))
        self.assertEqual(opener.open.call_count, 1)

    def test_proxy_disables_environment_proxy_and_redirects(self):
        self.descriptor()
        response = ResponseFixture({"instance_id": INSTANCE, "namespace": "test", "model_calls": 0})
        with patch.dict("os.environ", {"HTTP_PROXY": "http://external.invalid:8080", "NO_PROXY": ""}), self.opener(response) as (factory, _):
            proxy = host.RemoteApplication(self.root, "test", expected_instance_id=INSTANCE)
            proxy.status()
        handlers = factory.call_args.args
        self.assertTrue(any(isinstance(handler, ProxyHandler) and handler.proxies == {} for handler in handlers))
        redirect = next(handler for handler in handlers if isinstance(handler, HTTPRedirectHandler))
        request = Request(URL + "/api/operator", data=b"{}", headers={"Authorization": "Bearer " + TOKEN})
        try:
            moved = redirect.redirect_request(request, io.BytesIO(), 302, "redirect", {}, "http://external.invalid/")
        except HTTPError:
            pass
        else:
            self.assertIsNone(moved, "redirect handler must never create a token-bearing external request")

    def test_changed_descriptor_is_rejected_before_mutation_or_rebinding(self):
        self.descriptor()
        with self.opener(ResponseFixture({})) as (_, opener):
            proxy = host.RemoteApplication(self.root, "test", expected_instance_id=INSTANCE)
            self.descriptor(instance_id=OTHER_INSTANCE)
            value = proxy.monitor_control("start", operation_id="fixture-start")
        self.assertEqual(proxy.instance_id, INSTANCE)
        self.assertIn(value["state"], {"unknown", "blocked"})
        self.assertEqual(value["instance_id"], INSTANCE)
        self.assertFalse(value["automatic_retry_allowed"])
        opener.open.assert_not_called()

    def test_constructor_expected_instance_cannot_silently_adopt_a_replacement(self):
        self.descriptor(instance_id=OTHER_INSTANCE)
        with self.assertRaises(host.ApplicationHostError):
            host.RemoteApplication(self.root, "test", expected_instance_id=INSTANCE)

    def test_unknown_http_receipt_is_never_retried_or_reported_as_success(self):
        self.descriptor()
        cases = (ResponseFixture({"instance_id": OTHER_INSTANCE, "namespace": "test"}),
                 ResponseFixture({"instance_id": INSTANCE, "namespace": "live"}),
                 ResponseFixture([], raw=b"{PRIVATE-CANARY"),
                 ResponseFixture({}, raw=b"x" * (1024*1024 + 1)),
                 ResponseFixture({"instance_id": INSTANCE, "namespace": "test"}, code=202),
                 ResponseFixture({"instance_id": INSTANCE, "namespace": "test"}, url="http://external.invalid/"))
        for response in cases:
            with self.subTest(code=response.status, url=response.url), self.opener(response) as (_, opener):
                proxy = host.RemoteApplication(self.root, "test", expected_instance_id=INSTANCE)
                value = proxy.monitor_control("pause", operation_id="fixture-pause")
                self.assertEqual(value["state"], "unknown")
                self.assertTrue(value["operation_may_have_completed"])
                self.assertFalse(value["automatic_retry_allowed"])
                self.assertEqual(value["instance_id"], INSTANCE)
                self.assertNotIn(TOKEN, json.dumps(value))
                self.assertNotIn("PRIVATE-CANARY", json.dumps(value))
                self.assertEqual(opener.open.call_count, 1)

    def test_direct_sdk_dispatch_refuses_scope_or_unknown_keys_before_rpc(self):
        self.descriptor()
        with self.opener(ResponseFixture({})) as (_, opener):
            proxy = host.RemoteApplication(self.root, "test", expected_instance_id=INSTANCE)
            for args in ({"namespace": "live"}, {"root": "elsewhere"}, {"command": "anything"}):
                with self.assertRaisesRegex(ValueError, "^invalid_application_tool_arguments$"):
                    call_application_tool(proxy, "start_monitor", args)
        opener.open.assert_not_called()

    def test_observer_stdio_exit_does_not_create_or_shutdown_someone_elses_app(self):
        self.descriptor()
        server = Mock()
        with patch("eventguard.application.Application", side_effect=AssertionError("observer cannot create an owner")) as create, \
             patch("eventguard.application_mcp.build_application_server", return_value=server) as build:
            code = host.serve_stdio(self.root, fixture="tests/fixtures/normal.json")
        self.assertEqual(code, 0)
        create.assert_not_called()
        target = build.call_args.args[0]
        self.assertIsInstance(target, host.RemoteApplication)
        self.assertEqual(target.instance_id, INSTANCE)
        server.run.assert_called_once_with(transport="stdio")
        self.assertFalse((self.root / "data/application/stdio-exit.json").exists())
        self.assertEqual(host.connection(self.runtime, "test")["state"], "ready")


class ApplicationControlServicesTests(ApplicationHostFixture):
    def application(self):
        return SimpleNamespace(runtime=self.runtime, instance_id=INSTANCE, namespace="test", mcp_enabled=False,
                               web=SimpleNamespace(token=TOKEN, url=URL))

    def test_connection_capability_is_local_only_and_public_receipts_omit_token(self):
        services = host.ApplicationControlServices(self.application())
        try:
            started = services.start()
            self.assertNotIn(TOKEN, json.dumps(started))
            self.assertEqual(host.connection(self.runtime, "test")["instance_id"], INSTANCE)
            stopped = services.close()
            self.assertTrue(stopped["thread_exited"])
            self.assertNotIn(TOKEN, json.dumps(stopped))
            self.assertNotIn("control_token", json.loads(self.path.read_text(encoding="utf-8")))
            self.assertIsNotNone(services.lease.stream)
            # Only the application owner can combine Web/monitor/SDK exit and
            # release the installation lease. close() alone is insufficient.
            services.release(clean=True)
            self.assertIsNone(services.lease.stream)
        finally:
            services.lease.release()

    def test_bad_descriptor_close_is_fixed_unknown_and_keeps_owned_lease(self):
        services = host.ApplicationControlServices(self.application())
        try:
            services.start()
            atomic_json(self.path, ["bad fixture descriptor"])
            value = services.close()
            self.assertTrue(value["thread_exited"])
            self.assertFalse(value["descriptor_saved"])
            services.release(clean=False)
            self.assertIsNotNone(services.lease.stream)
            self.assertNotIn(TOKEN, json.dumps(value))
        finally:
            services.lease.release()

    def test_unknown_server_thread_exit_keeps_lease_and_is_not_closed_success(self):
        services = host.ApplicationControlServices(self.application())
        try:
            services.start()
            services.manager = Mock()
            services.manager.close.return_value = {"thread_exited": False, "state": "shutdown_unconfirmed"}
            value = services.close()
            self.assertFalse(value["thread_exited"])
            self.assertEqual(services.view["state"], "shutdown_unconfirmed")
            self.assertIsNotNone(services.lease.stream)
            self.assertNotIn("control_token", json.loads(self.path.read_text(encoding="utf-8")))
        finally:
            services.lease.release()


class StdioOwnedStartupFailureTests(ApplicationHostFixture):
    def test_sdk_build_failure_still_closes_only_new_owned_application(self):
        parent = self

        class OwnedFixture:
            instance_id = INSTANCE
            namespace = "test"

            def __init__(self):
                self.cancel = threading.Event()
                self.thread = None
                self.actions = []

            def run(self, max_seconds=None, announce=None):
                self.thread = threading.current_thread()
                announce({"state": "ready"})
                self.cancel.wait(3)
                return {"state": "stopped", "model_calls": 0}

            def monitor_control(self, action, source="mcp", operation_id=None):
                self.actions.append((action, source))
                self.cancel.set()
                return {"state": "stop_requested", "model_calls": 0}

        owned = OwnedFixture()
        try:
            with patch.object(host, "connection", return_value=None), \
                 patch("eventguard.application.Application", return_value=owned), \
                 patch("eventguard.application_mcp.build_application_server", side_effect=ImportError("synthetic SDK unavailable")):
                with self.assertRaises((ImportError, host.ApplicationHostError)):
                    host.serve_stdio(self.root, fixture="tests/fixtures/normal.json")
            self.assertEqual(owned.actions, [("shutdown", "system")])
            self.assertIsNotNone(owned.thread)
            self.assertFalse(owned.thread.is_alive())
            receipt = json.loads((self.root / "data/application/stdio-exit.json").read_text(encoding="utf-8"))
            self.assertTrue(receipt["application_thread_exited"])
            self.assertNotIn(TOKEN, json.dumps(receipt))
        finally:
            owned.cancel.set()
            if owned.thread is not None:
                owned.thread.join(5)
                parent.assertFalse(owned.thread.is_alive(), "only this bounded fixture thread must exit")


if __name__ == "__main__":
    unittest.main()
