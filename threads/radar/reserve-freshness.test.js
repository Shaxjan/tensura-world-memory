"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {evaluate}=require("./reserve_check.js");
const {krasnoyarskToday}=require("./semantic.js");

function oldDay(){
 const today=krasnoyarskToday();
 return new Date(Date.parse(today+"T00:00:00Z")-2*86400000).toISOString().slice(0,10);
}
function fixture(){
 const day=oldDay();
 const posts=[{
  post_id:"12345678901234567",state:"published",source:"windsor_root_snapshot",
  url:"https://www.threads.com/@mirpottera/post/fixture",original_text:"Запись об искусстве книгопечатания.",
  search_text:"Запись об искусстве книгопечатания.",published_at:day+"T10:00:00+0000"
 }];
 const ideas=[];
 for(let n=0;n<30;n++)ideas.push({
  id:"SAFE"+String(n+1).padStart(2,"0"),
  slot:n<10?"03:00":n<20?"11:00":"15:00",
  universe:n%3?"Гарри Поттер":"Book Threads",
  format:"TEXT",title:"Новый сюжет "+n,
  premise:"Неизвестный музыкант играет на арфе перед волшебниками.",
  event:"Новая история об арфе "+n,characters:["Волшебник"],
  key_detail:"арфа",viewpoint:"волшебник",
  conflict:"герой боится потерять вдохновение",
  dramatic_turn:"находит новую мелодию",reader_value:"Творческий конфликт",
  canon_or_source_basis:"Редакторская проверка",canon_review:"PENDING",
  editorial_status:"IDEA_NOT_APPROVED"
 });
 return {
  doc:{revision:4,count:30,source_index_posts:1,source_index_date:day,
   source_index_post_ids:[posts[0].post_id],source_editorial_journal_ids:[],ideas},
  posts,journal:[]
 };
}
test("default reserve evaluation marks older snapshots stale using Krasnoyarsk today",()=>{
 const {doc,posts,journal}=fixture();
 const result=evaluate(doc,posts,journal);
 assert.equal(result.checked_at,krasnoyarskToday());
 assert.equal(result.ideas_count,30);
 assert.equal(result.summary.STALE_RECHECK,30);
 assert.ok(result.ideas.every(x=>x.requires_human_approval));
});
test("explicit historical date remains available only for historical reproduction",()=>{
 const {doc,posts,journal}=fixture();
 const old=evaluate(doc,posts,journal,{as_of:doc.source_index_date});
 assert.equal(old.checked_at,doc.source_index_date);
 assert.equal(old.summary.STALE_RECHECK||0,0);
});
test("future or invalid history checks never certify novelty",()=>{
 const {doc,posts,journal}=fixture();
 for(const as_of of ["2026-02-30","2030-01-01"]){
  const result=evaluate(doc,posts,journal,{as_of});
  assert.equal(result.summary.STALE_RECHECK,30);
 }
});
