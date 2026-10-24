#!/usr/bin/env node
"use strict";
/*
 * Stage 6 delivery preparation. Pure planning, no outbound requests or
 * repository writes. A separate authorized runner may save the candidate
 * into threads/radar/inbox/ on the radar draft branch only.
 */
const crypto=require("node:crypto");
const {scrutinize}=require("./watch_check.js");
const {validateInput,utcDate}=require("./snapshot_intake.js");
const FIELDS=["post_id","post_timestamp","post_text","post_permalink","post_media_type","post_views"];
const ACCOUNT="mirpottera";
const ACCOUNT_ID="28902703019346338";

function fetchTimestamp(live,now=new Date()){
 if(!live||live.status!=="done"||!Array.isArray(live.data))
  throw Error("Windsor response is not done");
 if(!Number.isSafeInteger(live.total_rows)||live.total_rows!==live.data.length)
  throw Error("Missing or inconsistent total_rows");
 if(!live.data.length)return null;
 const stamps=[...new Set(live.data.map(x=>x.data_fetched_at))];
 if(stamps.length!==1||!/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z)?$/.test(stamps[0]||""))
  throw Error("Missing or inconsistent data_fetched_at for source rows");
 const fetched=new Date(stamps[0].endsWith("Z")?stamps[0]:stamps[0]+"Z");
 if(Number.isNaN(fetched.getTime())||fetched.toISOString().slice(0,19)!==stamps[0].slice(0,19))
  throw Error("Invalid provider fetch timestamp");
 const age=now.getTime()-fetched.getTime();
 if(age< -5*60*1000||age>36*3600*1000)
  throw Error("Provider pull is stale or dated in the future");
 return fetched;
}

function planDelivery(live,index,inboxes=[],options={}){
 const now=options.now||new Date();
 const status=scrutinize(live,index,inboxes);
 const fetched=fetchTimestamp(live,now);
 if(status.conflicts.length)
  return {status:"BLOCKED_CONFLICTS",report:status,snapshot:null,filename:null,save_allowed:false};
 if(!status.new_author_roots.length)
  return {status:"NO_NEW_ROOTS",report:status,snapshot:null,filename:null,save_allowed:false};
 if(!fetched)throw Error("New roots are impossible without source rows");
 const rows=validateInput({account:ACCOUNT,count:live.total_rows,posts:live.data});
 if(rows.some(p=>Date.parse(p.post_timestamp.replace(/\+0000$/,"Z"))>fetched.getTime()))
  throw Error("Publication after provider fetch");
 const dates=rows.map(p=>utcDate(p.post_timestamp)).sort();
 const retrieved=fetched.toISOString().slice(0,10);
 if(dates[dates.length-1]>retrieved)throw Error("Source date is earlier than a post");
 const snapshot={
  schema_version:1,account:ACCOUNT,source:"Windsor.ai Threads",
  source_account_id:ACCOUNT_ID,retrieval_date_utc:retrieved,
  data_fetched_at_utc:fetched.toISOString().slice(0,19),
  period_utc:[dates[0],dates[dates.length-1]],
  count:rows.length,read_fields:FIELDS,state:"INBOX_NOT_INDEXED",
  full_account_export_confirmed:false,posts:rows
 };
 const serialized=JSON.stringify(snapshot,null,2)+"\n";
 const digest=crypto.createHash("sha256").update(serialized).digest("hex").slice(0,16);
 const time=fetched.toISOString().replace(/[-:]/g,"").slice(0,15)+"Z";
 const filename="windsor-"+time+"-"+digest+"-retrieved.json";
 return {
  status:"STAGED_NEW_ROOTS",report:status,snapshot,filename,serialized,
  sha256:crypto.createHash("sha256").update(serialized).digest("hex"),
  save_allowed:true,github_written:false,index_modified:false,
  repository_scope:"threads/radar/inbox/",
  target_branch:"radar-stage-b-index-20261020"
 };
}
module.exports={planDelivery,fetchTimestamp};
