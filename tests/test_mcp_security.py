"""Offline security tests. All tokens/keys below are public test fixtures."""
import base64
import ctypes
import hashlib
import hmac
import io
import os
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

from contrib.mcp_bridge.security import BearerAuth, Principal, sign_headers, validate_secret
from contrib.mcp_bridge.network import SafeHTTPSPoster
from contrib.mcp_bridge.vault import DPAPIVault


KEY = "whsec_" + base64.b64encode(bytes(range(32))).decode()
OLD_KEY = "whsec_" + base64.b64encode(b"x" * 24).decode()
TOKEN = "public-test-fixture-not-a-real-token-12345"


class MemoryVault:
    """Test double only; deliberately absent from the product package."""
    def __init__(self):
        self.values = {}

    def put(self, secret):
        reference = "fixture_ref_" + str(len(self.values))
        self.values[reference] = secret
        return reference

    def get(self, reference):
        return self.values[reference]


class SecurityTests(unittest.TestCase):
    def auth(self, records=None, environ=None):
        return BearerAuth(records if records is not None else [{"principal_id": "alice", "host_refs": ["host_1"],
                         "roles": ["subscriber"], "token_env": "EG_TEST_TOKEN"}],
                         {"EG_TEST_TOKEN": TOKEN} if environ is None else environ)

    def test_bearer_scoped_principal(self):
        self.assertEqual(self.auth().authenticate("Bearer " + TOKEN),
                         Principal("alice", frozenset({"host_1"}), frozenset({"subscriber"})))
        self.assertIsNotNone(self.auth().authenticate("bearer " + TOKEN))

    def test_only_named_env_is_read_and_only_digest_retained(self):
        class NamedOnly(dict):
            def get(self, name):
                self_name = name
                if self_name != "EG_TEST_TOKEN":
                    raise AssertionError("unconfigured environment access")
                return TOKEN
        auth = self.auth(environ=NamedOnly())
        self.assertNotIn(TOKEN, repr(vars(auth)))
        self.assertEqual(auth._records[0][0], hashlib.sha256(TOKEN.encode()).digest())

    def test_missing_short_malformed_tokens_fail_closed(self):
        for env in ({}, {"EG_TEST_TOKEN": "short"}, {"EG_TEST_TOKEN": "x" * 31}, {"EG_TEST_TOKEN": "x" * 32 + "\n"}):
            self.assertIsNone(self.auth(environ=env).authenticate("Bearer " + TOKEN))
        for header in (None, "", TOKEN, "Basic " + TOKEN, "Bearer  " + TOKEN, "Bearer " + TOKEN + "\r\n", "Bearer short"):
            self.assertIsNone(self.auth().authenticate(header))

    def test_auth_uses_constant_time_digest_compare(self):
        with patch("contrib.mcp_bridge.security.hmac.compare_digest", wraps=hmac.compare_digest) as compare:
            self.auth().authenticate("Bearer " + TOKEN)
            self.assertTrue(compare.called)
            self.assertEqual(len(compare.call_args.args[0]), 32)

    def test_duplicate_token_conflicting_owner_denied(self):
        records = [{"principal_id": p, "host_refs": ["h"], "roles": ["producer"], "token_env": "EG_TEST_TOKEN"}
                   for p in ("alice", "bob")]
        self.assertIsNone(self.auth(records).authenticate("Bearer " + TOKEN))

    def test_invalid_records_never_grant(self):
        for field, bad in (("principal_id", "../alice"), ("host_refs", []), ("roles", "subscriber"), ("token_env", "../TOKEN")):
            record = {"principal_id": "alice", "host_refs": ["h"], "roles": ["subscriber"], "token_env": "EG_TEST_TOKEN"}
            record[field] = bad
            self.assertIsNone(self.auth([record]).authenticate("Bearer " + TOKEN))

    def test_webhook_secret_bounds_and_fixed_errors(self):
        for size in (24, 32, 64):
            self.assertEqual(len(validate_secret("whsec_" + base64.b64encode(b"x" * size).decode())), size)
        for secret in (None, "", "whsec_bad!", "whsec_" + base64.b64encode(b"x" * 23).decode(),
                       "whsec_" + base64.b64encode(b"x" * 65).decode(), KEY + "\n"):
            with self.assertRaisesRegex(ValueError, "^invalid_webhook_secret$"):
                validate_secret(secret)

    def test_known_hmac_exact_bytes_and_rotation(self):
        body = b'{"synthetic":true}'
        headers = sign_headers(KEY, "evt_1", body, "sub_1", 123, OLD_KEY)
        expected = []
        for key in (KEY, OLD_KEY):
            digest = hmac.new(validate_secret(key), b"evt_1.123." + body, hashlib.sha256).digest()
            expected.append("v1," + base64.b64encode(digest).decode())
        self.assertEqual(headers["webhook-signature"], " ".join(expected))
        self.assertNotEqual(headers["webhook-signature"], sign_headers(KEY, "evt_1", body + b" ", "sub_1", 123)["webhook-signature"])
        self.assertEqual(sign_headers(KEY, "evt_1", body, "sub_1", 123, KEY)["webhook-signature"].count("v1,"), 1)

    def test_sign_header_injection_and_size_rejected(self):
        for args in ((KEY, "evt\r\nx", b"{}", "sub", 1), (KEY, "evt", b"{}", "sub\n", 1),
                     (KEY, "evt", b"x" * 8193, "sub", 1), (KEY, "evt", b"{}", "sub", True)):
            with self.assertRaisesRegex(ValueError, "^invalid_signature_input$"):
                sign_headers(*args)


