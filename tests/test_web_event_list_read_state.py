"""Run real event-list/refresh JS with synthetic DOM/API; not browser evidence."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from eventguard.processes import finish, spawn
from eventguard.web import JS


FIXTURE = r"""
'use strict';
const assert=require('node:assert/strict');
let eventSequence=0,detailSequence=0,deliverySequence=0,selected=null,offset=0,filterUrlValid=true;
let reloadPending=false,busy=false,refreshQueued=false,tab='events';
const document={activeElement:null},targets=new Map();
function node(tag,text){return {tag,textContent:text??'',children:[],dataset:{},disabled:false,
  append(...v){this.children.push(...v)},replaceChildren(...v){this.children=v},addEventListener(name,fn){this.click=fn},querySelectorAll(){return this.children.flatMap(x=>x.tag==='button'?[x]:x.querySelectorAll())},focus(){document.activeElement=this}}}
function $(id){if(!targets.has(id))targets.set(id,node('div'));return targets.get(id)}
class FormData{constructor(){return new URLSearchParams()}}
const severity={},sourceNames={},handling={},eventNames={};function when(x){return x}
const replies=[],failures=[];function fail(error){failures.push(error.message)}
async function api(path){assert.ok(path.startsWith('/api/events?'));return await replies.shift()()}
async function detail(){throw Error('unexpected detail read')}
async function sourceGap(){}async function refreshNotice(){throw Error('synthetic_notice_failure')}
async function sources(){}async function advisories(){}async function rules(){}async function agent(){}
__INVALIDATE__
__EVENTS__
__REFRESH__
function event(id){return {event_id:id,severity:'high',source:'listeners',status:'new',event_type:'listener.changed',observed_at:'2026-01-01'}}
function data(id){return {events:[event(id)],total:1,has_more:false}}
function text(x){return String(x.textContent)+' '+x.children.map(text).join(' ')}
function rows(){return $('event-rows').querySelectorAll().map(x=>x.dataset.eventId)}
async function read(value){replies.push(()=>value);await events()}
async function run(){
  await read(data('a'));assert.deepEqual(rows(),['a']);assert.match($('count').textContent,/符合條件 1/);
  selected='a';$('detail').hidden=false;
  replies.push(()=>Promise.reject(Error('private fixture')));await events();
  assert.match($('count').textContent,/讀取失敗.*未知/);assert.deepEqual(rows(),[]);
  assert.equal($('prev').disabled,true);assert.equal($('next').disabled,true);assert.equal(selected,null);assert.equal($('detail').hidden,true);
  await read(data('b'));assert.deepEqual(rows(),['b']);assert.match($('count').textContent,/符合條件 1/);
  for(const value of [{events:[],total:1,has_more:true},{events:[event('x'),event('x')],total:2,has_more:false},{events:[event('bad\nID')],total:1,has_more:false},{}]){
    await read(value);assert.match($('count').textContent,/未知/);assert.deepEqual(rows(),[]);
  }
  await read({events:[],total:0,has_more:false});assert.match(text($('event-rows')),/沒有符合條件.*不代表主機安全/);
  let resolveOld;replies.push(()=>new Promise(resolve=>{resolveOld=resolve}));const old=events();assert.equal($('next').disabled,true);
  await read(data('new'));resolveOld(data('old'));await old;assert.deepEqual(rows(),['new']);
  let rejectOld;replies.push(()=>new Promise((resolve,reject)=>{rejectOld=reject}));const late=events();await read(data('latest'));
  rejectOld(Error('old failure'));await late;assert.deepEqual(rows(),['latest']);
  replies.push(()=>data('after-notice-failure'));await refresh();assert.deepEqual(rows(),['after-notice-failure']);
  assert.match(text($('notice')),/無法確認/);assert.equal(busy,false);assert.equal(replies.length,0);
  console.log('actual event list functions passed synthetic error and ordering checks');
}
run().catch(()=>{process.exitCode=1;console.error('synthetic event list assertions failed')});
"""


@unittest.skipUnless(os.name == 'nt' and shutil.which('node'), 'Windows private Job and existing Node required')
class WebEventListReadStateTests(unittest.TestCase):
    def test_actual_list_and_refresh_fail_closed_without_stale_counts(self):
        events = 'async function events(){' + JS.split('async function events(){', 1)[1].split('async function detail(', 1)[0]
        refresh = 'async function refresh(){' + JS.split('async function refresh(){', 1)[1].split("$('filters').addEventListener", 1)[0]
        invalidate = 'function invalidateEventList(){' + JS.split('function invalidateEventList(){', 1)[1].split('function writeFilterUrl()', 1)[0]
        script = FIXTURE.replace('__EVENTS__', events).replace('__REFRESH__', refresh).replace('__INVALIDATE__', invalidate)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'fixture.js').write_text(script, encoding='utf-8')
            with (root/'stdout').open('wb') as output, (root/'stderr').open('wb') as error:
                child = spawn([shutil.which('node'), str(root/'fixture.js')], stdin=subprocess.DEVNULL, stdout=output, stderr=error)
                try:
                    child.wait(timeout=20)
                finally:
                    receipt = finish(child, 'test_teardown', grace=5)
            self.assertTrue(receipt['managed'])
            self.assertTrue(receipt['child_exited'])
            self.assertEqual(receipt['exit_code'], 0)
            self.assertEqual(receipt['remaining_owned_processes'], 0)
            self.assertFalse(receipt['forcibly_terminated'])
            self.assertIn('actual event list functions passed', (root/'stdout').read_text(encoding='utf-8'))
