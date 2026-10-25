"""Synthetic GitHub pages and SQLite cache contracts; no public HTTP calls."""
from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.intelligence import sources
from eventguard.intelligence.sources import SourceError, fetch_source
from eventguard.intelligence.store import IntelligenceError, IntelligenceStore

BASE = "https://api.github.com/repos/synthetic-owner/synthetic-repo/security-advisories?per_page=100&state=published"
NEXT = BASE + "&page=2"
LAST = BASE + "&page=3"
METADATA = "https://api.github.com/repos/synthetic-owner/synthetic-repo"
CANONICAL = "https://api.github.com/repositories/123456/security-advisories?per_page=100&state=published"
AFTER = CANONICAL + "&after=Y3Vyc29yOnYyOpHOAAkX8w%3D%3D"
AFTER_NEXT = CANONICAL + "&after=another-opaque-cursor"
NOW = "2026-10-26T00:00:00Z"
LATER = "2026-10-26T00:01:00Z"
IDS = ("GHSA-2222-3333-4444", "GHSA-5555-6666-7777", "GHSA-8888-9999-cccc")


def source(**extra):
    return {"id": "synthetic-github", "adapter": "github_advisories", "url": BASE,
            "interval_seconds": 60, "stale_after_seconds": 600, **extra}


def advisory(identity, title="Synthetic fixture"):
    return {"ghsa_id": identity, "summary": title, "vulnerabilities": [],
            "html_url": "https://github.com/synthetic-owner/synthetic-repo/security/advisories/" + identity}


def link(url):
    return '<' + url + '>; rel="next"'


def repository(**extra):
    return {"id": 123456, "full_name": "synthetic-owner/synthetic-repo", "private": False, **extra}


class Response(io.BytesIO):
    def __init__(self, data, *, next_url=None, headers=None, url=None, status=200):
        super().__init__(data if isinstance(data, bytes) else json.dumps(data).encode())
        self.headers = dict(headers or {})
        if next_url is not None:
            self.headers["Link"] = link(next_url)
        self.url, self.status = url, status

    def geturl(self):
        return self.url


class _FixtureFetch:
    def setUp(self):
        self.enterContext(patch("urllib.request.build_opener", side_effect=AssertionError("fixture must not connect")))
        self.calls = []

    def fetch(self, responses, *, config=None, previous=None, advance=None):
        responses = iter(responses)
        def opener(request, timeout):
            self.calls.append((request.full_url, dict(request.header_items()), timeout))
            if advance is not None:
                advance(len(self.calls))
            response = next(responses)
            if response.url is None:
                response.url = request.full_url
            return response
        return fetch_source(config or source(), previous, NOW, opener=opener)


