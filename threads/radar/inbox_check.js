#!/usr/bin/env node
"use strict";
/* Stage 6 read-only inbox preflight. No publishing, GitHub writes or promotion. */
const fs=require("node:fs");
const path=require("node:path");
const {validateInput,diff}=require("./snapshot_intake.js");

function checkInbox(inbox,indexed){
 if(!inbox||inbox.account!=="mirpottera"||inbox.source!=="Windsor.ai Threads")
  throw Error("Unexpected source or account");
 if(inbox.state!=="INBOX_NOT_INDEXED")throw Error("Not an unpromoted inbox snapshot");
 if(!/^20\d\d-\d\d-\d\d$/.test(inbox.retrieval_date_utc||""))
  throw Error("Missing retrieval date");
 const retrieval=new Date(inbox.retrieval_date_utc+"T00:00:00Z");
 if(Number.isNaN(retrieval.getTime())||retrieval.toISOString().slice(0,10)!==inbox.retrieval_date_utc)
  throw Error("Invalid retrieval date");
 if(!/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(inbox.data_fetched_at_utc||""))
  throw Error("Missing connector retrieval timestamp");
 const fetched=new Date(inbox.data_fetched_at_utc+"Z");
 if(Number.isNaN(fetched.getTime())||fetched.toISOString().slice(0,19)!==inbox.data_fetched_at_utc||
    fetched.toISOString().slice(0,10)!==inbox.retrieval_date_utc)
  throw Error("Retrieval timestamp does not match declared date");
 const rows=validateInput(inbox);
 if(!Array.isArray(inbox.period_utc)||inbox.period_utc.length!==2)
  throw Error("Missing source period");
 const start=rows[0].post_timestamp.slice(0,10);
 const end=rows[rows.length-1].post_timestamp.slice(0,10);
 if(inbox.period_utc[0]!==start||inbox.period_utc[1]!==end)
  throw Error("Source period disagrees with actual posts");
 if(rows.some(x=>Date.parse(x.post_timestamp.replace(/\+0000$/,"Z"))>fetched.getTime()))
  throw Error("Connector snapshot contains future publication");
 if(!Array.isArray(indexed)||!indexed.length)throw Error("No indexed baseline");
 const c=diff(rows,indexed);
 const previous=new Map(indexed.map(x=>[String(x.post_id),x]));
 const viewUpdates=rows.filter(x=>x.post_media_type!=="REPOST_FACADE"&&previous.has(x.post_id)&&
  previous.get(x.post_id).metrics?.views!==x.post_views).map(x=>({
    post_id:x.post_id,before:previous.get(x.post_id).metrics?.views??null,after:x.post_views
  }));
 const changed=c.changed_existing_ids.length>0;
 return {
  status:changed?"BLOCKED_IMMUTABLE_CONFLICT":"READ_ONLY_REVIEW_READY",
  account:"mirpottera",retrieved_at_utc:inbox.data_fetched_at_utc,
  full_account_export_confirmed:false,
  source_rows:rows.length,index_roots_before:indexed.length,
  proposed_roots_after:changed?null:indexed.length+c.new_author_ids.length,
  new_author_ids:c.new_author_ids,unchanged_author_ids:c.identical_ids,
  repost_ids:c.repost_ids,immutable_conflicts:c.changed_existing_ids,
  view_updates:viewUpdates,
  requires_human_review:true,source_promoted:false,index_modified:false,
  next_step:"Verify full source completeness and run full native build + tests before promotion and re-screening"
 };
}
function main(args=process.argv.slice(2)){
 if(args.length!==1)throw Error("Usage: node threads/radar/inbox_check.js threads/radar/inbox/<snapshot>.json");
 const source=path.resolve(args[0]);
 if(!source.includes(path.sep+"inbox"+path.sep)||!source.endsWith(".json"))
  throw Error("Input must be an inbox JSON");
 if(fs.statSync(source).size>15000000)throw Error("Inbox exceeds 15 MB");
 const snapshot=JSON.parse(fs.readFileSync(source,"utf8"));
 const indexed=fs.readFileSync(path.join(__dirname,"index","posts.jsonl"),"utf8")
  .trim().split(/\r?\n/).map(JSON.parse);
 const report=checkInbox(snapshot,indexed);
 console.log(JSON.stringify(report,null,2));
 if(report.immutable_conflicts.length)process.exitCode=2;
}
if(require.main===module){try{main()}catch(e){console.error("Inbox:",e.message);process.exitCode=1}}
module.exports={checkInbox,main};
