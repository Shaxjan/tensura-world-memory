"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {compare,fold,detectEvents,krasnoyarskToday}=require("./semantic.js");
const opts={as_of:"2026-10-23",last_synced_at:"2026-10-23",max_age_days:1};
const unrelated=[{post_id:"99999999999999999",original_text:"Здесь обсуждают историю книгопечатания и работу библиотек."}];
const invented={title:"Новая история об арфе",text:"Волшебник играет на арфе перед друзьями.",event:"Зачарованная арфа начинает петь",conflict:"Артист боится потерять вдохновение",characters:["Музыкант"]};
test("invalid as_of dates fail closed to REVIEW_REQUIRED",()=>{
 for(const as_of of ["2026-02-30","2026-13-01","2026-10-32","2026-10-2"]){
  const r=compare(invented,unrelated,[],{...opts,as_of});
  assert.equal(r.archive_fresh,false,as_of);
  assert.equal(r.verdict,"REVIEW_REQUIRED",as_of);
 }
});
test("invalid source date fails closed",()=>{
 const r=compare(invented,unrelated,[],{...opts,last_synced_at:"2026-02-30"});
 assert.equal(r.archive_fresh,false);
 assert.equal(r.verdict,"REVIEW_REQUIRED");
});
test("a fresh distinct scene remains explicitly provisional",()=>{
 const r=compare(invented,unrelated,[],opts);
 assert.equal(r.verdict,"NEW_STORY");
 assert.equal(r.provisional,true);
 assert.equal(r.confidence,"low");
});
test("known Molly Fabian watch episode detects old narrative",()=>{
 const post={post_id:"18070777397534641",original_text:"Молли Уизли подарила часы своего брата Фабиана Гарри на семнадцатилетие. Подарок стал частью семьи."};
 const idea={title:"Часы Фабиана для Гарри",event:"Молли дала Гарри часы Фабиана",conflict:"Гарри принят в семью Уизли",viewpoint:"Молли",characters:["Гарри","Молли"]};
 const r=compare(idea,[post],[],opts);
 assert.equal(r.verdict,"SAME_STORY");
 assert.ok(r.matches.some(x=>x.id===post.post_id));
});
test("literal duplicate gets high-confidence DUPLICATE",()=>{
 const text="Однажды библиотекарь обнаружил в старом шкафу неизвестную рукопись, оставленную забытым волшебником много лет назад.";
 const r=compare({...invented,text},[{post_id:"9911111111111111",original_text:text}],[],opts);
 assert.equal(r.verdict,"DUPLICATE");
 assert.equal(r.confidence,"high");
});
test("stale index blocks freshness verdicts",()=>{
 const r=compare(invented,unrelated,[],{...opts,as_of:"2026-10-24"});
 assert.equal(r.archive_fresh,false);
 assert.equal(r.verdict,"REVIEW_REQUIRED");
});
test("empty archive cannot certify novelty",()=>{
 const r=compare(invented,[],[],opts);
 assert.equal(r.verdict,"REVIEW_REQUIRED");
});
test("Krasnoyarsk date format is UTC-independent",()=>{
 assert.match(krasnoyarskToday(),/^20\d\d-\d\d-\d\d$/);
 assert.equal(fold("Снейп и Волдеморт"),"снегг и волан де морт");
 assert.ok(detectEvents("Молли Уизли подарила часы Фабиана Гарри").includes("molly_fabian_watch"));
});
