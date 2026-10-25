#!/usr/bin/env node
"use strict";
/**
 * Stage 6 cumulative inbox inventory. Read-only. It is NOT a promotion,
 * a complete Threads export, or permission to auto-approve editorial ideas.
 */
const fs=require("node:fs");
const path=require("node:path");
const {validateInput,utcDate}=require("./snapshot_intake.js");

const IMMUTABLE=["post_timestamp","post_text","post_permalink","post_media_type"];
function asCanonical(p){
 return {post_id:String(p.post_id),post_timestamp:p.published_at,
  post_text:p.original_text,post_permalink:p.url,post_media_type:p.media_type};
}
function localKrasnoyarsk(ts){
 const date=new Date(ts.replace(/\+0000$/,"Z"));
 if(Number.isNaN(date.getTime()))throw Error("Invalid published timestamp");
 const parts=new Intl.DateTimeFormat("en-GB",{
  timeZone:"Asia/Krasnoyarsk",year:"numeric",month:"2-digit",day:"2-digit",
  hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"
 }).formatToParts(date);
 const f=Object.fromEntries(parts.map(x=>[x.type,x.value]));
 return f.year+"-"+f.month+"-"+f.day+"T"+f.hour+":"+f.minute+":"+f.second+"+0700";
}
function parseSourceTimestamp(box){
 const v=box.data_fetched_at_utc;
 if(typeof v!=="string"||!/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(v))
  throw Error("Inbox missing provider fetch timestamp");
 const dt=new Date(v+"Z");
 if(Number.isNaN(dt.getTime())||dt.toISOString().slice(0,19)!==v)
  throw Error("Invalid inbox fetch timestamp");
 if(box.retrieval_date_utc!==dt.toISOString().slice(0,10))
  throw Error("Inbox retrieval date conflicts with provider timestamp");
 return dt;
}
function inventory(index,boxes){
 if(!Array.isArray(index)||!index.length)throw Error("Missing indexed published archive");
 if(!Array.isArray(boxes)||!boxes.length)throw Error("No saved inbound snapshots");
 const canon=new Map(),indexIDs=new Set(),pending=new Map(),reposts=new Set();
 for(const row of index){
  const id=String(row.post_id);
  if(!/^\d{12,22}$/.test(id)||canon.has(id)||row.state!=="published")
   throw Error("Malformed or duplicate baseline author root");
  indexIDs.add(id);canon.set(id,{row:asCanonical(row),source:"published_index"});
 }
 const snapshots=[];
 const ordered=boxes.map((box,i)=>({
  name:box.name||"snapshot-"+i,
  doc:box.snapshot||box
 })).sort((a,b)=>String(a.name).localeCompare(String(b.name)));
 const prepared=ordered.map(({name,doc})=>{
  if(doc?.account!=="mirpottera"||doc?.source!=="Windsor.ai Threads"||doc?.state!=="INBOX_NOT_INDEXED")
   throw Error("Unsafe inbox account, source or state: "+name);
  if(doc.source_account_id&&doc.source_account_id!=="28902703019346338")
   throw Error("Wrong connected account ID: "+name);
  if(doc.full_account_export_confirmed===true)
   throw Error("Unverified source cannot claim full account export");
  const fetched=parseSourceTimestamp(doc);
  const rows=validateInput(doc);
  const days=rows.map(x=>utcDate(x.post_timestamp)).sort();
  if(!Array.isArray(doc.period_utc)||doc.period_utc.length!==2
    ||doc.period_utc[0]!==days[0]||doc.period_utc[1]!==days[days.length-1])
   throw Error("Inbox period mismatch: "+name);
  if(rows.some(x=>new Date(x.post_timestamp.replace(/\+0000$/,"Z"))>fetched))
   throw Error("Inbox contains publication after fetch: "+name);
  return {name,rows,fetched};
 }).sort((a,b)=>a.fetched-b.fetched||a.name.localeCompare(b.name));
 const conflicts=[];
 const seen=new Map(canon);
 for(const {name,rows,fetched} of prepared){
  snapshots.push({filename:name,source_rows:rows.length,retrieved_at_utc:fetched.toISOString()});
  for(const p of rows){
   const id=p.post_id;
   if(p.post_media_type==="REPOST_FACADE"){reposts.add(id);continue}
   const was=seen.get(id);
   if(was){
    const diff=IMMUTABLE.filter(k=>String(was.row[k]??"")!==String(p[k]??""));
    if(diff.length)conflicts.push({post_id:id,fields:diff,previous_source:was.source,new_source:name});
   }else{
    seen.set(id,{row:p,source:name});
   }
   if(!indexIDs.has(id)){
    const existing=pending.get(id);
    if(!existing||fetched.getTime()>=existing.fetched.getTime())
     pending.set(id,{record:p,fetched,first_source:existing?.first_source||name,last_source:name});
   }
  }
 }
 if(conflicts.length)return {
  status:"BLOCKED_CONFLICTS",account:"mirpottera",baseline_roots:index.length,
  saved_inboxes:snapshots,pending_roots:[],conflicts,
  source_completeness_unverified:true,index_modified:false,
  permitted_action:"REVIEW_SOURCE_CONFLICTS"
 };
 const pendingRoots=[...pending.entries()].map(([id,p])=>({
  post_id:id,post_timestamp_utc:p.record.post_timestamp,
  post_timestamp_krasnoyarsk:localKrasnoyarsk(p.record.post_timestamp),
  permalink:p.record.post_permalink,media_type:p.record.post_media_type,
  latest_views:p.record.post_views,first_source:p.first_source,last_source:p.last_source
 })).sort((a,b)=>a.post_timestamp_utc.localeCompare(b.post_timestamp_utc)||a.post_id.localeCompare(b.post_id));
 return {
  status:"PENDING_NATIVE_ACCEPTANCE",account:"mirpottera",
  baseline_roots:index.length,saved_inboxes:snapshots,
  unique_pending_roots:pendingRoots.length,
  expected_roots_after_verified_promotion:index.length+pendingRoots.length,
  pending_roots:pendingRoots,distinct_repost_facades:reposts.size,
  conflicts:[],source_completeness_unverified:true,
  requires_human_review:true,index_modified:false,source_promoted:false,
  permitted_action:"FULL_NATIVE_BUILD_AND_RESCREEN_BEFORE_PROMOTION"
 };
}
function readLines(p){
 const contents=fs.readFileSync(p,"utf8").trim();
 return contents?contents.split(/\r?\n/).map(JSON.parse):[];
}
function main(){
 const base=__dirname;
 const index=readLines(path.join(base,"index","posts.jsonl"));
 const dir=path.join(base,"inbox");
 const boxes=fs.readdirSync(dir).filter(x=>/^windsor-.*-retrieved\.json$/.test(x)).map(name=>({
  name,snapshot:JSON.parse(fs.readFileSync(path.join(dir,name),"utf8"))
 }));
 const result=inventory(index,boxes);
 console.log(JSON.stringify(result,null,2));
 if(result.conflicts.length)process.exitCode=2;
}
if(require.main===module){try{main()}catch(e){console.error("Radar inbox inventory:",e.message);process.exitCode=1}}
module.exports={inventory,parseSourceTimestamp,localKrasnoyarsk,main};
