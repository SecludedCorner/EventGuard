"""Representative saved source shapes; synthetic relationships, no detection claim."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.events.schema import validate_event
from eventguard.synthetic import make_synthetic

FIXTURE = Path(__file__).resolve().parent / "fixtures/investigation-source-golden.json"
NOW = "2026-10-26T12:00:00+00:00"


def golden_events(case, now=NOW):
    events = []
    for index in range(2):
        event = make_synthetic("listener")
        stamp = (datetime.fromisoformat(now)-timedelta(seconds=120-index*60)).isoformat()
        evidence = deepcopy(case["evidence"])
        if case["source"] != "unknown":
            evidence["section"] = case["source"]
        if index and case.get("resolved"):
            evidence = {"previous": evidence}
        event.update(event_id="evt-"+case["id"]+"-"+str(index), event_type=case["event_type"],
                     episode_id="synthetic-episode-"+case["id"], sequence=index+1, evidence=evidence,
                     observed_at=stamp, persisted_at=stamp, window={"start":stamp,"end":stamp},
                     transition="resolved" if index and case.get("resolved") else "new")
        event["coverage"] = {"status":case.get("coverage","ok"),"source":"synthetic_fixture"}
        events.append(event)
    return events


class SourceGoldenTests(unittest.TestCase):
    def test_saved_source_shapes_known_relationships_and_explicit_unknowns(self):
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases), 9)
        with tempfile.TemporaryDirectory() as temporary, patch("subprocess.Popen",side_effect=AssertionError("no child/model/collector")):
            root = Path(temporary)
            for case in cases:
                with self.subTest(case=case["id"]):
                    source = root / "reports" / case["id"] / "source"
                    store = EventStore(source)
                    events = golden_events(case)
                    for event in events:
                        store.enqueue(event)
                    before = [(row["event_id"],event_payload_hash(validate_event(row)),row["delivery_status"]) for row in store.list_events()]
                    catalog = EventCatalog(root,"test",directory=source)
                    saved = catalog.investigate(events[0]["event_id"],now=NOW)
                    value = saved["case"]
                    self.assertEqual(len(value["timeline"]),case["expected_members"])
                    self.assertTrue(set(case["expected_gaps"]).issubset({v["reason"] for v in value["gaps"]}))
                    self.assertEqual(value["os_owner_status"],"unknown")
                    self.assertEqual(value["allowed_actions"],[])
                    self.assertEqual(value["incident_conclusion"],"not_assessed")
                    self.assertEqual(value["diagnostic_context"]["state"],"missing")
                    self.assertEqual(saved,EventCatalog(root,"test",directory=source).detail(events[0]["event_id"])["investigation"])
                    self.assertEqual(before,[(row["event_id"],event_payload_hash(validate_event(row)),row["delivery_status"]) for row in store.list_events()])


if __name__=="__main__":
    unittest.main()
