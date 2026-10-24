"""Finite validation entry points; no model, network, CI or native collection."""
import importlib.util
import hashlib
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time
import tomllib
import unittest
from unittest.mock import Mock, patch

from eventguard import delivery_validation as queue_validation
from eventguard import agent_service
from eventguard import processes
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
        stamp = lambda seconds: (self.base+timedelta(seconds=seconds)).isoformat()
        clock = [4]
        with patch("eventguard.events.store.time.time", side_effect=lambda: (self.base+timedelta(seconds=clock[0])).timestamp()), \
                patch("eventguard.queue_inbox._utc", side_effect=lambda: stamp(clock[0])):
            queue_validation.enqueue(self.root, self.manifest, [event])
            inbox = QueueInbox(self.root / "source", self.root / "inbox", event_id=event["event_id"])
            clock[0] = 5
            received = inbox.receive_event()
            clock[0] = 6
            queried = inbox.query_evidence(event["event_id"])
            clock[0] = 7
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
        parent = {"pid": 300, "created_at": stamp(-2)}
        scope = {"lifetime_owner": "application", "application_owner": parent,
                 "deadline_monotonic": 999 + queue_validation.SERVICE_TIMEOUT - 20}
        owner = {"kind": "eventguard-agent-service-owner-v1", "run_id": self.host_id, "pid": 301,
                 "created_at": self.created, "job_name": job_name, "session_id": 1, **scope}
        self.put(service / "owner.json", owner)
        self.put(service / "control.json", {"kind": "eventguard-agent-service-control-v1", "run_id": self.host_id,
            "job_name": job_name, "enabled": False, "paused": False, "allow_live": False,
            "updated_at": self.created, "source_dir": str(self.root / "source"), "state_dir": str(self.root / "inbox"),
            "codex_executable": "fixture-never-executed.exe", **scope})
        stop_process = {"managed": True, "job_name": job_name, "pid": owner["pid"], "created_at": self.created,
            "child_exited": True, "remaining_owned_processes": 0, "forcibly_terminated": False,
            "reason": "natural_exit", "shutdown_requested_reason": "cancelled", "exit_code": 0}
        self.put(service / "stop-receipt.json", stop_process)
        self.put(self.root / "service-stop.json", {"state": "stopped", "process": stop_process})
        self.put(self.root / "service-start.json", {"state": "started", "run_id": self.host_id, **scope,
            "handoff": {"managed": True, "ownership_transferred": False, "detached": False,
                        "lifetime_owner": "application", "lifetime_limited": True, "job_name": job_name,
                        "pid": owner["pid"], "created_at": owner["created_at"], "session_id": owner["session_id"]}})
        self.put(self.root / "service-owner-stop.json", {"kind": "eventguard-service-application-owner-exit-v1",
            "lifetime_owner": "application", "recorded_at": stamp(12), "children": [{"retained_handle_observed": True,
                "launch": {"kind": "eventguard-agent-service-owned-launch-v1", "run_id": self.host_id,
                           "pid": owner["pid"], "created_at": owner["created_at"], "job_name": job_name, **scope},
                "process": deepcopy(stop_process)}]})
        self.put(service / "exit.json", {**owner, "state": "stopped", "forcibly_terminated": False, "at": stamp(11.5)})
        self.put(service / "run.json", {"run_id": self.host_id, "state": "stopped", "exit_code": 0, **scope})
        supervisor = {"managed": True, "pid": 302, "created_at": stamp(4.1), "child_exited": True,
            "remaining_owned_processes": 0, "forcibly_terminated": False, "reason": "natural_exit", "exit_code": 0}
        self.put(attempt / "supervisor-exit.json", supervisor)
        worker_start = {"attempt_id": self.token, "run_id": self.dispatch_id, "nonce": "f"*32,
                        "pid": 302, "created_at": stamp(4.1)}
        self.put(attempt / "supervisor-start.json", worker_start)
        started = {"attempt_id": self.token, "codex_pid": 303, "created_at": stamp(4.2)}
        process = {"managed": True, "pid": 303, "created_at": stamp(4.2), "child_exited": True,
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
            "delivery_progress": progress, "supervisor_process": supervisor,
            "supervisor_identity_required": True, "supervisor_identity_level": "bound_v1",
            "supervisor_nonce": "f"*32, "supervisor_start": worker_start}
        self.put(directory / "status.json", state)
        self.put(directory / "dispatch.json", {"kind": DISPATCH_KIND, "run_id": self.dispatch_id})
        metadata = {"event_id": event["event_id"], "attempt_id": self.token, "run_id": self.dispatch_id,
                    "run_dir": str(directory), "supervisor_identity_required": True, "supervisor_exit_required": True,
                    "supervisor_nonce": "f"*32, "supervisor_start": worker_start}
        self.put(attempt / "attempt.json", metadata)
        self.put(self.root / "inbox/dispatcher-attempts.json", {"kind": DISPATCH_KIND, "events": {event["event_id"]: [metadata]}})
        def sample(seconds, tasks):
            return {"observed_at": stamp(seconds), "observed_monotonic": 1000+seconds, "clock_id": "e"*32, "service": {
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
            "clock_id": "e"*32, "started_at": stamp(-1), "started_monotonic": 999,
            "finished_monotonic": 1012, "timeout_seconds": queue_validation.SERVICE_TIMEOUT, **scope,
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
        for changes in ({"forcibly_terminated": True}, {"exit_code": 9}, {"remaining_owned_processes": 1}):
            receipt = {**original, **changes}
            self.put(path, receipt)
            self.put(self.root / "service-stop.json", {"state": "stopped", "process": receipt})
            self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"], changes)

    def test_empty_job_unknown_os_exit_needs_matching_original_handle_zero_exit(self):
        self.fixture()
        path = self.root / "data/agent-service/stop-receipt.json"
        receipt = {**read_json(path), "exit_code": None, "reason": "private_job_empty"}
        self.put(path, receipt)
        self.put(self.root / "service-stop.json", {"state": "stopped", "process": receipt})
        proof = queue_validation.verify_service(self.root, self.manifest)
        self.assertTrue(proof["passed"], "Fabricated fixture only, never a real wake")
        self.assertTrue(proof["application_owner_exit_verified"])
        self.assertIsNone(read_json(path)["exit_code"], "Original unknown receipt must remain unchanged")
        cleanup_path = self.root / "service-owner-stop.json"
        original = read_json(cleanup_path)
        for changes in ({"exit_code": None}, {"exit_code": 9}, {"forcibly_terminated": True},
                        {"pid": 999}, {"created_at": "2026-10-24T00:00:01+00:00"}):
            changed = deepcopy(original)
            changed["children"][0]["process"].update(changes)
            self.put(cleanup_path, changed)
            self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"], changes)

    def test_missing_or_mismatched_retained_owner_cleanup_cannot_pass(self):
        self.fixture()
        path = self.root / "service-owner-stop.json"
        original = read_json(path)
        for child_changes in ({"retained_handle_observed": False}, {"launch": {}}, {"process": {}}):
            value = deepcopy(original)
            value["children"][0].update(child_changes)
            self.put(path, value)
            self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"], child_changes)
        self.put(path, {**original, "children": []})
        self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"])
        path.unlink()
        with self.assertRaises((OSError, ValueError)):
            queue_validation.verify_service(self.root, self.manifest)

    def test_application_lifetime_does_not_claim_independent_or_unbounded_service(self):
        self.fixture()
        self.assertEqual(queue_validation.verify_service(self.root, self.manifest)["lifetime_owner"], "application")
        path = self.root / "service-start.json"
        original = read_json(path)
        changed = deepcopy(original)
        changed["handoff"]["ownership_transferred"] = True
        self.put(path, changed)
        self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"])
        self.put(path, original)
        self.manifest["service_execution"]["deadline_monotonic"] += 1
        self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"])

    def test_missing_or_forced_supervisor_receipt_cannot_pass(self):
        self.fixture()
        receipt = read_json(self.attempt / "supervisor-exit.json")
        receipt["forcibly_terminated"] = True
        self.put(self.attempt / "supervisor-exit.json", receipt)
        self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"])
        (self.attempt / "supervisor-exit.json").unlink()
        with self.assertRaisesRegex(ValueError, "supervisor_identity_unconfirmed"):
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

    def test_missing_host_or_kernel_identity_cannot_match_none_to_none(self):
        self.assertFalse(queue_validation._same_owner({}, {}))
        self.fixture()
        path = self.root / "data/agent-service/owner.json"
        original = read_json(path)
        for field in ("pid", "created_at"):
            owner = deepcopy(original)
            owner.pop(field)
            self.put(path, owner)
            with self.assertRaisesRegex(ValueError, "owner_identity_required"):
                queue_validation.verify_service(self.root, self.manifest)
        self.put(path, original)
        stop_path = self.root / "data/agent-service/stop-receipt.json"
        stopped = read_json(stop_path)
        stopped.pop("created_at")
        self.put(stop_path, stopped)
        self.put(self.root / "service-stop.json", {"state": "stopped", "process": stopped})
        self.assertFalse(queue_validation.verify_service(self.root, self.manifest)["passed"])

    def test_supervisor_requires_original_nonce_and_start_identity(self):
        self.fixture()
        path = self.attempt / "supervisor-start.json"
        original = read_json(path)
        for changes in ({"pid": True}, {"created_at": "2026-10-24T00:00:04"}, {"nonce": "0"*32}):
            self.put(path, {**original, **changes})
            with self.assertRaisesRegex(ValueError, "supervisor_identity_unconfirmed"):
                queue_validation.verify_service(self.root, self.manifest)
        path.unlink()
        with self.assertRaisesRegex(ValueError, "supervisor_identity_unconfirmed"):
            queue_validation.verify_service(self.root, self.manifest)

    def test_future_cli_creation_and_ack_before_query_fail_causal_timeline(self):
        self.fixture()
        start_path, exit_path = self.attempt / "capture-start.json", self.attempt / "capture-exit.json"
        started, exited = read_json(start_path), read_json(exit_path)
        self.put(start_path, {**started, "created_at": "2050-01-01T00:00:00+00:00"})
        later = deepcopy(exited)
        later["process"]["created_at"] = "2050-01-01T00:00:00+00:00"
        self.put(exit_path, later)
        proof = queue_validation.verify_service(self.root, self.manifest)
        self.assertFalse(proof["passed"])
        self.assertFalse(proof["chronology_verified"])
        self.put(start_path, started)
        self.put(exit_path, exited)
        import sqlite3
        with closing(sqlite3.connect(self.root / "source/eventguard.sqlite3")) as db:
            db.execute("UPDATE receipts SET acked_at=?", ((self.base+timedelta(seconds=5)).timestamp(),))
            db.commit()
        proof = queue_validation.verify_service(self.root, self.manifest)
        self.assertFalse(proof["passed"])
        self.assertFalse(proof["chronology_verified"])

    def test_missing_or_inconsistent_monotonic_clock_cannot_prove_idle(self):
        self.fixture()
        path = self.root / "service-observations.json"
        original = read_json(path)
        for changes in ({"observed_monotonic": None}, {"observed_monotonic": 999.0}, {"clock_id": "0"*32}):
            value = deepcopy(original)
            value["idle_after"]["after"].update(changes)
            self.put(path, value)
            proof = queue_validation.verify_service(self.root, self.manifest)
            self.assertFalse(proof["passed"])
            self.assertFalse(proof["monotonic_clock_verified"])

    def test_manifest_enqueue_receipt_time_is_not_the_database_commit_time(self):
        self.fixture()
        # Producer writes this manifest receipt after SQLite commit. A fast
        # receiver can legitimately read before the manifest write completes.
        self.manifest["enqueued"][0]["at"] = (self.base+timedelta(seconds=8)).isoformat()
        self.assertTrue(queue_validation.verify_service(self.root, self.manifest)["passed"])

    def test_default_main_and_verify_only_never_start_service(self):
        with patch.object(agent_service, "start") as start, patch("builtins.print"):
            self.assertEqual(queue_validation.main(["service", "--root", str(self.root)]), 0)
            self.assertEqual(queue_validation.main(["service", "--root", str(self.root), "--verify-only"]), 2)
        start.assert_not_called()

    def test_blocked_service_start_persists_intent_without_stop_or_retry(self):
        def blocked(*args, **kwargs):
            self.assertIn("service_execution", read_json(self.root / "manifest.json"))
            return {"state": "blocked", "reason": "missing_existing_mcp_sdk"}
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
            self.assertEqual(kwargs["lifetime_owner"], "application")
            self.assertTrue(callable(kwargs["child_owner"]))
            self.assertLess(kwargs["deadline_monotonic"], time.monotonic()+queue_validation.SERVICE_TIMEOUT)
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

    def test_driver_keeps_original_failure_and_cleans_retained_child_when_stop_fails(self):
        calls = []
        child = Mock(spec=processes.JobPopen)
        child.pid, child.created_at, child.detached = 301, self.created, False
        child.job = Mock()
        child.job.name = "Global\\EventGuard-" + "d"*32
        def start(*args, **kwargs):
            child._eventguard_agent_service_scope = {"kind": "eventguard-agent-service-owned-launch-v1",
                "run_id": self.host_id, "pid": child.pid, "created_at": child.created_at,
                "job_name": child.job.name, "lifetime_owner": "application",
                "application_owner": {"pid": 300, "created_at": self.created},
                "deadline_monotonic": kwargs["deadline_monotonic"]}
            kwargs["child_owner"](child)
            self.put(self.root / "data/agent-service/control.json", {"fixture": True})
            return {"state": "started", "run_id": self.host_id}
        def stop(*args, **kwargs):
            calls.append("cooperative_stop")
            raise OSError("private fixture failure")
        def finish(owned, *args, **kwargs):
            self.assertIs(owned, child)
            self.assertEqual(calls, ["cooperative_stop"])
            calls.append("retained_handle_finish")
            return {"managed": True, "pid": child.pid, "created_at": child.created_at,
                    "child_exited": True, "exit_code": 0, "remaining_owned_processes": 0,
                    "forcibly_terminated": False, "reason": "natural_exit"}
        with patch.object(agent_service, "start", side_effect=start), \
             patch.object(queue_validation, "_idle_service", side_effect=ValueError("fixture_original_failure")), \
             patch.object(agent_service, "stop", side_effect=stop), \
             patch.object(processes, "finish", side_effect=finish) as cleanup:
            with self.assertRaisesRegex(ValueError, "fixture_original_failure"):
                queue_validation.execute_service(self.root, self.manifest, "fixture-never-executed.exe")
        cleanup.assert_called_once()
        self.assertEqual(calls, ["cooperative_stop", "retained_handle_finish"])
        proof = read_json(self.root / "service-owner-stop.json")
        self.assertTrue(proof["children"][0]["retained_handle_observed"])
        self.assertEqual(proof["children"][0]["process"]["exit_code"], 0)
        self.assertEqual(read_json(self.root / "service-stop.json")["state"], "shutdown_unconfirmed")
        self.assertEqual(self.manifest["service_execution"]["state"], "failed_pending_preserved")
