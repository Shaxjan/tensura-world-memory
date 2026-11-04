"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {checkInbox}=require("./inbox_check.js");
const root=__dirname;
const incoming=JSON.parse(fs.readFileSync(path.join(root,"inbox","windsor-2026-10-24-retrieved.json"),"utf8"));
const {legacyIndex,r5Index}=require("./test_index_fixtures.js");
const indexed=legacyIndex;
const copy=x=>JSON.parse(JSON.stringify(x));

test("real inbox finds exactly two new author roots, one repost, no immutable conflicts",()=>{
 const x=checkInbox(incoming,indexed);
 assert.equal(x.status,"READ_ONLY_REVIEW_READY");
 assert.equal(x.index_roots_before,454);
 assert.equal(x.proposed_roots_after,456);
 assert.deepEqual(x.new_author_ids,["18058181561570070","17899242612398487"]);
 assert.deepEqual(x.repost_ids,["18130014499888055"]);
 assert.equal(x.unchanged_author_ids.length,3);
 assert.ok(x.view_updates.every(v=>v.post_id ? indexed.some(p=>p.post_id===v.post_id) : true));
 assert.equal(x.immutable_conflicts.length,0);
 assert.equal(x.source_promoted,false);
 assert.equal(x.full_account_export_confirmed,false);
});
test("a text revision on a known post blocks promotion",()=>{
 const x=copy(incoming);
 x.posts.find(p=>p.post_id==="18109268174261128").post_text+=" правка";
 const result=checkInbox(x,indexed);
 assert.equal(result.status,"BLOCKED_IMMUTABLE_CONFLICT");
 assert.deepEqual(result.immutable_conflicts,["18109268174261128"]);
 assert.equal(result.proposed_roots_after,null);
});
test("a fabricated earlier retrieval date fails closed",()=>{
 const x=copy(incoming);x.retrieval_date_utc="2026-10-23";
 assert.throws(()=>checkInbox(x,indexed));
});
test("a misleading source period fails closed",()=>{
 const x=copy(incoming);x.period_utc=["2026-10-01","2026-10-24"];
 assert.throws(()=>checkInbox(x,indexed),/period/);
});
test("future-post timestamp beyond receipt is rejected",()=>{
 const x=copy(incoming);
 x.posts.find(p=>p.post_id==="17899242612398487").post_timestamp="2026-10-24T07:00:00+0000";
 assert.throws(()=>checkInbox(x,indexed),/future publication/);
});
test("foreign account and previously promoted inbox are rejected",()=>{
 const x=copy(incoming);x.account="other";
 assert.throws(()=>checkInbox(x,indexed),/account/);
 x.account="mirpottera";x.state="INDEXED";
 assert.throws(()=>checkInbox(x,indexed),/unpromoted/);
});
test("missing indexed baseline fails closed",()=>{
 assert.throws(()=>checkInbox(incoming,[]),/No indexed baseline/);
});


test("promoted inbox does not create new IDs against the current index",()=>{
 const report=checkInbox(incoming,r5Index);
 assert.equal(report.index_roots_before,459);
 assert.deepEqual(report.new_author_ids,[]);
 assert.equal(report.immutable_conflicts.length,0);
});
