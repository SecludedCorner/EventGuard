"""Actual source renderer and node helper in Node; synthetic DOM, not browser."""
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
function element(){return {textContent:'',children:[],append(...v){this.children.push(...v)},replaceChildren(...v){this.children=v},set innerHTML(v){throw Error('HTML insertion forbidden')}}}
const document={createElement:element},targets=new Map();
function $(id){if(!targets.has(id))targets.set(id,element());return targets.get(id)}
function when(x){return x||'尚無紀錄'}
__LABELS__
__HELPERS__
__SOURCES__
const replies=[];
async function api(path){assert.equal(path,'/api/sources');return await replies.shift()()}
function rows(){return SOURCE_IDS.map(source_id=>({source_id,status:'ok',saved_status:'ok',freshness:'fresh',
  last_collected_at:'2026-01-01T00:00:00Z',last_success_at:'2025-12-31T00:00:00Z',last_success_state:'known',row_count:0,reasons:[]}))}
function text(x){return x.textContent+' '+x.children.map(text).join(' ')}
function saved(){return text($('source-cards'))}
async function render(value){replies.push(()=>value);await sources()}
async function run(){
  let value=rows();value[0].status=value[0].saved_status='denied';value[0].name='<img src=x onerror=attack()>';value[0].reasons=[{reason:'<script>attack()</script>'}];
  await render({sources:value});assert.equal($('source-cards').children.length,7);assert.match(saved(),/目前：拒讀/);assert.ok(saved().includes(when('2025-12-31T00:00:00Z')));assert.match(saved(),/<script>attack/);
  value=rows();value[0].status='stale';value[0].freshness='stale';await render({sources:value});assert.match(saved(),/結果：成功。目前：資料過期/);assert.match(saved(),/新鮮度：已過期/);
  for(const [state,at] of [['unknown',null],['known','invalid'],['known','2099-01-01T00:00:00Z']]){
    value=rows();value.forEach(x=>{x.last_success_state=state;x.last_success_at=at});await render({sources:value});assert.match(saved(),/未知／尚無成功紀錄/);
  }
  await render({sources:rows().reverse()});assert.equal($('source-cards').children[0].children[0].textContent,'Defender');assert.match(saved(),/觀測列數：0/);assert.match($('source-read-state').textContent,/不代表目前主機安全/);
  replies.push(()=>Promise.reject(Error('private fixture')));await sources();assert.match(saved(),/未知/);assert.ok(!saved().includes(when('2025-12-31T00:00:00Z')));assert.match($('source-read-state').textContent,/讀取失敗/);
  for(const sources of [[],rows().slice(1),[...rows().slice(0,6),rows()[0]]]){await render({sources});assert.match(saved(),/未知/);assert.equal($('source-cards').children.length,1)}
  let resolveOld;replies.push(()=>new Promise(resolve=>{resolveOld=resolve}));const old=sources();assert.match(saved(),/正在讀取/);
  value=rows();value[0].status=value[0].saved_status='denied';await render({sources:value});const current=saved();resolveOld({sources:rows()});await old;assert.equal(saved(),current);
  let rejectOld;replies.push(()=>new Promise((resolve,reject)=>{rejectOld=reject}));const failed=sources();await render({sources:value});rejectOld(Error('old failure'));await failed;assert.equal(saved(),current);
  assert.equal(replies.length,0);console.log('actual source renderer passed synthetic six-scenario and failure checks');
}
run().catch(()=>{process.exitCode=1;console.error('synthetic source assertions failed')});
"""


@unittest.skipUnless(os.name == 'nt' and shutil.which('node'), 'Windows private Job and existing Node required')
class WebSourceReadStateTests(unittest.TestCase):
    def test_actual_source_renderer_rejects_invalid_and_stale_replies(self):
        labels = '\n'.join(line for line in JS.splitlines() if line.startswith(('const sourceNames=', 'const states=', 'const SOURCE_IDS=')))
        helpers = 'function node(' + JS.split('function node(', 1)[1].split('function renderHandlingHistory', 1)[0]
        sources = 'let sourceCardsSequence=0;\nasync function sources(){' + JS.split('async function sources(){', 1)[1].split('async function rules(){', 1)[0]
        script = FIXTURE.replace('__LABELS__', labels).replace('__HELPERS__', helpers).replace('__SOURCES__', sources)
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
            self.assertIn('actual source renderer passed', (root/'stdout').read_text(encoding='utf-8'))