class GitHubPaginationTests(_FixtureFetch, unittest.TestCase):
    def test_pages_share_scope_and_deduplicate_identical_records_in_first_seen_order(self):
        first, second, third = [advisory(identity) for identity in IDS]
        result = self.fetch([Response([first, second], next_url=NEXT, headers={"ETag": '"page-one"'}),
                             Response([second, third], headers={"Last-Modified": NOW})],
            previous={"status": "success", "content_hash": "a" * 64, "etag": '"prior"', "last_modified": NOW})
        self.assertEqual(result["status"], "success")
        self.assertEqual([row["ids"][0] for row in result["records"]], list(IDS))
        self.assertEqual([row[0] for row in self.calls], [BASE, NEXT])
        self.assertEqual(result["pages_fetched"], 2)
        self.assertTrue(result["clear_validators"])
        self.assertIsNone(result["etag"])
        self.assertIsNone(result["last_modified"])
        for _url, headers, _timeout in self.calls:
            self.assertNotIn("If-none-match", headers)
            self.assertNotIn("If-modified-since", headers)
            self.assertNotIn("Authorization", headers)

    def test_page_two_failure_is_partial_and_cannot_refresh_from_304(self):
        for status in (304, 403, 503):
            with self.subTest(status=status):
                self.calls = []
                result = self.fetch([Response([advisory(IDS[0])], next_url=NEXT), Response(b"", status=status)],
                    previous={"status": "partial", "content_hash": "a" * 64, "etag": '"old"'})
                self.assertEqual(result["status"], "partial")
                self.assertEqual(len(result["records"]), 1)
                self.assertEqual(result["coverage"], "partial")
                self.assertEqual(result["error_code"], "unexpected_304" if status == 304 else "http_" + str(status))
                self.assertNotIn("If-none-match", self.calls[1][1])
        result = self.fetch([Response(b"", status=304)], previous={"content_hash": "a" * 64, "etag": "old"})
        self.assertEqual((result["status"], result["error_code"]), ("failed", "unexpected_304"))

    def test_conflicting_same_id_is_removed_from_partial_assertions(self):
        result = self.fetch([Response([advisory(IDS[0], "first"), advisory(IDS[1])], next_url=NEXT),
                             Response([advisory(IDS[0], "conflicting"), advisory(IDS[2])])])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["error_code"], "github_record_conflict")
        self.assertEqual([row["ids"][0] for row in result["records"]], list(IDS[1:]))
        empty = self.fetch([Response([advisory(IDS[0], "first")], next_url=NEXT),
                            Response([advisory(IDS[0], "conflicting")])])
        self.assertEqual((empty["status"], empty["coverage"], empty["records"]), ("failed", "partial", []))

    def test_global_page_limit_and_cycle_preserve_only_partial_records(self):
        result = self.fetch([Response([advisory(IDS[0])], next_url=NEXT),
                             Response([advisory(IDS[1])], next_url=LAST)], config=source(max_pages=2))
        self.assertEqual((result["status"], result["error_code"], len(self.calls)),
                         ("partial", "github_pagination_page_limit", 2))
        self.calls = []
        result = self.fetch([Response([advisory(IDS[0])], next_url=NEXT),
                             Response([advisory(IDS[1])], next_url=BASE)])
        self.assertEqual((result["status"], result["error_code"], len(self.calls)),
                         ("partial", "github_pagination_cycle", 2))

    def test_total_body_budget_is_shared_across_pages_with_at_most_one_probe_byte(self):
        bodies = [json.dumps([advisory(identity)]).encode() for identity in IDS[:2]]
        limit = sum(map(len, bodies)) - 1
        for length_header in (False, True):
            with self.subTest(length_header=length_header):
                self.calls = []
                headers = {"Content-Length": str(len(bodies[1]))} if length_header else {}
                result = self.fetch([Response(bodies[0], next_url=NEXT), Response(bodies[1], headers=headers)],
                                    config=source(max_bytes=limit))
                self.assertEqual((result["status"], result["error_code"]), ("partial", "body_too_large"))
                self.assertEqual(result["pages_fetched"], 1)
                self.assertLessEqual(result["bytes_received"], limit + 1)

    def test_second_request_receives_only_remaining_global_deadline(self):
        now = [0.0]
        def advance(count):
            now[0] += 6 if count == 1 else 5
        with patch.object(sources.time, "monotonic", side_effect=lambda: now[0]):
            result = self.fetch([Response([advisory(IDS[0])], next_url=NEXT), Response([advisory(IDS[1])])], advance=advance)
        self.assertEqual([row[2] for row in self.calls], [10.0, 4.0])
        self.assertEqual((result["status"], result["error_code"]), ("partial", "deadline_exceeded"))

    def test_next_cannot_change_origin_repository_filters_or_page_size(self):
        rejected = (NEXT.replace("api.github.com", "outside.example"),
            NEXT.replace("api.github.com", "127.0.0.1"), NEXT.replace("https://", "http://"),
            NEXT.replace("https://", "https://user:private@"), NEXT.replace("https://", "https://@"),
            NEXT.replace("synthetic-owner", "another-owner"), NEXT.replace("state=published", "state=closed"),
            NEXT.replace("per_page=100", "per_page=50"), NEXT + "#fragment", NEXT.replace("/repos/", "/%72epos/"),
            NEXT.replace("/repos/", "/repos\\"), NEXT.replace("page=2", "page=4"), NEXT + "&cursor=private")
        for target in rejected:
            with self.subTest(target=target):
                self.calls = []
                result = self.fetch([Response([advisory(IDS[0])], next_url=target)])
                self.assertEqual(result["status"], "partial")
                self.assertTrue(result["error_code"])
                self.assertEqual(len(self.calls), 1)
                self.assertNotIn("private", str(result))

    def test_initial_nonfirst_page_and_cursor_never_connect(self):
        for url in (NEXT, BASE + "&page=0", BASE + "&cursor=opaque", BASE + "&after=opaque", BASE + "&before=opaque"):
            with self.subTest(url=url):
                self.calls = []
                result = self.fetch([], config=source(url=url))
                self.assertEqual(result["status"], "failed")
                self.assertEqual(self.calls, [])
        for value in (0, True, sources.MAX_GITHUB_PAGES + 1):
            self.assertEqual(self.fetch([], config=source(max_pages=value))["error_code"], "invalid_max_pages")

    def test_malformed_duplicate_or_oversized_link_is_not_end_of_listing(self):
        invalid = ('<' + NEXT + '>; rel="next', link(NEXT) + "," + link(NEXT),
                   '<' + NEXT + '>', '<' + NEXT + '>; rel="last";',
                   "not-a-link", "x" * (sources.MAX_LINK_BYTES + 1))
        for header in invalid:
            with self.subTest(header_length=len(header)):
                self.calls = []
                result = self.fetch([Response([advisory(IDS[0])], headers={"Link": header})])
                self.assertEqual(result["status"], "partial")
                self.assertEqual(len(self.calls), 1)
        self.calls = []
        result = self.fetch([Response([advisory(IDS[0])], headers={"Link": '<' + NEXT + '>; type="application/json"; rel=next'}),
                             Response([advisory(IDS[1])])])
        self.assertEqual(result["status"], "success")

    def test_same_origin_redirect_is_rejected_and_handler_never_follows(self):
        result = self.fetch([Response([advisory(IDS[0])], url=BASE + "&page=1")])
        self.assertEqual((result["status"], result["error_code"]), ("failed", "github_redirect_rejected"))
        with self.assertRaisesRegex(SourceError, "^github_redirect_rejected$"):
            sources._GitHubRedirect().redirect_request(None, None, 302, "private", {}, NEXT)

    def test_page_two_malformed_json_retains_valid_page_one_as_partial(self):
        result = self.fetch([Response([advisory(IDS[0])], next_url=NEXT), Response(b"{private malformed body")])
        self.assertEqual((result["status"], result["error_code"]), ("partial", "parse_failed"))
        self.assertNotIn("private", str(result))

    def test_canonical_after_uses_one_independent_repo_identity_lookup_and_deduplicates(self):
        first, second = [advisory(identity) for identity in IDS[:2]]
        responses = [Response([first], next_url=AFTER), Response(repository()), Response([first, second])]
        total_bytes = sum(len(response.getvalue()) for response in responses)
        result = self.fetch(responses, config=source(max_pages=2))
        self.assertEqual((result["status"], result["pages_fetched"]), ("success", 2))
        self.assertEqual([row[0] for row in self.calls], [BASE, METADATA, AFTER])
        self.assertEqual([row["ids"][0] for row in result["records"]], list(IDS[:2]))
        self.assertEqual(result["bytes_received"], total_bytes)
        self.assertEqual(result["repository_metadata_requests"], 1)
        self.assertTrue(result["repository_id_verified"])
        for _url, headers, _timeout in self.calls:
            self.assertNotIn("Authorization", headers)
            self.assertNotIn("If-none-match", headers)
            self.assertNotIn("If-modified-since", headers)

    def test_canonical_path_cannot_be_trusted_without_exact_public_repository_mapping(self):
        invalid = [repository(id=654321), repository(id=True), repository(id="123456"),
                   repository(id=0), repository(id=2**63), repository(full_name="another-owner/synthetic-repo"),
                   repository(private=True), {"id": 123456, "full_name": repository()["full_name"]}, [], b"{private malformed"]
        for metadata in invalid:
            with self.subTest(metadata_type=type(metadata).__name__):
                self.calls = []
                result = self.fetch([Response([advisory(IDS[0])], next_url=AFTER), Response(metadata)])
                self.assertEqual((result["status"], result["error_code"], len(self.calls)),
                                 ("partial", "github_repository_identity_unverified", 2))
                self.assertEqual([row[0] for row in self.calls], [BASE, METADATA])
                self.assertFalse(result["repository_id_verified"])
                self.assertNotIn("private", str(result))

    def test_canonical_cursor_rejects_scope_changes_before_metadata_request(self):
        targets = (AFTER.replace("api.github.com", "outside.example"),
                   AFTER.replace("api.github.com", "127.0.0.1"), AFTER.replace("https://", "https://user:private@"),
                   AFTER.replace("/repositories/", "/%72epositories/"), AFTER.replace("/repositories/", "/repositories\\"),
                   AFTER.replace("state=published", "state=closed"), AFTER.replace("per_page=100", "per_page=50"),
                   AFTER + "&page=2", AFTER + "&before=private", AFTER + "&cursor=private",
                   AFTER + "&after=private", AFTER + "#fragment", CANONICAL + "&after=", CANONICAL + "&after=" + "a" * 257)
        for target in targets:
            with self.subTest(target_length=len(target)):
                self.calls = []
                result = self.fetch([Response([advisory(IDS[0])], next_url=target)])
                self.assertEqual((result["status"], len(self.calls)), ("partial", 1))
                self.assertEqual(result["repository_metadata_requests"], 0)
                self.assertNotIn("private", str(result))
        self.calls = []
        result = self.fetch([], config=source(url=CANONICAL))
        self.assertEqual((result["status"], result["error_code"], self.calls),
                         ("failed", "github_pagination_initial_page_required", []))

    def test_cursor_progress_freezes_canonical_path_mode_and_rejects_repeated_cursor(self):
        for target, reason in ((AFTER, "github_pagination_cycle"),
                               (NEXT, "github_pagination_scope_changed"),
                               (CANONICAL + "&page=3", "github_pagination_scope_changed"),
                               (AFTER_NEXT.replace("123456", "654321"), "github_pagination_scope_changed")):
            with self.subTest(reason=reason):
                self.calls = []
                result = self.fetch([Response([advisory(IDS[0])], next_url=AFTER), Response(repository()),
                                     Response([advisory(IDS[1])], next_url=target)])
                self.assertEqual((result["status"], result["error_code"], len(self.calls)), ("partial", reason, 3))
                self.assertEqual(result["repository_metadata_requests"], 1)
        self.calls = []
        result = self.fetch([Response([advisory(IDS[0])], next_url=AFTER), Response(repository()),
                             Response([advisory(IDS[1])], next_url=AFTER_NEXT), Response([advisory(IDS[2])])])
        self.assertEqual((result["status"], result["pages_fetched"], len(self.calls)), ("success", 3, 4))
        self.assertEqual(result["repository_metadata_requests"], 1)

    def test_named_cursor_and_page_modes_cannot_switch_after_first_continuation(self):
        named_after = AFTER.replace(CANONICAL, BASE)
        for first_next, second_next in ((NEXT, named_after), (named_after, LAST), (NEXT, AFTER_NEXT)):
            with self.subTest(first_next=first_next):
                self.calls = []
                result = self.fetch([Response([advisory(IDS[0])], next_url=first_next),
                                     Response([advisory(IDS[1])], next_url=second_next)])
                self.assertEqual((result["status"], result["error_code"], len(self.calls)),
                                 ("partial", "github_pagination_scope_changed", 2))
                self.assertEqual(result["repository_metadata_requests"], 0)

    def test_identity_lookup_and_advisory_page_share_total_body_and_deadline_budgets(self):
        body = json.dumps([advisory(IDS[0])]).encode()
        metadata = json.dumps(repository()).encode()
        for length_header in (False, True):
            with self.subTest(length_header=length_header):
                self.calls = []
                limit = len(body) + len(metadata) - 1
                headers = {"Content-Length": str(len(metadata))} if length_header else {}
                result = self.fetch([Response(body, next_url=AFTER), Response(metadata, headers=headers)],
                                    config=source(max_bytes=limit))
                self.assertEqual((result["status"], result["error_code"], result["pages_fetched"], len(self.calls)),
                                 ("partial", "body_too_large", 1, 2))
                self.assertLessEqual(result["bytes_received"], limit + 1)
        self.calls = []
        now = [0.0]
        def advance(count):
            now[0] += 3 if count == 1 else 4
        with patch.object(sources.time, "monotonic", side_effect=lambda: now[0]):
            result = self.fetch([Response(body, next_url=AFTER), Response(metadata), Response([advisory(IDS[1])])], advance=advance)
        self.assertEqual([row[2] for row in self.calls], [10.0, 7.0, 3.0])
        self.assertEqual((result["status"], result["error_code"], result["pages_fetched"]), ("partial", "deadline_exceeded", 1))

    def test_failed_or_redirected_metadata_is_partial_and_page_quota_never_triggers_lookup(self):
        for response, reason in ((Response(b"", status=304), "unexpected_304"),
                                 (Response(b"", status=403), "http_403"),
                                 (Response(repository(), url=METADATA + "/renamed"), "github_redirect_rejected")):
            with self.subTest(reason=reason):
                self.calls = []
                result = self.fetch([Response([advisory(IDS[0])], next_url=AFTER), response])
                self.assertEqual((result["status"], result["error_code"], len(self.calls)), ("partial", reason, 2))
                self.assertFalse(result["repository_id_verified"])
        self.calls = []
        result = self.fetch([Response([advisory(IDS[0])], next_url=AFTER)], config=source(max_pages=1))
        self.assertEqual((result["status"], result["error_code"], len(self.calls)),
                         ("partial", "github_pagination_page_limit", 1))
        self.assertEqual(result["repository_metadata_requests"], 0)


