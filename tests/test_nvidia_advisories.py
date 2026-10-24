"""Synthetic CSAF/SQLite acceptance. No live NVIDIA source or model is called.

Schema reviewed against NVIDIA/product-security at
2c9454053cf5d2942d4f361d455c749b725fe920, 2026/5903/5903.json.
Public sample SHA256: 72aa9d435f542a5abf248dccffd97317b1ceccb40489c9bee46f07b9ed540664.
The hash proves byte consistency, not independent publisher authenticity.
No upstream bulletin text is included: the repository has no declared license.
"""
from contextlib import closing
from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.intelligence import engine
from eventguard.intelligence.applicability import evaluate
from eventguard.intelligence.sources import SourceError, SourceRecords, fetch_source, load_config, parse_source
from eventguard.intelligence.store import IntelligenceCapacityError, IntelligenceError, IntelligenceStore


FIXTURE = Path(__file__).parent / "fixtures/intelligence_sources/nvidia_csaf.synthetic.json"
URL = "https://raw.githubusercontent.com/NVIDIA/product-security/main/2026/5903/5903.json"
NOW = "2026-10-24T04:00:00Z"


def source(**extra):
    return {"id": "synthetic-nvidia", "adapter": "nvidia_csaf", "url": URL,
            "component": "synthetic-widget", "ecosystem": "NVIDIA",
            "interval_seconds": 60, "stale_after_seconds": 600, "failure_threshold": 2, **extra}


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def encoded(data):
    return json.dumps(data).encode("utf-8")


def parsed(data=None):
    return parse_source(encoded(fixture() if data is None else data), source())


class Response(io.BytesIO):
    def __init__(self, body, *, status=200, url=URL):
        super().__init__(body)
        self.status, self.url = status, url
        self.headers = {"ETag": '"synthetic"'}

    def geturl(self):
        return self.url


def fetched(data=None, previous=None, *, now=NOW):
    return fetch_source(source(), previous, now, opener=lambda request, **options: Response(encoded(fixture() if data is None else data)))


def partial_data():
    data = fixture()
    data["vulnerabilities"].append({"cve": "not-an-id", "product_status": []})
    return data


