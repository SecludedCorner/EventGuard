"""Pure evidence fixtures only; no CLI, model, network or filesystem operations."""
from copy import deepcopy
import json
import unittest

from eventguard.acceptance_evidence import assess

STAMP = "2026-10-22T05:00:00+00:00"
FINISH = "2026-10-22T05:00:03+00:00"


def evidence():
    """Wire-shaped official exec JSONL items paired with LocalWait-shaped replies."""
    identity, query = "evt-test", "query-test"
    envelope = {"eventId": identity, "data": {"synthetic": True}}
    result = {"status": "synthetic_result_recorded", "event_id": identity,
              "query_id": query, "decision": "reviewed_synthetic", "result_id": "result-test",
              "recorded_at": FINISH, "incident_conclusion": "not_assessed",
              "real_agent_wake_verified": False, "experiment_only": True}
    wait = {"wait_id": "wait-test", "status": "event_available", "started_at": STAMP,
            "finished_at": FINISH, "duration_seconds": 3.0}
    ledger = {"schema_version": "1.0", "kind": "eventguard-single-synthetic-local-wait-experiment",
              "experiment_id": "experiment-test", "events": {identity: {"event": envelope,
              "delivered_at": FINISH, "query_id": query, "queried_at": FINISH, "result": result}},
              "waits": [wait]}
    replies = [{"status": "event_available", "event_id": identity, "event": envelope,
                **{key: value for key, value in wait.items() if key != "status"},
                "experiment_only": True, "real_agent_wake_verified": False},
               {"status": "synthetic_snapshot", "event_id": identity, "query_id": query,
                "event": envelope, "snapshot_only": True, "system_query_executed": False,
                "experiment_only": True}, {**result, "outbox_acknowledged": True}]
    arguments = [{"timeout_seconds": 30}, {"event_id": identity},
                 {"event_id": identity, "query_id": query, "decision": "reviewed_synthetic"}]
    trace = [{"type": "thread.started", "thread_id": "thread-test"}, {"type": "turn.started"}]
    for number, (tool, args, reply) in enumerate(zip(
            ("wait_for_event", "query_evidence", "ack_event"), arguments, replies)):
        item = {"id": "item_" + str(number), "type": "mcp_tool_call", "server": "eventguard_local",
                "tool": tool, "arguments": args, "status": "in_progress", "error": None, "result": None}
        trace.append({"type": "item.started", "item": deepcopy(item)})
        item.update(status="completed", result={"content": [{"type": "text", "text": json.dumps(reply)}],
                                                "structured_content": None})
        trace.append({"type": "item.completed", "item": item})
    trace.append({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 20}})
    return trace, ledger, identity


def completed(trace):
    return [row["item"] for row in trace if row.get("type") == "item.completed"]


