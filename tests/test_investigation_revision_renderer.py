"""Execute the real revision renderer against a synthetic DOM, not a browser."""
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
const document={activeElement:null};
const target={children:[],replaceChildren(){this.children=[]},append(...v){this.children.push(...v)},
  querySelectorAll(){return this.children.filter(x=>x.tag==='details')}};
function $(id){assert.equal(id,'investigation-revisions');return target}
function node(tag,text,cls){return {tag,text:text??'',cls,dataset:{},open:false,children:[],
  append(...v){this.children.push(...v)},querySelector(k){return this.children.find(x=>x.tag===k)},
  focus(){document.activeElement=this}}}
function when(x){return String(x)}
const eventNames={},sourceNames={listeners:'監聽端點'},states={ok:'成功'};
__LABELS__
function renderInvestigationRevisions(value,preserve=false){__RENDERER__
function flatten(x){return [x.text||'',...(x.children||[]).flatMap(flatten)]}
const c={as_of:'2026-10-26',case_id:'case-synthetic',timeline:[],gaps:[],
  diagnostic_context:{state:'saved',observed_at:'2026-10-26',result_status:'partial',observations:[]}};
function revision(id,state='changed'){return {revision_id:id,case:c,saved_at:123,case_hash:'a'.repeat(64),
  evidence_status:'saved_snapshot',diagnostic_evidence_status:state,missing_event_ids:[],changed_event_ids:[]}}
function data(ids){return {state:'available',revisions:ids.map(x=>revision(x)),count_capacity:'available'}}
function boxes(){return target.children.filter(x=>x.tag==='details')}
renderInvestigationRevisions(data([2,1]));
assert.match(boxes()[0].children[0].text,/保存成員相符.*診斷：目前診斷已變更/);
assert.match(boxes()[0].children.flatMap(flatten).join('|'),/部分觀測，資料不完整/);
boxes()[1].open=true;boxes()[1].querySelector('summary').focus();
renderInvestigationRevisions(data([3,2,1]),true);
assert.deepEqual(boxes().map(x=>x.open),[false,false,true]);
assert.equal(document.activeElement,boxes()[2].querySelector('summary'));
const outside=node('button','outside');outside.focus();renderInvestigationRevisions(data([3,2,1]),true);
assert.equal(document.activeElement,outside);assert.equal(boxes()[2].open,true);
renderInvestigationRevisions(data([1]),false);assert.equal(boxes()[0].open,false);assert.equal(document.activeElement,outside);
renderInvestigationRevisions(null);assert.match(target.children.flatMap(flatten).join('|'),/無法確認/);
console.log('synthetic revision renderer passed');
"""


@unittest.skipUnless(os.name == "nt" and shutil.which("node"), "Windows private Job and existing Node required")
class RevisionRendererBehaviorTests(unittest.TestCase):
    def test_renderer_keeps_context_and_distinguishes_evidence(self):
        labels = next(line for line in JS.splitlines() if line.startswith("const investigationGapLabels="))
        body = JS.split("function renderInvestigationRevisions(value,preserve=false){", 1)[1].split(
            "function renderInvestigation(value){", 1)[0]
        script = FIXTURE.replace("__LABELS__", labels).replace("__RENDERER__", body)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "fixture.js").write_text(script, encoding="utf-8", newline="\n")
            with (root / "stdout").open("wb") as output, (root / "stderr").open("wb") as error:
                child = spawn([shutil.which("node"), str(root / "fixture.js")], stdin=subprocess.DEVNULL,
                              stdout=output, stderr=error)
                try:
                    child.wait(timeout=20)
                finally:
                    receipt = finish(child, "test_teardown", grace=5)
            self.assertTrue(receipt["managed"])
            self.assertTrue(receipt["child_exited"])
            self.assertEqual(receipt["exit_code"], 0)
            self.assertEqual(receipt["remaining_owned_processes"], 0)
            self.assertFalse(receipt["forcibly_terminated"])
            self.assertIn("synthetic revision renderer passed", (root / "stdout").read_text(encoding="utf-8"))
