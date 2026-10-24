"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {evaluate,validateReserve,EXCLUDED}=require("./reserve_check.js");

const root=__dirname;
const load=(name)=>JSON.parse(fs.readFileSync(path.join(root,name),"utf8"));
const lines=(name)=>fs.readFileSync(path.join(root,name),"utf8").trim().split(/\r?\n/).map(JSON.parse);
const reserve=load("reserve/ideas-2026-10-23-r4.json");
const screening=load("reserve/screening-2026-10-23-r4.json");
const manifest=load("index/manifest.json");
const replies=load("snapshots/author-continuations-2026-10-23.json");
const posts=lines("index/posts.jsonl");
const journal=lines("index/editorial.jsonl");
const byPost=new Map(posts.map(p=>[p.post_id,p]));

test("R4 uses exact current source sizes, 30 candidates, and 40 separate journal entries",()=>{
 assert.equal(posts.length,454);
 assert.equal(new Set(posts.map(x=>x.post_id)).size,454);
 assert.equal(journal.length,40);
 assert.equal(reserve.source_index_posts,454);
 assert.equal(reserve.source_index_date,"2026-10-23");
 assert.equal(reserve.count,30);
 assert.equal(reserve.ideas.length,30);
 assert.equal(screening.compared_author_posts,454);
 assert.equal(screening.compared_editorial_cards,40);
 assert.deepEqual(validateReserve(reserve,posts,journal),{"03:00":10,"11:00":10,"15:00":10});
});
test("R4 stays a proposal, never an approved post or 21:00 video",()=>{
 assert.equal(new Set(reserve.ideas.map(x=>x.id)).size,30);
 assert.equal(new Set(reserve.ideas.map(x=>x.title)).size,30);
 assert.equal(new Set(reserve.ideas.map(x=>x.event)).size,30);
 assert.ok(reserve.ideas.every(x=>x.editorial_status==="IDEA_NOT_APPROVED"));
 assert.ok(screening.ideas.every(x=>x.author_approved===false && x.originality_certified===false));
 assert.equal(reserve.ideas.some(x=>x.slot==="21:00"),false);
});
test("the index retains exactly 16 separate probable author continuations",()=>{
 assert.equal(manifest.counts.author_continuation_parts,16);
 assert.equal(replies.continuation_count,16);
 assert.equal(replies.continuations.length,16);
 assert.equal(new Set(replies.continuations.map(x=>x.reply_id)).size,16);
 assert.equal(new Set(replies.continuations.map(x=>x.root_post_id)).size,16);
 assert.equal(posts.filter(p=>p.continuations_status==="PROBABLE_NOT_CHAIN_VERIFIED").length,16);
});
test("every probable continuation is indexed only in search text, not replacing the root",()=>{
 for(const c of replies.continuations){
  const p=byPost.get(c.root_post_id);
  assert.ok(p, "missing continuation root: "+c.root_post_id);
  assert.ok(p.search_text.startsWith(p.original_text));
  assert.ok(p.search_text.includes(c.original_text));
  assert.equal(p.original_text.includes(c.original_text),false);
  assert.equal(p.chain_complete,false);
  assert.equal(p.continuations_status,"PROBABLE_NOT_CHAIN_VERIFIED");
  assert.ok(p.author_continuation_parts.some(x=>x.reply_id===c.reply_id));
 }
});
test("historical 414 published roots are never promoted to probable continuations",()=>{
 const historical=posts.filter(x=>x.source==="verified_full_chain");
 assert.equal(historical.length,414);
 assert.ok(historical.every(x=>x.continuations_status!=="PROBABLE_NOT_CHAIN_VERIFIED"));
});
test("current R4 automated comparison executes and reproduces the stored status totals",()=>{
 const report=evaluate(reserve,posts,journal,{as_of:"2026-10-23"});
 assert.equal(report.ideas_count,30);
 assert.equal(report.compared_author_posts,454);
 assert.deepEqual(report.summary,screening.summary);
 assert.deepEqual(screening.summary,{PRECHECKED_LOW_SIMILARITY:15,REVIEW_REQUIRED:15});
});
test("all candidate decisions include narrative evidence and only grounded archive IDs",()=>{
 const idSet=new Set([...posts.map(x=>x.post_id),...journal.map(x=>x.journal_id)]);
 for(const idea of screening.ideas){
  assert.ok(idea.editorial_difference_and_risk);
  assert.ok(idea.semantic_dimensions.event);
  assert.ok(idea.semantic_dimensions.conflict);
  assert.ok(idea.semantic_dimensions.viewpoint);
  assert.ok(idea.semantic_dimensions.central_thesis);
  assert.ok(idea.similar_refs.every(x=>idSet.has(x.id)));
  assert.equal(idea.author_approved,false);
 }
});
test("R4 G21 replaces the risky duplicate Sectumsempra incident",()=>{
 const c=reserve.ideas.find(x=>x.id==="G21");
 assert.ok(c.title.includes("Министр"));
 assert.ok(c.replaces_idea.title.includes("заклинания"));
 assert.ok(EXCLUDED.some(x=>x.post_id==="18057792662603776"));
 assert.ok(c.canon_or_source_basis.includes("слух"),"rumor must not be asserted as certain");
});
test("the latest Hermione coins publication is explicitly flagged as near-repeat",()=>{
 const f=screening.additional_findings.find(x=>x.later_post_id==="18109268174261128");
 assert.ok(f);
 assert.equal(f.first_post_id,"18094564298550359");
 assert.ok(byPost.has(f.first_post_id)&&byPost.has(f.later_post_id));
});
test("new archive data never permits stale screening or automatic originality certification",()=>{
 const stale=evaluate(reserve,posts,journal,{as_of:"2026-10-24"});
 assert.equal(stale.ideas.filter(x=>x.screen_status==="STALE_RECHECK").length,30);
 assert.ok(stale.ideas.every(x=>x.requires_human_approval));
 assert.ok(screening.ideas.every(x=>x.originality_certified===false));
});
test("missing source records or new unreviewed records fail closed",()=>{
 assert.throws(()=>validateReserve(reserve,posts.slice(1),journal));
 const extra={...posts[0],post_id:"unscreened-root"};
 assert.throws(()=>validateReserve(reserve,[...posts,extra],journal));
});
test("former reserve R3 remains invalid against the refreshed index",()=>{
 const old=load("reserve/ideas-2026-10-21-r3.json");
 assert.equal(old.source_index_posts,448);
 assert.throws(()=>validateReserve(old,posts,journal));
});

