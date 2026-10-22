"""Authenticated MCP methods and delivery orchestration; synthetic evidence only."""
from __future__ import annotations
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timezone

from .protocol import (PROTOCOL_VERSION, EVENT_NAME, event_definition, validate_arguments,
                       project_event, tool_definitions, validate_tool_arguments, query_snapshot)
from .security import sign_headers, validate_secret
from .store import subscription_id, BridgeError


def iso(stamp):
    return datetime.fromtimestamp(stamp,timezone.utc).isoformat(timespec="milliseconds")


class RPCError(ValueError):
    def __init__(self,code,reason):
        self.code=code
        self.reason=reason
        super().__init__(reason)


class BridgeService:
    def __init__(self,store,vault,poster,clock=time.time,principal_is_active=None,challenge_factory=None,subscription_is_authorized=None):
        self.store=store
        self.vault=vault
        self.poster=poster
        self.clock=clock
        self.principal_is_active=principal_is_active or (lambda owner:False)
        self.subscription_is_authorized=subscription_is_authorized or (lambda owner,host:False)
        self.challenge_factory=challenge_factory or (lambda:secrets.token_urlsafe(24))

    @staticmethod
    def _require(principal,role):
        if principal is None or role not in principal.roles:
            raise RPCError(-32001,"not_authorized")

    @staticmethod
    def _keys(value,allowed,required=()):
        if not isinstance(value,dict) or set(value)-set(allowed) or set(required)-set(value):
            raise RPCError(-32602,"invalid_params")

    def _event(self,principal,event_id):
        event=self.store.get_event(principal.id,event_id)
        if event is None or event["host_id"] not in principal.hosts or event.get("synthetic") is not True:
            raise RPCError(-32001,"event_not_authorized")
        return event

    def _subscribe(self,principal,params):
        self._keys(params,{"name","arguments","delivery","cursor","ttlMs"},{"name","arguments","delivery"})
        if params["name"]!=EVENT_NAME or params.get("cursor") is not None:
            raise RPCError(-32602,"unsupported_event_or_cursor")
        arguments=validate_arguments(params["arguments"])
        if arguments["host_ref"] not in principal.hosts:
            raise RPCError(-32001,"host_not_authorized")
        delivery=params["delivery"]
        self._keys(delivery,{"mode","url","secret"},{"mode","url","secret"})
        if delivery["mode"]!="webhook" or not isinstance(delivery["url"],str):
            raise RPCError(-32602,"invalid_delivery")
        self.poster.validate_target(delivery["url"])
        secret=delivery["secret"]
        key=validate_secret(secret)
        ttl=params.get("ttlMs")
        if ttl is not None and (type(ttl) not in (int,float) or not 0<ttl<=86400000):
            raise RPCError(-32602,"invalid_ttl")
        lifetime=3600 if ttl is None else ttl/1000
        now=self.clock()
        identity=subscription_id(principal.id,delivery["url"],EVENT_NAME,arguments)
        old=self.store.find_subscription(principal.id,delivery["url"],EVENT_NAME,arguments)
        old_secret=None
        same_secret=False
        if old and not old.get("revoked"):
            old_secret=self.vault.get(old["secret_ref"])
            same_secret=hmac.compare_digest(validate_secret(old_secret),key)
        cached=bool(old and same_secret and old["expires_at"]>now and 0<=now-old["verified_at"]<300)
        if not cached:
            challenge=self.challenge_factory()
            verification_id="verification-"+uuid.uuid4().hex
            body=json.dumps({"type":"verification","challenge":challenge},separators=(",",":")).encode()
            headers=sign_headers(secret,verification_id,body,identity,int(now))
            try:
                response=self.poster.post(delivery["url"],body,headers)
                answer=json.loads(response["body"])
                valid=200<=response["status"]<300 and isinstance(answer,dict) and isinstance(answer.get("challenge"),str)
                valid=valid and hmac.compare_digest(answer["challenge"],challenge) and 0<=self.clock()-now<=30
            except (ValueError,TypeError,KeyError,OSError,PermissionError):
                valid=False
            if not valid:
                raise RPCError(-32015,"challenge_failed")
        now=self.clock()
        secret_ref=old["secret_ref"] if old and same_secret else self.vault.put(secret)
        previous_ref=None
        previous_until=None
        if old and old_secret and not same_secret and old["expires_at"]>now:
            previous_ref=old["secret_ref"]
            previous_until=now+min(60,lifetime)
        elif old and same_secret and (old.get("previous_valid_until") or 0)>now:
            previous_ref=old.get("previous_secret_ref")
            previous_until=min(old["previous_valid_until"],now+lifetime)
        row=self.store.upsert_subscription(principal.id,delivery["url"],EVENT_NAME,arguments,secret_ref,
                now+lifetime,now if not cached else old["verified_at"],previous_ref,previous_until)
        return {"id":row["id"],"refreshBefore":iso(row["expires_at"]),"cursor":None,"truncated":False}

    def _unsubscribe(self,principal,params):
        self._keys(params,{"name","arguments","delivery"},{"name","arguments","delivery"})
        arguments=validate_arguments(params["arguments"])
        delivery=params["delivery"]
        self._keys(delivery,{"mode","url"},{"mode","url"})
        if params["name"]!=EVENT_NAME or delivery["mode"]!="webhook" or arguments["host_ref"] not in principal.hosts:
            raise RPCError(-32001,"subscription_not_authorized")
        return self.store.unsubscribe(principal.id,delivery["url"],EVENT_NAME,arguments)

    def _call_tool(self,principal,params):
        self._keys(params,{"name","arguments"},{"name","arguments"})
        name=params["name"]
        args=validate_tool_arguments(name,params["arguments"])
        event=self._event(principal,args["event_id"])
        if name=="eventguard_get_event":
            result={"event":project_event(event)["data"],"evidence_source":"persisted_synthetic_event","current_system_query":False}
        elif name=="eventguard_query_evidence":
            result=query_snapshot(event,args["operation"],args.get("max_rows",20))
            result["request_id"]=args["request_id"]
            self.store.record_query(principal.id,args["event_id"],args["request_id"],args["operation"],result)
        else:
            result=self.store.record_result(principal.id,args["event_id"],{key:value for key,value in args.items() if key!="event_id"})
        return {"content":[{"type":"text","text":json.dumps(result,ensure_ascii=True,separators=(",",":"))}],
                "structuredContent":result,"isError":False}

    def dispatch(self,principal,request):
        identity=None
        try:
            self._require(principal,"subscriber")
            if not isinstance(request,dict) or set(request)-{"jsonrpc","id","method","params"} or not {"jsonrpc","id","method"}<=set(request):
                raise RPCError(-32600,"invalid_request")
            candidate=request["id"]
            if request["jsonrpc"]!="2.0" or type(candidate) not in (str,int) or isinstance(candidate,str) and len(candidate)>100:
                raise RPCError(-32600,"invalid_request")
            identity=candidate
            method=request["method"]
            params=request.get("params",{})
            if not isinstance(params,dict):
                raise RPCError(-32602,"invalid_params")
            if not self.principal_is_active(principal.id):
                raise RPCError(-32001,"principal_revoked")
            if method=="server/discover":
                self._keys(params,{"protocolVersion"})
                result={"resultType":"complete","supportedVersions":[PROTOCOL_VERSION],"capabilities":{"tools":{},"events":{}}}
            elif method=="events/list":
                self._keys(params,{"cursor"})
                if params.get("cursor") is not None:raise RPCError(-32602,"unsupported_cursor")
                result={"events":[event_definition()]}
            elif method=="events/subscribe":result=self._subscribe(principal,params)
            elif method=="events/unsubscribe":result=self._unsubscribe(principal,params)
            elif method=="tools/list":
                self._keys(params,{"cursor"})
                if params.get("cursor") is not None:raise RPCError(-32602,"unsupported_cursor")
                result={"tools":tool_definitions()}
            elif method=="tools/call":result=self._call_tool(principal,params)
            else:raise RPCError(-32601,"method_not_found")
            return {"jsonrpc":"2.0","id":identity,"result":result}
        except RPCError as error:
            return {"jsonrpc":"2.0","id":identity,"error":{"code":error.code,"message":error.reason,"data":{"reason":error.reason}}}
        except (ValueError,TypeError,KeyError):
            return {"jsonrpc":"2.0","id":identity,"error":{"code":-32602,"message":"invalid_params"}}
        except (BridgeError,OSError):
            return {"jsonrpc":"2.0","id":identity,"error":{"code":-32000,"message":"storage_or_transport_unavailable"}}

    def ingest(self,principal,event):
        self._require(principal,"producer")
        if not self.principal_is_active(principal.id) or not isinstance(event,dict) or event.get("host_id") not in principal.hosts:
            raise RPCError(-32001,"event_not_authorized")
        project_event(event)  # Validates/minimizes, including synthetic-only scope.
        return self.store.enqueue_event(principal.id,event)

    def pump_once(self):
        if getattr(self.poster,"enabled",False) is not True:
            return {"status":"transport_disabled","attempted":0,"real_agent_woken":False}
        job=self.store.claim_delivery()
        if job is None:return {"status":"idle","attempted":0,"real_agent_woken":False}
        sub=job["subscription"]
        outcome="failed"
        reason="principal_revoked"
        status=None
        if self.principal_is_active(sub["owner"]) and self.subscription_is_authorized(sub["owner"],sub["arguments"]["host_ref"]):
            try:
                now=self.clock()
                if sub["expires_at"]<=now or sub.get("revoked"):
                    reason="subscription_expired_or_revoked"
                else:
                    envelope=project_event(job["event"])
                    body=json.dumps(envelope,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()
                    previous=self.vault.get(sub["previous_secret_ref"]) if sub.get("previous_secret_ref") and (sub.get("previous_valid_until") or 0)>now else None
                    headers=sign_headers(self.vault.get(sub["secret_ref"]),envelope["eventId"],body,sub["id"],int(now),previous)
                    response=self.poster.post(sub["url"],body,headers)
                    status=response["status"]
                    if 200<=status<300:outcome,reason="received","webhook_received_async"
                    elif status in (408,429) or 500<=status<600:outcome,reason="retry","callback_transient"
                    else:outcome,reason="failed","callback_permanent"
            except PermissionError:outcome,reason="failed","callback_policy_rejected"
            except (OSError,TimeoutError):outcome,reason="retry","callback_transport_uncertain"
            except (ValueError,KeyError,TypeError):outcome,reason="failed","callback_policy_rejected"
        self.store.complete_delivery(job["delivery_id"],job["lease_token"],outcome,reason,http_status=status)
        return {"status":outcome,"attempted":1,"event_id":job["event"]["event_id"],"real_agent_woken":False,
                "note":"Webhook receipt alone does not prove an agent turn or processing."}
