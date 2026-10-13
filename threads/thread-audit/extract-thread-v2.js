async () => {
  const sleep=n=>new Promise(r=>setTimeout(r,n));
  let cards=[];
  for(let i=0;i<30;i++){cards=[...document.querySelectorAll('[data-pressable-container="true"]')];if(cards.length)break;await sleep(150)}
  const marker=text=>(text||"").match(/(?:^|\n)(\d+)\s*\n\/\s*\n(\d+)(?:\n|$)/);
  const first=marker(cards[0]?.innerText);
  const n=first&&Number(first[1])===1?Number(first[2]):1;
  for(let i=0;i<30&&cards.length<n;i++){await sleep(150);cards=[...document.querySelectorAll('[data-pressable-container="true"]')]}
  const parts=cards.slice(0,Math.min(n,20)).map((el,i)=>{
    const textSpans=[...el.querySelectorAll('span[dir="auto"].xi7mnp6')].filter(s=>!s.parentElement?.closest('span[dir="auto"].xi7mnp6'));
    const blocks=textSpans.map(s=>s.innerText.replace(/\s*\d+\s*\/\s*\d+\s*$/,"").trim()).filter(Boolean);
    const text=blocks.join("\n\n");
    const m=marker(el.innerText);
    const url=[...el.querySelectorAll('a[href*="/post/"]')].map(a=>a.href).find(u=>u.includes('/@mirpottera/post/'))||null;
    return{index:m?Number(m[1]):i+1,total:m?Number(m[2]):n,text,block_count:blocks.length,permalink:url,media_links:[...el.querySelectorAll('a[href*="/media"]')].map(a=>a.href).slice(0,10)};
  });
  return{total:n,parts,success:parts.length===n&&parts.every((p,i)=>p.index===i+1&&p.total===n&&p.permalink),url:location.href};
}