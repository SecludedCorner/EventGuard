"""Opt-in producer adapter for a configured HTTPS bridge; never loads credentials itself."""
import json
from urllib.parse import urlsplit
from ..events.schema import validate_event
from ..events.store import validate_receipt
from .network import SafeHTTPSPoster


class BridgeHTTPSPoster(SafeHTTPSPoster):
    """Separate producer policy: bearer only to one approved /events endpoint.

    The callback poster's header allowlist remains unchanged. DNS pinning,
    HTTPS certificate checks, redirect refusal and all limits are inherited.
    """
    def __init__(self,allowed_hosts,**kwargs):
        hosts=tuple(allowed_hosts)
        if len(hosts)!=1:raise ValueError("one_producer_host_required")
        super().__init__(hosts,**kwargs)

    def _target(self,url):
        result=super()._target(url)
        parts=urlsplit(url)
        if parts.path!="/events" or parts.query:raise ValueError("invalid_producer_endpoint")
        return result

    @staticmethod
    def _header_bytes(headers):
        if not isinstance(headers,dict) or set(headers)!={"Content-Type","Authorization"}:
            raise ValueError("invalid_producer_headers")
        value=headers["Authorization"]
        if not isinstance(value,str) or not value.startswith("Bearer ") or not 39<=len(value)<=263 or any(not 33<=ord(c)<=126 for c in value[7:]):
            raise ValueError("invalid_producer_headers")
        base=SafeHTTPSPoster._header_bytes({"Content-Type":headers["Content-Type"]})
        return base+("Authorization: "+value+"\r\n").encode("ascii")


class BridgeProducerAdapter:
    """Drop-in EventStore pump adapter. An ACK proves bridge persistence only.

    The caller supplies an existing, separately approved producer bearer and a
    BridgeHTTPSPoster whose single exact host is the approved bridge.
    This adapter is not automatically selected by the monitor or CLI.
    """
    real_agent_woken=False
    kind="synthetic_mcp_bridge"

    def __init__(self,url,bearer,poster,enabled=False):
        parts=urlsplit(url)
        if parts.scheme!="https" or not parts.hostname or parts.path!="/events" or parts.query or parts.fragment or parts.username or parts.password:
            raise ValueError("invalid_producer_endpoint")
        if not isinstance(bearer,str) or not 32<=len(bearer)<=256 or any(ord(c)<33 or ord(c)>126 for c in bearer):
            raise ValueError("invalid_producer_credential")
        self.url=url
        self._bearer=bearer
        self.poster=poster
        self.connected=enabled is True and getattr(poster,"enabled",False) is True

    def send(self,event):
        if not self.connected:
            return {"ack":False,"retryable":False,"reason":"bridge_disabled","real_agent_woken":False}
        clean=validate_event(event)
        if clean["synthetic"] is not True:
            return {"ack":False,"retryable":False,"reason":"synthetic_only","real_agent_woken":False}
        body=json.dumps(clean,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()
        try:
            response=self.poster.post(self.url,body,{"Content-Type":"application/json","Authorization":"Bearer "+self._bearer})
            if not 200<=response["status"]<300:
                return {"ack":False,"retryable":response["status"] in (408,409,429) or 500<=response["status"]<600,
                        "reason":"bridge_not_accepted","real_agent_woken":False}
            receipt=validate_receipt(clean["event_id"],json.loads(response["body"]))
            return dict(receipt,real_agent_woken=False)
        except (ValueError,TypeError,KeyError,PermissionError):
            return {"ack":False,"retryable":False,"reason":"bridge_response_or_policy_rejected","real_agent_woken":False}
        except OSError:
            return {"ack":False,"retryable":True,"reason":"bridge_delivery_uncertain","real_agent_woken":False}
