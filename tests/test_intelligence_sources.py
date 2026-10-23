"""Offline source contracts. These fixtures are not a live-source acceptance."""
import hashlib
import io
import json
import ssl
import tempfile
import unittest
import urllib.error
from pathlib import Path

from eventguard.intelligence.sources import SourceError, fetch_source, load_config, parse_source

FIXTURES = Path(__file__).parent / "fixtures" / "intelligence_sources"
NOW = "2026-10-23T05:00:00Z"


def source(adapter="osv", **extra):
    return {"id": "synthetic-source", "adapter": adapter, "url": "https://example.org/advisory", **extra}


class Response(io.BytesIO):
    def __init__(self, body, *, status=200, headers=None, url="https://example.org/advisory"):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}
        self.url = url

    def geturl(self):
        return self.url


class IntelligenceSourcesTests(unittest.TestCase):
    def test_default_configuration_is_static_and_bounded(self):
        config = load_config(Path(__file__).parents[1] / "config" / "advisories.json")
        self.assertEqual(config["inventory"]["paths"], [])
        self.assertIn("zdi", {s["adapter"] for s in config["sources"]})
        self.assertIn("rustsec", {s["adapter"] for s in config["sources"]})
        self.assertLessEqual(len(config["sources"]), 64)

    def test_osv_preserves_alias_and_semver_boundaries(self):
        record = parse_source((FIXTURES / "advisory.json").read_bytes(), source())[0]
        self.assertEqual(record["ids"], ["CVE-2026-111943", "RUSTSEC-2026-0381"])
        self.assertEqual(record["affected"][0]["ranges"][0]["events"][-1], {"fixed": "1.0.10"})
        self.assertEqual(record["fixes"][0]["stage"], "released")
        self.assertEqual(record["exploitation"], "unknown")

    def test_rustsec_preserves_prerelease_requirements(self):
        record = parse_source((FIXTURES / "rustsec.md").read_bytes(), source("rustsec"))[0]
        self.assertEqual(record["affected"][0]["patched"], [">= 0.103.16, < 0.104.0-alpha.1", ">= 0.104.0-alpha.8"])
        self.assertEqual(record["conditions"]["deployment"], "unknown")

    def test_git_fix_commit_does_not_prove_merge_or_release(self):
        data = {"id": "CVE-2026-111943", "affected": [{"package": {"ecosystem": "Linux", "name": "linux"}, "ranges": [{"type": "GIT", "events": [{"introduced": "0"}, {"fixed": "a" * 40}]}]}]}
        record = parse_source(json.dumps(data).encode(), source())[0]
        self.assertEqual(record["fixes"][0]["stage"], "unknown")
        self.assertEqual(record["fixes"][0]["commit"], "a" * 40)
        self.assertIsNone(record["fixes"][0]["version"])

    def test_rustsec_wrapper_requires_independent_parent_evidence(self):
        body = (FIXTURES / "rustsec.md").read_text().replace("rustls-webpki", "webpki-roots").replace('[versions]', '[versions]\nunaffected = ["= 0.26.11"]')
        record = parse_source(body.encode(), source("rustsec"))[0]
        self.assertEqual(record["conditions"]["compatibility_wrapper"]["parent_min_version"], "1.0.10")

    def test_zdi_connman_is_not_kernel_and_dates_not_publication(self):
        records = parse_source((FIXTURES / "zdi.html").read_bytes(), source("zdi"))
        by_id = {record["ids"][0]: record for record in records}
        self.assertEqual(by_id["ZDI-CAN-32005"]["component"], "connman")
        self.assertEqual(by_id["ZDI-CAN-33549"]["component"], "linux-kernel")
        self.assertIsNone(by_id["ZDI-CAN-33549"]["published_at"])
        self.assertEqual(by_id["ZDI-CAN-33549"]["conditions"]["vendor_notified_at"], "2026-10-21")
        self.assertNotIn("CVE-2026-999999", str(records))

    def test_zdi_changed_format_is_explicit_failure(self):
        with self.assertRaisesRegex(SourceError, "zdi_format_changed"):
            parse_source(b"<h1>Unrelated page</h1>", source("zdi"))

    def test_zdi_missing_all_tracked_ids_is_not_empty_success(self):
        with self.assertRaisesRegex(SourceError, "tracked_ids_missing"):
            parse_source((FIXTURES / "zdi.html").read_bytes(), source("zdi", tracking_ids=["ZDI-CAN-99999"]))

    def test_zdi_missing_one_tracked_id_is_not_complete_success(self):
        with self.assertRaisesRegex(SourceError, "tracked_ids_missing"):
            parse_source((FIXTURES / "zdi.html").read_bytes(), source("zdi", tracking_ids=["ZDI-CAN-33549", "ZDI-CAN-99999"]))

    def test_explicit_larger_zdi_limit_and_tail_are_not_truncated(self):
        body = b"<html><p>" + b"x" * (2 * 1024 * 1024) + b"</p>" + (FIXTURES / "zdi.html").read_bytes() + b"</html>"
        config = source("zdi", max_bytes=4 * 1024 * 1024, tracking_ids=["ZDI-CAN-33549", "ZDI-CAN-32005"])
        records = parse_source(body, config)
        self.assertEqual({r["ids"][0] for r in records}, {"ZDI-CAN-33549", "ZDI-CAN-32005"})
        with self.assertRaisesRegex(SourceError, "invalid_max_bytes"):
            parse_source(body, source("zdi", max_bytes=9 * 1024 * 1024))

    def test_feed_parses_ids_but_does_not_infer_version_fix(self):
        records = parse_source((FIXTURES / "feed.xml").read_bytes(), source("feed"))
        self.assertEqual({record["ids"][0] for record in records}, {"CVE-2026-111943", "RUSTSEC-2026-0382"})
        self.assertTrue(all(len(record["ids"]) == 1 for record in records))
        self.assertTrue(all(record["fixes"] == [] for record in records))
        self.assertTrue(all(record["published_at"] == "2026-10-20T12:00:00Z" for record in records))

    def test_feed_rejects_entities(self):
        with self.assertRaisesRegex(SourceError, "unsafe_xml"):
            parse_source(b'<!DOCTYPE x [<!ENTITY a "x">]><rss/>', source("feed"))

    def test_generic_html_does_not_merge_cooccurring_ids(self):
        records = parse_source(b"<h1>Official advisory index</h1><p>ZDI-CAN-33549 ZDI-CAN-32005</p>", source("html", html_markers=["Official advisory"]))
        self.assertEqual(len(records), 2)
        self.assertTrue(all(len(record["ids"]) == 1 for record in records))
        self.assertTrue(all(record["fixes"] == [] for record in records))

    def test_generic_html_requires_literal_marker(self):
        with self.assertRaisesRegex(SourceError, "html_format_changed"):
            parse_source(b"<p>ZDI-CAN-33549</p>", source("html", html_markers=["Expected official heading"]))

    def test_github_preserves_version_requirement(self):
        data = [{"ghsa_id": "GHSA-hq85-5cpj-mr62", "summary": "Synthetic uv notice", "html_url": "https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62", "vulnerabilities": [{"package": {"ecosystem": "pip", "name": "uv"}, "vulnerable_version_range": "< 0.13.4", "first_patched_version": "0.13.4"}]}]
        record = parse_source(json.dumps(data).encode(), source("github_advisories"))[0]
        self.assertEqual(record["affected"][0]["vulnerable_requirement"], "< 0.13.4")
        self.assertEqual(record["fixes"][0]["version"], "0.13.4")
        self.assertEqual(record["exploitation"], "unknown")

    def test_cve_rejection_is_withdrawn_not_unaffected(self):
        data = {"dataType": "CVE_RECORD", "cveMetadata": {"cveId": "CVE-2026-111943", "state": "REJECTED"}, "containers": {"cna": {}}}
        record = parse_source(json.dumps(data).encode(), source("cve"))[0]
        self.assertTrue(record["withdrawn"])
        self.assertEqual(record["fixes"], [])

    def test_success_sends_conditionals_and_returns_body_hash(self):
        body = (FIXTURES / "advisory.json").read_bytes()
        calls = []
        def open_(request, timeout):
            calls.append((request, timeout))
            return Response(body, headers={"ETag": '"revision-2"', "Last-Modified": "Fri, 23 Oct 2026 00:00:00 GMT"})
        result = fetch_source(source(), {"etag": '"revision-1"', "last_modified": "Thu, 22 Oct 2026 00:00:00 GMT"}, NOW, opener=open_)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["content_hash"], hashlib.sha256(body).hexdigest())
        self.assertEqual(result["fetched_at"], NOW)
        self.assertEqual(calls[0][0].get_header("If-none-match"), '"revision-1"')
        self.assertLessEqual(calls[0][1], 30)

    def test_304_requires_cache_and_does_not_invent_records(self):
        def open_(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 304, "untrusted text", {}, None)
        result = fetch_source(source(), {"content_hash": "a" * 64, "etag": '"one"'}, NOW, opener=open_)
        self.assertEqual(result["status"], "not_modified")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["content_hash"], "a" * 64)
        self.assertEqual(fetch_source(source(), {}, NOW, opener=open_)["error_code"], "unexpected_304")

    def test_429_returns_retry_after_without_retrying(self):
        calls = []
        def open_(request, timeout):
            calls.append(1)
            raise urllib.error.HTTPError(request.full_url, 429, "private raw server error", {"Retry-After": "120"}, None)
        result = fetch_source(source(), now=NOW, opener=open_)
        self.assertEqual(result["error_code"], "http_429")
        self.assertEqual(result["retry_after_seconds"], 120)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("private raw", str(result))

    def test_http_date_retry_after_is_clamped(self):
        def open_(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 503, "x", {"Retry-After": "Sat, 24 Oct 2026 05:00:00 GMT"}, None)
        self.assertEqual(fetch_source(source(), now=NOW, opener=open_)["retry_after_seconds"], 86400)

    def test_content_limit_rejects_header_and_stream(self):
        for headers in ({"Content-Length": "999999999"}, {}):
            result = fetch_source(source(max_bytes=128), now=NOW, opener=lambda *a, **kw: Response(b"x" * 129, headers=headers))
            self.assertEqual(result["error_code"], "body_too_large")

    def test_redirect_cannot_escape_source_origin(self):
        result = fetch_source(source(), now=NOW, opener=lambda *a, **kw: Response(b"{}", url="https://other.example/advisory"))
        self.assertEqual(result["error_code"], "cross_origin_redirect")

    def test_transport_error_contains_no_exception_text(self):
        def open_(request, timeout):
            raise urllib.error.URLError("private proxy endpoint and credential")
        result = fetch_source(source(), now=NOW, opener=open_)
        self.assertEqual(result["error_code"], "transport_error")
        self.assertNotIn("credential", str(result))

    def test_timeout_tls_and_proxy_reasons_are_fixed_codes(self):
        for reason, expected in ((TimeoutError("private host"), "timeout"),
                                 (ssl.SSLCertVerificationError(1, "private certificate"), "tls_verification_failed"),
                                 (OSError("Tunnel connection failed: 403 Forbidden private proxy"), "proxy_connect_403")):
            def open_(request, timeout):
                raise urllib.error.URLError(reason)
            result = fetch_source(source(), now=NOW, opener=open_)
            self.assertEqual(result["error_code"], expected)
            self.assertNotIn("private", str(result))

    def test_header_injection_is_not_forwarded(self):
        def open_(request, timeout):
            self.assertIsNone(request.get_header("If-none-match"))
            return Response((FIXTURES / "advisory.json").read_bytes())
        self.assertEqual(fetch_source(source(), {"etag": "one\r\nAuthorization: private"}, NOW, opener=open_)["status"], "success")

    def test_malformed_content_is_explicit_parse_failure(self):
        for body in (b"{not json", b"{\"id\":\"CVE-2026-111943\"}", b"\xff"):
            result = fetch_source(source(), now=NOW, opener=lambda *a, **kw: Response(body))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["records"], [])
            self.assertTrue(result["error_code"])

    def test_config_rejects_private_http_and_excessive_frequency(self):
        for extra in ({"url": "http://example.org/a"}, {"url": "https://127.0.0.1/a"}, {"url": "https://localhost/a"}, {"url": "https://user:secret@example.org/a"}, {"interval_seconds": 1}):
            result = fetch_source(source(**extra), now=NOW, opener=lambda *a, **kw: self.fail("must not connect"))
            self.assertEqual(result["status"], "failed")

    def test_bad_explicit_config_fails_and_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"schema_version": 1, "sources": [source(), source()]}))
            with self.assertRaisesRegex(SourceError, "duplicate_source_id"):
                load_config(path)

    def test_configuration_policy_and_event_rules_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for extra in ({"namespace": "other"}, {"storage": {"max_bytes": 1}}, {"storage": {"max_records": True}},
                          {"rules": {"enabled_reasons": ["execute_command"], "severity": {}}},
                          {"rules": {"enabled_reasons": [], "severity": {"source_stale": ["high"]}}}):
                path.write_text(json.dumps({"schema_version": 1, "sources": [source()], **extra}))
                with self.assertRaises(SourceError):
                    load_config(path)
            path.write_text(json.dumps({"schema_version": 1, "failure_threshold": 5, "sources": [source(enabled=False)]}))
            config = load_config(path)
            self.assertFalse(config["sources"][0]["enabled"])
            self.assertEqual(config["sources"][0]["failure_threshold"], 5)
            self.assertIn("source_stale", config["rules"]["enabled_reasons"])

    def test_repository_patch_field_and_pagination_limit_are_explicit(self):
        data = [{"ghsa_id": "GHSA-hq85-5cpj-mr62", "vulnerabilities": [{"package": {"ecosystem": "pip", "name": "uv"}, "vulnerable_version_range": "< 0.13.4", "patched_versions": "0.13.4"}]}]
        record = parse_source(json.dumps(data).encode(), source("github_advisories"))[0]
        self.assertEqual(record["fixes"][0]["version"], "0.13.4")
        result = fetch_source(source("github_advisories"), now=NOW, opener=lambda *a, **kw: Response(b"[]", headers={"Link": '<https://example.org/advisory?page=2>; rel="next"'}))
        self.assertEqual(result["error_code"], "pagination_required")


if __name__ == "__main__":
    unittest.main()
