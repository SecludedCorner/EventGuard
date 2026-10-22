"""Small authenticated JSON-over-HTTP WSGI transport. Construction never opens a port."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from ..runtime import read_json, safe_child

ALLOWED_CONFIG={"enabled","network_enabled","synthetic_only","listen_host","listen_port","public_origin",
                "allowed_callback_hosts","principals"}


def validate_config(config):
    if not isinstance(config,dict) or set(config)-ALLOWED_CONFIG:
        raise ValueError("invalid_bridge_config")
    for key in ("enabled","network_enabled","synthetic_only"):
        if type(config.get(key)) is not bool:raise ValueError("invalid_bridge_config")
    if config["synthetic_only"] is not True or config.get("listen_host")!="127.0.0.1":
        raise ValueError("unsupported_bridge_scope_or_binding")
    port=config.get("listen_port")
    if type(port) is not int or not 1024<=port<=65535:raise ValueError("invalid_listen_port")
    origin=config.get("public_origin")
    if not isinstance(origin,str) or not origin.isascii() or any(ord(c)<33 for c in origin):raise ValueError("invalid_public_origin")
    parsed=urlsplit(origin)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.port not in (None,443):
        raise ValueError("invalid_public_origin")
    hosts=config.get("allowed_callback_hosts")
    if not isinstance(hosts,list) or len(hosts)>10 or not all(isinstance(x,str) and x and len(x)<=253 and x==x.lower() and not any(c in x for c in "/:@*\\\r\n") for x in hosts):
        raise ValueError("invalid_callback_allowlist")
    records=config.get("principals")
    if not isinstance(records,list) or not 1<=len(records)<=20:raise ValueError("invalid_principals")
    for row in records:
        if not isinstance(row,dict) or set(row)!={"principal_id","host_refs","roles","token_env"}:
            raise ValueError("invalid_principals")
        if not isinstance(row["principal_id"],str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}",row["principal_id"]):
            raise ValueError("invalid_principals")
        if not isinstance(row["token_env"],str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}",row["token_env"]):
            raise ValueError("invalid_principals")
        refs=row["host_refs"]
        if not isinstance(refs,list) or not 1<=len(refs)<=20 or not all(isinstance(x,str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}",x) for x in refs):
            raise ValueError("invalid_principals")
        roles=row["roles"]
        if not isinstance(roles,list) or not 1<=len(roles)<=2 or any(x not in ("subscriber","producer") for x in roles):
            raise ValueError("invalid_principals")
    if config["enabled"] and (parsed.hostname.endswith(".invalid") or not config["network_enabled"] or not hosts):
        raise ValueError("enabled_bridge_requires_approved_destination")
    return dict(config)


def load_config(path):
    return validate_config(read_json(Path(path),65536))


class BridgeApplication:
    def __init__(self,config,service=None,auth=None):
        self.config=validate_config(config)
        self.service=service
        self.auth=auth
        self.delivery_worker_status="not_started"

    def __call__(self,environ,start_response):
        def respond(status,value,extra=()):
            raw=json.dumps(value,ensure_ascii=True,allow_nan=False,separators=(",",":")).encode()
            start_response(status,[("Content-Type","application/json; charset=utf-8"),("Content-Length",str(len(raw))),
                                   ("Cache-Control","no-store"),("X-Content-Type-Options","nosniff"),*extra])
            return [raw]
        if not self.config["enabled"]:
            return respond("503 Service Unavailable",{"error":"bridge_disabled"})
        if self.service is None or self.auth is None:
            return respond("503 Service Unavailable",{"error":"bridge_unconfigured"})
        origin=environ.get("HTTP_ORIGIN")
        if origin and origin.rstrip("/")!=self.config["public_origin"].rstrip("/"):
            return respond("403 Forbidden",{"error":"origin_not_allowed"})
        allowed_hosts={urlsplit(self.config["public_origin"]).netloc,"127.0.0.1:"+str(self.config["listen_port"])}
        if environ.get("HTTP_HOST","") not in allowed_hosts:
            return respond("403 Forbidden",{"error":"host_not_allowed"})
        header=environ.get("HTTP_AUTHORIZATION","")
        principal=self.auth.authenticate(header) if isinstance(header,str) and len(header)<=512 else None
        if principal is None:
            return respond("401 Unauthorized",{"error":"authentication_required"},
                           [("WWW-Authenticate",'Bearer realm="EventGuard"')])
        path=environ.get("PATH_INFO","")
        method=environ.get("REQUEST_METHOD","")
        if path=="/status" and method=="GET":
            if "subscriber" not in principal.roles:return respond("403 Forbidden",{"error":"not_authorized"})
            try:
                counts=self.service.store.stats()
            except Exception:
                return respond("503 Service Unavailable",{"error":"bridge_storage_unavailable"})
            return respond("200 OK",{"bridge":"engineering_preview","synthetic_only":True,"counts":counts,
                                      "delivery_worker_status":self.delivery_worker_status,"real_agent_woken":False,
                                      "note":"Counts do not verify platform agent execution."})
        if path not in ("/mcp","/events"):return respond("404 Not Found",{"error":"not_found"})
        if method!="POST":return respond("405 Method Not Allowed",{"error":"post_required"},[("Allow","POST")])
        if environ.get("CONTENT_TYPE","").split(";",1)[0].strip().lower()!="application/json":
            return respond("415 Unsupported Media Type",{"error":"json_required"})
        try:
            length=int(environ.get("CONTENT_LENGTH","0"))
            if not 1<=length<=32768:raise ValueError()
            raw=environ["wsgi.input"].read(length)
            if len(raw)!=length:raise ValueError()
            value=json.loads(raw)
            if not isinstance(value,dict):raise ValueError()
        except (ValueError,TypeError,KeyError,OSError):
            return respond("400 Bad Request",{"error":"invalid_bounded_json"})
        if path=="/mcp":
            from .protocol import PROTOCOL_VERSION
            version=environ.get("HTTP_MCP_PROTOCOL_VERSION")
            if version and version!=PROTOCOL_VERSION:
                return respond("400 Bad Request",{"error":"unsupported_protocol_version"})
            return respond("200 OK",self.service.dispatch(principal,value))
        try:
            return respond("200 OK",self.service.ingest(principal,value))
        except Exception as error:
            from .service import RPCError
            permanent=isinstance(error,(RPCError,ValueError,TypeError,PermissionError))
            status="403 Forbidden" if isinstance(error,RPCError) else ("422 Unprocessable Entity" if permanent else "409 Conflict")
            return respond(status,{"error":"event_not_accepted","retryable":not permanent})


def create_app(root,config,environ=None):
    config=validate_config(config)
    if not config["enabled"]:
        return BridgeApplication(config)
    from .security import BearerAuth
    from .network import SafeHTTPSPoster
    from .vault import DPAPIVault
    from .store import BridgeStore
    from .service import BridgeService
    auth=BearerAuth(config["principals"],environ=environ)
    subscribers={(row["principal_id"],host) for row in config["principals"] for host in row["host_refs"]
                 if auth.is_authorized(row["principal_id"],role="subscriber",host_ref=host)}
    producers={(row["principal_id"],host) for row in config["principals"] for host in row["host_refs"]
               if auth.is_authorized(row["principal_id"],role="producer",host_ref=host)}
    if not subscribers&producers:
        raise ValueError("matching_scoped_credentials_required")
    directory=safe_child(Path(root),"data/bridge")
    store=BridgeStore(directory)
    vault=DPAPIVault(safe_child(Path(root),"data/bridge/vault"))
    poster=SafeHTTPSPoster(config["allowed_callback_hosts"],enabled=config["network_enabled"])
    service=BridgeService(store,vault,poster,principal_is_active=lambda owner:auth.is_authorized(owner),
        subscription_is_authorized=lambda owner,host:auth.is_authorized(owner,role="subscriber",host_ref=host))
    return BridgeApplication(config,service,auth)