class FakeSocket:
    def __init__(self, response=b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}"):
        self.response = io.BytesIO(response)
        self.connected = None
        self.sent = b""
        self.closed = False
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def connect(self, sockaddr):
        self.connected = sockaddr

    def sendall(self, data):
        self.sent += data

    def recv_into(self, buffer):
        data = self.response.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)

    def close(self):
        self.closed = True


class FakeContext:
    check_hostname = True
    verify_mode = ssl.CERT_REQUIRED

    def __init__(self):
        self.server_hostname = None

    def wrap_socket(self, sock, server_hostname):
        self.server_hostname = server_hostname
        return sock


class NetworkTests(unittest.TestCase):
    def poster(self, response=None, addresses=None, **kwargs):
        self.sock = FakeSocket() if response is None else FakeSocket(response)
        self.context = FakeContext()
        self.resolver = Mock(return_value=addresses or [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))])
        self.factory = Mock(return_value=self.sock)
        return SafeHTTPSPoster(["receiver.example.com"], enabled=True, resolver=self.resolver,
                               socket_factory=self.factory, context_factory=lambda: self.context, **kwargs)

    def test_disabled_has_zero_dns_and_socket_activity(self):
        resolver, factory = Mock(), Mock()
        p = SafeHTTPSPoster(["receiver.example.com"], resolver=resolver, socket_factory=factory)
        with self.assertRaisesRegex(PermissionError, "^transport_disabled$"):
            p.post("https://receiver.example.com/", b"{}", {})
        resolver.assert_not_called()
        factory.assert_not_called()

    def test_pins_validated_ip_preserves_tls_hostname_exact_body(self):
        p = self.poster()
        headers = sign_headers(KEY, "evt", b"{}", "sub", 123)
        self.assertEqual(p.post("https://receiver.example.com/callback?q=1", b"{}", headers), {"status": 200, "body": b"{}"})
        self.assertEqual(self.sock.connected, ("8.8.8.8", 443))
        self.assertEqual(self.context.server_hostname, "receiver.example.com")
        self.assertTrue(self.sock.sent.endswith(b"\r\n\r\n{}"))
        self.assertIn(b"Host: receiver.example.com\r\n", self.sock.sent)
        self.assertTrue(self.sock.closed)
        self.assertEqual(self.resolver.call_count, 1)

    def test_invalid_urls_rejected_before_dns(self):
        p = self.poster()
        for url in ("http://receiver.example.com/", "https://receiver.example.com:444/", "https://user@receiver.example.com/",
                    "https://receiver.example.com/#x", "https://receiver.example.com/#", "https://receiver.example.com/\r\n",
                    "https://receiver.example.com/%0dX", "https://receiver.example.com.evil.org/", "https://other.example.com/",
                    "https://receiver.example.com\\@evil.org/", "https://receiver.example.com./"):
            with self.assertRaisesRegex(ValueError, "^invalid_callback_url$"):
                p.post(url, b"{}", {})
        self.resolver.assert_not_called()

    def test_private_loopback_linklocal_reserved_or_mixed_dns_refused(self):
        for address in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "fc00::1", "fe80::1", "192.0.2.1", "0.0.0.0"):
            p = self.poster(addresses=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
            with self.assertRaisesRegex(OSError, "^callback_transport_failed$"):
                p.post("https://receiver.example.com/", b"{}", {})
            self.factory.assert_not_called()
        p = self.poster(addresses=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ("8.8.8.8", "127.0.0.1")])
        with self.assertRaises(OSError):
            p.post("https://receiver.example.com/", b"{}", {})
        self.factory.assert_not_called()

    def test_resolves_every_attempt_not_cached(self):
        p = self.poster()
        p.post("https://receiver.example.com/", b"{}", {})
        self.resolver.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with self.assertRaises(OSError):
            p.post("https://receiver.example.com/", b"{}", {})
        self.assertEqual(self.resolver.call_count, 2)
        self.assertEqual(self.factory.call_count, 1)

    def test_redirect_not_followed(self):
        p = self.poster(b"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1/\r\nContent-Length: 0\r\n\r\n")
        with self.assertRaisesRegex(ValueError, "^callback_redirect_refused$"):
            p.post("https://receiver.example.com/", b"{}", {})
        self.assertEqual(self.resolver.call_count, 1)

    def test_request_response_and_headers_are_bounded(self):
        p = self.poster()
        with self.assertRaisesRegex(ValueError, "^invalid_callback_body$"):
            p.post("https://receiver.example.com/", b"x" * 8193, {})
        for headers in ({"Host": "evil"}, {"webhook-id": "a\r\nHost: evil"}, {"webhook-id": "x" * 2049}):
            with self.assertRaisesRegex(ValueError, "^invalid_callback_headers$"):
                p.post("https://receiver.example.com/", b"{}", headers)
        self.resolver.assert_not_called()
        p = self.poster(b"HTTP/1.1 200 OK\r\nContent-Length: 4097\r\n\r\n" + b"x" * 4097)
        with self.assertRaisesRegex(ValueError, "^callback_response_too_large$"):
            p.post("https://receiver.example.com/", b"{}", {})

    def test_dns_timeout_tls_and_raw_errors_are_sanitized(self):
        p = self.poster()
        self.resolver.side_effect = RuntimeError("secret callback url details")
        with self.assertRaisesRegex(OSError, "^callback_transport_failed$"):
            p.post("https://receiver.example.com/", b"{}", {})
        p = self.poster()
        self.context.check_hostname = False
        with self.assertRaisesRegex(OSError, "^callback_transport_failed$"):
            p.post("https://receiver.example.com/", b"{}", {})
        self.assertTrue(self.sock.closed)
        for timeout in (0, -1, 11, True):
            with self.assertRaisesRegex(ValueError, "^invalid_transport_timeout$"):
                SafeHTTPSPoster([], timeout=timeout)

    def test_read_deadline_and_header_cap(self):
        ticks = iter([0, 0, 0, 0, 11])
        p = self.poster(clock=lambda: next(ticks))
        with self.assertRaisesRegex(OSError, "^callback_transport_failed$"):
            p.post("https://receiver.example.com/", b"{}", {})

    def test_dns_wait_is_bounded_without_overlapping_stuck_lookups(self):
        entered, release = threading.Event(), threading.Event()
        def resolver(*args, **kwargs):
            entered.set()
            release.wait(1)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        p = self.poster(timeout=0.02)
        p.resolver = resolver
        try:
            with self.assertRaisesRegex(OSError, "^callback_transport_failed$"):
                p.post("https://receiver.example.com/", b"{}", {})
            self.assertTrue(entered.is_set())
            self.assertTrue(p.pending_dns)
            with self.assertRaisesRegex(OSError, "^callback_transport_failed$"):
                p.post("https://receiver.example.com/", b"{}", {})
            self.factory.assert_not_called()
        finally:
            release.set()
            p._dns_pending.wait(1)
        self.assertFalse(p.pending_dns)

    def test_stuck_resolver_slots_are_shared_across_instances(self):
        release = threading.Event()
        started = []
        def resolver(*args, **kwargs):
            started.append(True)
            release.wait(2)
            return []
        posters = [self.poster(timeout=0.01) for _ in range(5)]
        try:
            for p in posters:
                p.resolver = resolver
                with self.assertRaisesRegex(OSError, "^callback_transport_failed$"):
                    p.post("https://receiver.example.com/", b"{}", {})
            self.assertEqual(len(started), 4)
        finally:
            release.set()
            for p in posters:
                if p._dns_pending is not None:
                    p._dns_pending.wait(1)
        p = self.poster(b"HTTP/1.1 200 OK\r\nX-Long: " + b"x" * 20000 + b"\r\n\r\n")
        with self.assertRaisesRegex(OSError, "^callback_transport_failed$"):
            p.post("https://receiver.example.com/", b"{}", {})


