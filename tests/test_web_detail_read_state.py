"""Execute actual Web detail code with a synthetic DOM/API, not a browser."""
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
let selected=null,detailSequence=0,deliverySequence=0;
const elements=new Map(),buttons=['new','read','handled','ignored'].map(status=>({dataset:{status},disabled:false,addEventListener(name,fn){this.click=fn}}));
function $(id){if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,dataset:{},textContent:'',children:[],
  replaceChildren(...items){this.children=items},append(...items){this.children.push(...items)},querySelectorAll(){return buttons},addEventListener(name,fn){this.click=fn}});return elements.get(id)}
function node(tag,text){return {tag,text}}
function when(x){return x}
const severity={},sourceNames={},handling={};
function renderHandlingHistory(x){$('handling-history').replaceChildren(node('p',x))}
function renderInvestigation(x){$('investigation-view').replaceChildren(node('p',x))}
function renderInvestigationRevisions(x){$('investigation-revisions').replaceChildren(node('p',x))}
const calls=[],replies=[];
async function api(path){calls.push(path);assert.ok(path.startsWith('/api/events/'));return await replies.shift()(path)}
__DETAIL__
__DELIVERY__
__ACTIONS__
const event=id=>({event_id:id,severity:'high',source:'listeners',status:'new',observed_at:'2026-01-01',guidance:{observation:'saved fixture'}});
function success(id){replies.push(()=>event(id),()=>({state:'saved',event_id:id}))}
async function run(){
  success('a');await detail('a');assert.equal($('detail-id').textContent,'a');assert.match($('detail-json').textContent,/"event_id": "a"/);
  assert.ok(buttons.some(b=>!b.disabled));
  replies.push(()=>Promise.reject(Error('private synthetic message')));const before=calls.length;await detail('a');
  assert.equal(calls.length,before+1);assert.match($('detail-read-state').textContent,/讀取失敗.*未知/);
  assert.ok(buttons.every(b=>b.disabled));assert.equal($('investigate').disabled,true);
  const failedCalls=calls.length;await $('investigate').click();await buttons[2].click();assert.equal(calls.length,failedCalls);
  for(const id of ['detail-json','delivery-json'])assert.match($(id).textContent,/未知/);
  for(const id of ['guidance','handling-history','investigation-view','investigation-revisions'])assert.match($(id).children[0].text,/未知/);
  assert.ok(!JSON.stringify([...elements.values()]).includes('private synthetic message'));
  success('a');await detail('a');assert.match($('detail-read-state').textContent,/已讀取/);assert.equal($('investigate').disabled,false);
  replies.push(()=>event('different-case'));await detail('a');assert.match($('detail-read-state').textContent,/未知/);
  assert.ok(!$('detail-json').textContent.includes('different-case'));assert.ok(buttons.every(b=>b.disabled));
  let rejectOld;replies.push(()=>new Promise((resolve,reject)=>{rejectOld=reject}));const old=detail('a');
  assert.ok(buttons.every(b=>b.disabled));assert.equal($('investigate').disabled,true);
  await Promise.resolve();success('b');await detail('b');const saved=$('detail-json').textContent;
  rejectOld(Error('old failure'));await old;assert.equal($('detail-json').textContent,saved);assert.equal($('detail-id').textContent,'b');
  let resolveOld;replies.push(()=>new Promise(resolve=>{resolveOld=resolve}));const stale=detail('a');
  await Promise.resolve();success('b');await detail('b');resolveOld(event('a'));await stale;
  assert.equal($('detail-id').textContent,'b');assert.match($('detail-json').textContent,/"event_id": "b"/);
  assert.equal(replies.length,0);console.log('actual Web detail functions passed synthetic failure and ordering checks');
}
run().catch(()=>{process.exitCode=1;console.error('synthetic Web detail assertions failed')});
"""


@unittest.skipUnless(os.name == 'nt' and shutil.which('node'), 'Windows private Job and existing Node required')
class WebDetailReadStateTests(unittest.TestCase):
    def test_failure_identity_retry_and_late_results_use_real_detail_functions(self):
        detail = 'async function detail(id){' + JS.split('async function detail(id){', 1)[1].split('async function sources(){', 1)[0]
        delivery = 'const showDetail=detail;' + JS.split('const showDetail=detail;', 1)[1].split("$('return-to-list')", 1)[0]
        investigate = "$('investigate').addEventListener" + JS.split("$('investigate').addEventListener", 1)[1].split('function openNoticeSeverity', 1)[0]
        status = "for(const button of $('status-buttons').querySelectorAll('button'))" + JS.split("for(const button of $('status-buttons').querySelectorAll('button'))", 1)[1].split('restoreFilterUrl();renderApplication();', 1)[0]
        script = FIXTURE.replace('__DETAIL__', detail).replace('__DELIVERY__', delivery).replace('__ACTIONS__', investigate + status)
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
            self.assertIn('actual Web detail functions passed', (root/'stdout').read_text(encoding='utf-8'))
