"use strict";
// Exact published index plus the immutable 24-25 October inbox sources.
// Exercises replay-safe delivery and canonical snapshot normalization.
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {scrutinize}=require("./watch_check.js");
const {planDelivery}=require("./inbox_delivery.js");
const root=__dirname;
const readJSON=rel=>JSON.parse(fs.readFileSync(path.join(root,rel),"utf8"));
const prior=readJSON("inbox/windsor-2026-10-24-retrieved.json");
const saved=readJSON("inbox/windsor-20261025T003529Z-eddca5900dc17028-retrieved.json");
const {legacyIndex,currentIndex}=require("./test_index_fixtures.js");
const index=legacyIndex;
const source=()=>({status:"done",total_rows:saved.count,data:saved.posts.map(x=>({...x}))});
const clock=new Date("2026-10-25T01:00:00Z");
const ids=["18152771278539108","18472636933140300","17915165559493626"];

test("real 25 October source: three new roots after previous saved inbox",()=>{
 const report=scrutinize(source(),index,[prior]);
 assert.equal(index.length,454);
 assert.equal(prior.count,6);
 assert.equal(saved.count,15);
 assert.equal(report.status,"NEW_AUTHOR_ROOTS");
 assert.deepEqual(report.new_author_roots.map(x=>x.post_id),ids);
 assert.equal(report.conflicts.length,0);
 assert.equal(report.new_repost_facades.length,3); // three previously unseen repost facades
});
test("saved 25 October delivery suppresses duplicate alerts and writes",()=>{
 const report=scrutinize(source(),index,[prior,saved]);
 assert.equal(report.status,"NO_NEW_AUTHOR_ROOTS");
 assert.equal(report.new_author_roots.length,0);
 assert.equal(report.conflicts.length,0);
 const plan=planDelivery(source(),index,[prior,saved],{now:clock});
 assert.equal(plan.status,"NO_NEW_ROOTS");
 assert.equal(plan.save_allowed,false);
 assert.equal(plan.snapshot,null);
});
test("planner retains all original fields, including per-row fetch provenance",()=>{
 const p=planDelivery(source(),index,[prior],{now:clock});
 assert.equal(p.status,"STAGED_NEW_ROOTS");
 assert.equal(p.save_allowed,true);
 assert.equal(p.snapshot.count,15);
 assert.equal(p.snapshot.data_fetched_at_utc,"2026-10-25T00:35:29");
 assert.equal(p.snapshot.full_account_export_confirmed,false);
 assert.deepEqual(p.snapshot.read_fields,saved.read_fields);
 assert.ok(p.snapshot.posts.every(x=>x.data_fetched_at==="2026-10-25T00:35:29"));
 const sort=x=>[...x].sort((a,b)=>a.post_id.localeCompare(b.post_id));
 assert.deepEqual(sort(p.snapshot.posts),sort(saved.posts));
});
test("incoming provider order does not change deterministic canonical snapshot",()=>{
 const a=planDelivery(source(),index,[prior],{now:clock});
 const reversed=source();
 reversed.data.reverse();
 const b=planDelivery(reversed,index,[prior],{now:clock});
 assert.equal(a.filename,b.filename);
 assert.equal(a.serialized,b.serialized);
});
test("known source text conflict blocks staging of unrelated fresh roots",()=>{
 const live=source();
 live.data.find(x=>x.post_id===ids[0]).post_text+=" изменение";
 const p=planDelivery(live,index,[prior,saved],{now:clock});
 assert.equal(p.status,"BLOCKED_CONFLICTS");
 assert.equal(p.save_allowed,false);
 assert.equal(p.report.conflicts.length,1);
});


test("replayed October 25 sources are known after actual 459-root promotion",()=>{
 const r=scrutinize(source(),currentIndex,[]);
 assert.equal(r.status,"NO_NEW_AUTHOR_ROOTS");
 assert.deepEqual(r.new_author_roots,[]);
});
