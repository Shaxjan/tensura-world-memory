#!/usr/bin/env node
"use strict";
/**
 * Read-only-by-default import of an author-supplied Windsor.ai Threads JSON
 * snapshot. No account tokens, browsers, API calls, GitHub pushes or publishing.
 * Use --write-local only in a non-main Git branch. Run radar.py build separately.
 */
const fs=require("node:fs");
const path=require("node:path");
const crypto=require("node:crypto");
const cp=require("node:child_process");
const ROOT=__dirname;
const ALLOWED=new Set(["TEXT_POST","IMAGE","VIDEO","CAROUSEL_ALBUM","REPOST_FACADE"]);
const FIELDS=["post_id","post_timestamp","post_text","post_permalink","post_media_type","post_views"];
function lines(p){return fs.readFileSync(p,"utf8").trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);}
function utcDate(ts){
 if(typeof ts!=="string"||!/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\+0000|Z)$/.test(ts))throw Error("Bad UTC post_timestamp");
 const iso=ts.replace(/\+0000$/,"Z");
 const date=new Date(iso);
 // Date silently normalizes impossible calendar dates such as February 30.
 if(Number.isNaN(date.getTime())||date.toISOString().slice(0,19)!==iso.slice(0,19))
  throw Error("Invalid UTC post_timestamp");
 return date.toISOString().slice(0,10);
}
function validateInput(obj,account="mirpottera"){
 const rows=Array.isArray(obj?.posts)?obj.posts:Array.isArray(obj?.data)?obj.data:null;
 if(!rows||!rows.length)throw Error("Export must have nonempty posts or data array");
 if(rows.length>10000)throw Error("Input too large, split by date");
 if(obj.account && obj.account!==account)throw Error("Wrong account");
 if(obj.status&&obj.status!=="done")throw Error("Windsor export is not complete");
 if(obj.count!=null&&obj.count!==rows.length)throw Error("Count mismatch");
 if(obj.total_rows!=null&&obj.total_rows!==rows.length)throw Error("Expected all rows, not a partial page");
 const ids=new Set(),urls=new Set(), normalized=[];
 for(const raw of rows){
  const id=String(raw.post_id??"");
  if(!/^\d{12,22}$/.test(id)||ids.has(id))throw Error("Invalid or duplicate post_id");
  ids.add(id);
  const media=String(raw.post_media_type??"");
  if(!ALLOWED.has(media))throw Error("Unexpected post_media_type: "+media);
  if(utcDate(raw.post_timestamp)==="")throw Error("Missing time");
  const link=String(raw.post_permalink??"");
  if(!/^https:\/\/(?:www\.)?threads\.com\/@mirpottera\/post\/[A-Za-z0-9_-]+\/?$/.test(link))throw Error("Bad permalink");
  if(urls.has(link))throw Error("Duplicate permalink");
  urls.add(link);
  const body=raw.post_text==null?"":String(raw.post_text);
  if(media!=="REPOST_FACADE"&&!body.trim())throw Error("Root post has no text; manual review required: "+id);
  if(body.length>150000)throw Error("Unexpectedly large post text");
  const views=raw.post_views==null?null:Number(raw.post_views);
  if(views!==null&&(!Number.isFinite(views)||views<0))throw Error("Invalid views");
  normalized.push({post_id:id,post_timestamp:raw.post_timestamp,post_text:body||null,post_permalink:link,post_media_type:media,post_views:views});
 }
 normalized.sort((a,b)=>a.post_timestamp.localeCompare(b.post_timestamp)||a.post_id.localeCompare(b.post_id));
 return normalized;
}
function diff(added, indexed){
 const ids=new Map(indexed.map(p=>[String(p.post_id),p]));
 const unique=[],identical=[],changed=[],reposts=[];
 for(const p of added){
  if(p.post_media_type==="REPOST_FACADE"){reposts.push(p.post_id);continue;}
  const old=ids.get(p.post_id);
  if(!old){unique.push(p.post_id);continue;}
  if((old.original_text||"")!==(p.post_text||"")||(old.url||"")!==p.post_permalink||
    (old.published_at||"")!==p.post_timestamp||(old.media_type||"")!==p.post_media_type){changed.push(p.post_id);}
  else identical.push(p.post_id);
 }
 return {new_author_ids:unique,identical_ids:identical,changed_existing_ids:changed,repost_ids:reposts,needs_manual_review:changed.length>0};
}
function envelope(rows,meta={}) {
 const dates=rows.map(p=>utcDate(p.post_timestamp)).sort();
 const latest=meta.retrieval_date_utc||new Date().toISOString().slice(0,10);
 if(!/^\d{4}-\d\d-\d\d$/.test(latest)||new Date(latest+"T00:00:00Z").toISOString().slice(0,10)!==latest)throw Error("Bad retrieval date");
 if(dates[dates.length-1]>latest)throw Error("Snapshot retrieval predates a post");
 return {schema_version:1,account:"mirpottera",source:"Windsor.ai Threads",retrieval_date_utc:latest,period_utc:[dates[0],dates[dates.length-1]],read_fields:FIELDS,count:rows.length,posts:rows};
}
function plan(incoming,indexed,opts={}){
 const rows=validateInput(incoming);
 const changes=diff(rows,indexed);
 const snapshot=envelope(rows,{retrieval_date_utc:opts.retrieval_date_utc||incoming.retrieval_date_utc});
 const stable=JSON.stringify(snapshot,null,2)+"\n";
 const hash=crypto.createHash("sha256").update(stable,"utf8").digest("hex").slice(0,12);
 const basename="windsor-import-"+snapshot.retrieval_date_utc+"-"+hash+".json";
 return {rows:rows.length,roots:rows.filter(p=>p.post_media_type!=="REPOST_FACADE").length,changes,snapshot,serialized:stable,filename:basename};
}
function writeLocal(p,directory=path.join(ROOT,"snapshots")){
 const branch=cp.execFileSync("git",["branch","--show-current"],{cwd:ROOT,encoding:"utf8",timeout:4000}).trim();
 if(!/^radar-[A-Za-z0-9._-]+$/.test(branch))throw Error("Writing allowed only on a dedicated radar-* branch");
 if(p.changes.needs_manual_review)throw Error("Existing published ID changed; reconcile manually first");
 const target=path.join(directory,p.filename);
 fs.mkdirSync(directory,{recursive:true});
 // wx is atomic: never overwrite any previously saved snapshot.
 try{fs.writeFileSync(target,p.serialized,{encoding:"utf8",flag:"wx"});}
 catch(e){if(e.code!=="EEXIST"||fs.readFileSync(target,"utf8")!==p.serialized)throw e;}
 return target;
}
function main(args=process.argv.slice(2)){
 if(!args.length||args.includes("--help")){
  console.log("Usage: node threads/radar/snapshot_intake.js path/to/windsor-export.json [--write-local] [--date YYYY-MM-DD]");
  console.log("Default: read-only preview. --write-local only saves an immutable file on a radar-* branch; no posting, index updates or push.");
  return;
 }
 const source=args[0];
 if(source.startsWith("-"))throw Error("First argument must be JSON export path");
 if(fs.statSync(source).size>15000000)throw Error("Export exceeds 15 MB");
 const dateIndex=args.indexOf("--date");
 if(dateIndex>=0&&!args[dateIndex+1])throw Error("Missing date");
 const date=dateIndex>=0?args[dateIndex+1]:null;
 const exported=JSON.parse(fs.readFileSync(source,"utf8"));
 const indexed=lines(path.join(ROOT,"index","posts.jsonl"));
 const p=plan(exported,indexed,{retrieval_date_utc:date});
 const preview={snapshot:p.filename,total_source_rows:p.rows,author_root_rows:p.roots,...p.changes};
 if(args.includes("--write-local"))preview.saved_path=writeLocal(p);
 console.log(JSON.stringify(preview,null,2));
 if(p.changes.needs_manual_review)process.exitCode=2;
}
if(require.main===module){try{main();}catch(e){console.error("Radar intake:",e.message);process.exitCode=1;}}
module.exports={validateInput,utcDate,diff,envelope,plan,writeLocal,main};
