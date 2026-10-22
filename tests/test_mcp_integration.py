"""In-process protocol/HTTP/producer tests. No listener, DNS, model or native query."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
from contrib.mcp_bridge.app import BridgeApplication,create_app,validate_config
from contrib.mcp_bridge.service import BridgeService
from contrib.mcp_bridge.store import BridgeStore
from contrib.mcp_bridge.security import Principal,BearerAuth
from contrib.mcp_bridge.protocol import EVENT_NAME
from contrib.mcp_bridge.producer import BridgeProducerAdapter,BridgeHTTPSPoster
from eventguard.synthetic import make_synthetic


class TestVault:
    def __init__(self):self.values={};self.put_calls=0
    def put(self,secret):
        self.put_calls+=1
        ref='ref-'+hashlib.sha256(secret.encode()).hexdigest()
        self.values[ref]=secret
        return ref
    def get(self,ref):return self.values[ref]


class TestPoster:
    def __init__(self):
        self.enabled=True
        self.calls=[]
        self.status=202
        self.bad_challenge=False
        self.failure=None
    def post(self,url,body,headers):
        self.calls.append((url,body,headers))
        if self.failure:raise self.failure
        value=json.loads(body)
        if value.get('type')=='verification':
            answer='incorrect' if self.bad_challenge else value['challenge']
            return {'status':200,'body':json.dumps({'challenge':answer}).encode()}
        return {'status':self.status,'body':b'{}'}
    def validate_target(self,url):
        if not url.startswith('https://receiver.example.test/'):
            raise ValueError('invalid_callback_url')


class MCPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='eventguard-mcp-test-')
        self.addCleanup(self.temp.cleanup)
        self.now=[1800000000.0]
        self.store=BridgeStore(Path(self.temp.name),clock=lambda:self.now[0])
        self.vault=TestVault()
        self.poster=TestPoster()
        self.active={'owner'}
        self.service=BridgeService(self.store,self.vault,self.poster,clock=lambda:self.now[0],
                                  principal_is_active=lambda owner:owner in self.active,
                                  subscription_is_authorized=lambda owner,host:owner in self.active and host=='synthetic-host',
                                  challenge_factory=lambda:'synthetic-fresh-challenge')
        self.subscriber=Principal('owner',frozenset({'synthetic-host'}),frozenset({'subscriber'}))
        self.producer=Principal('owner',frozenset({'synthetic-host'}),frozenset({'producer'}))
        self.secret='whsec_'+base64.b64encode(b'\x01'*32).decode()
        self.params={'name':EVENT_NAME,'arguments':{'host_ref':'synthetic-host'},
                     'delivery':{'mode':'webhook','url':'https://receiver.example.test/callback','secret':self.secret}}

    def rpc(self,method,params=None,principal=None):
        return self.service.dispatch(principal or self.subscriber,{'jsonrpc':'2.0','id':1,'method':method,'params':params or {}})

    def subscribe(self,params=None):
        result=self.rpc('events/subscribe',params or self.params)
        self.assertIn('result',result,result)
        return result['result']

    def ingest(self):
        event=make_synthetic('listener')
        self.service.ingest(self.producer,event)
        return event

    def test_documented_discovery_and_event_catalog(self):
        self.assertEqual(self.rpc('server/discover')['result']['supportedVersions'],['2026-07-28'])
        self.assertEqual(self.rpc('events/list')['result']['events'][0]['name'],EVENT_NAME)
        self.assertEqual(len(self.rpc('tools/list')['result']['tools']),3)

    def test_subscription_verification_precedes_persistence_and_is_idempotent(self):
        first=self.subscribe()
        self.assertEqual(first,self.subscribe())
        self.assertEqual(len(self.poster.calls),1)
        self.assertEqual(first['cursor'],None)
        self.assertEqual(self.store.stats()['subscriptions'],1)
        self.assertEqual(json.loads(self.poster.calls[0][1])['type'],'verification')
        self.assertEqual(len(self.vault.values),1)

    def test_refresh_reuses_secret_reference_and_short_rotation_window(self):
        self.subscribe()
        before=self.store.find_subscription('owner',self.params['delivery']['url'],EVENT_NAME,{'host_ref':'synthetic-host','event_types':[]})['secret_ref']
        for unused in range(3):self.subscribe()
        self.assertEqual(self.vault.put_calls,1)
        after=self.store.find_subscription('owner',self.params['delivery']['url'],EVENT_NAME,{'host_ref':'synthetic-host','event_types':[]})['secret_ref']
        self.assertEqual(before,after)
        params=copy.deepcopy(self.params)
        params['ttlMs']=1000
        params['delivery']['secret']='whsec_'+base64.b64encode(b'\x03'*32).decode()
        self.subscribe(params)
        changed=self.store.find_subscription('owner',params['delivery']['url'],EVENT_NAME,{'host_ref':'synthetic-host','event_types':[]})
        self.assertLessEqual(changed['previous_valid_until'],changed['expires_at'])

    def test_failed_verification_does_not_activate_or_save_secret(self):
        self.poster.bad_challenge=True
        result=self.rpc('events/subscribe',self.params)
        self.assertEqual(result['error']['code'],-32015)
        self.assertEqual(self.vault.values,{})
        self.assertEqual(self.store.active_subscriptions(),[])

    def test_refresh_secret_rotation_signs_with_two_keys(self):
        self.subscribe()
        changed=copy.deepcopy(self.params)
        changed['delivery']['secret']='whsec_'+base64.b64encode(b'\x02'*32).decode()
        self.subscribe(changed)
        self.ingest()
        self.assertEqual(self.service.pump_once()['status'],'received')
        self.assertEqual(len(self.poster.calls[-1][2]['webhook-signature'].split()),2)

    def test_full_synthetic_contract_without_real_agent_claim(self):
        self.subscribe()
        event=self.ingest()
        self.assertEqual(self.service.pump_once()['status'],'received')
        envelope=json.loads(self.poster.calls[-1][1])
        self.assertEqual(envelope['eventId'],event['event_id'])
        self.assertEqual(self.poster.calls[-1][2]['webhook-id'],event['event_id'])
        query={'name':'eventguard_query_evidence','arguments':{'event_id':event['event_id'],'request_id':'q-1','operation':'query_listener'}}
        observed=self.rpc('tools/call',query)['result']['structuredContent']
        self.assertFalse(observed['system_query_executed'])
        result={'name':'eventguard_record_result','arguments':{'event_id':event['event_id'],'decision':'benign_change',
                    'evidence_request_ids':['q-1'],'reason_code':'synthetic_evidence_reviewed'}}
        first=self.rpc('tools/call',result)['result']['structuredContent']
        second=self.rpc('tools/call',result)['result']['structuredContent']
        self.assertEqual(first,second)
        self.assertEqual(first['status'],'agent_result_recorded')
        self.assertFalse(first['platform_run_verified'])
        self.assertFalse(first['system_actions_performed'])
        self.assertEqual(self.service.pump_once()['attempted'],0)

    def test_unsubscribe_is_idempotent_and_stops_waiting_delivery(self):
        self.subscribe();self.ingest()
        args=copy.deepcopy(self.params);args['delivery'].pop('secret')
        self.assertEqual(self.rpc('events/unsubscribe',args)['result'],{})
        self.assertEqual(self.rpc('events/unsubscribe',args)['result'],{})
        count=len(self.poster.calls)
        self.assertEqual(self.service.pump_once()['attempted'],0)
        self.assertEqual(len(self.poster.calls),count)

    def test_transient_retry_keeps_event_id_but_fresh_signing_timestamp(self):
        self.subscribe();event=self.ingest();self.poster.status=503
        self.assertEqual(self.service.pump_once()['status'],'retry')
        first=self.poster.calls[-1]
        self.now[0]+=3601
        # Refresh the subscription before its finite expiration.
        self.subscribe()
        self.poster.status=202
        self.assertEqual(self.service.pump_once()['status'],'received')
        second=self.poster.calls[-1]
        self.assertEqual(json.loads(first[1])['eventId'],event['event_id'])
        self.assertEqual(first[1],second[1])
        self.assertNotEqual(first[2]['webhook-timestamp'],second[2]['webhook-timestamp'])

    def test_410_is_permanent_and_never_agent_processing(self):
        self.subscribe();self.ingest();self.poster.status=410
        result=self.service.pump_once()
        self.assertEqual(result['status'],'failed')
        self.assertFalse(result['real_agent_woken'])
        self.now[0]+=100
        self.assertEqual(self.service.pump_once()['attempted'],0)

    def test_revoked_principal_does_not_send_callback(self):
        self.subscribe();self.ingest();self.active.clear()
        previous=len(self.poster.calls)
        self.assertEqual(self.service.pump_once()['status'],'failed')
        self.assertEqual(len(self.poster.calls),previous)
        self.assertEqual(self.rpc('server/discover')['error']['code'],-32001)

    def test_owner_role_host_and_live_event_boundaries(self):
        self.assertEqual(self.rpc('events/list',principal=self.producer)['error']['code'],-32001)
        wrong=copy.deepcopy(self.params);wrong['arguments']['host_ref']='other-host'
        self.assertEqual(self.rpc('events/subscribe',wrong)['error']['code'],-32001)
        self.subscribe();event=self.ingest()
        outsider=Principal('other',self.subscriber.hosts,self.subscriber.roles)
        self.active.add('other')
        result=self.rpc('tools/call',{'name':'eventguard_get_event','arguments':{'event_id':event['event_id']}},outsider)
        self.assertEqual(result['error']['code'],-32001)
        event['synthetic']=False
        with self.assertRaises(ValueError):self.service.ingest(self.producer,event)

    def test_tool_rejects_free_text_and_unlinked_evidence(self):
        self.subscribe();event=self.ingest()
        result=self.rpc('tools/call',{'name':'eventguard_record_result','arguments':{'event_id':event['event_id'],
            'decision':'benign_change','evidence_request_ids':['not-observed'],'reason_code':'synthetic_evidence_reviewed'}})
        self.assertIn('error',result)
        result=self.rpc('tools/call',{'name':'eventguard_get_event','arguments':{'event_id':event['event_id'],'shell':'anything'}})
        self.assertEqual(result['error']['code'],-32602)

    def test_transport_disabled_consumes_no_attempt(self):
        self.subscribe();self.ingest();self.poster.enabled=False
        before=self.store.stats()
        self.assertEqual(self.service.pump_once()['attempted'],0)
        self.assertEqual(before,self.store.stats())

    def test_wsgi_auth_roles_origin_bounded_json_and_disabled_factory(self):
        config=json.loads((ROOT/'config/bridge.example.json').read_text(encoding='utf-8'))
        config.update(enabled=True,network_enabled=True,public_origin='https://bridge.example.test',allowed_callback_hosts=['receiver.example.test'])
        env={'EVENTGUARD_MCP_TOKEN':'SYNTHETIC-SUBSCRIBER-NOT-A-REAL-KEY-0001','EVENTGUARD_PRODUCER_TOKEN':'SYNTHETIC-PRODUCER-NOT-A-REAL-KEY-000001'}
        auth=BearerAuth(config['principals'],environ=env)
        # The example's owner is intentionally fixed by configuration, never by a header.
        app=BridgeApplication(config,self.service,auth)
        def request(path='/mcp',header=None,origin=None,raw=b'{}',method='POST'):
            result={}
            environ={'REQUEST_METHOD':method,'PATH_INFO':path,'HTTP_HOST':'bridge.example.test','CONTENT_TYPE':'application/json',
                     'CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)}
            if header:environ['HTTP_AUTHORIZATION']=header
            if origin:environ['HTTP_ORIGIN']=origin
            body=b''.join(app(environ,lambda status,headers:result.update(status=status,headers=headers)))
            return result['status'],json.loads(body)
        self.assertTrue(request()[0].startswith('401'))
        subscriber='Bearer '+env['EVENTGUARD_MCP_TOKEN']
        self.assertTrue(request(origin='https://untrusted.example',header=subscriber)[0].startswith('403'))
        self.assertTrue(request(header=subscriber,raw=b'[')[0].startswith('400'))
        self.assertTrue(request(path='/events',header=subscriber,raw=json.dumps(make_synthetic()).encode())[0].startswith('403'))
        config['enabled']=False
        disabled=create_app(Path(self.temp.name)/'no-runtime',config)
        result={}
        body=b''.join(disabled({},lambda status,headers:result.update(status=status)))
        self.assertEqual(json.loads(body)['error'],'bridge_disabled')
        self.assertFalse((Path(self.temp.name)/'no-runtime').exists())

    def test_producer_adapter_is_disabled_and_synthetic_only(self):
        poster=TestPoster()
        adapter=BridgeProducerAdapter('https://bridge.example.test/events','SYNTHETIC-PRODUCER-NOT-A-REAL-KEY-000001',poster)
        self.assertFalse(adapter.connected)
        self.assertFalse(adapter.send(make_synthetic())['ack'])
        self.assertEqual(poster.calls,[])
        enabled=BridgeProducerAdapter(adapter.url,'SYNTHETIC-PRODUCER-NOT-A-REAL-KEY-000001',poster,enabled=True)
        event=make_synthetic();event['synthetic']=False
        self.assertEqual(enabled.send(event)['reason'],'synthetic_only')
        self.assertEqual(poster.calls,[])

    def test_config_forbids_live_scope_public_bind_and_enabled_placeholders(self):
        config=json.loads((ROOT/'config/bridge.example.json').read_text(encoding='utf-8'))
        for key,value in (('synthetic_only',False),('listen_host','0.0.0.0'),('enabled',True)):
            changed=copy.deepcopy(config);changed[key]=value
            with self.assertRaises(ValueError):validate_config(changed)

    def test_invalid_rpc_ids_never_escape_into_response(self):
        for identity in ({},[],True,float('nan'),None):
            result=self.service.dispatch(self.subscriber,{'jsonrpc':'2.0','id':identity,'method':'server/discover'})
            self.assertIsNone(result['id'])
            self.assertEqual(result['error']['code'],-32600)
            json.dumps(result,allow_nan=False)
        self.assertEqual(self.service.dispatch(self.subscriber,{'method':'server/discover'})['error']['code'],-32600)

    def test_current_subscription_role_and_host_are_rechecked(self):
        self.subscribe();self.ingest()
        self.service.subscription_is_authorized=lambda owner,host:False
        count=len(self.poster.calls)
        self.assertEqual(self.service.pump_once()['status'],'failed')
        self.assertEqual(len(self.poster.calls),count)

    def test_auth_current_grant_tracks_subscriber_role_and_host(self):
        token='SYNTHETIC-SUBSCRIBER-NOT-A-REAL-KEY-0001'
        record={'principal_id':'owner','host_refs':['synthetic-host'],'roles':['subscriber'],'token_env':'TOKEN'}
        auth=BearerAuth([record],environ={'TOKEN':token})
        self.assertTrue(auth.is_authorized('owner',role='subscriber',host_ref='synthetic-host'))
        narrowed=dict(record,host_refs=['other-host'])
        auth=BearerAuth([narrowed],environ={'TOKEN':token})
        self.assertFalse(auth.is_authorized('owner',role='subscriber',host_ref='synthetic-host'))
        auth=BearerAuth([dict(record,roles=['producer'])],environ={'TOKEN':token})
        self.assertFalse(auth.is_authorized('owner',role='subscriber',host_ref='synthetic-host'))

    def test_missing_configured_credentials_fail_before_runtime_creation(self):
        config=json.loads((ROOT/'config/bridge.example.json').read_text(encoding='utf-8'))
        config.update(enabled=True,network_enabled=True,public_origin='https://bridge.example.test',allowed_callback_hosts=['receiver.example.test'])
        target=Path(self.temp.name)/'not-created'
        with self.assertRaises(ValueError):create_app(target,config,environ={})
        self.assertFalse(target.exists())

    def test_result_cas_can_progress_without_overwriting_audit(self):
        self.subscribe();event=self.ingest()
        base={'event_id':event['event_id'],'decision':'needs_more_evidence','evidence_request_ids':[],
              'reason_code':'coverage_incomplete'}
        first=self.rpc('tools/call',{'name':'eventguard_record_result','arguments':base})['result']['structuredContent']
        self.rpc('tools/call',{'name':'eventguard_query_evidence','arguments':{'event_id':event['event_id'],
                    'request_id':'q-cas','operation':'query_listener'}})
        final=dict(base,decision='benign_change',evidence_request_ids=['q-cas'],reason_code='synthetic_evidence_reviewed',
                   expected_result_id=first['result_id'])
        second=self.rpc('tools/call',{'name':'eventguard_record_result','arguments':final})['result']['structuredContent']
        self.assertEqual(second['revision'],2)
        repeated=self.rpc('tools/call',{'name':'eventguard_record_result','arguments':base})['result']['structuredContent']
        self.assertEqual(repeated['result_id'],first['result_id'])
        self.assertEqual(self.store.get_case('owner',event['event_id'])['result_id'],second['result_id'])

    def test_outbox_producer_http_handler_and_callback_states_are_separate(self):
        from eventguard.events.store import EventStore
        self.subscribe()
        config=json.loads((ROOT/'config/bridge.example.json').read_text(encoding='utf-8'))
        config.update(enabled=True,network_enabled=True,public_origin='https://bridge.example.test',allowed_callback_hosts=['receiver.example.test'])
        for record in config['principals']:record['principal_id']='owner'
        token='SYNTHETIC-PRODUCER-NOT-A-REAL-KEY-000001'
        auth=BearerAuth(config['principals'],environ={'EVENTGUARD_PRODUCER_TOKEN':token})
        app=BridgeApplication(config,self.service,auth)
        class InlineHTTP:
            enabled=True
            def post(self,url,body,headers):
                answer={}
                environ={'REQUEST_METHOD':'POST','PATH_INFO':'/events','HTTP_HOST':'bridge.example.test',
                         'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(body)),
                         'HTTP_AUTHORIZATION':headers['Authorization'],'wsgi.input':io.BytesIO(body)}
                raw=b''.join(app(environ,lambda status,headers:answer.update(status=int(status[:3]))))
                return {'status':answer['status'],'body':raw}
        producer=BridgeProducerAdapter('https://bridge.example.test/events',token,InlineHTTP(),enabled=True)
        sender=EventStore(Path(self.temp.name)/'sender')
        event=make_synthetic();sender.enqueue(event)
        result=sender.pump(producer)
        self.assertEqual(result['acknowledged'],1)
        self.assertFalse(result['real_agent_woken'])
        self.assertEqual(self.store.stats()['deliveries']['pending'],1)
        self.assertEqual(self.service.pump_once()['status'],'received')
        self.assertEqual(self.store.stats()['results'],0)
        self.assertEqual(sender.pump(producer)['attempted'],0)

    def test_real_transport_policies_separate_producer_bearer_from_callbacks(self):
        import socket
        from unittest.mock import Mock
        from test_mcp_security import FakeSocket,FakeContext
        from contrib.mcp_bridge.network import SafeHTTPSPoster
        sock=FakeSocket();context=FakeContext()
        resolver=Mock(return_value=[(socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',('8.8.8.8',443))])
        poster=BridgeHTTPSPoster(['bridge.example.test'],enabled=True,resolver=resolver,
            socket_factory=lambda *unused:sock,context_factory=lambda:context)
        headers={'Content-Type':'application/json','Authorization':'Bearer '+'SYNTHETIC-PRODUCER-NOT-A-REAL-KEY-000001'}
        poster.post('https://bridge.example.test/events',b'{}',headers)
        self.assertIn(b'Authorization: Bearer SYNTHETIC-',sock.sent)
        with self.assertRaises(ValueError):SafeHTTPSPoster._header_bytes(headers)
        with self.assertRaises(ValueError):poster.post('https://bridge.example.test/other',b'{}',headers)

    def test_signatures_accept_full_core_identifier_limit(self):
        from contrib.mcp_bridge.security import sign_headers
        headers=sign_headers(self.secret,'e'*160,b'{}','s'*160,1)
        self.assertEqual(len(headers['webhook-id']),160)


if __name__=='__main__':unittest.main()