class VaultTests(unittest.TestCase):
    def test_non_windows_fails_closed(self):
        with patch("contrib.mcp_bridge.vault.os.name", "posix"):
            with self.assertRaisesRegex(OSError, "^vault_platform_unsupported$"):
                DPAPIVault("never-created")

    @unittest.skipUnless(os.name == "nt", "Windows local path policy")
    def test_vault_rejects_network_device_root_and_stream_paths(self):
        with patch("contrib.mcp_bridge.vault.ctypes.WinDLL") as win_dll:
            for directory in ("\\\\server\\share\\vault", "\\\\?\\C:\\vault", "C:\\", "C:\\vault:stream", "..\\vault"):
                with self.assertRaisesRegex(ValueError, "^invalid_vault_directory$"):
                    DPAPIVault(directory)
            win_dll.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows drive type policy")
    def test_vault_rejects_mapped_or_removable_drive_before_file_io(self):
        for kind in (0, 1, 2, 4, 5, 6):
            kernel = Mock()
            kernel.GetDriveTypeW.return_value = kind
            with patch("contrib.mcp_bridge.vault.ctypes.WinDLL", return_value=kernel):
                with self.assertRaisesRegex(ValueError, "^invalid_vault_directory$"):
                    DPAPIVault("Z:\\vault")
            kernel.CreateFileW.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI test")
    def test_dpapi_roundtrip_no_plaintext_and_opaque_refs(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = DPAPIVault(Path(folder) / "vault")
            ref = vault.put(KEY)
            self.assertRegex(ref, r"^v1_[0-9a-f]{32}$")
            self.assertEqual(vault.get(ref), KEY)
            self.assertNotIn(KEY.encode(), (vault.directory / (ref + ".bin")).read_bytes())
            self.assertEqual(DPAPIVault(vault.directory).get(ref), KEY)
            for bad in ("../secret", str(vault.directory / ref), "v1_" + "z" * 32, None):
                with self.assertRaisesRegex(ValueError, "^invalid_vault_reference$"):
                    vault.get(bad)

    @unittest.skipUnless(os.name == "nt", "Windows vault file policy")
    def test_vault_capacity_and_corrupt_ciphertext(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = DPAPIVault(Path(folder) / "vault")
            ref = vault.put(KEY)
            path = vault.directory / (ref + ".bin")
            path.write_bytes(b"not-dpapi")
            with self.assertRaisesRegex(OSError, "^vault_read_failed$"):
                vault.get(ref)
            for index in range(127):
                (vault.directory / ("non-secret-fixture-" + str(index))).touch()
            with self.assertRaisesRegex(OSError, "^vault_capacity_reached$"):
                vault.put(KEY)

    @unittest.skipUnless(os.name == "nt", "Windows reparse handle policy")
    def test_reparse_handle_is_refused_without_read(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = DPAPIVault(folder)
            class Kernel:
                closed = False
                def CreateFileW(self, *args):
                    return 101
                def GetFileInformationByHandleEx(self, handle, kind, pointer, size):
                    pointer._obj.attributes = 0x400
                    return 1
                def CloseHandle(self, handle):
                    self.closed = True
            kernel = Kernel()
            vault._kernel = kernel
            with self.assertRaisesRegex(OSError, "^vault_reparse_refused$"):
                vault._open(Path(folder) / "ref.bin", 0, 0, 3, 0)
            self.assertTrue(kernel.closed)


if __name__ == "__main__":
    unittest.main()
