#!/usr/bin/env node
"use strict";
/** Automated *preliminary* duplicate screening; no editorial approval. */
const fs=require("node:fs");
const path=require("node:path");
const {evaluate}=require("./reserve_check.js");
const {krasnoyarskToday}=require("./semantic.js");
const ROOT=__dirname;
const json=p=>JSON.parse(fs.readFileSync(p,"utf8"));
const jsonl=p=>fs.readFileSync(p,"utf8").trim().split(/\r?\n/).map(JSON.parse);
function run(candidateRoot,outputDirectory,asOf=krasnoyarskToday()){
 const index=path.join(candidateRoot,"threads","radar","index");
 const posts=jsonl(path.join(index,"posts.jsonl"));
 const journal=jsonl(path.join(index,"editorial.jsonl"));
 const manifest=json(path.join(index,"manifest.json"));
 const template=json(path.join(ROOT,"reserve","ideas-2026-10-25-r5.json"));
 if(posts.length<459||posts.length!==manifest.counts.total_author_roots||journal.length!==40)
  throw Error("Archive counts incompatible with authenticated editorial reserve");
 const sourceDate=manifest.generated_date_utc;
 if(!/^20\d\d-\d\d-\d\d$/.test(sourceDate)||sourceDate>asOf)
  throw Error("Source snapshot date is not valid for Krasnoyarsk screening");
 const ideas={...template,
  schema_version:1,revision:6,
  status:"AUTOMATED_ONLY_NOT_APPROVED",
  source_index_posts:posts.length,source_index_date:sourceDate,
  source_index_post_ids:posts.map(p=>String(p.post_id)).sort(),
  source_editorial_journal_ids:journal.map(p=>String(p.journal_id)).sort(),
  ideas:template.ideas.map(c=>({...c,
    editorial_status:"IDEA_NOT_APPROVED",last_check_date:asOf}))
 };
 const report=evaluate(ideas,posts,journal,{as_of:asOf});
 if(report.ideas_count!==30||report.compared_author_posts!==posts.length
   ||report.ideas.some(c=>!c.requires_human_approval)||ideas.ideas.some(c=>c.editorial_status!=="IDEA_NOT_APPROVED"))
  throw Error("Automatic screening violated approval or source safeguards");
 const dest=path.resolve(outputDirectory);
 fs.mkdirSync(dest,{recursive:true});
 for(const [name,doc] of [
   ["automated-current-ideas.json",ideas],
   ["automated-current-screening.json",report]
 ]) {
  const target=path.join(dest,name);
  if(fs.existsSync(target))throw Error("Refusing to overwrite staged reserve: "+name);
  fs.writeFileSync(target,JSON.stringify(doc,null,2)+"\n",{flag:"wx"});
 }
 return {status:"SCREENED_UNAPPROVED",roots:posts.length,ideas:30,
  summary:report.summary,requires_human_approval:true,source_date:sourceDate};
}
if(require.main===module){
 try{
  if(process.argv.length!==4)throw Error("Usage: stage8_rescreen.js <candidate-root> <empty-output-dir>");
  console.log(JSON.stringify(run(process.argv[2],process.argv[3]),null,2));
 }catch(e){console.error(e.stack||e.message);process.exitCode=1}
}
module.exports={run};
