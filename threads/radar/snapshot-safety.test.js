"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {utcDate,validateInput,diff,envelope,plan} = require("./snapshot_intake.js");
const p={post_id:"18109268174261128",post_timestamp:"2026-10-23T14:00:10+0000",post_text:"Текст",post_permalink:"https://www.threads.com/@mirpottera/post/De1uOOfikHf",post_media_type:"TEXT_POST",post_views:460};
const c=()=>JSON.parse(JSON.stringify(p));
const normalized=()=>validateInput({count:1,account:"mirpottera",posts:[c()]});
const old=()=>({post_id:p.post_id,original_text:p.post_text,url:p.post_permalink,published_at:p.post_timestamp,media_type:p.post_media_type,metrics:{views:p.post_views}});
test("valid UTC posts accept both +0000 and Z",()=>{
 assert.equal(utcDate("2026-10-23T14:00:10+0000"),"2026-10-23");
 assert.equal(utcDate("2028-02-29T23:59:59Z"),"2028-02-29");
});
test("calendar rollover and impossible timestamps are rejected",()=>{
 for(const ts of ["2026-02-30T13:00:00Z","2026-04-31T12:00:00Z","2026-10-23T25:00:00Z","2026-10-23T14:61:00Z"])
  assert.throws(()=>utcDate(ts));
});
test("invalid retrieval calendar dates are rejected",()=>{
 for(const bad of ["2026-02-30","2026-13-20","2026-11-31","2026-10-2"])
  assert.throws(()=>envelope(normalized(),{retrieval_date_utc:bad}));
});
test("retrieval date earlier than any post is rejected",()=>{
 assert.throws(()=>envelope(normalized(),{retrieval_date_utc:"2026-10-22"}),/predates/);
});
test("immutable timestamp changes are flagged before importing",()=>{
 const r=normalized();r[0].post_timestamp="2026-10-23T14:05:10+0000";
 assert.deepEqual(diff(r,[old()]).changed_existing_ids,[p.post_id]);
});
test("immutable media-type changes are flagged before importing",()=>{
 const r=normalized();r[0].post_media_type="VIDEO";
 assert.deepEqual(diff(r,[old()]).changed_existing_ids,[p.post_id]);
});
test("only view-count refresh is permitted",()=>{
 const r=normalized();r[0].post_views=1000;
 const check=diff(r,[old()]);
 assert.deepEqual(check.changed_existing_ids,[]);
 assert.deepEqual(check.identical_ids,[p.post_id]);
});
test("stable local preview produces deterministic name and no manual conflict",()=>{
 const inp={count:1,account:"mirpottera",retrieval_date_utc:"2026-10-23",posts:[c()]};
 const a=plan(inp,[old()]),b=plan(inp,[old()]);
 assert.equal(a.filename,b.filename);
 assert.equal(a.changes.needs_manual_review,false);
 assert.equal(a.snapshot.posts[0].post_text,p.post_text);
 assert.match(a.filename,/^windsor-import-2026-10-23-[a-f0-9]{12}\.json$/);
});
test("account mismatch and changed post text fail closed",()=>{
 assert.throws(()=>validateInput({account:"wrong",posts:[c()]}),/Wrong account/);
 const x=normalized();x[0].post_text="Подмена";
 assert.equal(diff(x,[old()]).needs_manual_review,true);
});
