"""Small, fail-closed authentication and Standard Webhooks signing primitives."""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import hmac
import os
import re
from collections.abc import Mapping


@dataclass(frozen=True)
class Principal:
    id: str
    hosts: frozenset[str]
    roles: frozenset[str]


_LABEL = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_ENV = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")


class BearerAuth:
    """Read only configured environment names; retain SHA-256 digests, never tokens.

    Invalid records are ignored. Conflicting token ownership fails closed.
    Tokens must be 32..4096 ASCII non-whitespace characters. This length check
    cannot establish entropy: provisioning an unpredictable token is external.
    """

    def __init__(self, records: list[dict], environ: Mapping | None = None):
        env = os.environ if environ is None else environ
        self._records: list[tuple[bytes, Principal]] = []
        for record in records if isinstance(records, list) else []:
            if not isinstance(record, dict):
                continue
            pid, name = record.get("principal_id"), record.get("token_env")
            hosts, roles = record.get("host_refs"), record.get("roles")
            if not isinstance(pid, str) or not _LABEL.fullmatch(pid):
                continue
            if not isinstance(name, str) or not _ENV.fullmatch(name):
                continue
            if not isinstance(hosts, (list, tuple, set, frozenset)) or not hosts:
                continue
            if not isinstance(roles, (list, tuple, set, frozenset)) or not roles:
                continue
            if any(not isinstance(x, str) or not _LABEL.fullmatch(x) for x in (*hosts, *roles)):
                continue
            token = env.get(name)
            if not self._valid_token(token):
                continue
            digest = hashlib.sha256(token.encode("ascii")).digest()
            self._records.append((digest, Principal(pid, frozenset(hosts), frozenset(roles))))

    @staticmethod
    def _valid_token(value):
        return (isinstance(value, str) and 32 <= len(value) <= 4096
                and all(33 <= ord(ch) <= 126 for ch in value))

    def authenticate(self, header: str | None) -> Principal | None:
        if not isinstance(header, str) or len(header) > 4103:
            return None
        parts = header.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer" or not self._valid_token(parts[1]):
            return None
        digest = hashlib.sha256(parts[1].encode("ascii")).digest()
        matches = [principal for expected, principal in self._records
                   if hmac.compare_digest(expected, digest)]
        return matches[0] if matches and all(p == matches[0] for p in matches) else None

    def is_authorized(self,principal_id,role=None,host_ref=None):
        """Current configured role/host grant, excluding conflicting credentials."""
        for digest,principal in self._records:
            if principal.id!=principal_id or role is not None and role not in principal.roles or host_ref is not None and host_ref not in principal.hosts:
                continue
            if all(not hmac.compare_digest(digest,other) or principal==owner for other,owner in self._records):
                return True
        return False


def validate_secret(secret: str) -> bytes:
    """Return key bytes or raise the stable, non-sensitive validation code."""
    try:
        if not isinstance(secret, str) or not secret.startswith("whsec_") or len(secret) > 100:
            raise ValueError
        encoded = secret[6:]
        key = base64.b64decode(encoded, validate=True)
        if not 24 <= len(key) <= 64 or base64.b64encode(key).decode("ascii") != encoded:
            raise ValueError
        return key
    except (ValueError, binascii.Error, UnicodeError, TypeError):
        raise ValueError("invalid_webhook_secret") from None


def sign_headers(secret: str, event_id: str, body: bytes, subscription_id: str,
                 timestamp: int, previous_secret: str | None = None) -> dict[str, str]:
    """Sign the exact bytes once; rotation uses space-separated v1 signatures."""
    if (not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}",event_id)
            or not isinstance(subscription_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}",subscription_id)
            or type(timestamp) is not int or not 0 <= timestamp <= 2**63 - 1
            or not isinstance(body, bytes) or len(body) > 8192):
        raise ValueError("invalid_signature_input")
    keys = [validate_secret(secret)]
    if previous_secret is not None:
        previous = validate_secret(previous_secret)
        if not hmac.compare_digest(keys[0], previous):
            keys.append(previous)
    message = event_id.encode("ascii") + b"." + str(timestamp).encode("ascii") + b"." + body
    signatures = ["v1," + base64.b64encode(hmac.digest(key, message, "sha256")).decode("ascii")
                  for key in keys]
    return {"Content-Type": "application/json", "webhook-id": event_id,
            "webhook-timestamp": str(timestamp), "webhook-signature": " ".join(signatures),
            "X-MCP-Subscription-Id": subscription_id}
