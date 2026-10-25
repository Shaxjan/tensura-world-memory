"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {evaluate,validateReserve}=require("./reserve_check.js");
const {currentIndex,r5Index,legacyIndex,PROMOTED_IDS}=require("./test_index_fixtures.js");
const readJSON=f=>JSON.parse(fs.readFileSync(path.join(__dirname,f),"utf8"));
const readLines=f=>fs.readFileSync(path.join(__dirname,f),"utf8").trim().split(/\r?\n/).map(JSON.parse);
const r5=readJSON("reserve/ideas-2026-10-25-r5.json");
const screening=readJSON("reserve/screening-2026-10-25-r5.json");
const journal=readLines("index/editorial.jsonl");
test("R5 checkpoints all 459 real published IDs and all 40 editorial IDs",()=>{
 assert.equal(r5Index.length,459);
 assert.equal(legacyIndex.length,454);
 assert.equal(r5.source_index_posts,459);
 assert.equal(r5.source_index_date,"2026-10-25");
 assert.equal(r5.revision,5);
 assert.deepEqual(r5.source_index_post_ids,r5Index.map(x=>String(x.post_id)).sort());
 assert.deepEqual(r5.source_editorial_journal_ids,journal.map(x=>String(x.journal_id)).sort());
 assert.ok([...PROMOTED_IDS].every(id=>currentIndex.some(p=>String(p.post_id)===id)));
 assert.deepEqual(validateReserve(r5,r5Index,journal),{"03:00":10,"11:00":10,"15:00":10});
});
test("R5 comparison reproduces stored result on all 459 roots",()=>{
 const result=evaluate(r5,r5Index,journal,{as_of:"2026-10-25"});
 assert.equal(result.compared_author_posts,459);
 assert.equal(result.compared_editorial_cards,40);
 assert.equal(result.ideas_count,30);
 assert.deepEqual(result.summary,screening.summary);
 assert.deepEqual(result.ideas.map(x=>x.screen_status),
                  screening.ideas.map(x=>x.screen_status));
 assert.ok(result.ideas.every(x=>x.requires_human_approval));
 assert.ok(r5.ideas.every(x=>x.editorial_status==="IDEA_NOT_APPROVED"));
});
test("R5 must fail closed if even one promoted post is lost or replaced",()=>{
 assert.throws(()=>validateReserve(r5,r5Index.slice(1),journal));
 const swapped=r5Index.map(x=>({...x}));
 const p=swapped.find(x=>PROMOTED_IDS.has(String(x.post_id)));
 p.post_id="19999888887777777";
 assert.throws(()=>validateReserve(r5,swapped,journal),/IDs changed/);
});
test("R5 becomes stale on next Krasnoyarsk day without new sync",()=>{
 const report=evaluate(r5,r5Index,journal,{as_of:"2026-10-27"});
 assert.equal(report.ideas.filter(x=>x.screen_status==="STALE_RECHECK").length,30);
});


test("newly promoted Nick and McGonagall near-misses remain linked for human review",()=>{
 for(const [id,published] of [["G12","17915165559493626"],["G17","17899242612398487"]]){
   const idea=screening.ideas.find(x=>x.id===id);
   assert.ok(idea);
   assert.equal(idea.screen_status,"REVIEW_REQUIRED");
   assert.ok(idea.similar_refs.some(ref=>ref.id===published &&
     typeof ref.note==="string" && ref.note.length>40));
   assert.equal(idea.requires_human_approval,true);
 }
});