test("all 414 historical roots retain the original verified full-chain texts",()=>{
 const original=JSON.parse(fs.readFileSync(path.join(root,"..","full-posts-verified.json"),"utf8"));
 assert.equal(original.posts.length,414);
 for(const p of original.posts){
  const index=byPost.get(p.post_id);
  assert.ok(index, "missing historical post: "+p.post_id);
  assert.equal(index.source,"verified_full_chain");
  assert.equal(index.original_text,p.full_text_original||p.original_first_text||"");
  assert.equal(index.search_text,p.full_text_editorial||p.original_first_text||"");
  assert.equal(index.url,p.url);
  assert.equal(index.parts_count,p.parts_count);
 }
});
test("all stored new-root metrics use the latest immutable Windsor snapshot",()=>{
 const snapshots=[
  "windsor-2026-10-13_to_2026-10-20.json",
  "windsor-2026-10-21.json",
  "windsor-2026-10-21_rev2.json",
  "windsor-2026-10-22.json",
  "windsor-2026-10-23.json"
 ];
 const latest=new Map();
 const stable=new Map();
 for(const filename of snapshots){
  const snapshot=load("snapshots/"+filename);
  assert.equal(snapshot.count,snapshot.posts.length);
  for(const p of snapshot.posts){
   if(stable.has(p.post_id)){
    const old=stable.get(p.post_id);
    for(const field of ["post_timestamp","post_text","post_permalink","post_media_type"])
     assert.equal(p[field],old[field], "Conflicting immutable field "+field+" on "+p.post_id);
   }else stable.set(p.post_id,p);
   latest.set(p.post_id,p);
  }
 }
 assert.equal(latest.size,50);
 assert.equal([...latest.values()].filter(p=>p.post_media_type==="REPOST_FACADE").length,10);
 for(const p of latest.values()){
  if(p.post_media_type==="REPOST_FACADE")continue;
  const row=byPost.get(p.post_id);
  assert.ok(row);
  assert.equal(row.original_text,p.post_text);
  assert.equal(row.url,p.post_permalink);
  assert.equal(row.published_at,p.post_timestamp);
  assert.equal(row.metrics.views,p.post_views);
 }
});

test("same-sized substituted published root cannot bypass R4 staleness",()=>{
 const mutated=posts.map(x=>({...x}));
 mutated[0].post_id="19999999999999999";
 assert.equal(mutated.length,posts.length);
 assert.throws(()=>validateReserve(reserve,mutated,journal),/Source IDs changed/);
});
test("same-sized substituted editorial card cannot bypass R4 staleness",()=>{
 const mutated=journal.map(x=>({...x}));
 mutated[0].journal_id="unexpected-journal-id";
 assert.equal(mutated.length,journal.length);
 assert.throws(()=>validateReserve(reserve,posts,mutated),/Source IDs changed/);
});
test("R4 source-ID checkpoints cannot be absent or truncated",()=>{
 const incomplete={...reserve,source_index_post_ids:reserve.source_index_post_ids.slice(1)};
 assert.throws(()=>validateReserve(incomplete,posts,journal));
 const missing={...reserve};delete missing.source_editorial_journal_ids;
 assert.throws(()=>validateReserve(missing,posts,journal));
});
