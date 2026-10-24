"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {planDelivery}=require("./inbox_delivery.js");
const inbox=JSON.parse(fs.readFileSync(path.join(__dirname,"inbox","windsor-2026-10-24-retrieved.json"),"utf8"));
const index=fs.readFileSync(path.join(__dirname,"index","posts.jsonl"),"utf8").trim().split(/\r?\n/).map(JSON.parse);
const copy=x=>JSON.parse(JSON.stringify(x));
const clock=new Date("2026-10-24T05:30:00Z");
const live=()=>({status:"done",total_rows:inbox.count,data:inbox.posts.map(p=>({...p,data_fetched_at:inbox.data_fetched_at_utc}))});
function addNew(source){
 const row={...source.data.find(p=>p.post_id==="17899242612398487"),
  post_id:"18888888888888888",post_timestamp:"2026-10-24T04:30:00+0000",
  post_text:"Новая проверочная авторская публикация",
  post_permalink:"https://www.threads.com/@mirpottera/post/FreshIncoming888"};
 source.data.push(row);source.total_rows++;return source;
}

test("known saved inbox is replay safe and does not emit a new file",()=>{
 const p=planDelivery(live(),index,[inbox],{now:clock});
 assert.equal(p.status,"NO_NEW_ROOTS");
 assert.equal(p.save_allowed,false);
 assert.equal(p.snapshot,null);
});
test("an unseen root generates a deterministic unpromoted inbox",()=>{
 const source=addNew(live());
 const a=planDelivery(source,index,[inbox],{now:clock});
 const b=planDelivery(source,index,[inbox],{now:clock});
 assert.equal(a.status,"STAGED_NEW_ROOTS");
 assert.equal(a.save_allowed,true);
 assert.equal(a.filename,b.filename);
 assert.equal(a.serialized,b.serialized);
 assert.match(a.filename,/^windsor-20261024T045831-[a-f0-9]{16}-retrieved\.json$/);
 assert.equal(a.snapshot.state,"INBOX_NOT_INDEXED");
 assert.equal(a.snapshot.count,7);
 assert.equal(a.snapshot.posts.filter(x=>x.post_id==="18888888888888888").length,1);
 assert.equal(a.github_written,false);
 assert.equal(a.index_modified,false);
});
test("the same root in an already saved inbox never triggers repeat delivery",()=>{
 const source=addNew(live());
 const planned=planDelivery(source,index,[inbox],{now:clock});
 const again=planDelivery(source,index,[inbox,planned.snapshot],{now:clock});
 assert.equal(again.status,"NO_NEW_ROOTS");
});
test("immutable conflict blocks delivery even if another root is new",()=>{
 const source=addNew(live());
 source.data.find(p=>p.post_id==="17899242612398487").post_text+=" подменён";
 const plan=planDelivery(source,index,[inbox],{now:clock});
 assert.equal(plan.status,"BLOCKED_CONFLICTS");
 assert.equal(plan.save_allowed,false);
 assert.ok(plan.report.conflicts.length);
});
test("stale provider cached result cannot be written",()=>{
 const source=addNew(live());
 assert.throws(()=>planDelivery(source,index,[inbox],{now:new Date("2026-10-27T00:00:00Z")}),/stale/);
});
test("future provider timestamp is rejected",()=>{
 const source=addNew(live());
 for(const p of source.data)p.data_fetched_at="2026-10-25T05:30:00";
 assert.throws(()=>planDelivery(source,index,[inbox],{now:clock}),/future/);
});
test("inconsistent row fetch timestamps cannot be written",()=>{
 const source=addNew(live());
 source.data[0].data_fetched_at="2026-10-24T04:00:00";
 assert.throws(()=>planDelivery(source,index,[inbox],{now:clock}),/inconsistent/);
});
test("not done, partial or zero-source never creates files",()=>{
 const s=addNew(live());s.status="pending";
 assert.throws(()=>planDelivery(s,index,[inbox],{now:clock}));
 const partial=addNew(live());partial.total_rows--;
 assert.throws(()=>planDelivery(partial,index,[inbox],{now:clock}));
 const zero={status:"done",total_rows:0,data:[]};
 assert.equal(planDelivery(zero,index,[inbox],{now:clock}).save_allowed,false);
});
test("future-dated publication cannot be delivered",()=>{
 const source=addNew(live());
 source.data.find(x=>x.post_id==="18888888888888888").post_timestamp="2026-10-24T07:00:00+0000";
 assert.throws(()=>planDelivery(source,index,[inbox],{now:clock}),/after provider fetch/);
});
