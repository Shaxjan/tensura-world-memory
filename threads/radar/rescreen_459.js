"use strict";
const fs=require("node:fs");
const path=require("node:path");
const {evaluate}=require("./reserve_check.js");
const root=__dirname;
const load=f=>JSON.parse(fs.readFileSync(path.join(root,f),"utf8"));
const lines=f=>fs.readFileSync(path.join(root,f),"utf8").trim().split(/\r?\n/).map(JSON.parse);
const old=load("reserve/ideas-2026-10-23-r4.json");
const posts=lines("index/posts.jsonl"), journal=lines("index/editorial.jsonl");
if(posts.length!==459||journal.length!==40)throw Error("Unexpected new index size");
const reserve={...old,revision:5,source_index_posts:posts.length,
 source_index_post_ids:posts.map(x=>String(x.post_id)).sort(),
 source_editorial_journal_ids:journal.map(x=>String(x.journal_id)).sort(),
 source_index_date:"2026-10-25",status:"UNAPPROVED_R5_AUTOMATED_RESCREEN_459",
 ideas:old.ideas.map(x=>({...x,last_check_date:"2026-10-25"}))};
const report=evaluate(reserve,posts,journal,{as_of:"2026-10-25"});
if(report.ideas_count!==30||report.compared_author_posts!==459 ||
 report.ideas.some(x=>!x.requires_human_approval))throw Error("Unsafe candidate rescreen");
const out=path.join(root,"reserve");
fs.writeFileSync(path.join(out,"ideas-2026-10-25-r5.json"),JSON.stringify(reserve,null,2)+"\n");
fs.writeFileSync(path.join(out,"screening-2026-10-25-r5.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({status:"R5_AUTOMATED_ONLY",roots:459,journal:40,summary:report.summary,
 pending_human_review:30,output_files:["ideas-2026-10-25-r5.json","screening-2026-10-25-r5.json"]},null,2));
