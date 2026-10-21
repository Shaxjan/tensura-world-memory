"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {evaluate,validateReserve,EXCLUDED} = require("./reserve_check.js");
const root=__dirname;
const data=JSON.parse(fs.readFileSync(path.join(root,"reserve","ideas-2026-10-21.json"),"utf8"));
const saved=JSON.parse(fs.readFileSync(path.join(root,"reserve","screening-2026-10-21.json"),"utf8"));
const posts=fs.readFileSync(path.join(root,"index","posts.jsonl"),"utf8").trim().split(/\r?\n/).map(JSON.parse);
const journal=fs.readFileSync(path.join(root,"index","editorial.jsonl"),"utf8").trim().split(/\r?\n/).map(JSON.parse);
test("exactly thirty unique concepts, ten in each text slot",()=>{
 assert.deepEqual(validateReserve(data,posts,journal),{"03:00":10,"11:00":10,"15:00":10});
 assert.equal(new Set(data.ideas.map(x=>x.id)).size,30);
 assert.equal(new Set(data.ideas.map(x=>x.event.toLowerCase())).size,30);
});
test("20 Harry Potter and 10 Book Threads concepts",()=>{
 assert.equal(data.ideas.filter(x=>x.universe==="Гарри Поттер").length,20);
 assert.equal(data.ideas.filter(x=>x.universe==="Book Threads").length,10);
});
test("21:00 is reserved for author-provided videos, not concepts",()=>{
 assert.equal(data.ideas.some(x=>x.slot==="21:00"),false);
});
test("no reserved idea was approved, planned or published",()=>{
 assert.ok(data.ideas.every(x=>x.editorial_status==="IDEA_NOT_APPROVED"));
 assert.ok(data.ideas.every(x=>x.canon_review==="PENDING_SOURCE_VERIFICATION"));
});
test("former duplicate concepts excluded and linked to actual published IDs",()=>{
 const ids=new Set(posts.map(p=>p.post_id));
 assert.ok(EXCLUDED.every(x=>ids.has(x.post_id)));
 assert.equal(EXCLUDED.length,7);
 assert.equal(data.ideas.some(x=>x.title.includes("Ужин, который Кикимер")||x.title.includes("упырь изображает")||x.title.includes("Письмо Петунии")),false);
});
test("screening recorded thirty concepts against all 447 author posts and 40 journal cards",()=>{
 assert.equal(saved.ideas_count,30);
 assert.equal(saved.compared_author_posts,447);
 assert.equal(saved.compared_editorial_cards,40);
 assert.equal(saved.ideas.length,30);
 assert.equal(Object.values(saved.summary).reduce((a,b)=>a+b,0),30);
 assert.ok(saved.ideas.every(x=>x.similar_refs.every(r=>r.kind && r.id)));
});
test("sensitive known-neighbor ideas include direct linked post evidence",()=>{
 const by=id=>saved.ideas.find(x=>x.id===id);
 assert.ok(by("G04").similar_refs.some(r=>r.id==="18434719531134355"));
 assert.ok(by("G05").similar_refs.some(r=>r.id==="2026-10-13-1500-locket-fletcher-umbridge"&&r.status==="scheduled"));
 assert.ok(by("G17").similar_refs.some(r=>r.id==="17902019613561331"));
 assert.ok(by("G22").similar_refs.some(r=>r.id==="18015539756984642"));
});
test("no saved candidate was proven DUPLICATE or SAME_STORY",()=>{
 assert.ok(saved.ideas.every(x=>!["DUPLICATE","SAME_STORY"].includes(x.algorithm_verdict)));
 assert.ok(saved.ideas.every(x=>x.screen_status!=="BLOCKED_REWORK"));
});
test("full-corpus screening is deterministic on fixed snapshots",()=>{
 const now=evaluate(data,posts,journal,{as_of:"2026-10-21"});
 assert.equal(JSON.stringify(now),JSON.stringify(saved));
});
test("new day requires recheck; old snapshot cannot certify any concept",()=>{
 const stale=evaluate(data,posts,journal,{as_of:"2026-10-22"});
 assert.equal(stale.ideas.filter(x=>x.screen_status==="STALE_RECHECK").length,30);
});
test("missing source post blocks reserve validation",()=>{
 assert.throws(()=>validateReserve(data,posts.slice(0,-1),journal));
});
