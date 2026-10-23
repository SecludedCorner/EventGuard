"""Operator-owned monitor contracts and Windows SDK fixture Jobs; no live scan/model."""
import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

from eventguard import background, processes
from eventguard.agent_access import set_enabled
from eventguard.operations import OperatorAPI
from eventguard.runtime import Runtime, atomic_json

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts/eventguard_inbox_mcp.py"
CREATED = "2026-10-23T00:00:00.000000+00:00"
SCOPE = {"kind": "eventguard-background-owned-launch-v1", "run_id": "a" * 32,
         "control_generation": "b" * 32, "job_name": "Global\\EventGuard-" + "c" * 32,
         "namespace": "live", "pid": 4242, "created_at": CREATED}
EXIT = {"managed": True, "child_exited": True, "exit_code": 0,
        "remaining_owned_processes": 0, "forcibly_terminated": False, "reason": "natural_exit"}


class FixtureRoot:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for relative in ("config/default.json", "playbooks/default.json", "tests/fixtures/normal.json"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, path)

    def adapter(self):
        try:
            import mcp  # noqa: F401
        except ImportError:
            self.skipTest("optional installed MCP SDK unavailable; no installation")
        spec = importlib.util.spec_from_file_location("operator_owned_monitor_tests", ENTRY)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class OperatorOwnerContracts(FixtureRoot, unittest.TestCase):
    def owned_api(self, *, job_name=None):
        api = OperatorAPI(self.root, background_lifetime_owner="application")
        child = type("FixtureOwnedChild", (), {"_eventguard_background_scope": dict(SCOPE),
                     "pid": SCOPE["pid"], "created_at": CREATED,
                     "job": SimpleNamespace(name=job_name or SCOPE["job_name"])})()

        def started(root, **kwargs):
            self.assertEqual(Path(root), self.root)
            self.assertEqual(kwargs["lifetime_owner"], "application")
            kwargs["child_owner"](child)
            return {"state": "started", "namespace": "live", "model_calls": 0}

        with patch.object(background, "start", side_effect=started):
            self.assertEqual(api.background_start()["state"], "started")
        return api, child

    def test_default_independent_contract_is_unchanged(self):
        api = OperatorAPI(self.root)
        with patch.object(background, "start", return_value={"state": "fixture"}) as start:
            self.assertEqual(api.background_start(), {"state": "fixture"})
        start.assert_called_once_with(self.root)
        with patch.object(background, "stop") as stop, patch.object(processes, "finish") as finish:
            api.close_owned_monitor()
        stop.assert_not_called()
        finish.assert_not_called()

    def test_invalid_lifetime_is_rejected_without_creating_state(self):
        for owner in (None, True, "host_os_exit", "application "):
            with self.subTest(owner=owner), self.assertRaises(ValueError):
                OperatorAPI(self.root, background_lifetime_owner=owner)
        self.assertFalse((self.root / "data").exists())

    def test_capabilities_explain_application_lifetime_without_claiming_reboot(self):
        value = OperatorAPI(self.root, background_lifetime_owner="application").capabilities()
        self.assertEqual(value["background"]["start_lifetime_owner"], "application")
        self.assertEqual(value["background"]["lifetime_scope"], "owning_application_process")
        self.assertTrue(value["background"]["lifetime_limited"])
        self.assertTrue(value["background"]["owner_exit_stops_monitor"])
        self.assertTrue(value["background"]["scheduler_installation_requires_separate_approval"])
        self.assertEqual(value["model_calls"], 0)

    def test_application_close_uses_copied_exact_scope_and_only_owned_child(self):
        api, child = self.owned_api()
        child._eventguard_background_scope.update(run_id="d" * 32, control_generation="e" * 32)
        with patch.object(background, "stop", return_value={"state": "stopped"}) as stop, \
                patch.object(processes, "finish", return_value=dict(EXIT)) as finish:
            api.close_owned_monitor(grace_seconds=1)
            api.close_owned_monitor(grace_seconds=1)
        stop.assert_called_once_with(self.root, grace_seconds=1, expected_namespace="live",
                                    expected_run_id=SCOPE["run_id"],
                                    expected_control_generation=SCOPE["control_generation"],
                                    expected_job_name=SCOPE["job_name"])
        self.assertEqual(finish.call_count, 1)
        self.assertIs(finish.call_args.args[0], child)

    def test_already_running_monitor_without_callback_is_not_adopted(self):
        api = OperatorAPI(self.root, background_lifetime_owner="application")
        with patch.object(background, "start", return_value={"state": "running", "reason": "background_already_running"}):
            api.background_start()
        with patch.object(background, "stop") as stop, patch.object(processes, "finish") as finish:
            api.close_owned_monitor()
        stop.assert_not_called()
        finish.assert_not_called()

    def test_application_start_never_uses_gui_automatic_agent_resume(self):
        from eventguard.desktop import DesktopController
        from eventguard import agent_dispatch
        with patch.object(DesktopController, "_resume_automatic_agent", side_effect=AssertionError("model resume forbidden")) as resume, \
                patch.object(agent_dispatch, "run", side_effect=AssertionError("model dispatch forbidden")) as dispatch:
            api, _ = self.owned_api()
            with patch.object(background, "stop", return_value={"state": "stopped"}), \
                    patch.object(processes, "finish", return_value=dict(EXIT)):
                api.close_owned_monitor(grace_seconds=0)
        resume.assert_not_called()
        dispatch.assert_not_called()

    def test_replacement_generation_does_not_prevent_releasing_only_own_job(self):
        api, child = self.owned_api()
        with patch.object(background, "stop", return_value={"state": "busy", "reason": "background_owner_changed"}) as stop, \
                patch.object(processes, "finish", return_value=dict(EXIT)) as finish:
            api.close_owned_monitor(grace_seconds=0)
        self.assertEqual(stop.call_args.kwargs["expected_run_id"], SCOPE["run_id"])
        self.assertIs(finish.call_args.args[0], child)
        self.assertNotIn("stop_persistent", repr(finish.call_args))

    def test_close_fences_future_start_without_reenabling_control(self):
        api, _ = self.owned_api()
        with patch.object(background, "stop", return_value={"state": "stopped"}), \
                patch.object(processes, "finish", return_value=dict(EXIT)):
            api.close_owned_monitor(grace_seconds=0)
        with patch.object(background, "start") as start:
            result = api.background_start()
        self.assertEqual((result["state"], result["reason"]), ("blocked", "operator_monitor_owner_closed"))
        start.assert_not_called()

    def test_stop_error_still_releases_own_child_and_omits_raw_error(self):
        api, child = self.owned_api()
        with patch.object(background, "stop", side_effect=OSError("PRIVATE fixture error")), \
                patch.object(processes, "finish", return_value=dict(EXIT)) as finish:
            result = api.close_owned_monitor(grace_seconds=0)
        self.assertIs(finish.call_args.args[0], child)
        self.assertEqual(result["state"], "closed")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(result["owned_monitor_results"][0]["stop"]["reason"], "operator_owned_stop_unconfirmed")

    def test_receipt_write_failure_preserves_exit_but_marks_evidence_incomplete(self):
        api, _ = self.owned_api()
        with patch.object(background, "stop", return_value={"state": "stopped"}), \
                patch.object(processes, "finish", return_value=dict(EXIT)), \
                patch("eventguard.operations.atomic_json", side_effect=OSError("PRIVATE receipt path")):
            result = api.close_owned_monitor(grace_seconds=0)
        self.assertTrue(result["child_exited"])
        self.assertFalse(result["evidence_saved"])
        self.assertTrue(result["evidence_write_failed"])
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertFalse((self.root / "data/background/operator-stop-receipt.json").exists())

    def test_mismatched_scope_job_never_changes_shared_control(self):
        api, child = self.owned_api(job_name="Global\\EventGuard-" + "d" * 32)
        with patch.object(background, "stop") as stop, \
                patch.object(processes, "finish", return_value=dict(EXIT)) as finish:
            result = api.close_owned_monitor(grace_seconds=0)
        stop.assert_not_called()
        self.assertIs(finish.call_args.args[0], child)
        self.assertIsNone(result["owned_monitor_results"][0]["scope"])
        self.assertTrue(result["child_exited"])

    def test_forced_stop_or_forced_child_finish_remains_visible_in_aggregate_receipt(self):
        for stop_forced, finish_forced in ((True, False), (False, True)):
            with self.subTest(stop_forced=stop_forced, finish_forced=finish_forced):
                api, _ = self.owned_api()
                with patch.object(background, "stop", return_value={"state": "stopped",
                                  "process": dict(EXIT, forcibly_terminated=stop_forced)}), \
                        patch.object(processes, "finish", return_value=dict(EXIT, forcibly_terminated=finish_forced)):
                    result = api.close_owned_monitor(grace_seconds=0)
                self.assertTrue(result["forcibly_terminated"])
                saved = json.loads((self.root / "data/background/operator-stop-receipt.json").read_text(encoding="utf-8"))
                self.assertTrue(saved["forcibly_terminated"])

    def test_main_keyboard_interrupt_returns_error_when_owned_cleanup_is_unconfirmed(self):
        module = self.adapter()
        server = SimpleNamespace(run=Mock(side_effect=KeyboardInterrupt),
                                 shutdown_owned_monitor=Mock(return_value={"state": "shutdown_unconfirmed", "child_exited": False}))
        with patch.object(module, "build_operator_server", return_value=server), patch("sys.stderr", io.StringIO()):
            code = module.main(["--operator-root", str(self.root), "--namespace", "live", "--allow-live"])
        self.assertEqual(code, 2)
        server.shutdown_owned_monitor.assert_called_once_with()

    def test_unconfirmed_child_exit_is_retained_and_retry_can_confirm(self):
        api, child = self.owned_api()
        with patch.object(background, "stop", return_value={"state": "stopped"}), \
                patch.object(processes, "finish", side_effect=[dict(EXIT, child_exited=None,
                             remaining_owned_processes=1), dict(EXIT)]) as finish:
            first = api.close_owned_monitor(grace_seconds=0)
            second = api.close_owned_monitor(grace_seconds=0)
        self.assertEqual(first["state"], "shutdown_unconfirmed")
        self.assertEqual(first["owned_monitors_remaining"], 1)
        self.assertFalse(first["child_exited"])
        self.assertEqual(second["state"], "closed")
        self.assertEqual(second["owned_monitors_remaining"], 0)
        self.assertEqual([item.args[0] for item in finish.call_args_list], [child, child])

    def test_close_fences_before_waiting_for_inflight_start_and_drains_its_child(self):
        api = OperatorAPI(self.root, background_lifetime_owner="application")
        child = type("FixtureOwnedChild", (), {"_eventguard_background_scope": dict(SCOPE),
                     "pid": SCOPE["pid"], "created_at": CREATED,
                     "job": SimpleNamespace(name=SCOPE["job_name"])})()
        entered, release = threading.Event(), threading.Event()
        results, errors = {}, []

        def delayed_start(root, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test failed to release its admitted Start")
            kwargs["child_owner"](child)
            return {"state": "started", "namespace": "live", "model_calls": 0}

        def run(label, function):
            try:
                results[label] = function()
            except BaseException as error:
                errors.append((label, type(error).__name__))

        threads = []
        with patch.object(background, "start", side_effect=delayed_start) as start, \
                patch.object(background, "stop", return_value={"state": "stopped"}) as stop, \
                patch.object(processes, "finish", return_value=dict(EXIT)) as finish:
            try:
                first = threading.Thread(target=run, args=("first", api.background_start))
                threads.append(first)
                first.start()
                self.assertTrue(entered.wait(2))
                closer = threading.Thread(target=run, args=("close", lambda: api.close_owned_monitor(grace_seconds=0)))
                threads.append(closer)
                closer.start()
                self.assertTrue(api._background_owner_closed.wait(2), "close must fence before waiting for the Start lock")
                second = threading.Thread(target=run, args=("second", api.background_start))
                threads.append(second)
                second.start()
            finally:
                release.set()
                for thread in threads:
                    thread.join(timeout=5)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(results["first"]["state"], "started")
        self.assertEqual(results["close"]["state"], "closed")
        self.assertEqual(results["second"]["reason"], "operator_monitor_owner_closed")
        self.assertEqual(start.call_count, 1)
        self.assertEqual(stop.call_args.kwargs["expected_run_id"], SCOPE["run_id"])
        self.assertIs(finish.call_args.args[0], child)

    def test_owned_cleanup_is_not_a_remotely_selectable_operation(self):
        value = OperatorAPI(self.root, background_lifetime_owner="application").call("close_owned_monitor")
        self.assertEqual(value["status"], "invalid_request")
        self.assertFalse((self.root / "data").exists())


class BackgroundScopeContracts(FixtureRoot, unittest.TestCase):
    def record(self, *, lifetime="application"):
        runtime = Runtime(self.root)
        background._write(runtime, "control.json", {"kind": background.CONTROL_KIND, "enabled": True,
            "generation": SCOPE["control_generation"], "namespace": "live", "fixture": None,
            "max_cycles": None, "updated_at": background._stamp(), "reason": "fixture"})
        owner = {"kind": background.OWNER_KIND, "run_id": SCOPE["run_id"],
            "generation": SCOPE["control_generation"], "namespace": "live", "pid": SCOPE["pid"],
            "created_at": CREATED, "session_id": 1, "job_name": SCOPE["job_name"],
            "lifetime_owner": lifetime, "started_at": background._stamp()}
        if lifetime == "application":
            owner["application_owner"] = {"pid": 4241, "created_at": CREATED}
        background._write(runtime, "owner.json", owner)
        background._write(runtime, "run.json", {"kind": background.RUN_KIND,
            "run_id": SCOPE["run_id"], "state": "running", "heartbeat_at": background._stamp(),
            "lifetime_owner": "host_os_exit", "restart_count": 0})
        return runtime

    def guards(self):
        return {"expected_namespace": "live", "expected_run_id": SCOPE["run_id"],
                "expected_control_generation": SCOPE["control_generation"], "expected_job_name": SCOPE["job_name"]}

    def test_stale_run_generation_or_job_does_not_mutate_control(self):
        runtime = self.record()
        before = background._path(runtime, "control.json").read_bytes()
        with patch.object(background.processes, "identity", return_value={"pid": SCOPE["pid"], "created_at": CREATED, "state": "alive"}), \
                patch.object(background, "_session", return_value=1), \
                patch.object(background.processes, "stop_persistent") as stop:
            for field, value in (("expected_run_id", "d" * 32),
                                 ("expected_control_generation", "e" * 32),
                                 ("expected_job_name", "Global\\EventGuard-" + "f" * 32)):
                with self.subTest(field=field):
                    result = background.stop(self.root, grace_seconds=0, **dict(self.guards(), **{field: value}))
                    self.assertEqual(result["reason"], "background_owner_changed")
                    self.assertEqual(background._path(runtime, "control.json").read_bytes(), before)
                    self.assertFalse(background._path(runtime, "stop.json").exists())
        stop.assert_not_called()

    def test_partial_or_unscoped_identity_guards_are_rejected(self):
        for kwargs in ({"expected_run_id": SCOPE["run_id"]},
                       {"expected_namespace": "live", "expected_run_id": SCOPE["run_id"]},
                       {key: value for key, value in self.guards().items() if key != "expected_namespace"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                background.stop(self.root, grace_seconds=0, **kwargs)
        self.assertFalse((self.root / "data").exists())

    def test_new_control_generation_with_old_owner_cannot_be_disabled_by_old_close(self):
        runtime = self.record()
        old_owner = background._read(runtime, "owner.json")
        background._write(runtime, "launch.json", dict(old_owner, kind=background.LAUNCH_KIND, state="started"))
        control = background._control(runtime)
        control["generation"] = "d" * 32
        background._write(runtime, "control.json", control)
        before = background._path(runtime, "control.json").read_bytes()
        with patch.object(background.processes, "identity", return_value={"pid": SCOPE["pid"], "created_at": CREATED, "state": "alive"}), \
                patch.object(background, "_session", return_value=1), \
                patch.object(background.processes, "stop_persistent") as stop:
            result = background.stop(self.root, grace_seconds=0, **self.guards())
        self.assertEqual(result["reason"], "background_owner_changed")
        self.assertFalse(result["disabled_persisted"])
        self.assertEqual(background._path(runtime, "control.json").read_bytes(), before)
        self.assertFalse(background._path(runtime, "stop.json").exists())
        stop.assert_not_called()

    def test_application_lifetime_survives_status_and_old_keeper_label(self):
        self.record()
        with patch.object(background.processes, "identity", return_value={"pid": SCOPE["pid"], "created_at": CREATED, "state": "alive"}), \
                patch.object(background, "_session", return_value=1):
            value = background.status(self.root)
        self.assertEqual(value["state"], "running")
        self.assertEqual(value["lifetime_owner"], "application")
        self.assertTrue(value["lifetime_limited"])
        self.assertEqual(value["owner"]["lifetime_owner"], "application")
        self.assertEqual(value["last_report"]["lifetime_owner"], "application")


@unittest.skipUnless(os.name == "nt", "Windows owned Job APIs")
class OperatorOwnedSDKFixtureTests(FixtureRoot, unittest.TestCase):
    """Real stdio/Jobs, with the monitor forced to fixed synthetic frames."""
    def setUp(self):
        super().setUp()
        self.adapter()
        set_enabled(self.root, True)
        self.children = []
        self.addCleanup(self.cleanup_children)
        self.host_entry = self.root / "fixture-host.py"
        self.host_entry.write_text(
            "import sys\nfrom pathlib import Path\n"
            + "sys.path.insert(0, " + repr(str(ROOT / "src")) + ")\n"
            + "from eventguard import background\nfrom eventguard.monitor import Monitor\n"
            + "from eventguard.runtime import atomic_json\n"
            + "class FixtureMonitor(Monitor):\n"
            + " def run(self, **kwargs):\n"
            + "  kwargs.update(fixture='tests/fixtures/normal.json',max_cycles=100000,fixture_interval=.1)\n"
            + "  return super().run(**kwargs)\n"
            + "background.Monitor=FixtureMonitor\n"
            + "value=background.serve(Path(sys.argv[1]),run_id=sys.argv[2],job_name=sys.argv[3])\n"
            + "atomic_json(Path(sys.argv[1])/'host-exit.json',value)\n"
            + "raise SystemExit(0)\n", encoding="utf-8")
        self.server_entry = self.root / "fixture-operator.py"
        self.server_entry.write_text(
            "import importlib.util,sys\nfrom pathlib import Path\n"
            + "sys.path.insert(0, " + repr(str(ROOT / "src")) + ")\n"
            + "from eventguard import background,processes\nfrom eventguard.runtime import atomic_json\n"
            + "background._host_argv=lambda runtime,run_id,job_name,fixture,max_cycles: "
            + "[sys.executable,'-B'," + repr(str(self.host_entry)) + ",str(runtime.root),run_id,job_name]\n"
            + "spec=importlib.util.spec_from_file_location('owned_operator'," + repr(str(ENTRY)) + ")\n"
            + "module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)\n"
            + "code=module.main(['--operator-root',sys.argv[1],'--namespace','live','--allow-live'])\n"
            + "atomic_json(Path(sys.argv[1])/('server-exit-'+sys.argv[2]+'.json'),"
            + "{'code':code,'remaining_owned_processes':processes.remaining_owned(),'scope':'SDK fixture no live scan/model'})\n"
            + "raise SystemExit(code)\n", encoding="utf-8")

    def launch(self):
        token = uuid.uuid4().hex
        stderr = (self.root / ("stderr-" + token + ".txt")).open("xb")
        child = processes.spawn([sys.executable, "-B", str(self.server_entry), str(self.root), token],
            job_name="Global\\EventGuard-" + uuid.uuid4().hex,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
        incoming = queue.Queue()
        def reader():
            for line in child.stdout:
                try:
                    incoming.put(json.loads(line))
                except (ValueError, UnicodeError):
                    incoming.put({"invalid_protocol_line": True})
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        item = {"child": child, "incoming": incoming, "thread": thread, "stderr": stderr,
                "token": token, "transcript": [], "next_id": 1, "receipt": None}
        self.children.append(item)
        self.request(item, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "fixture-owned-monitor-no-agent", "version": "1"}})
        self.send(item, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        return item

    def send(self, item, value):
        item["child"].stdin.write((json.dumps(value) + "\n").encode())
        item["child"].stdin.flush()

    def request(self, item, method, params):
        identifier = item["next_id"]
        item["next_id"] += 1
        request = {"jsonrpc": "2.0", "id": identifier, "method": method, "params": params}
        self.send(item, request)
        response = item["incoming"].get(timeout=40)
        self.assertEqual(response.get("id"), identifier, response)
        self.assertNotIn("error", response)
        item["transcript"].append({"request": request, "response": response})
        return response

    def tool(self, item, name):
        response = self.request(item, "tools/call", {"name": name, "arguments": {}})
        self.assertFalse(response["result"].get("isError", False), response)
        return json.loads(response["result"]["content"][0]["text"])

    def eof(self, item):
        child = item["child"]
        child.stdin.close()
        self.assertEqual(child.wait(timeout=25), 0)
        receipt = processes.finish(child, "descendants_remaining", grace=1)
        item["receipt"] = receipt
        self.assertTrue(receipt["child_exited"])
        self.assertFalse(receipt["forcibly_terminated"], receipt)
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        saved = json.loads((self.root / ("server-exit-" + item["token"] + ".json")).read_text())
        self.assertEqual(saved["remaining_owned_processes"], 0)
        item["thread"].join(timeout=2)
        self.assertFalse(item["thread"].is_alive())
        return receipt

    def cleanup_children(self):
        for item in reversed(self.children):
            child = item["child"]
            try:
                if child.stdin is not None and not child.stdin.closed:
                    child.stdin.close()
                receipt = processes.finish(child, "test_teardown", grace=10)
                self.assertFalse(receipt["forcibly_terminated"], receipt)
                self.assertEqual(receipt["remaining_owned_processes"], 0)
            finally:
                item["thread"].join(timeout=2)
                child.stdout.close()
                item["stderr"].close()

    def assert_application(self, value):
        self.assertEqual(value["lifetime_owner"], "application", value)
        self.assertTrue(value["lifetime_limited"], value)
        self.assertEqual(value["model_calls"], 0)

    def shutdown_receipt(self, run_id):
        path = self.root / "data/background/operator-stop-receipt.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["kind"], "eventguard-operator-monitor-shutdown-v1")
        self.assertTrue(saved["child_exited"])
        self.assertFalse(saved["forcibly_terminated"])
        entries = [entry for entry in saved["results"] if (entry.get("scope") or {}).get("run_id") == run_id]
        self.assertEqual(len(entries), 1, saved)
        self.assertEqual(entries[0]["scope"]["job_name"],
                         background.status(self.root)["owner"]["job_name"])
        self.assertTrue(entries[0]["process"]["child_exited"])
        self.assertEqual(entries[0]["process"]["remaining_owned_processes"], 0)
        self.assertFalse(entries[0]["process"]["forcibly_terminated"])
        return path.read_bytes()

    def evidence_for(self, *items):
        return {"scope": "real Windows owned Jobs and SDK stdio with synthetic fixture Monitor; not main-chat/live/reboot",
                "machine_scan_executed": False, "model_calls": 0, "real_agent_woken": False,
                "servers": [{"transcript": item["transcript"], "process": item["receipt"]} for item in items],
                "background": background.status(self.root)}

    def test_sdk_start_status_stop_uses_application_job_without_agent(self):
        item = self.launch()
        started = self.tool(item, "start_monitor")
        self.assertEqual(started["state"], "started", started)
        self.assert_application(started)
        self.assertFalse(started["handoff"]["detached"])
        self.assertFalse(started["handoff"]["ownership_transferred"])
        state = self.tool(item, "status")["background"]
        self.assert_application(state)
        self.assertEqual(state["run_id"], started["run_id"])
        self.assertEqual(state["state"], "running")
        stopped = self.tool(item, "stop")
        self.assertEqual(stopped["state"], "stopped", stopped)
        self.assertFalse(stopped["desired_enabled"])
        self.assertFalse(stopped["process"]["forcibly_terminated"])
        self.assert_application(self.tool(item, "status")["background"])
        self.eof(item)
        self.evidence = self.evidence_for(item)

    def test_sdk_eof_cooperatively_stops_its_retained_host(self):
        item = self.launch()
        started = self.tool(item, "start_monitor")
        self.assertEqual(started["state"], "started", started)
        self.eof(item)
        state = background.status(self.root)
        self.assertEqual(state["state"], "stopped", state)
        self.assertFalse(state["desired_enabled"])
        self.assertEqual(state["host_liveness"], "exited_verified")
        self.assertEqual(state["run_id"], started["run_id"])
        self.shutdown_receipt(started["run_id"])
        self.evidence = self.evidence_for(item)

    def test_observer_server_eof_does_not_stop_another_servers_host(self):
        owner = self.launch()
        started = self.tool(owner, "start_monitor")
        self.assertEqual(started["state"], "started", started)
        observer = self.launch()
        reused = self.tool(observer, "start_monitor")
        self.assertEqual(reused["reason"], "background_already_running", reused)
        self.assertEqual(reused["run_id"], started["run_id"])
        self.eof(observer)
        still_running = self.tool(owner, "status")["background"]
        self.assertEqual(still_running["state"], "running", still_running)
        self.assertEqual(still_running["run_id"], started["run_id"])
        self.eof(owner)
        self.assertEqual(background.status(self.root)["state"], "stopped")
        before = self.shutdown_receipt(started["run_id"])
        idle_observer = self.launch()
        self.eof(idle_observer)
        self.assertEqual((self.root / "data/background/operator-stop-receipt.json").read_bytes(), before,
                         "an idle observer cannot erase the previous owned-host shutdown proof")
        self.evidence = self.evidence_for(owner, observer, idle_observer)

    def test_eof_after_launch_intent_without_waiting_for_start_response_cleans_host(self):
        item = self.launch()
        identifier = item["next_id"]
        item["next_id"] += 1
        request = {"jsonrpc": "2.0", "id": identifier, "method": "tools/call",
                   "params": {"name": "start_monitor", "arguments": {}}}
        self.send(item, request)
        item["transcript"].append({"request": request, "response_not_awaited_before_eof": True})
        launch_path = self.root / "data/background/launch.json"
        deadline = time.monotonic() + 15
        observed = None
        while time.monotonic() < deadline:
            if launch_path.is_file():
                try:
                    observed = json.loads(launch_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    observed = None
                if observed is not None:
                    break
            self.assertIsNone(item["child"].poll(), "server exited before publishing launch intent")
            time.sleep(.02)
        self.assertIsNotNone(observed, "one exact launch was observed; do not restart on observation expiry")
        self.assertIn(observed["state"], {"launch_intent", "started"})
        self.eof(item)
        state = background.status(self.root)
        self.assertEqual(state["run_id"], observed["run_id"])
        self.assertEqual(state["state"], "stopped", state)
        self.assertFalse(state["desired_enabled"])
        self.assertEqual(state["host_liveness"], "exited_verified")
        self.shutdown_receipt(observed["run_id"])
        self.evidence = dict(self.evidence_for(item), launch_observed_before_eof=observed)


if __name__ == "__main__":
    unittest.main()
