"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const intake=require("./snapshot_intake.js");
const dir=__dirname;
const saved=JSON.parse(fs.readFileSync(path.join(dir,"snapshots","windsor-2026-10-21.json"),"utf8"));
const posts=fs.readFileSync(path.join(dir,"index","posts.jsonl"),"utf8").trim().split(/\r?\n/).map(JSON.parse);
function copy(x){return JSON.parse(JSON.stringify(x));}
test("archived snapshot validated including one repost",()=>{
 const x=intake.validateInput(saved);
 assert.equal(x.length,3);
 assert.equal(x.filter(p=>p.post_media_type==="REPOST_FACADE").length,1);
});
test("old snapshot does not add duplicated published posts",()=>{
 const outcome=intake.diff(intake.validateInput(saved),posts);
 assert.equal(outcome.new_author_ids.length,0);
 assert.equal(outcome.identical_ids.length,2);
 assert.equal(outcome.repost_ids.length,1);
 assert.equal(outcome.needs_manual_review,false);
});
test("new validated post is reported without mutating archive",()=>{
 const x=copy(saved);
 x.posts[1].post_id="19999999999999999";
 x.posts[1].post_permalink="https://www.threads.com/@mirpottera/post/NewUnseen99";
 const outcome=intake.diff(intake.validateInput(x),posts);
 assert.equal(outcome.new_author_ids.length,1);
 assert.equal(posts.length,447);
});
test("changed text for known ID requires manual review",()=>{
 const x=copy(saved);
 x.posts.find(p=>p.post_media_type==="TEXT_POST").post_text+=" изменённый текст";
 const result=intake.diff(intake.validateInput(x),posts);
 assert.equal(result.changed_existing_ids.length,1);
 assert.equal(result.needs_manual_review,true);
});
test("reject duplicate IDs before import",()=>{
 const x=copy(saved);
 x.posts[1].post_id=x.posts[0].post_id;
 assert.throws(()=>intake.validateInput(x));
});
test("reject missing permalink or wrong account",()=>{
 const x=copy(saved);
 x.posts[1].post_permalink="https://evil.example/payload";
 assert.throws(()=>intake.validateInput(x));
 x.posts[1].post_permalink=saved.posts[1].post_permalink;
 x.account="another_account";
 assert.throws(()=>intake.validateInput(x));
});
test("reject post without full timestamp or text",()=>{
 const x=copy(saved);
 x.posts[1].post_timestamp="2026-10-21";
 assert.throws(()=>intake.validateInput(x));
 x.posts[1].post_timestamp=saved.posts[1].post_timestamp;
 x.posts[1].post_text="";
 assert.throws(()=>intake.validateInput(x));
});
test("reject partial export and invalid metrics",()=>{
 const x=copy(saved);
 x.count=99;
 assert.throws(()=>intake.validateInput(x));
 x.count=3;
 x.posts[1].post_views=-10;
 assert.throws(()=>intake.validateInput(x));
});
test("envelope preserves day range and schema",()=>{
 const rows=intake.validateInput(saved),e=intake.envelope(rows,{retrieval_date_utc:"2026-10-21"});
 assert.equal(e.count,3);
 assert.equal(e.account,"mirpottera");
 assert.equal(e.period_utc[0],"2026-10-21");
 assert.deepEqual(e.read_fields,["post_id","post_timestamp","post_text","post_permalink","post_media_type","post_views"]);
});
test("all source timestamps parse as UTC",()=>{
 const rows=intake.validateInput(saved);
 assert.ok(rows.every(x=>intake.utcDate(x.post_timestamp)==="2026-10-21"));
});