class AcceptanceEvidenceTests(unittest.TestCase):
    def test_requires_actual_returns_and_completed_cli_turn(self):
        trace, ledger, identity = evidence()
        self.assertTrue(assess(trace, ledger, identity, 0, True)["passed"])
        for change in ("missing_turn", "missing_return", "error_return", "wrong_ack", "prose_only"):
            rows = deepcopy(trace)
            if change == "missing_turn":
                rows.pop()
            elif change == "missing_return":
                completed(rows)[0]["result"] = None
            elif change == "error_return":
                completed(rows)[1]["result"]["content"][0]["text"] = '{"status":"error"}'
            elif change == "wrong_ack":
                reply = json.loads(completed(rows)[2]["result"]["content"][0]["text"])
                reply["outbox_acknowledged"] = False
                completed(rows)[2]["result"]["content"][0]["text"] = json.dumps(reply)
            else:
                rows = [{"type": "item.completed", "item": {"type": "agent_message", "text": "success"}},
                        {"type": "turn.completed"}]
            with self.subTest(change=change):
                self.assertFalse(assess(rows, ledger, identity, 0, True)["passed"])

    def test_same_event_query_snapshot_and_wait_timing_must_match(self):
        trace, ledger, identity = evidence()
        for index, field, wrong in [(0, "event_id", "evt-other"), (0, "wait_id", "wait-other"),
                                    (0, "duration_seconds", 2), (1, "query_id", "query-other"),
                                    (1, "system_query_executed", True), (2, "result_id", "result-other")]:
            rows = deepcopy(trace)
            item = completed(rows)[index]
            reply = json.loads(item["result"]["content"][0]["text"])
            reply[field] = wrong
            item["result"]["content"][0]["text"] = json.dumps(reply)
            with self.subTest(index=index, field=field):
                self.assertFalse(assess(rows, ledger, identity, 0, True)["passed"])

    def test_retry_proves_one_new_wait_and_preserves_old_waits(self):
        trace, ledger, identity = evidence()
        historical = {"wait_id": "wait-before", "status": "cancelled", "started_at": STAMP,
                      "finished_at": FINISH, "duration_seconds": 3}
        ledger["waits"].insert(0, historical)
        self.assertFalse(assess(trace, ledger, identity, 0, True)["passed"])
        summary = assess(trace, ledger, identity, 0, True, wait_ids_before=("wait-before",))
        self.assertTrue(summary["passed"])
        self.assertEqual([row["wait_id"] for row in summary["waits"]], ["wait-test"])
        self.assertEqual(len(ledger["waits"]), 2, "Assessment must not mutate saved evidence")
        self.assertFalse(assess(trace, ledger, identity, 0, True,
                                wait_ids_before=("wait-before", "wait-test"))["passed"])

    def test_structured_and_text_results_must_agree(self):
        trace, ledger, identity = evidence()
        item = completed(trace)[0]
        reply = json.loads(item["result"]["content"][0]["text"])
        item["result"]["structured_content"] = deepcopy(reply)
        self.assertTrue(assess(trace, ledger, identity, 0, True)["passed"])
        item["result"]["structured_content"]["event_id"] = "evt-other"
        self.assertFalse(assess(trace, ledger, identity, 0, True)["passed"])
        item["result"] = {"structured_content": reply}
        self.assertTrue(assess(trace, ledger, identity, 0, True)["passed"])

    def test_repeated_or_unfinished_calls_and_other_tools_fail(self):
        trace, ledger, identity = evidence()
        for extra in ({"type": "item.started", "item": deepcopy(completed(trace)[0])},
                      {"type": "item.completed", "item": {"type": "command_execution"}},
                      {"type": "turn.failed"}, {"type": "turn.completed"}):
            self.assertFalse(assess(trace + [extra], ledger, identity, 0, True)["passed"])
        rows = deepcopy(trace)
        completed(rows)[2]["arguments"]["query_id"] = "query-other"
        self.assertFalse(assess(rows, ledger, identity, 0, True)["passed"])

    def test_malformed_ledger_and_trace_never_raise_or_pass(self):
        trace, ledger, identity = evidence()
        for value in (None, [], 1, "invalid", {"events": []}, {"events": {}, "waits": [None]}):
            self.assertFalse(assess(trace, value, identity, 0, True)["passed"])
        for key, wrong in [("events", []), ("waits", [None]), ("waits", [{"status": []}])]:
            invalid = deepcopy(ledger)
            invalid[key] = wrong
            self.assertFalse(assess(trace, invalid, identity, 0, True)["passed"])
        for value in (None, "invalid", [None], [{"type": []}], [{"type": "item.completed", "item": []}]):
            self.assertFalse(assess(value, ledger, identity, 0, True)["passed"])
        self.assertFalse(assess(trace, ledger, [], 0, True)["passed"])
        self.assertFalse(assess(trace, ledger, identity, 0, True, wait_ids_before=[[]])["passed"])
        bad = deepcopy(ledger)
        bad["events"][identity]["result"]["decision"] = []
        self.assertFalse(assess(trace, bad, identity, 0, True)["passed"])

    def test_limits_and_outcome_types_cannot_be_coerced(self):
        trace, ledger, identity = evidence()
        self.assertFalse(assess(trace, ledger, identity, False, True)["passed"])
        self.assertFalse(assess(trace, ledger, identity, 0, 1)["passed"])
        self.assertFalse(assess([{}] * 4097, ledger, identity, 0, True)["passed"])
        completed(trace)[0]["result"]["content"][0]["text"] = " " * 65537
        self.assertFalse(assess(trace, ledger, identity, 0, True)["passed"])
        bad = deepcopy(ledger)
        bad["waits"][0]["duration_seconds"] = float("nan")
        self.assertFalse(assess(trace, bad, identity, 0, True)["passed"])
