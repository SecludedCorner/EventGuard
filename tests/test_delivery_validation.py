"""Finite validation entry points; no model, network, CI or native collection."""
import importlib.util
import hashlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from eventguard import delivery_validation as queue_validation
from eventguard import agent_service
from eventguard.acceptance_control import read_json, write_json
from eventguard.agent_dispatch import KIND as DISPATCH_KIND, TOOLS
from eventguard.queue_inbox import QueueInbox
from eventguard.events.schema import validate_event
from eventguard.events.store import event_payload_hash

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("finite_delivery_validation", ROOT / "contrib/legacy_delivery_validation.py")
validation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validation)


class DeliveryValidationTests(unittest.TestCase):
    def test_checkout_root_and_finite_tool_whitelists(self):
        self.assertEqual(validation.ROOT, ROOT)
        with patch.object(validation.shutil, "which", return_value="C:/Codex/codex.exe") as lookup:
            single = validation.argv(Path("runtime"), Path("evidence"), 1, native_executable="C:/Codex/codex.exe")
            lookup.assert_called_once_with("C:/Codex/codex.exe")
            multiple = validation.argv(Path("runtime"), Path("evidence"), 3)
            read_only = validation.argv(Path("runtime"), Path("evidence"), 1, read_only=True)
        self.assertTrue(any('--single-wait' in value for value in single))
        self.assertFalse(any('--single-wait' in value for value in multiple))
        config = next(value for value in read_only if value.startswith('mcp_servers.'))
        self.assertIn('query_evidence', config)
        self.assertNotIn('ack_event', config)
        server = tomllib.loads(config)["mcp_servers"]["eventguard_local"]
        self.assertEqual(server["enabled_tools"], ["wait_for_event", "query_evidence"])
        self.assertEqual(server["tools"], {name: {"approval_mode": "approve"}
                                         for name in server["enabled_tools"]})
        self.assertNotIn("default_tools_approval_mode", server)
        self.assertIn('features.unbounded_connection_retries=false', multiple)
        for args in (single, multiple, read_only):
            self.assertIn('mcp_servers.eventguard_test.enabled=false', args)
            self.assertIn('mcp_servers.eventguard.enabled=false', args)

    def test_prepare_is_durable_finite_and_never_launches_model(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(validation, 'capture') as capture:
            for case, count in (("continuous", 2), ("batch", 3), ("recovery", 1)):
                root = Path(temp) / case
                manifest = validation.prepare(root, case)
                self.assertEqual(len(manifest['events']), count)
                self.assertEqual(len({event['event_id'] for event in manifest['events']}), count)
                self.assertTrue(all(event['synthetic'] for event in manifest['events']))
                self.assertEqual(manifest['attempts'], {})
                self.assertEqual(manifest['enqueued'], [])
                self.assertEqual(validation.prepare(root, case), manifest)
                self.assertEqual(json.loads((root / 'manifest.json').read_text()), manifest)
            capture.assert_not_called()

    def test_verify_only_missing_evidence_does_not_create_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'absent'
            args = ['validate_delivery.py', 'batch', '--verify-only', '--root', str(root)]
            with patch.object(validation.sys, 'argv', args), self.assertRaisesRegex(ValueError, 'evidence_required'):
                validation.main()
            self.assertFalse(root.exists())

    def test_native_cli_wrapper_is_refused_without_model(self):
        with patch.object(validation.shutil, 'which', return_value='C:/npm/codex.cmd'):
            with self.assertRaisesRegex(ValueError, 'native_codex_required'):
                validation.argv(Path('runtime'), Path('evidence'), 1)

    def test_legacy_cli_refuses_execution_without_creating_source_or_calling_model(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(validation, 'capture') as capture:
            root = Path(temp) / 'absent'
            args = ['legacy_delivery_validation.py', 'batch', '--root', str(root), '--execute']
            with patch.object(validation.sys, 'argv', args), self.assertRaisesRegex(ValueError, 'legacy_execution_retired'):
                validation.main()
            self.assertFalse(root.exists())
            capture.assert_not_called()

    def test_legacy_reader_does_not_rewrite_schema_policy_ledger_or_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'old'
            manifest = validation.prepare(root, 'batch')
            backend = validation.LocalWait(root / 'runtime')
            event = manifest['events'][0]
            backend.store.enqueue(event)
            runtime = root / 'runtime'
            def snapshot():
                return {p.relative_to(runtime).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in runtime.rglob('*') if p.is_file()}
            before = snapshot()
            reader = validation.EvidenceReader(runtime)
            self.assertEqual(reader.store.get_event(event['event_id'])['delivery_status'], 'pending')
            self.assertEqual(reader.store.stats()['pending'], 1)
            validation.prepare(root, 'batch')
            with self.assertRaisesRegex(validation.LocalWaitError, 'read_only'):
                reader._save(reader._load())
            self.assertEqual(snapshot(), before)


class ServiceDeliveryValidationTests(unittest.TestCase):
    """Service driver mocks and saved fake CLI evidence; never a real agent."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "acceptance"
        self.manifest = queue_validation.prepare(self.root, "service")
        self.host_id, self.dispatch_id, self.token = "a"*32, "b"*32, "c"*32
        self.base = datetime(2026, 10, 24, tzinfo=timezone.utc)
        self.created = self.base.isoformat()

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, value)

    def fixture(self):
        """Use actual synthetic SQLite/inbox ACK, with explicitly fabricated CLI/Job receipts."""
        event = self.manifest["events"][0]
        queue_validation.enqueue(self.root, self.manifest, [event])
        inbox = QueueInbox(self.root / "source", self.root / "inbox", event_id=event["event_id"])
        received = inbox.receive_event()
        queried = inbox.query_evidence(event["event_id"])
        acked = inbox.ack_event(event["event_id"], queried["query_id"], "reviewed_metadata")
        arguments = [{}, {"event_id": event["event_id"]}, {"event_id": event["event_id"],
            "query_id": queried["query_id"], "decision": "reviewed_metadata"}]
        trace = [{"type": "item.completed", "item": {"id": "fixture-"+name, "type": "mcp_tool_call",
            "server": "eventguard_inbox", "tool": name, "status": "completed", "error": None,
            "arguments": args, "result": {"content": [{"type": "text", "text": json.dumps(reply)}]}}}
            for name, args, reply in zip(TOOLS, arguments, (received, queried, acked))]
        trace.append({"type": "turn.completed"})
        service = self.root / "data/agent-service"
        directory = service / "runs" / self.host_id
        attempt = directory / "attempts" / self.token
        attempt.mkdir(parents=True)
        self.attempt = attempt
        self.directory = directory
        job_name = "Global\\EventGuard-" + "d"*32
        owner = {"kind": "eventguard-agent-service-owner-v1", "run_id": self.host_id, "pid": 301,
                 "created_at": self.created, "job_name": job_name, "session_id": 1}
        self.put(service / "owner.json", owner)
        self.put(service / "control.json", {"kind": "eventguard-agent-service-control-v1", "run_id": self.host_id,
            "job_name": job_name, "enabled": False, "paused": False, "allow_live": False,
            "updated_at": self.created, "source_dir": str(self.root / "source"), "state_dir": str(self.root / "inbox"),
            "codex_executable": "fixture-never-executed.exe"})
        stop_process = {"managed": True, "job_name": job_name, "pid": owner["pid"], "created_at": self.created,
            "child_exited": True, "remaining_owned_processes": 0, "forcibly_terminated": False,
            "reason": "natural_exit", "shutdown_requested_reason": "cancelled", "exit_code": 0}
        self.put(service / "stop-receipt.json", stop_process)
        self.put(self.root / "service-stop.json", {"state": "stopped", "process": stop_process})
        self.put(service / "exit.json", {**owner, "state": "stopped", "forcibly_terminated": False})
        self.put(service / "run.json", {"run_id": self.host_id, "state": "stopped", "exit_code": 0})
        supervisor = {"managed": True, "pid": 302, "created_at": self.created, "child_exited": True,
            "remaining_owned_processes": 0, "forcibly_terminated": False, "reason": "natural_exit", "exit_code": 0}
        self.put(attempt / "supervisor-exit.json", supervisor)
        started = {"attempt_id": self.token, "codex_pid": 303, "created_at": self.created}
        process = {"managed": True, "pid": 303, "created_at": self.created, "child_exited": True,
            "remaining_owned_processes": 0, "exit_code": 0, "forcibly_terminated": False,
            "reason": "natural_exit", "shutdown_requested_reason": "descendants_remaining"}
        receipt = {"attempt_id": self.token, "codex_pid": 303, "child_exited": True, "codex_exit_code": 0,
            "process": process, "capture_complete": True, "stdout_truncated": False, "stderr_truncated": False,
            "forcibly_terminated": False, "stop_reason": "descendants_remaining"}
        self.put(attempt / "capture-start.json", started)
        self.put(attempt / "capture-exit.json", receipt)
        (attempt / "codex.jsonl").write_text("\n".join(map(json.dumps, trace)), encoding="utf-8")
        progress = {key: True for key in ("capture_worker_started", "cli_started", "event_received", "evidence_queried",
            "result_saved", "outbox_acknowledged", "provider_turn_completed", "natural_cli_exit", "owned_tree_exited")}
        state = {"kind": DISPATCH_KIND, "run_id": self.dispatch_id, "state": "stopped", "tasks_started": 1,
            "tasks_passed": 1, "child_exited": True, "events_total": 1, "events": [event["event_id"]],
            "delivery_progress": progress, "supervisor_process": supervisor}
        self.put(directory / "status.json", state)
        self.put(directory / "dispatch.json", {"kind": DISPATCH_KIND, "run_id": self.dispatch_id})
        self.put(self.root / "inbox/dispatcher-attempts.json", {"kind": DISPATCH_KIND, "events": {event["event_id"]: [
            {"event_id": event["event_id"], "attempt_id": self.token, "run_id": self.dispatch_id, "run_dir": str(directory)}]}})
        def sample(seconds, tasks):
            return {"observed_at": (self.base+timedelta(seconds=seconds)).isoformat(), "service": {
                "run_id": self.host_id, "owner": owner, "host_liveness": "alive_verified", "state": "running",
                "namespace": "test", "pending_events": 0, "dispatch_run_dir": str(directory),
                "model_calls": 0 if tasks == 0 else None, "dispatcher": {"run_id": self.dispatch_id, "tasks_started": tasks, "tasks_passed": tasks,
                    "child_exited": True, "state": "waiting"}}}
        observations = {"kind": "eventguard-service-acceptance-v1",
            "idle_before": {"before": sample(0, 0), "after": sample(3, 0), "minimum_seconds": queue_validation.SERVICE_IDLE_SECONDS},
            "completed": sample(7, 1),
            "idle_after": {"before": sample(8, 1), "after": sample(11, 1), "minimum_seconds": queue_validation.SERVICE_IDLE_SECONDS}}
        self.put(self.root / "service-observations.json", observations)
        config = self.root / "config/default.json"
        config.parent.mkdir()
        config.write_bytes((ROOT / "config/default.json").read_bytes())
        self.manifest["enqueued"][0]["at"] = (self.base+timedelta(seconds=4)).isoformat()
        self.manifest["service_execution"] = {"kind": "eventguard-service-acceptance-v1", "state": "observed",
            "host_run_id": self.host_id, "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "finished_at": (self.base+timedelta(seconds=12)).isoformat(), "evidence_scope": "fabricated_fixture_no_model"}
        self.put(self.root / "manifest.json", self.manifest)
        return event

    def test_prepare_service_has_one_high_synthetic_event_and_empty_source_without_model(self):
        with patch.object(agent_service, "start") as start, patch.object(queue_validation, "capture") as capture:
            manifest = queue_validation.prepare(self.root, "service")
        self.assertEqual(len(manifest["events"]), 1)
        self.assertTrue(manifest["events"][0]["synthetic"])
        self.assertEqual(manifest["events"][0]["severity"], "high")
        self.assertEqual(manifest["events"][0], validate_event(manifest["events"][0]))
        self.assertEqual(manifest["enqueued"], [])
        self.assertNotIn("service_execution", manifest)
        self.assertFalse((self.root / "data").exists())
        start.assert_not_called()
        capture.assert_not_called()

    def test_service_generated_payload_uses_same_canonical_hash_as_eventstore(self):
        event = self.manifest["events"][0]
        queue_validation.enqueue(self.root, self.manifest, [event])
        inbox = QueueInbox(self.root / "source", self.root / "inbox", event_id=event["event_id"])
        self.assertEqual(inbox.delivery_reference(event["event_id"])["payload_hash"], event_payload_hash(event))

    def test_fake_service_evidence_is_reassessed_and_inbox_is_unchanged(self):
        self.fixture()
        def hashes():
            return {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for directory in (self.root / "source", self.root / "inbox") for path in directory.rglob("*") if path.is_file()}
        before = hashes()
        with patch.object(agent_service, "start") as start, patch.object(queue_validation, "capture") as capture:
            proof = queue_validation.verify_service(self.root, self.manifest)
        self.assertTrue(proof["passed"], "Fixture validation only; not real wake")
        self.assertFalse(proof["real_agent_woken"])
        self.assertEqual(hashes(), before)
        start.assert_not_called()
        capture.assert_not_called()

    def test_saved_passed_claim_cannot_replace_missing_cli_trace(self):
        self.fixture()
        self.put(self.root / "validation.json", {"passed": True})
        (self.attempt / "codex.jsonl").write_text('{"type":"turn.completed"}', encoding="utf-8")
        self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"])

    def test_forced_nonzero_or_unknown_host_exit_cannot_pass(self):
        self.fixture()
        path = self.root / "data/agent-service/stop-receipt.json"
        original = read_json(path)
        for changes in ({"forcibly_terminated": True}, {"exit_code": 9}, {"exit_code": None}, {"remaining_owned_processes": 1}):
            receipt = {**original, **changes}
            self.put(path, receipt)
            self.put(self.root / "service-stop.json", {"state": "stopped", "process": receipt})
            self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"], changes)

    def test_missing_or_forced_supervisor_receipt_cannot_pass(self):
        self.fixture()
        receipt = read_json(self.attempt / "supervisor-exit.json")
        receipt["forcibly_terminated"] = True
        self.put(self.attempt / "supervisor-exit.json", receipt)
        self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"])
        (self.attempt / "supervisor-exit.json").unlink()
        with self.assertRaises(OSError):
            queue_validation.verify_service(self.root, self.manifest)

    def test_idle_before_or_after_task_counts_are_rechecked(self):
        self.fixture()
        path = self.root / "service-observations.json"
        original = read_json(path)
        for phase in ("idle_before", "idle_after"):
            observation = deepcopy(original)
            observation[phase]["after"]["service"]["dispatcher"]["tasks_started"] = 2
            self.put(path, observation)
            self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"])

    def test_extra_attempt_or_changed_generated_payload_cannot_pass(self):
        self.fixture()
        (self.directory / "attempts" / ("e"*32)).mkdir()
        with self.assertRaisesRegex(ValueError, "extra_attempt"):
            queue_validation.verify_service(self.root, self.manifest)
        (self.directory / "attempts" / ("e"*32)).rmdir()
        self.manifest["events"][0]["severity"] = "critical"
        self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"])

    def test_default_main_and_verify_only_never_start_service(self):
        with patch.object(agent_service, "start") as start, patch("builtins.print"):
            self.assertEqual(queue_validation.main(["service", "--root", str(self.root)]), 0)
            self.assertEqual(queue_validation.main(["service", "--root", str(self.root), "--verify-only"]), 2)
        start.assert_not_called()

    def test_budget_blocked_execution_persists_intent_without_stop_or_retry(self):
        def blocked(*args, **kwargs):
            self.assertIn("service_execution", read_json(self.root / "manifest.json"))
            return {"state": "blocked", "reason": "budget_unavailable"}
        with patch.object(agent_service, "start", side_effect=blocked) as start, patch.object(agent_service, "stop") as stop:
            with self.assertRaisesRegex(ValueError, "start_blocked"):
                queue_validation.execute_service(self.root, self.manifest, "fixture-never-executed.exe")
            self.assertEqual(read_json(self.root / "manifest.json")["service_execution"]["state"], "failed_pending_preserved")
            with self.assertRaisesRegex(ValueError, "existing_service_execution"):
                queue_validation.execute_service(self.root, self.manifest, "fixture-never-executed.exe")
        start.assert_called_once()
        stop.assert_not_called()
        self.assertFalse((self.root / "data/agent-service").exists())

    def test_driver_waits_empty_before_enqueue_and_stops_after_failure(self):
        calls = []
        def start(*args, **kwargs):
            self.assertFalse(self.manifest["enqueued"])
            self.assertTrue(kwargs["execute"])
            self.assertFalse(kwargs["allow_live"])
            self.assertEqual(kwargs["source_dir"], self.root / "source")
            self.assertEqual(kwargs["state_dir"], self.root / "inbox")
            self.put(self.root / "data/agent-service/control.json", {"fixture": True})
            calls.append("start")
            return {"state": "started", "run_id": self.host_id}
        def idle(*args, **kwargs):
            self.assertEqual(self.manifest["enqueued"], [])
            calls.append("idle_before")
            return {"fixture": "idle_no_model"}
        def wait(*args, **kwargs):
            self.assertEqual(len(self.manifest["enqueued"]), 1)
            calls.append("enqueued")
            raise ValueError("fixture_failed_before_ACK")
        def stop(*args, **kwargs):
            calls.append("stop")
            return {"state": "stopped", "fixture": True}
        with patch.object(agent_service, "start", side_effect=start), patch.object(agent_service, "stop", side_effect=stop), \
                patch.object(queue_validation, "_idle_service", side_effect=idle), \
                patch.object(queue_validation, "_wait_service", side_effect=wait):
            with self.assertRaisesRegex(ValueError, "fixture_failed_before_ACK"):
                queue_validation.execute_service(self.root, self.manifest, "fixture-never-executed.exe")
        self.assertEqual(calls, ["start", "idle_before", "enqueued", "stop"])
        self.assertEqual(read_json(self.root / "manifest.json")["service_execution"]["state"], "failed_pending_preserved")