class GitHubPaginationCacheTests(_FixtureFetch, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "intelligence.sqlite3"
        self.store = IntelligenceStore(self.path, cooldown_seconds=0)

    def legacy_complete(self):
        result = self.fetch([Response([advisory(IDS[0]), advisory(IDS[1])])])
        result.update(etag='"legacy-first-page"', last_modified=NOW, clear_validators=False)
        self.store.record_fetch(source(), result, NOW)
        return result

    def test_max_pages_budget_preserves_legacy_cache_and_partial_baseline(self):
        configured = sources._source(source())
        self.assertEqual(configured["max_pages"], 5)
        legacy = dict(configured)
        legacy.pop("max_pages")
        complete = self.fetch([Response([advisory(IDS[0]), advisory(IDS[1])])], config=legacy)
        self.store.record_fetch(legacy, complete, NOW)
        before = self.store.source_state(legacy["id"], NOW)
        self.assertEqual(self.store.due_sources([configured], "2026-10-26T00:00:01Z"), [])
        failed = self.fetch([Response(b"", status=503)], config=configured)
        self.store.record_fetch(configured, failed, LATER)
        current = self.store.source_state(configured["id"], LATER)
        self.assertTrue(current["cache_matches_config"])
        self.assertEqual(current["last_success"], before["last_success"])
        self.assertEqual(current["cached_records"], before["cached_records"])
        with closing(sqlite3.connect(self.path)) as db:
            last_good = db.execute("SELECT cached_records,content_hash,last_success FROM sources").fetchone()
        reduced = {**configured, "max_pages": 2}
        partial = self.fetch([Response([advisory(IDS[2])], next_url=NEXT),
                              Response([], next_url=LAST)], config=reduced)
        self.assertEqual((partial["status"], partial["error_code"]),
                         ("partial", "github_pagination_page_limit"))
        self.store.record_fetch(reduced, partial, "2026-10-26T00:02:00Z")
        current = self.store.source_state(reduced["id"], "2026-10-26T00:02:00Z")
        self.assertTrue(current["cache_matches_config"])
        self.assertTrue(current["has_partial_cache"])
        self.assertEqual(current["freshness"], "unknown")
        self.assertEqual(current["last_success"], before["last_success"])
        self.assertEqual(current["content_hash"], complete["content_hash"])
        self.assertEqual({row["ids"][0] for row in current["cached_records"]}, set(IDS))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT cached_records,content_hash,last_success FROM sources").fetchone(), last_good)

    def test_complete_paginated_result_clears_preexisting_page_one_validators(self):
        self.legacy_complete()
        result = self.fetch([Response([advisory(IDS[0])], next_url=NEXT), Response([advisory(IDS[1])])])
        self.store.record_fetch(source(), result, LATER)
        state = self.store.source_state(source()["id"], LATER)
        self.assertIsNone(state["etag"])
        self.assertIsNone(state["last_modified"])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT etag,last_modified FROM sources").fetchone(), (None, None))
        self.assertEqual(state["status"], "success")

    def test_partial_preserves_full_cache_and_304_cannot_complete_it(self):
        self.legacy_complete()
        with closing(sqlite3.connect(self.path)) as db:
            old = db.execute("SELECT cached_records,etag,last_modified,content_hash,last_success FROM sources").fetchone()
        partial = self.fetch([Response([advisory(IDS[2])], next_url=NEXT), Response(b"", status=503)])
        self.store.record_fetch(source(), partial, LATER)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT cached_records,etag,last_modified,content_hash,last_success FROM sources").fetchone(), old)
        state = self.store.source_state(source()["id"], LATER)
        self.assertTrue(state["has_partial_cache"])
        self.assertEqual(state["freshness"], "unknown")
        result = self.fetch([Response(b"", status=304)], previous=state)
        self.assertEqual((result["status"], result["error_code"]), ("failed", "unexpected_304"))
        self.store.record_fetch(source(), result, "2026-10-26T00:02:00Z")
        self.assertTrue(self.store.source_state(source()["id"], "2026-10-26T00:02:00Z")["has_partial_cache"])

    def test_validator_clear_policy_must_be_boolean(self):
        result = self.fetch([Response([advisory(IDS[0])])])
        result["clear_validators"] = 1
        with self.assertRaisesRegex(IntelligenceError, "invalid_cache_validator_policy"):
            self.store.record_fetch(source(), result, NOW)
