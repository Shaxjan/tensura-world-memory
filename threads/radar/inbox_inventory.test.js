"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {inventory}=require("./inbox_inventory.js");

const root=__dirname;
const raw=rel=>fs.readFileSync(path.join(root,rel),"utf8");
const {legacyIndex,currentIndex}=require("./test_index_fixtures.js");
const index=legacyIndex;
const first=JSON.parse(raw("inbox/windsor-2026-10-24-retrieved.json"));
const next=JSON.parse(raw("inbox/windsor-20261025T003529Z-eddca5900dc17028-retrieved.json"));
const copy=x=>JSON.parse(JSON.stringify(x));
const boxes=()=>[
 {name:"windsor-2026-10-24-retrieved.json",snapshot:copy(first)},
 {name:"windsor-20261025T003529Z-eddca5900dc17028-retrieved.json",snapshot:copy(next)}
];
const expected=["18058181561570070","17899242612398487","18152771278539108","18472636933140300","17915165559493626"];
test("full backlog finds five new roots without changing 454-root archive",()=>{
 const r=inventory(index,boxes());
 assert.equal(r.status,"PENDING_NATIVE_ACCEPTANCE");
 assert.equal(r.baseline_roots,454);
 assert.equal(r.unique_pending_roots,5);
 assert.equal(r.expected_roots_after_verified_promotion,459);
 assert.deepEqual(r.pending_roots.map(x=>x.post_id),expected);
 assert.equal(r.distinct_repost_facades,4);
 assert.equal(r.conflicts.length,0);
 assert.equal(r.index_modified,false);
 assert.equal(r.source_promoted,false);
 assert.equal(r.source_completeness_unverified,true);
});
test("replayed inboxes do not generate duplicate roots",()=>{
 const prior=boxes();
 const r=inventory(index,[prior[1],prior[0],prior[1]]);
 assert.equal(r.unique_pending_roots,5);
 assert.deepEqual(r.pending_roots.map(x=>x.post_id),expected);
});
test("uses latest October 25 metrics, but never edits original archive",()=>{
 const before=JSON.stringify(index);
 const r=inventory(index,boxes());
 const kram=r.pending_roots.find(x=>x.post_id==="18058181561570070");
 assert.equal(kram.latest_views,1940);
 assert.equal(kram.first_source,"windsor-2026-10-24-retrieved.json");
 assert.equal(kram.last_source,"windsor-20261025T003529Z-eddca5900dc17028-retrieved.json");
 assert.equal(JSON.stringify(index),before);
});
test("date calculations always use Krasnoyarsk UTC+7",()=>{
 const r=inventory(index,boxes());
 assert.equal(r.pending_roots.find(x=>x.post_id==="18058181561570070").post_timestamp_krasnoyarsk,"2026-10-24T03:00:51+0700");
 assert.equal(r.pending_roots.find(x=>x.post_id==="17915165559493626").post_timestamp_krasnoyarsk,"2026-10-25T03:00:18+0700");
});
test("conflicting author text blocks the entire batch",()=>{
 const b=boxes();
 b[1].snapshot.posts.find(x=>x.post_id==="18058181561570070").post_text+=" tampered";
 const r=inventory(index,b);
 assert.equal(r.status,"BLOCKED_CONFLICTS");
 assert.equal(r.pending_roots.length,0);
 assert.ok(r.conflicts.some(x=>x.post_id==="18058181561570070"&&x.fields.includes("post_text")));
});
test("repost ID conflicts also block the whole batch",()=>{
 const b=boxes();
 b[1].snapshot.posts.find(x=>x.post_id==="18130014499888055").post_permalink="https://www.threads.com/@mirpottera/post/OtherRepost";
 const r=inventory(index,b);
 assert.equal(r.status,"BLOCKED_CONFLICTS");
 assert.ok(r.conflicts.some(x=>x.post_id==="18130014499888055"));
});
test("foreign account and incorrect connector identity are refused",()=>{
 const b=boxes();
 b[0].snapshot.account="not_mirpottera";
 assert.throws(()=>inventory(index,b),/Unsafe inbox account/);
 b[0].snapshot.account="mirpottera";
 b[0].snapshot.source_account_id="12345";
 assert.throws(()=>inventory(index,b),/Wrong connected account/);
});
test("invalid time, source period and a future publication are rejected",()=>{
 const b=boxes();b[0].snapshot.data_fetched_at_utc="2026-02-30T04:58:31";
 assert.throws(()=>inventory(index,b));
 const c=boxes();c[0].snapshot.period_utc=["2026-10-01","2026-10-24"];
 assert.throws(()=>inventory(index,c),/period mismatch/);
 const d=boxes();d[0].snapshot.posts.find(x=>x.post_id==="17899242612398487").post_timestamp="2026-10-24T20:00:00+0000";
 assert.throws(()=>inventory(index,d),/after fetch/);
});
test("no baseline and no inbox fail closed",()=>{
 assert.throws(()=>inventory([],boxes()),/Missing indexed/);
 assert.throws(()=>inventory(index,[]),/No saved inbound/);
});
test("wrong state and unsupported full-account claim fail closed",()=>{
 const b=boxes();b[0].snapshot.state="INDEXED";
 assert.throws(()=>inventory(index,b),/Unsafe inbox/);
 const c=boxes();c[0].snapshot.full_account_export_confirmed=true;
 assert.throws(()=>inventory(index,c),/Unverified source/);
});
test("known root cannot be changed in inbox without conflict",()=>{
 const b=boxes();
 b[0].snapshot.posts.find(x=>x.post_id==="18109268174261128").post_text+=" mutated";
 const r=inventory(index,b);
 assert.equal(r.status,"BLOCKED_CONFLICTS");
 assert.ok(r.conflicts.some(x=>x.post_id==="18109268174261128"));
});


test("post-promotion inventory has no pending roots in 459-root index",()=>{
 const r=inventory(currentIndex,boxes());
 assert.equal(r.status,"PENDING_NATIVE_ACCEPTANCE");
 assert.equal(r.baseline_roots,459);
 assert.equal(r.unique_pending_roots,0);
 assert.equal(r.expected_roots_after_verified_promotion,459);
 assert.deepEqual(r.pending_roots,[]);
 assert.equal(r.conflicts.length,0);
 assert.equal(r.index_modified,false);
});
