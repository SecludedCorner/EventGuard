"""Opt-in HTTPS callback POST with DNS pinning and no redirect handling."""
from __future__ import annotations

import http.client
import io
import ipaddress
import re
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit


_HOST = re.compile(r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_HEADERS = {"content-type", "webhook-id", "webhook-timestamp", "webhook-signature", "x-mcp-subscription-id"}
_DNS_SLOTS = threading.BoundedSemaphore(4)


def _hostname(value):
    if not isinstance(value, str) or value != value.strip() or not value.isascii():
        raise ValueError("invalid_callback_url")
    value = value.lower()
    # IPv6 literals are supported only as exact allowlist values, without brackets.
    try:
        ipaddress.ip_address(value)
        if "%" in value:
            raise ValueError
        return value
    except ValueError:
        if not _HOST.fullmatch(value):
            raise ValueError("invalid_callback_url") from None
        return value


class _DeadlineReader(io.RawIOBase):
    def __init__(self, tls, deadline, clock):
        super().__init__()
        self.tls, self.deadline, self.clock, self.total = tls, deadline, clock, 0

    def readable(self):
        return True

    def readinto(self, buffer):
        left = self.deadline - self.clock()
        if left <= 0:
            raise TimeoutError
        if self.total >= 16384:
            raise OSError("response_limit")
        self.tls.settimeout(left)
        count = self.tls.recv_into(memoryview(buffer)[:min(len(buffer), 16384 - self.total)])
        self.total += count
        return count


class _ResponseSocket:
    def __init__(self, tls, deadline, clock):
        self.tls, self.deadline, self.clock = tls, deadline, clock

    def makefile(self, mode):
        if mode != "rb":
            raise OSError("invalid_response_mode")
        return io.BufferedReader(_DeadlineReader(self.tls, self.deadline, self.clock))


class SafeHTTPSPoster:
    """No DNS/socket activity until enabled; all resolved addresses must be public.

    Each POST resolves once and connects to a validated sockaddr directly. TLS
    authenticates the original URL hostname, not the selected address. Injected
    factories are for offline tests, never configured from untrusted requests.
    """

    def __init__(self, allowed_hosts, enabled=False, resolver=socket.getaddrinfo,
                 socket_factory=socket.socket, context_factory=ssl.create_default_context,
                 response_factory=http.client.HTTPResponse, timeout=10, clock=time.monotonic):
        self.allowed_hosts = frozenset(_hostname(host) for host in allowed_hosts)
        self.enabled = enabled is True
        self.resolver, self.socket_factory = resolver, socket_factory
        self.context_factory, self.response_factory = context_factory, response_factory
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 10:
            raise ValueError("invalid_transport_timeout")
        self.timeout, self.clock = float(timeout), clock
        self._dns_lock = threading.Lock()
        self._dns_pending = None

    @property
    def pending_dns(self):
        """An OS resolver cannot be killed; prevent another while it is pending."""
        with self._dns_lock:
            return self._dns_pending is not None and not self._dns_pending.is_set()

    def _resolve(self, host, deadline):
        with self._dns_lock:
            if self._dns_pending is not None and not self._dns_pending.is_set():
                raise OSError("resolver_pending")
            if not _DNS_SLOTS.acquire(blocking=False):
                raise OSError("resolver_capacity")
            ready, result = threading.Event(), {}
            self._dns_pending = ready

            def resolve():
                try:
                    result["addresses"] = self.resolver(host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
                except Exception:
                    result["failed"] = True
                finally:
                    _DNS_SLOTS.release()
                    ready.set()

            # Timeout returns to the caller; one pending OS lookup may finish
            # naturally. Daemon status prevents a stuck resolver blocking exit.
            try:
                threading.Thread(target=resolve, name="EventGuard-callback-dns", daemon=True).start()
            except Exception:
                _DNS_SLOTS.release()
                ready.set()
                raise OSError("resolver_failed") from None
        if not ready.wait(max(0, deadline - self.clock())) or result.get("failed"):
            raise OSError("resolver_failed")
        return result["addresses"]

    def _target(self, url):
        try:
            if (not isinstance(url, str) or not 1 <= len(url) <= 2048 or not url.isascii()
                    or any(ord(x) <= 32 or ord(x) == 127 for x in url) or "\\" in url
                    or "#" in url or re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", url, re.I)):
                raise ValueError
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.username is not None or parsed.password is not None:
                raise ValueError
            host = _hostname(parsed.hostname)
            if host not in self.allowed_hosts or parsed.port not in (None, 443):
                raise ValueError
            target = parsed.path or "/"
            if not target.startswith("/"):
                raise ValueError
            if parsed.query:
                target += "?" + parsed.query
            return host, target
        except (ValueError, TypeError, AttributeError):
            raise ValueError("invalid_callback_url") from None

    def validate_target(self,url):
        """Recheck the current exact destination policy without DNS or transport."""
        return self._target(url)

    @staticmethod
    def _header_bytes(headers):
        if not isinstance(headers, dict) or len(headers) > 8:
            raise ValueError("invalid_callback_headers")
        items, seen = [], set()
        for name, value in headers.items():
            if (not isinstance(name, str) or name.lower() not in _HEADERS or name.lower() in seen
                    or not isinstance(value, str) or len(value) > 2048
                    or not name.isascii() or not value.isascii()
                    or any(ord(x) < 32 or ord(x) == 127 for x in value)):
                raise ValueError("invalid_callback_headers")
            seen.add(name.lower())
            items.append((name + ": " + value + "\r\n").encode("ascii"))
        result = b"".join(items)
        if len(result) > 8192:
            raise ValueError("invalid_callback_headers")
        return result

    def post(self, url, body, headers):
        if not self.enabled:
            raise PermissionError("transport_disabled")
        host, target = self._target(url)
        if not isinstance(body, bytes) or len(body) > 8192:
            raise ValueError("invalid_callback_body")
        header_bytes = self._header_bytes(headers)
        raw = tls = response = None
        try:
            deadline = self.clock() + self.timeout
            addresses = self._resolve(host, deadline)
            if not addresses or len(addresses) > 16:
                raise OSError
            validated = []
            for family, kind, proto, _canonical, addr in addresses:
                if (family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM
                        or proto not in (0, socket.IPPROTO_TCP) or addr[1] != 443
                        or "%" in addr[0] or not ipaddress.ip_address(addr[0]).is_global):
                    raise OSError
                validated.append((family, kind, proto, addr))
            family, kind, proto, addr = validated[0]
            left = deadline - self.clock()
            if left <= 0:
                raise TimeoutError
            raw = self.socket_factory(family, kind, proto)
            raw.settimeout(left)
            raw.connect(addr)  # No hostname here: do not allow a second DNS lookup.
            context = self.context_factory()
            if context.check_hostname is not True or context.verify_mode != ssl.CERT_REQUIRED:
                raise OSError
            left = deadline - self.clock()
            if left <= 0:
                raise TimeoutError
            raw.settimeout(left)
            tls = context.wrap_socket(raw, server_hostname=host)
            left = deadline - self.clock()
            if left <= 0:
                raise TimeoutError
            tls.settimeout(left)
            host_header = "[" + host + "]" if ":" in host else host
            request = ("POST " + target + " HTTP/1.1\r\nHost: " + host_header
                       + "\r\nContent-Length: " + str(len(body))
                       + "\r\nConnection: close\r\n").encode("ascii")
            tls.sendall(request + header_bytes + b"\r\n" + body)
            response = self.response_factory(_ResponseSocket(tls, deadline, self.clock))
            response.begin()
            if type(response.status) is not int or not 100 <= response.status <= 599:
                raise OSError
            if 300 <= response.status < 400:
                raise ValueError("callback_redirect_refused")
            payload = response.read(4097)
            if len(payload) > 4096:
                raise ValueError("callback_response_too_large")
            return {"status": response.status, "body": payload}
        except ValueError as exc:
            if str(exc) in {"callback_redirect_refused", "callback_response_too_large"}:
                raise ValueError(str(exc)) from None
            raise OSError("callback_transport_failed") from None
        except Exception:
            raise OSError("callback_transport_failed") from None
        finally:
            for item in (response, tls, raw):
                if item is not None:
                    try:
                        item.close()
                    except Exception:
                        pass