class NvidiaSourcesTests(unittest.TestCase):
    def test_example_is_disabled_and_no_inventory_paths_are_enabled(self):
        config = load_config(Path(__file__).parents[1] / "config/advisories.json")
        entry = next(item for item in config["sources"] if item["adapter"] == "nvidia_csaf")
        self.assertFalse(entry["enabled"])
        self.assertEqual(config["inventory"]["paths"], [])

    def test_source_is_restricted_to_official_raw_bulletins(self):
        for url in ("https://example.org/2026/5903/5903.json", URL.replace("/NVIDIA/", "/attacker/"),
                    URL + "?next=other", URL.replace("/5903.json", "/5904.json"),
                    URL.replace("/main/", "/unreviewed/"), URL.replace("/main/", "/%2e%2e/")):
            with self.subTest(url=url), self.assertRaises(SourceError):
                parse_source(encoded(fixture()), source(url=url))
        pinned = URL.replace("/main/", "/" + "a" * 40 + "/")
        self.assertEqual(len(parse_source(encoded(fixture()), source(url=pinned))), 1)

    def test_schema_dates_tracking_and_product_associations_survive(self):
        records = parsed()
        self.assertIsInstance(records, SourceRecords)
        self.assertEqual(records.coverage, "success")
        record = records[0]
        self.assertEqual(record["ids"], ["CVE-2099-90001"])
        self.assertEqual(record["updated_at"], "2026-10-02T00:00:00Z")
        self.assertEqual(record["evidence"][0]["bulletin_id"], "5903")
        self.assertEqual(record["evidence"][0]["revision"], "1.0.0")
        rows = {row["csaf_status"]: row for row in record["affected"]}
        self.assertEqual(rows["known_affected"]["csaf_product"]["product_id"], "widget-old")
        self.assertEqual(rows["known_affected"]["csaf_product"]["version_label"], "0-1.0.0")
        self.assertEqual(rows["known_affected"]["ranges"], [])
        self.assertEqual(record["fixes"][0]["version"], "2.0.0")
        self.assertEqual(record["fixes"][0]["installed"], "unknown")
        self.assertEqual(record["exploitation"], "unknown")

    def test_multiple_vulnerabilities_are_not_aliases(self):
        data = fixture()
        sibling = deepcopy(data["vulnerabilities"][0])
        sibling["cve"] = "CVE-2099-90002"
        data["vulnerabilities"].append(sibling)
        self.assertEqual([row["ids"] for row in parsed(data)], [["CVE-2099-90001"], ["CVE-2099-90002"]])

    def test_bad_sibling_preserves_good_record_and_reports_partial(self):
        records = parsed(partial_data())
        self.assertEqual(len(records), 1)
        self.assertEqual(records.coverage, "partial")
        self.assertEqual(records.item_errors, [{"index": 1, "reason": "invalid_csaf_vulnerability_id"}])
        result = fetched(partial_data())
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["records"][0]["fetched_at"], NOW)
        self.assertEqual(len(result["content_hash"]), 64)

    def test_duplicate_id_is_an_error_and_not_a_second_case(self):
        data = fixture()
        data["vulnerabilities"].append(deepcopy(data["vulnerabilities"][0]))
        records = parsed(data)
        self.assertEqual(len(records), 1)
        self.assertEqual(records.item_errors[0]["reason"], "duplicate_csaf_vulnerability")

    def test_no_valid_items_is_failed_instead_of_empty_success(self):
        data = partial_data()
        data["vulnerabilities"] = data["vulnerabilities"][1:]
        result = fetched(data)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["coverage"], "partial")

    def test_missing_product_or_version_remains_partial_and_unknown(self):
        for product_id in ("widget-unspecified", "missing-product"):
            with self.subTest(product_id=product_id):
                data = fixture()
                data["vulnerabilities"][0]["product_status"] = {"fixed": [product_id]}
                result = fetched(data)
                self.assertEqual(result["status"], "partial")
                self.assertIsNone(result["records"][0]["fixes"][0]["version"])
                self.assertEqual(result["records"][0]["fixes"][0]["stage"], "unknown")
                self.assertEqual(result["records"][0]["conditions"]["local_applicability"], "unknown")

    def test_known_not_affected_and_disputed_do_not_withdraw(self):
        data = fixture()
        data["vulnerabilities"][0]["product_status"] = {"known_not_affected": ["widget-fixed"]}
        data["vulnerabilities"][0]["involvements"] = [{"party": "vendor", "status": "disputed"}]
        record = parsed(data)[0]
        self.assertFalse(record["withdrawn"])
        self.assertEqual(record["conditions"]["withdrawal_status"], "unknown")

    def test_unsupported_withdrawal_and_new_schema_fail_closed(self):
        for key, value in (("status", "withdrawn"), ("schema", "2.1")):
            with self.subTest(key=key):
                data = fixture()
                if key == "status":
                    data["document"]["tracking"]["status"] = value
                else:
                    data["document"]["csaf_version"] = value
                self.assertEqual(fetched(data)["status"], "failed")

    def test_partial_does_not_send_conditionals_or_accept_304(self):
        previous = {"status": "partial", "content_hash": "a" * 64, "etag": '"old"', "last_modified": NOW}
        requests = []
        def opener(request, **options):
            requests.append(dict(request.header_items()))
            return Response(b"", status=304)
        result = fetch_source(source(), previous, NOW, opener=opener)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "unexpected_304")
        self.assertNotIn("If-none-match", requests[0])
        self.assertNotIn("If-modified-since", requests[0])

    def test_redirect_cannot_escape_publisher_repository(self):
        result = fetch_source(source(), now=NOW, opener=lambda *args, **kw: Response(encoded(fixture()), url=URL.replace("/NVIDIA/", "/other/")))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "invalid_nvidia_source_url")

    def test_vendor_label_never_proves_local_affected_or_safe(self):
        inventory = {"status": "success", "collected_at": NOW, "assets": [{"asset_id": "one", "component": "synthetic-widget",
                     "ecosystem": "NVIDIA", "version": "1.0.0", "facts": {"observed_at": NOW, "deployed": True}}]}
        for state in ("known_affected", "known_not_affected", "fixed"):
            data = fixture()
            data["vulnerabilities"][0]["product_status"] = {state: ["widget-fixed"]}
            result = evaluate(parsed(data)[0], inventory, now=NOW)
            self.assertEqual(result["status"], "unknown")


class NvidiaDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "intelligence.sqlite3"
        self.store = IntelligenceStore(self.path, cooldown_seconds=0)
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("no model or subprocess")))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("no network")))

    def test_partial_preserves_complete_cache_and_recovers_after_restart(self):
        complete = fetched()
        old_second = deepcopy(complete["records"][0])
        old_second["ids"] = ["CVE-2099-90002"]
        complete["records"].append(old_second)
        self.store.record_fetch(source(), complete, NOW)
        partial = fetched(partial_data(), now="2026-10-24T04:01:00Z")
        new_third = deepcopy(partial["records"][0])
        new_third["ids"] = ["CVE-2099-90003"]
        partial["records"].append(new_third)
        self.store.record_fetch(source(), partial, "2026-10-24T04:01:00Z")
        reader = IntelligenceStore(self.path, readonly=True)
        state = reader.source_state("synthetic-nvidia", "2026-10-24T04:01:01Z")
        self.assertEqual(state["last_success"], "2026-10-24T04:00:00+00:00")
        self.assertEqual(state["content_hash"], complete["content_hash"])
        self.assertEqual(state["status"], "partial")
        self.assertEqual(state["freshness"], "unknown")
        self.assertIsNone(state["etag"])
        self.assertFalse(state["conditional_cache_allowed"])
        self.assertEqual({row["ids"][0] for row in state["cached_records"]}, {"CVE-2099-90001", "CVE-2099-90002", "CVE-2099-90003"})
        with closing(sqlite3.connect(self.path)) as db:
            full = db.execute("SELECT cached_records,etag FROM sources").fetchone()
        self.assertEqual(json.loads(full[0]), complete["records"])
        self.assertEqual(full[1], complete["etag"])
        self.store.record_fetch(source(), fetched(), "2026-10-24T04:02:00Z")
        recovered = self.store.source_state("synthetic-nvidia", "2026-10-24T04:02:01Z")
        self.assertFalse(recovered["has_partial_cache"])
        self.assertEqual(recovered["freshness"], "fresh")
        self.assertEqual(recovered["item_errors"], [])

    def test_first_partial_is_durable_without_inventing_full_success(self):
        self.store.record_fetch(source(), fetched(partial_data()), NOW)
        state = IntelligenceStore(self.path, readonly=True).source_state("synthetic-nvidia", NOW)
        self.assertIsNone(state["last_success"])
        self.assertTrue(state["cache_matches_config"])
        self.assertEqual(len(state["cached_records"]), 1)
        self.assertEqual(state["cache_status"], "partial")

    def test_partial_then_failure_still_requires_unconditional_fetch(self):
        self.store.record_fetch(source(), fetched(), NOW)
        self.store.record_fetch(source(), fetched(partial_data()), "2026-10-24T04:01:00Z")
        self.store.record_fetch(source(), {"status": "failed", "error_code": "http_503"}, "2026-10-24T04:02:00Z")
        state = self.store.source_state("synthetic-nvidia", "2026-10-24T04:02:01Z")
        self.assertFalse(state["conditional_cache_allowed"])
        self.assertTrue(state["has_partial_cache"])
        with self.assertRaises(IntelligenceError):
            self.store.record_fetch(source(), {"status": "not_modified"}, "2026-10-24T04:03:00Z")

    def test_partial_downgrades_current_exclusion_without_rewriting_history(self):
        record = fetched()["records"][0]
        assessment = {"status": "not_applicable", "asset_refs": ["one"], "reason_codes": [],
                      "inventory_freshness": {"status": "fresh", "observed_at": NOW, "valid_until": "2026-10-24T05:00:00Z"}}
        self.store.record_fetch(source(), fetched(), NOW)
        self.store.ingest(record, assessment, source()["id"], NOW)
        identity = self.store.cases(now=NOW)[0]["case_id"]
        self.assertEqual(self.store.advisory(identity, now=NOW)["case_status"], "not_applicable")
        self.store.record_fetch(source(), fetched(partial_data()), "2026-10-24T04:01:00Z")
        case = self.store.advisory(identity, now="2026-10-24T04:01:01Z")
        self.assertEqual(case["case_status"], "unknown")
        self.assertEqual(case["historical_case_status"], "not_applicable")
        self.assertIn("source_evidence_partial", case["current_assessment"]["reason_codes"])

    def test_partial_cache_capacity_rolls_back_without_discarding_pending(self):
        tiny = IntelligenceStore(self.root / "small.sqlite3", max_records=1)
        tiny.record_fetch(source(), fetched(), NOW)
        tiny.ingest(fetched()["records"][0], {"status": "unknown", "asset_refs": ["one"], "fix_available": True}, source()["id"], NOW)
        pending = tiny.pending_changes(100, now=NOW)
        partial = fetched(partial_data())
        second = deepcopy(partial["records"][0])
        second["ids"] = ["CVE-2099-90002"]
        partial["records"].append(second)
        with self.assertRaises(IntelligenceCapacityError):
            tiny.record_fetch(source(), partial, "2026-10-24T04:01:00Z")
        state = tiny.source_state("synthetic-nvidia", "2026-10-24T04:01:01Z")
        self.assertEqual(state["status"], "success")
        self.assertEqual(len(state["cached_records"]), 1)
        self.assertEqual(tiny.pending_changes(100, now="2026-10-24T04:01:01Z"), pending)

    def test_source_failure_alert_is_deduplicated_until_complete_recovery(self):
        self.store.record_fetch(source(), fetched(partial_data()), NOW)
        self.store.record_fetch(source(), fetched(partial_data()), "2026-10-24T04:01:00Z")
        self.store.record_fetch(source(), fetched(partial_data()), "2026-10-24T04:02:00Z")
        self.assertEqual([row["reason"] for row in self.store.pending_changes(100, now="2026-10-24T04:02:00Z")], ["source_stale"])
        self.store.record_fetch(source(), fetched(), "2026-10-24T04:03:00Z")
        self.assertEqual([row["reason"] for row in self.store.pending_changes(100, now="2026-10-24T04:03:00Z")], ["source_stale", "recovered"])

    def test_title_revision_and_time_changes_do_not_emit_but_product_change_does(self):
        assessment = {"status": "unknown", "asset_refs": ["one"], "reason_codes": ["version_or_affected_range_unknown"], "fix_available": True}
        first = fetched()["records"][0]
        self.assertEqual(len(self.store.ingest(first, assessment, source()["id"], NOW)), 1)
        metadata = fixture()
        metadata["document"]["title"] = "Different formatting only"
        metadata["document"]["tracking"].update(version="1.0.1", current_release_date="2026-10-24T04:01:00Z")
        self.assertEqual(self.store.ingest(parsed(metadata)[0], assessment, source()["id"], "2026-10-24T04:01:00Z"), [])
        metadata["product_tree"]["branches"][0]["branches"][0]["branches"][1]["product"]["name"] = "3.0.0"
        self.assertEqual(len(self.store.ingest(parsed(metadata)[0], assessment, source()["id"], "2026-10-24T04:02:00Z")), 1)

    def test_engine_surfaces_partial_and_never_starts_model(self):
        (self.root / "config").mkdir()
        config = {"schema_version": 1, "namespace": "test", "sources": [source()], "inventory": {"paths": []}}
        (self.root / "config/advisories.json").write_text(json.dumps(config), encoding="utf-8")
        inventory = {"status": "success", "synthetic": True, "collected_at": NOW, "assets": []}
        result = engine.cycle(self.root, fetcher=lambda *args, **kwargs: fetched(partial_data()),
                              inventory_reader=lambda *args, **kwargs: inventory, now=NOW, synthetic=True)
        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["errors"][0]["reason"], "partial_parse")
        state = IntelligenceStore(self.root / "data/advisories/intelligence.sqlite3", readonly=True).source_state("synthetic-nvidia", NOW)
        self.assertEqual(state["partial_record_count"], 1)


if __name__ == "__main__":
    unittest.main()
