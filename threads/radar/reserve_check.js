#!/usr/bin/env node
"use strict";
/**
 * Stage G reserve audit for Mir Pottera.
 * Offline, read-only. Node.js built-ins only.
 * Checks 30 editorial candidate stories against all currently indexed posts,
 * the independent scheduled/approved journal and each other.
 * Uses retrieval heuristics to surface related work; never certifies originality.
 */
const fs=require("node:fs");
const path=require("node:path");
const {compare,fold,words,krasnoyarskToday}=require("./semantic.js");
const ROOT=__dirname;
const REQUIRED=["id","slot","universe","format","title","premise","event","characters","key_detail","viewpoint","conflict","dramatic_turn","reader_value","canon_or_source_basis","canon_review","editorial_status"];
const ANCHORS={
 G01:[],
 G02:[{id:"18118536869070394",note:"Другая история о похищении Полумны; не путать с поддержкой Олливандера в плену."},{id:"18108890942350335",since:"2026-10-22",note:"Новый октябрьский пост о принятии Полумны в друзьях, не про Олливандера."}],
 G03:[],
 G04:[{id:"18434719531134355",note:"Кэти уже фигурировала в споре о цене решения Дамблдора защищать Драко. Новый взгляд - пострадавшая, переживающая случайное ранение."}],
 G05:[{id:"18119550259962793",note:"В восстановленном авторском продолжении октября уже описана история медальона в доме Блэков; новая идея только о продаже Меропой."},{id:"18103660046524436",note:"О медальоне уже был пост, но о его владельце Амбридж. Новый ракурс посвящён нужде Меропы при продаже."},{id:"2026-10-13-1500-locket-fletcher-umbridge",note:"В журнале медальон уже запланирован как цепочка переходов. История Меропы не должна повторить эту структуру."}],
 G06:[],
 G07:[{id:"17969400099169195",note:"Ранее объясняли природу боггартов в целом, новый рассказ о личном страхе учителя."}],
 G08:[],G09:[],G10:[],
 G11:[],
 G12:[{id:"17932249074366851",note:"С Ником уже было рассуждение о призраках после гибели Сириуса; здесь другой эпизод и жанр."}],
 G13:[{id:"18385798864204017",note:"С мандрагорами уже был пост о пересадке, здесь взросление и лекарство."}],G14:[],G15:[],G16:[{id:"18109268174261128",since:"2026-10-23",note:"Новый пост о тайной связи зачарованными монетами; иная технология и драматургия подпольного радио."}],
 G17:[{id:"17902019613561331",note:"В архиве есть комментирование квиддича Полумной. Здесь Ли Джордан, преподавательский контроль и спорт."}],
 G18:[],G19:[],G20:[],
 G21:[{id:"18099053732569238",note:"Гибель Скримджера уже кратко названа в посте о падении Министерства; здесь новый акцент на слухе, переданном Люпином."}],
 G22:[],
 G23:[],G24:[],
 G25:[{id:"18088445684561400",note:"В архиве есть викторина о подводном дыхании, но не моральный выбор, связанный с сестрой Флёр."}],
 G26:[],G27:[],G28:[],G29:[],G30:[]
};
const EXCLUDED=[
 {topic:"Кикимер готовит пирог, которого герои не дождались",post_id:"18124917808689599",reason:"То же событие, тот же конфликт и финал. Первоначальный кандидат исключён."},
 {topic:"Упырь изображает заболевшего Рона",post_id:"18407809276080562",reason:"Сюжет и комическая функция уже повторяют опубликованный пост. Первоначальный кандидат исключён."},
 {topic:"Письмо Петунии директору с просьбой взять её в Хогвартс",post_id:"17889884388671268",reason:"То же событие, психологическая причина и смысл уже подробно раскрыты в опубликованном тексте. Первоначальный G04 исключён."},
 {topic:"Невилл и обёртка от матери",post_id:"17948465820318555",reason:"Уже опубликованная эмоциональная сцена."},
 {topic:"Отец Дина Томаса",post_id:"18092802638545644",reason:"Уже опубликованное раскрытие судьбы отца."},
 {topic:"Жук Рита Скитер и расследование Гермионы",post_id:"17900136351510191",reason:"Уже опубликованная детективная цепочка."},
 {topic:"Шутка Фреда с плюшевым медведем Рона",post_id:"18112139308787863",reason:"Уже опубликованное объяснение арахнофии."},
 {topic:"Прежняя G21: Автор заклинания лечит его жертву",post_id:"18057792662603776",reason:"Ранее пропущена конкретная сцена, где Гарри ранит Драко Сектумсемпрой; сюжет отложен как потенциальный повтор."}
];
function readJSON(p){return JSON.parse(fs.readFileSync(p,"utf8"));}
function readJSONL(p){return fs.readFileSync(p,"utf8").trim().split(/\r?\n/).map(JSON.parse);}
function stem(s){return words(s).map(w=>w.length>6?w.slice(0,-2):w.length>4?w.slice(0,-1):w);}
function termCoverage(needle,hay){
 const qs=[...new Set(stem(needle))];
 if(!qs.length)return 0;
 const base=new Set(stem(hay));
 return qs.filter(w=>base.has(w)).length/qs.length;
}
function bestOverlap(idea,posts,journal){
 const query=[idea.event,idea.key_detail,idea.viewpoint,idea.characters.slice(1).join(" ")].join(" ");
 const all=[
   ...posts.map(p=>({kind:"published",id:p.post_id,url:p.url,status:"published",text:[p.original_text,p.search_text].filter(Boolean).join("\n")})),
   ...journal.filter(j=>!["cancelled","canceled"].includes(j.state)).map(j=>({kind:"editorial",id:j.journal_id,url:j.url||null,status:j.state,text:[j.topic,j.angle,j.text].join(" ")}))
 ];
 return all.map(p=>{
  const event=termCoverage(idea.event,p.text);
  const object=termCoverage(idea.key_detail,p.text);
  const character=termCoverage(idea.viewpoint,p.text);
  const score=0.65*event+0.22*object+0.13*character;
  return {...p,score:Math.round(score*1000)/1000,event_overlap:event};
 }).filter(p=>p.score>=0.14).sort((a,b)=>b.score-a.score).slice(0,5);
}
function validateReserve(doc,posts,journal){
 if(doc.count!==30||doc.ideas.length!==30)throw Error("Reserve must contain 30 cards");
 if(doc.source_index_posts!==posts.length)throw Error("Source index size differs from recorded reserve snapshot; refresh and recheck");
 if(doc.revision>=4){
  if(!Array.isArray(doc.source_index_post_ids)||!Array.isArray(doc.source_editorial_journal_ids))
   throw Error("Current reserve has no complete source-ID checkpoint");
  const exact=(expected,observed)=>expected.length===observed.length
   && expected.every((id,i)=>id===observed[i]);
  const published=posts.map(x=>String(x.post_id)).sort();
  const editorial=journal.map(x=>String(x.journal_id)).sort();
  if(!exact(doc.source_index_post_ids,published)||!exact(doc.source_editorial_journal_ids,editorial))
   throw Error("Source IDs changed without re-screening; reserve stale");
 }

 const ids=new Set(), titles=new Set(), dist={};
 for(const c of doc.ideas){
  for(const field of REQUIRED){const val=c[field];if(!val || (Array.isArray(val)&&!val.length))throw Error(c.id+": missing "+field);}
  if(ids.has(c.id)||titles.has(fold(c.title)))throw Error("Duplicate idea id or title "+c.id);
  ids.add(c.id);titles.add(fold(c.title));
  if(!["03:00","11:00","15:00"].includes(c.slot))throw Error("No video/extra slot ideas: "+c.id);
  if(!["Гарри Поттер","Book Threads"].includes(c.universe))throw Error("Unexpected universe");
  if(c.editorial_status!=="IDEA_NOT_APPROVED"||!c.canon_review)throw Error("Unsafe status");
  dist[c.slot]=(dist[c.slot]||0)+1;
 }
 if(Object.values(dist).some(n=>n!==10)||Object.keys(dist).length!==3)throw Error("Wrong distribution");
 const publishedIDs=new Set(posts.map(x=>x.post_id)),journalIDs=new Set(journal.map(x=>x.journal_id));
 if(publishedIDs.size!==posts.length)throw Error("Duplicate indexed posts");
 if(journalIDs.size!==journal.length)throw Error("Duplicate editorial journal records");
 return dist;
}
function evaluate(data, posts, journal, opts={}){
 const dist=validateReserve(data,posts,journal);
 const asOf=opts.as_of||krasnoyarskToday();
 const out=[];
 for(const c of data.ideas){
  const idea={title:c.title,text:c.premise,event:c.event,characters:c.characters,viewpoint:c.viewpoint,conflict:c.conflict,conclusion:c.dramatic_turn};
  const result=compare(idea,posts,journal,{as_of:asOf,last_synced_at:data.source_index_date,max_age_days:1});
  const rel=bestOverlap(c,posts,journal);
  const anchors=(ANCHORS[c.id]||[]).filter(a=>!a.since||a.since<=data.source_index_date).map(a=>{
   const row=posts.find(p=>p.post_id===a.id)||journal.find(j=>j.journal_id===a.id);
   if(!row)throw Error("Anchor missing from index "+a.id);
   return {id:a.id,kind:row.post_id?"published":"editorial",url:row.url||null,status:row.post_id?"published":row.state,note:a.note};
  });
  const linked=new Set(anchors.map(x=>x.id));
  const neighbors=[...anchors,...rel.filter(p=>!linked.has(p.id)).slice(0,3).map(p=>({id:p.id,kind:p.kind,url:p.url,status:p.status,score:p.score,event_overlap:Math.round(p.event_overlap*100)/100,note:"Алгоритмический кандидат; требует редакторского сравнения сюжета"}))];
  const postCollision=result.verdict==="DUPLICATE"||result.verdict==="SAME_STORY";
  const concerns=result.verdict==="REVIEW_REQUIRED"||postCollision||anchors.length>0||rel.some(p=>p.score>=0.60);
  const review=postCollision?"BLOCKED_REWORK":concerns?"REVIEW_REQUIRED":"PRECHECKED_LOW_SIMILARITY";
  const notes=[
   "Сопоставлено с полным индексом опубликованных корневых постов и редакционным журналом; не гарантия отсутствия повторов.",
   c.canon_or_source_basis,
   ...anchors.map(a=>a.note)
  ];
  if(!result.archive_fresh)notes.push("Индекс устарел: новую идею нельзя подтверждать до синхронизации.");
  out.push({id:c.id,title:c.title,slot:c.slot,universe:c.universe,screen_status:!result.archive_fresh?"STALE_RECHECK":review,algorithm_verdict:result.verdict,algorithm_confidence:result.confidence,similar_refs:neighbors,editorial_notes:notes,canon_review:c.canon_review,requires_human_approval:true});
 }
 return {schema_version:1,account:"mirpottera",checked_at:asOf,snapshot_date:data.source_index_date,compared_author_posts:posts.length,compared_editorial_cards:journal.length,ideas_count:out.length,distrib:dist,summary:out.reduce((o,c)=>(o[c.screen_status]=(o[c.screen_status]||0)+1,o),{}),exclusions:EXCLUDED,ideas:out};
}
if(require.main===module){
 const doc=readJSON(path.join(ROOT,"reserve","ideas-2026-10-23-r4.json"));
 const posts=readJSONL(path.join(ROOT,"index","posts.jsonl"));
 const journal=readJSONL(path.join(ROOT,"index","editorial.jsonl"));
 const report=evaluate(doc,posts,journal,{as_of:process.argv[2]||krasnoyarskToday()});
 console.log(JSON.stringify(report,null,2));
}
module.exports={evaluate,validateReserve,bestOverlap,EXCLUDED,ANCHORS};
