"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const os=require("node:os");
const path=require("node:path");
const {run}=require("./stage8_rescreen.js");
const fixture=require("./test_index_fixtures.js");
const base=path.resolve(__dirname,"../..");
const readJSON=p=>JSON.parse(fs.readFileSync(p,"utf8"));
function tempRun(transform){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),"mirpottera-stage8-screen-"));
 try{
  const idx=path.join(root,"threads/radar/index");
  fs.mkdirSync(idx,{recursive:true});
  for(const name of ["posts.jsonl","editorial.jsonl","manifest.json"])
   fs.copyFileSync(path.join(__dirname,"index",name),path.join(idx,name));
  if(transform)transform(idx);
  const dest=path.join(root,"output");
  const result=run(root,dest,"2026-10-25");
  return {result,ideas:readJSON(path.join(dest,"automated-current-ideas.json")),
   report:readJSON(path.join(dest,"automated-current-screening.json"))};
 }finally{fs.rmSync(root,{recursive:true,force:true})}
}
test("stage8 report checks current published baseline but approves nothing",()=>{
 const x=tempRun();
 assert.equal(x.result.status,"SCREENED_UNAPPROVED");
 assert.ok(x.result.roots>=459);
 assert.equal(x.ideas.count,30);
 assert.equal(x.ideas.source_index_posts,x.result.roots);
 assert.ok(x.ideas.ideas.every(i=>i.editorial_status==="IDEA_NOT_APPROVED"));
 assert.ok(x.report.ideas.every(i=>i.requires_human_approval));
});
test("stage8 reserve advances with synthetic valid new published root",()=>{
 const next=tempRun(index=>{
  const posts=path.join(index,"posts.jsonl");
  const current=fs.readFileSync(posts,"utf8").trim().split(/\r?\n/).map(JSON.parse);
  const sample={...current.find(x=>x.source==="windsor_root_snapshot"),
    post_id:"19999887766554433",original_text:"Новый независимый сюжет",
    search_text:"Новый независимый сюжет",
    url:"https://www.threads.com/@mirpottera/post/Stage8Fixture",
    published_at:"2026-10-25T05:00:00+0000"};
  fs.appendFileSync(posts,JSON.stringify(sample)+"\n");
  const manifestPath=path.join(index,"manifest.json");
  const manifest=readJSON(manifestPath);
  manifest.counts.total_author_roots=current.length+1;
  fs.writeFileSync(manifestPath,JSON.stringify(manifest));
 });
 assert.equal(next.result.roots,fixture.currentIndex.length+1);
 assert.equal(next.report.compared_author_posts,fixture.currentIndex.length+1);
 assert.equal(next.report.ideas_count,30);
 assert.ok(next.ideas.source_index_post_ids.includes("19999887766554433"));
 assert.equal(next.ideas.status,"AUTOMATED_ONLY_NOT_APPROVED");
});
test("refuses to overwrite already staged current reserve",()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),"mirpottera-radar-no-overwrite-"));
 try{
  const dest=path.join(root,"output");
  run(base,dest,"2026-10-25");
  assert.throws(()=>run(base,dest,"2026-10-25"),/Refusing to overwrite/);
 }finally{fs.rmSync(root,{recursive:true,force:true})}
});
