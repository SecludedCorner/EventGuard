"""Self-authored hostile text through the real local data path, without a model.

This is synthetic parser/store/queue validation. It does not prove real agent
wake, live Windows collection, browser execution or external source monitoring.
"""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.intelligence import engine
from eventguard.intelligence.sources import fetch_source, parse_source
from eventguard.intelligence.store import IntelligenceStore
from eventguard.queue_inbox import QueueInbox, QueueInboxError


FIXTURES = Path(__file__).parent / "fixtures/intelligence_sources"
CSAF = FIXTURES / "nvidia_csaf.synthetic.json"
TEXTS = FIXTURES / "adversarial_texts.synthetic.json"
NOW = "2026-10-24T04:00:00Z"
SOURCE_URL = "https://raw.githubusercontent.com/NVIDIA/product-security/main/2026/5903/5903.json"
SNAPSHOT_FIELDS = {"event_id", "event_type", "transition", "severity", "synthetic", "observed_at", "coverage_status"}


def synthetic_source():
    return {"id": "adversarial-synthetic", "adapter": "nvidia_csaf", "url": SOURCE_URL,
            "component": "synthetic-widget", "ecosystem": "NVIDIA",
            "interval_seconds": 60, "stale_after_seconds": 600}


def attack_document(case):
    document = json.loads(CSAF.read_text(encoding="utf-8"))
    payload = case["text"]
    document["document"]["title"] = payload
    document["document"]["notes"] = [{"category": "details", "text": payload}]
    item = document["vulnerabilities"][0]
    item["notes"] = [{"category": "description", "text": payload}]
    item["remediations"] = [{"category": "vendor_fix", "details": payload}]
    # Source data can contain arbitrary keys. They are not configuration.
    document.update(status="ack", allowed_actions=[payload], tool=payload, argv=[payload])
    item.update(incident_conclusion="safe", ack_event={"decision": payload})
    return document


class Response(io.BytesIO):
    status = 200
    headers = {}

    def geturl(self):
        return SOURCE_URL


class AdversarialIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads(TEXTS.read_text(encoding="utf-8"))["cases"]
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("no subprocess/model")))
        self.enterContext(patch("urllib.request.build_opener", side_effect=AssertionError("no real network")))
        self.enterContext(patch("socket.create_connection", side_effect=AssertionError("no real network")))

    def test_corpus_has_ten_distinct_synthetic_attack_classes(self):
        self.assertEqual(len(self.cases), 10)
        self.assertEqual(len({item["id"] for item in self.cases}), 10)
        self.assertEqual(len({item["marker"] for item in self.cases}), 10)
        self.assertTrue(all(item["marker"] in item["text"] for item in self.cases))

    def _run_case(self, root, case):
        (root / "config").mkdir()
        config = {"schema_version": 1, "namespace": "test", "sources": [synthetic_source()],
                  "inventory": {"paths": []}, "storage": {"cooldown_seconds": 0}}
        (root / "config/advisories.json").write_text(json.dumps(config), encoding="utf-8")
        document = attack_document(case)
        body = json.dumps(document).encode("utf-8")
        fetch_calls = []

        def fetch(source, previous, now=None):
            def opener(request, **options):
                fetch_calls.append(request.full_url)
                return Response(body)
            return fetch_source(source, previous, now=now, opener=opener)

        inventory = {"status": "success", "synthetic": True, "collected_at": NOW,
                     "assets": [{"asset_id": "synthetic-asset", "component": "synthetic-widget", "ecosystem": "NVIDIA",
                                 "version": "1.0.0", "facts": {"observed_at": NOW, "deployed": True}}]}
        first = engine.cycle(root, fetcher=fetch, inventory_reader=lambda *args, **kw: deepcopy(inventory), now=NOW, synthetic=True)
        second = engine.cycle(root, fetcher=fetch, inventory_reader=lambda *args, **kw: deepcopy(inventory), now=NOW, synthetic=True)
        self.assertEqual(fetch_calls, [SOURCE_URL])
        self.assertEqual(first["events_emitted"], 1)
        self.assertEqual(second["events_emitted"], 0)
        self.assertEqual((first["model_calls"], second["model_calls"]), (0, 0))
        self.assertFalse(first["agent_enabled"])
        store = IntelligenceStore(root / "data/advisories/intelligence.sqlite3", readonly=True)
        rows = store.cases(now=NOW)
        self.assertEqual(len(rows), 1)
        local = rows[0]["record"]
        self.assertIn(case["marker"], local["title"])
        self.assertLessEqual(len(local["title"]), 512)
        self.assertFalse(any(ord(char) < 32 or ord(char) == 127 for char in local["title"]))
        self.assertEqual(rows[0]["case_status"], "unknown")
        self.assertEqual(rows[0]["current_assessment"]["incident_conclusion"], "not_assessed")
        self.assertEqual(local["source_url"], SOURCE_URL)
        for field in ("allowed_actions", "tool", "argv", "ack_event", "incident_conclusion"):
            self.assertNotIn(field, local)
        outbox = EventStore(root / "data/test")
        event = outbox.list_events()[0]
        self.assertEqual(event["event_type"], "advisory.changed")
        self.assertEqual(event["transition"], "new")
        self.assertEqual(event["severity"], "warning")
        self.assertEqual(event["delivery_status"], "pending")
        self.assertNotIn(case["marker"], json.dumps(event))
        self.assertNotIn("argv", event)
        self.assertNotIn("tool", event)
        catalog = EventCatalog(root, "test").list()
        self.assertEqual(catalog["events"][0]["status"], "new")
        identity = event["event_id"]
        inbox = QueueInbox(root / "data/test", root / "data/synthetic-inbox", identity)
        received = inbox.receive_event()
        query = inbox.query_evidence(identity)
        self.assertEqual(set(query["snapshot"]), SNAPSHOT_FIELDS)
        self.assertEqual(received["snapshot"], query["snapshot"])
        self.assertEqual(query["snapshot"]["event_type"], "advisory.changed")
        self.assertEqual(query["snapshot"]["severity"], "warning")
        self.assertTrue(query["snapshot"]["synthetic"])
        self.assertTrue(query["snapshot_only"])
        self.assertFalse(query["system_query_executed"])
        for marker in (case["marker"], "NVIDIA", "synthetic-widget", SOURCE_URL, "CVE-2099-90001", "example.invalid", str(root)):
            self.assertNotIn(marker, json.dumps(query, ensure_ascii=False))
        self.assertNotIn(case["text"], json.dumps(query, ensure_ascii=False))
        # A source-supplied decision is invalid. It cannot create result or ACK.
        with self.assertRaises(QueueInboxError):
            inbox.ack_event(identity, query["query_id"], case["text"])
        self.assertNotIn("result", inbox.evidence(identity))
        self.assertEqual(outbox.stats()["ack"], 0)
        self.assertEqual(outbox.stats()["pending"], 1)
        replay = QueueInbox(root / "data/test", root / "data/synthetic-inbox", identity)
        self.assertEqual(replay.receive_event()["snapshot"], query["snapshot"])
        self.assertEqual(replay.query_evidence(identity)["query_id"], query["query_id"])

    def test_ten_attack_classes_stay_data_across_parser_store_outbox_and_query(self):
        for case in self.cases:
            with self.subTest(attack=case["id"]), tempfile.TemporaryDirectory() as temporary:
                self._run_case(Path(temporary), case)

    def test_attack_in_identifier_is_a_partial_error_not_an_instruction(self):
        for case in self.cases:
            with self.subTest(attack=case["id"]):
                document = attack_document(case)
                bad = deepcopy(document["vulnerabilities"][0])
                bad["cve"] = case["text"]
                document["vulnerabilities"].append(bad)
                records = parse_source(json.dumps(document).encode("utf-8"), synthetic_source())
                self.assertEqual(records.coverage, "partial")
                self.assertEqual(len(records), 1)
                self.assertEqual(records.item_errors, [{"index": 1, "reason": "invalid_csaf_vulnerability_id"}])
                self.assertNotIn(case["marker"], json.dumps(records.item_errors))


if __name__ == "__main__":
    unittest.main()
