#!/usr/bin/env node
"use strict";
/**
 * Stage 6: read-only, replay-safe check of an external Windsor Threads pull
 * against the published index AND already saved, unpromoted inbox snapshots.
 * No provider calls, tokens, writes, posts, or scheduled execution.
 */
const fs=require("node:fs");
const path=require("node:path");
const {validateInput}=require("./snapshot_intake.js");
const IMMUTABLE=["post_timestamp","post_text","post_permalink","post_media_type"];

function canonicalIndex(p){
 return {
  post_id:String(p.post_id),
  post_timestamp:p.published_at,post_text:p.original_text,
  post_permalink:p.url,post_media_type:p.media_type
 };
}
function scrutinize(live,index,inboxes=[]){
 if(!live||live.status!=="done"||!Array.isArray(live.data))
  throw Error("Windsor pull is incomplete: status is not done");
 if(!Number.isSafeInteger(live.total_rows)||live.total_rows!==live.data.length)
  throw Error("Windsor row count is absent or inconsistent");
 if(!Array.isArray(index)||index.length===0)throw Error("Published index is missing");
 if(!Array.isArray(inboxes))throw Error("Inbox snapshots must be an array");
 const seen=new Map(), conflict=new Map();
 const register=(row,source)=>{
  const id=String(row.post_id);
  const previous=seen.get(id);
  if(!previous){seen.set(id,{row,source});return;}
  const differences=IMMUTABLE.filter(k=>String(previous.row[k]??"")!==String(row[k]??""));
  if(differences.length){
   const key=id+":"+differences.join(",");
   conflict.set(key,{post_id:id,fields:differences,sources:[previous.source,source]});
  }
 };
 for(const p of index)register(canonicalIndex(p),"index");
 for(const box of inboxes){
  if(!box||box.account!=="mirpottera"||box.state!=="INBOX_NOT_INDEXED"||
      box.source!=="Windsor.ai Threads")throw Error("Invalid prior inbox snapshot");
  for(const row of validateInput(box))register(row,"saved_inbox");
 }
 const entries=live.data.length?validateInput({account:"mirpottera",count:live.total_rows,posts:live.data}):[];
 const existing=new Set(seen.keys());
 const newRoots=[],newReposts=[],known=[],refreshes=[];
 for(const row of entries){
  register(row,"new_pull");
  if(row.post_media_type==="REPOST_FACADE"){
   if(!existing.has(row.post_id))newReposts.push(row.post_id);
   continue;
  }
  if(existing.has(row.post_id)){known.push(row.post_id);continue;}
  newRoots.push({post_id:row.post_id,post_timestamp_utc:row.post_timestamp,
    permalink:row.post_permalink,media_type:row.post_media_type});
 }
 const collisions=[...conflict.values()];
 return {
  status:collisions.length?"BLOCKED_CONFLICTS":newRoots.length?"NEW_AUTHOR_ROOTS":"NO_NEW_AUTHOR_ROOTS",
  account:"mirpottera",source_status:"done",source_rows:entries.length,
  index_roots:index.length,already_saved_inboxes:inboxes.length,
  new_author_roots:collisions.length?[]:newRoots,
  new_repost_facades:newReposts,known_author_roots:known,
  conflicts:collisions,manual_review_required:true,
  source_completeness_unverified:true,github_modified:false,index_modified:false,
  action:"READ_ONLY_NOTIFICATION_ONLY"
 };
}
function lines(filename){
 const content=fs.readFileSync(filename,"utf8").trim();
 return content?content.split(/\r?\n/).map(JSON.parse):[];
}
function main(args=process.argv.slice(2)){
 if(args.length!==1)throw Error("Usage: node threads/radar/watch_check.js path/to/windsor-get_data-response.json");
 const file=path.resolve(args[0]);
 if(fs.statSync(file).size>15000000)throw Error("Windsor response exceeds 15 MB");
 const snapshot=JSON.parse(fs.readFileSync(file,"utf8"));
 const root=__dirname;
 const index=lines(path.join(root,"index","posts.jsonl"));
 const inboxes=fs.readdirSync(path.join(root,"inbox"))
  .filter(name=>/^windsor-.*-retrieved\.json$/.test(name))
  .map(name=>JSON.parse(fs.readFileSync(path.join(root,"inbox",name),"utf8")));
 const report=scrutinize(snapshot,index,inboxes);
 console.log(JSON.stringify(report,null,2));
 if(report.conflicts.length)process.exitCode=2;
}
if(require.main===module){try{main()}catch(e){console.error("Radar watch:",e.message);process.exitCode=1;}}
module.exports={scrutinize,canonicalIndex,IMMUTABLE,main};
