"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const radar = require("./semantic.js");

const INDEX = path.join(__dirname, "index");
function readJSONL(name) { return fs.readFileSync(path.join(INDEX, name), "utf8").trim().split(/\r?\n/).map(line=>JSON.parse(line)); }
const posts = readJSONL("posts.jsonl");
const journal = readJSONL("editorial.jsonl");
const CURRENT={as_of:"2026-10-21",last_synced_at:"2026-10-21",max_age_days:1};
function verdict(c, options=CURRENT, j=journal, p=posts){return radar.compare(c,p,j,options);}

test("index covers 447 unique published author roots",()=>{
 assert.equal(posts.length,447);
 assert.equal(new Set(posts.map(p=>p.post_id)).size,447);
 assert.equal(posts.filter(p=>p.state!=="published").length,0);
 assert.equal(posts.filter(p=>p.media_type==="REPOST_FACADE").length,0);
});
test("Molly's seventeenth-birthday gift is SAME_STORY, not new",()=>{
 const r=verdict({text:"Молли Уизли подарила Гарри часы Фабиана на семнадцатилетие. Это означало, что Гарри стал своим в семье."});
 assert.equal(r.verdict,"SAME_STORY");
 assert.ok(r.matches.some(p=>p.id==="18070777397534641"));
});
test("Hagrid's parents-photo album is SAME_STORY even if hidden in original continuation",()=>{
 const r=verdict({text:"Хагрид собрал для Гарри альбом с фотографиями Лили и Джеймса, чтобы вернуть память о родителях."});
 assert.equal(r.verdict,"SAME_STORY");
 assert.ok(r.matches.some(p=>p.id==="18101742425202406"));
});
test("verbatim copy is DUPLICATE",()=>{
 const original=posts.find(p=>p.post_id==="18070777397534641");
 const r=verdict({text:original.search_text});
 assert.equal(r.verdict,"DUPLICATE");
});
test("different narrator AND conflict produces provisional NEW_ANGLE",()=>{
 const r=verdict({text:"Рон видел, как Молли подарила Гарри часы Фабиана, и почувствовал зависть.",
  viewpoint:"Рон",conflict:"Страх быть неважным в собственной семье",
  event:"Молли дарит Гарри часы Фабиана",characters:["Рон","Молли","Гарри"]});
 assert.equal(r.verdict,"NEW_ANGLE");
 assert.equal(r.provisional,true);
 assert.ok(r.matches.some(p=>p.id==="18070777397534641"));
});
test("new event with familiar character not automatically classified as repetition",()=>{
 const r=verdict({text:"Молли поймала садовых гномов с украденным пирогом и решила вернуть его.",
  event:"гномы воруют пирог в Норе",conflict:"Молли ищет украденный пирог",characters:["Молли","садовые гномы"]});
 assert.equal(r.verdict,"NEW_STORY");
 assert.equal(r.confidence,"low");
 assert.equal(r.provisional,true);
});
test("known different event with same Molly and watches not confused with Fabian gift",()=>{
 const r=verdict({text:"Молли смотрит на часы Уизли: все стрелки показывают смертельную опасность.",
  event:"семейные часы во время войны",conflict:"Молли боится потерять детей",characters:["Молли"]});
 assert.equal(r.verdict,"SAME_STORY");
 assert.ok(r.matches.some(p=>p.id==="17910723501265122"));
});
test("nearby scheduled storyline is not silently ignored",()=>{
 const r=verdict({text:"Златопуст Локонс устраивает День святого Валентина с двенадцатью гномами-купидонами",
  event:"Локонс приглашает гномов-купидонов",characters:["Златопуст Локонс"],conflict:"Праздник срывает уроки"});
 assert.equal(r.verdict,"REVIEW_REQUIRED");
 assert.ok(r.reason.includes("запланированная"));
 assert.ok(r.matches.some(p=>p.status==="scheduled"));
});
test("low-score scheduled reference does not block different Molly watch angle",()=>{
 const r=verdict({text:"Рон наблюдал, как Молли отдавала Гарри часы Фабиана.",
  viewpoint:"Рон",event:"часы Фабиана",conflict:"Рон ревнует мать к Гарри",characters:["Рон","Молли"]});
 assert.equal(r.verdict,"NEW_ANGLE");
 assert.equal(r.reason.includes("схожая запланированная"),false);
});
test("canceled draft ignored; schedule retains separate state",()=>{
 const customJournal=[
  {journal_id:"cancel",state:"cancelled",topic:"Колин Криви фотографирует на уроке"},
  {journal_id:"schedule",state:"scheduled",topic:"Драко и змея в школьной библиотеке"}
 ];
 const canceled=verdict({text:"Колин Криви фотографирует на уроке",event:"Колин фотографирует класс",conflict:"спор о снимке",characters:["Колин"]},CURRENT,customJournal,[]);
 assert.equal(canceled.verdict,"REVIEW_REQUIRED"); // no posts: cannot declare new
 assert.equal(canceled.matches.length,0);
 const scheduled=radar.matchArchive({text:"Драко и змея в школьной библиотеке"},[],customJournal);
 assert.ok(scheduled.some(x=>x.id==="schedule"&&x.status==="scheduled"));
});
test("stale snapshot never proves NEW_STORY",()=>{
 const r=verdict({text:"Молли требует у садовых гномов вернуть яблочный пирог",
  event:"кража пирога",conflict:"попытка вернуть пирог",characters:["Молли","гномы"]},
  {as_of:"2026-10-22",last_synced_at:"2026-10-21",max_age_days:1});
 assert.equal(r.verdict,"REVIEW_REQUIRED");
 assert.equal(r.archive_fresh,false);
});
test("drafted metadata without evidence is REVIEW_REQUIRED",()=>{
 const r=verdict({text:"Я часто думаю о Гарри"});
 assert.equal(r.verdict,"REVIEW_REQUIRED");
});
test("duplicate source post_id is not surfaced twice",()=>{
 const post=posts.find(p=>p.post_id==="18070777397534641");
 const result=radar.matchArchive({text:"Молли и часы Фабиана Гарри"},[post,post],[]);
 assert.equal(result.filter(x=>x.id===post.post_id).length,1);
});
test("empty archive cannot certify novelty",()=>{
 const r=verdict({text:"Молли крадёт пирог",event:"кража пирога",conflict:"гномы воруют пирог",characters:["Молли"]},CURRENT,[],[]);
 assert.equal(r.verdict,"REVIEW_REQUIRED");
});
