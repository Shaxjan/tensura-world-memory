"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {scrutinize}=require("./watch_check.js");
const root=__dirname;
const inbox=JSON.parse(fs.readFileSync(path.join(root,"inbox","windsor-2026-10-24-retrieved.json"),"utf8"));
const {legacyIndex,r5Index}=require("./test_index_fixtures.js");
const index=legacyIndex;
const clone=x=>JSON.parse(JSON.stringify(x));
const source=()=>({status:"done",total_rows:inbox.count,data:clone(inbox.posts)});

test("24 October inbox posts do not trigger repeated new-root alerts",()=>{
 const report=scrutinize(source(),index,[inbox]);
 assert.equal(report.status,"NO_NEW_AUTHOR_ROOTS");
 assert.equal(report.new_author_roots.length,0);
 assert.equal(report.known_author_roots.length,5);
 assert.equal(report.conflicts.length,0);
 assert.equal(report.github_modified,false);
});
test("without saved inbox the same pull correctly shows two not-indexed roots",()=>{
 const report=scrutinize(source(),index,[]);
 assert.equal(report.status,"NEW_AUTHOR_ROOTS");
 assert.deepEqual(report.new_author_roots.map(x=>x.post_id),
  ["18058181561570070","17899242612398487"]);
});
test("newly published root after saved inbox is reported only once per ID",()=>{
 const live=source();
 live.data.push({...inbox.posts.find(x=>x.post_id==="17899242612398487"),
  post_id:"18888888888888888",
  post_permalink:"https://www.threads.com/@mirpottera/post/New20261024"});
 live.total_rows++;
 const r=scrutinize(live,index,[inbox]);
 assert.equal(r.status,"NEW_AUTHOR_ROOTS");
 assert.deepEqual(r.new_author_roots.map(x=>x.post_id),["18888888888888888"]);
});
test("repost facade never counts as original author root",()=>{
 const live=source();
 live.data.push({...inbox.posts.find(x=>x.post_media_type==="REPOST_FACADE"),
  post_id:"18888888888888889",
  post_permalink:"https://www.threads.com/@mirpottera/post/NewRepost10"});
 live.total_rows++;
 const r=scrutinize(live,index,[inbox]);
 assert.equal(r.new_author_roots.length,0);
 assert.deepEqual(r.new_repost_facades,["18888888888888889"]);
});
test("immutable conflict with saved inbox blocks new-root notification",()=>{
 const live=source();
 live.data.find(p=>p.post_id==="17899242612398487").post_text+=" изменён";
 const r=scrutinize(live,index,[inbox]);
 assert.equal(r.status,"BLOCKED_CONFLICTS");
 assert.ok(r.conflicts.some(c=>c.post_id==="17899242612398487"));
});
test("malformed, pending or partial Windsor result is not counted",()=>{
 for(const bad of [
  {status:"pending",total_rows:6,data:clone(inbox.posts)},
  {status:"done",total_rows:7,data:clone(inbox.posts)},
  {status:"done",data:clone(inbox.posts)},
 ]){
  assert.throws(()=>scrutinize(bad,index,[inbox]));
 }
});
test("repeated source records and substituted permalink fail closed",()=>{
 const duplicate=source();
 duplicate.data.push(clone(duplicate.data[0]));duplicate.total_rows++;
 assert.throws(()=>scrutinize(duplicate,index,[inbox]));
 const swapped=source();swapped.data[0].post_permalink="https://www.threads.com/@mirpottera/post/WrongPost";
 assert.equal(scrutinize(swapped,index,[inbox]).status,"BLOCKED_CONFLICTS");
});
test("empty completed date range is not falsely called a new publication",()=>{
 const r=scrutinize({status:"done",data:[],total_rows:0},index,[inbox]);
 assert.equal(r.status,"NO_NEW_AUTHOR_ROOTS");
 assert.equal(r.source_completeness_unverified,true);
});
test("foreign or promoted inbox is rejected",()=>{
 const invalid=clone(inbox);invalid.account="someoneelse";
 assert.throws(()=>scrutinize(source(),index,[invalid]));
 invalid.account="mirpottera";invalid.state="PROMOTED";
 assert.throws(()=>scrutinize(source(),index,[invalid]));
});


test("current 459-root index suppresses alerts even without old inbox files",()=>{
 const r=scrutinize(source(),r5Index,[]);
 assert.equal(r.status,"NO_NEW_AUTHOR_ROOTS");
 assert.deepEqual(r.new_author_roots,[]);
});
