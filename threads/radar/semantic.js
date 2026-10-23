"use strict";
/*
 * Threads Radar — Stage C: explainable candidate comparison.
 * No external API, model, dependencies or automatic publication.
 * "NEW_STORY" is preliminary, never a guarantee of originality.
 */
const STATES = Object.freeze(["DUPLICATE","SAME_STORY","NEW_ANGLE","NEW_STORY","REVIEW_REQUIRED"]);
const STOP = new Set("и в во на по с со к ко о об от до из за для не а но или что это как же он она они мы вы ты меня его ее её свою свой свое свои этого этой при еще уже был была были есть где когда если тот там тут все всей всех только это тот та те так".split(" "));
const EVENTS = [
 {id:"molly_fabian_watch", label:"Часы Фабиана как подарок Гарри", anchor:"18070777397534641",
  patterns:[["молли","фабиан","час"],["молли","гарри","час","семнадцатилет"],["молли","фабиан","подар"]],
  viewpoint:"молли", conflict:"гарри принят в семью Уизли", ending:"подарок означает родство"},
 {id:"hagrid_photo_album", label:"Фотоальбом родителей Гарри от Хагрида", anchor:"18101742425202406",
  patterns:[["хагрид","гарри","альбом"],["хагрид","гарри","фотограф","родител"],["хагрид","гарри","книга","родител"]],
  viewpoint:"гарри", conflict:"нет воспоминаний о родителях", ending:"альбом подарил память о семье"},
 {id:"molly_family_clock", label:"Семейные часы Молли во время войны", anchor:"17910723501265122",
  patterns:[["молли","часы","стрелк"],["молли","часы","смертельн","опасност"]],
  viewpoint:"молли", conflict:"тревога за детей на войне", ending:"страх потерять детей"}
];
function fold(v){return String(v == null ? "" : v).toLowerCase().replace(/ё/g,"е").replace(/снейп/g,"снегг").replace(/волдеморт|волан-де-морт|волдемар/g,"волан де морт").replace(/[^\p{L}\p{N}]+/gu," ").trim();}
function words(v){return fold(v).split(/\s+/).filter(x=>x.length>1&&!STOP.has(x));}
function root(t){return t.length>6?t.slice(0,-2):t.length>4?t.slice(0,-1):t;}
function vocabulary(v){return new Set(words(v).map(root));}
const NAMES = new Set("гарри молли рон уизли хагрид сириус джеймс лили гермиона драко фабиан".split(" "));
function conflictSimilarity(a,b){
 const strip=v=>words(v).filter(t=>!NAMES.has(t)).join(" ");
 const x=fold(a), y=fold(b);
 const shared=[/тревог|страх|бои[тс]|опасност|потеря|потерят/,
   /памят|воспомин|родител.*фотограф|альбом/,
   /ревност|завист|лишн|неважн/].some(re=>re.test(x)&&re.test(y));
 return shared?Math.max(0.7,similarity(strip(a),strip(b))):similarity(strip(a),strip(b));
}
function similarity(a,b){
  const x=vocabulary(a),y=vocabulary(b);
  if(!x.size||!y.size)return 0;
  let both=0;for(const k of x)if(y.has(k))both++;
  return Math.max(both/Math.max(x.size,y.size),0.72*both/Math.min(x.size,y.size));
}
function isLiteralDuplicate(a,b){
  const x=fold(a).replace(/\s+/g,""),y=fold(b).replace(/\s+/g,"");
  if(x.length<55||y.length<55)return false;
  if(x===y)return true;
  if(Math.min(x.length,y.length)/Math.max(x.length,y.length)<0.90)return false;
  const q=3,grams=v=>{const s=new Set();for(let i=0;i<=v.length-q;i++)s.add(v.slice(i,i+q));return s;};
  const g=grams(x),h=grams(y);let intersection=0;for(const k of g)if(h.has(k))intersection++;
  return intersection/(g.size+h.size-intersection)>=0.94;
}
function detectEvents(v){
 const s=fold(v).replace(/\s+/g," ");
 return EVENTS.filter(e=>e.patterns.some(p=>p.every(fragment=>s.includes(fold(fragment))))).map(e=>e.id);
}
function candidateText(c){return [c.title,c.text,c.event,c.conflict,c.viewpoint,c.conclusion,(c.characters||[]).join(" ")].filter(Boolean).join(" "); }
function archiveText(p){return [p.search_text,p.original_text,p.topic,p.angle,p.text].filter(Boolean).join(" ");}
function krasnoyarskToday() {
 const parts=new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Krasnoyarsk",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
 const dates=Object.fromEntries(parts.map(p=>[p.type,p.value]));
 return dates.year+"-"+dates.month+"-"+dates.day;
}
function parseISODate(v){
 if(!/^\d{4}-\d\d-\d\d$/.test(v||""))return null;
 const d=new Date(v+"T00:00:00Z");
 return Number.isNaN(d.getTime())||d.toISOString().slice(0,10)!==v?null:d;
}
function ready(c){return !!(String(c.event||"").trim()&&String(c.conflict||"").trim()&&Array.isArray(c.characters)&&c.characters.length);}
function matchArchive(c, posts, journal=[]){
 const q=candidateText(c), cEvents=new Set(detectEvents(q));
 if(c.event_id && EVENTS.some(e=>e.id===c.event_id))cEvents.add(c.event_id);
 const found=[];
 const emit=(p,kind)=>{
  const body=archiveText(p);
  const events=new Set(detectEvents(body));
  for(const e of EVENTS)if(e.anchor===String(p.post_id))events.add(e.id);
  const common=[...cEvents].filter(id=>events.has(id));
  const lex=similarity(c.text||c.title||q,body);
  const priority=common.length?Math.max(0.82,lex):lex;
  if(priority<0.11)return;
  found.push({kind,id:kind==="post"?p.post_id:p.journal_id,url:p.url||null,status:kind==="post"?"published":p.state||"unknown",score:Number(priority.toFixed(3)),event_ids:common,excerpt:(p.search_text||p.original_text||p.topic||p.angle||"").slice(0,230),same_wording:isLiteralDuplicate(c.text||"",p.search_text||p.original_text||p.text||"")});
 };
 const seen=new Set();
 for(const p of posts||[]){const id=String(p.post_id||"");if(!id||seen.has(id))continue;seen.add(id);emit(p,"post");}
 for(const j of journal||[]){
  if(j.state==="cancelled"||j.state==="canceled")continue;
  if(j.linked_post_id&&seen.has(String(j.linked_post_id)))continue;
  emit(j,"journal");
 }
 found.sort((a,b)=>b.score-a.score||+(b.same_wording)-+(a.same_wording)||String(a.id).localeCompare(String(b.id)));
 return found.slice(0,15);
}
function compare(c, posts=[], journal=[], options={}){
 const today=options.as_of||krasnoyarskToday();
 const lastSync=options.last_synced_at||null;
 const days=lastSync&&parseISODate(today)&&parseISODate(lastSync)?
    Math.floor((parseISODate(today)-parseISODate(lastSync))/86400000):null;
 const stale=days===null||days>=(options.max_age_days??1)||days<0;
 const matches=matchArchive(c,posts,journal);
 const first=matches[0]||null, eventMatches=matches.filter(m=>m.event_ids.length);
 const scheduled=matches.filter(m=>m.kind==="journal"&&["scheduled","approved","planned"].includes(m.status)&&(m.event_ids.length>0||m.score>=0.45));
 const duplicate=matches.find(m=>m.same_wording && m.kind==="post");
 const reasons=[];let verdict="REVIEW_REQUIRED",confidence="low";
 if(duplicate){
  verdict="DUPLICATE";confidence="high";reasons.push("Текст практически совпадает с ранее опубликованным.");
 }else if(eventMatches.length){
  const best=eventMatches[0];
  const profile=EVENTS.find(e=>best.event_ids.includes(e.id));
  const cview=fold(c.viewpoint),oldView=fold(profile?.viewpoint);
  const newConflict=fold(c.conflict),oldConflict=fold(profile?.conflict);
  const explicitOtherView=!!(cview&&oldView&&!cview.includes(oldView)&&!oldView.includes(cview));
  const explicitOtherConflict=!!(newConflict&&oldConflict&&conflictSimilarity(newConflict,oldConflict)<0.40);
  if(explicitOtherView&&explicitOtherConflict){
   verdict="NEW_ANGLE";confidence="medium";
   reasons.push("Событие уже встречалось, но предложены иная точка зрения и отдельный конфликт.");
   reasons.push("Отличие предварительное; редактор должен проверить драматургию и финальный вывод.");
  }else if(profile&&!explicitOtherView&&!explicitOtherConflict){
   verdict="SAME_STORY";confidence="medium";
   reasons.push("Обнаружено то же конкретное событие без доказанного нового конфликта и точки зрения.");
  }else{
   reasons.push("Событие совпадает, но подтверждения самостоятельной драматургии недостаточно.");
  }
 }else if(first && first.score>=0.74 && words(c.text||c.title||"").length>=9){
  verdict="SAME_STORY";confidence="medium";
  reasons.push("Высокое лексическое сходство с ранее использованным материалом; требуется смысловая проверка.");
 }else if(!stale&&ready(c)&&(!first||first.score<=0.18)){
  verdict="NEW_STORY";confidence="low";
  reasons.push("Конкретное событие и конфликт заданы, близких совпадений в доступном индексе не обнаружено.");
  reasons.push("Это предварительная оценка, а не доказательство уникальности.");
 }else{
  reasons.push(stale?"Данные публикаций недостаточно свежие для вывода о новой истории.":"Нет достаточных сведений для достоверной классификации.");
 }
 if(scheduled.length){
  reasons.push("В редакционном журнале есть схожая запланированная или утверждённая публикация.");
  if(verdict==="NEW_STORY"||verdict==="NEW_ANGLE"){verdict="REVIEW_REQUIRED";confidence="low";}
 }
 if((verdict==="NEW_STORY")&&stale){verdict="REVIEW_REQUIRED";confidence="low";}
 if(!posts.length){verdict="REVIEW_REQUIRED";confidence="low";reasons.push("Архив пуст.");}
 return {verdict,confidence,provisional:verdict!=="DUPLICATE",archive_fresh:!stale,latest_checked_date:lastSync,reason:reasons.join(" "),matches};
}
module.exports={STATES,EVENTS,fold,words,similarity,isLiteralDuplicate,detectEvents,matchArchive,compare,krasnoyarskToday};
