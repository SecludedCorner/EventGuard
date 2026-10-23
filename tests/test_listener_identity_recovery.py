"""Multi-round listener identity fixtures; no host queries or child processes."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard.rules.detector import evaluate


FIRST_REF = "proc-" + "a" * 24
SECOND_REF = "proc-" + "b" * 24


def listener(port=18080, *, ref=FIRST_REF, pid=42, protocol="TCP", address="0.0.0.0"):
    row = {"protocol": protocol, "address": address, "port": port, "pid": pid, "status": "ok"}
    if ref is not None:
        row.update(process_instance_ref=ref, created_at="2026-10-23T00:00:00Z")
    return row


def observed(rows, status="ok"):
    return {"id": "listeners", "status": status, "rows": rows,
            "coverage": {"status": status,
                         "process_identity_status": "ok" if all(row.get("process_instance_ref") for row in rows) else "unknown"}}


def transitions(events):
    return [event for event in events if event["event_type"] == "listener.changed"]


def active_listeners(state):
    return {key: record for key, record in state["active"].items() if key.startswith("listener:")}


class ListenerRecoveryTests(unittest.TestCase):
    def test_bound_owner_loses_identity_without_new_or_resolved_event(self):
        state, first = evaluate([observed([listener()])], now=1000)
        original = copy.deepcopy(active_listeners(state))
        self.assertEqual(len(transitions(first)), 1)
        for stamp in (1120, 1240, 1360):
            state, events = evaluate([observed([listener(ref=None)])], state, now=stamp)
            self.assertEqual(transitions(events), [])
            self.assertEqual(set(active_listeners(state)), set(original))
            record = next(iter(active_listeners(state).values()))
            self.assertEqual(record["evidence"]["process_instance_ref"], FIRST_REF)
            self.assertEqual(record["recovery_count"], 0)

    def test_original_bound_owner_returns_after_gap_and_remains_deduplicated(self):
        state, first = evaluate([observed([listener()])], now=1000)
        original_episode = transitions(first)[0]["episode_id"]
        for stamp, row in ((1120, listener(ref=None)), (1240, listener(ref=None)),
                           (1360, listener()), (1480, listener())):
            state, events = evaluate([observed([row])], state, now=stamp)
            self.assertEqual(transitions(events), [])
        self.assertEqual(len(active_listeners(state)), 1)
        self.assertEqual(next(iter(active_listeners(state).values()))["episode_id"], original_episode)

    def test_identity_gap_breaks_an_already_started_recovery_streak(self):
        state, _ = evaluate([observed([listener()])], now=1000)
        state, events = evaluate([observed([])], state, now=1120)
        self.assertEqual(transitions(events), [])
        self.assertEqual(next(iter(active_listeners(state).values()))["recovery_count"], 1)
        state, events = evaluate([observed([listener(ref=None)])], state, now=1240)
        self.assertEqual(transitions(events), [])
        state, events = evaluate([observed([])], state, now=1360)
        self.assertEqual(transitions(events), [])
        state, events = evaluate([observed([])], state, now=1480)
        resolved = transitions(events)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["transition"], "resolved")
        self.assertEqual(resolved[0]["evidence"]["previous"]["process_instance_ref"], FIRST_REF)
        self.assertEqual(active_listeners(state), {})

    def test_comparable_pid_reuse_produces_new_instance_event(self):
        state, first = evaluate([observed([listener()])], now=1000)
        state, changed = evaluate([observed([listener(ref=SECOND_REF)])], state, now=1120)
        new = transitions(changed)
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["transition"], "new")
        self.assertEqual(new[0]["evidence"]["process_instance_ref"], SECOND_REF)
        self.assertNotEqual(new[0]["event_id"], transitions(first)[0]["event_id"])
        state, events = evaluate([observed([listener(ref=SECOND_REF)])], state, now=1240)
        resolved = transitions(events)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["transition"], "resolved")
        self.assertEqual(resolved[0]["evidence"]["previous"]["process_instance_ref"], FIRST_REF)
        self.assertEqual(len(active_listeners(state)), 1)

    def test_initially_unknown_owner_gaining_identity_is_not_a_new_endpoint(self):
        state, first = evaluate([observed([listener(ref=None)])], now=1000)
        original_episode = transitions(first)[0]["episode_id"]
        for stamp in (1120, 1240):
            state, events = evaluate([observed([listener()])], state, now=stamp)
            self.assertEqual(transitions(events), [])
        record = next(iter(active_listeners(state).values()))
        self.assertEqual(record["episode_id"], original_episode)
        self.assertEqual(record["evidence"]["process_instance_ref"], FIRST_REF)
        state, changed = evaluate([observed([listener(ref=SECOND_REF)])], state, now=1360)
        self.assertEqual(transitions(changed)[0]["evidence"]["process_instance_ref"], SECOND_REF)

    def test_one_identity_gap_does_not_hide_other_endpoint_disappearance(self):
        state, _ = evaluate([observed([listener(), listener(18081, pid=43)])], now=1000)
        for stamp in (1120, 1240):
            state, events = evaluate([observed([listener(ref=None)])], state, now=stamp)
        changed = transitions(events)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["transition"], "resolved")
        self.assertEqual(changed[0]["evidence"]["previous"]["port"], 18081)
        self.assertEqual(len(active_listeners(state)), 1)

    def test_ambiguous_gap_preserves_both_currently_known_owner_episodes(self):
        state, _ = evaluate([observed([listener()])], now=1000)
        state, _ = evaluate([observed([listener(ref=SECOND_REF)])], state, now=1120)
        self.assertEqual(len(active_listeners(state)), 2)
        for stamp in (1240, 1360):
            state, events = evaluate([observed([listener(ref=None)])], state, now=stamp)
            self.assertEqual(transitions(events), [])
            self.assertEqual(len(active_listeners(state)), 2)
            self.assertTrue(all(record["recovery_count"] == 0 for record in active_listeners(state).values()))


if __name__ == "__main__":
    unittest.main()
