async () => {
  const nap = n => new Promise(resolve => setTimeout(resolve, n));
  let cards = [];
  for (let attempt = 0; attempt < 30; attempt++) {
    cards = Array.from(document.querySelectorAll('[data-pressable-container="true"]'));
    if (cards.length) break;
    await nap(150);
  }
  const marker = text => (text || "").match(/(?:^|\n)(\d+)\s*\n\/\s*\n(\d+)(?:\n|$)/);
  const rootMarker = marker(cards[0]?.innerText);
  const total = rootMarker && Number(rootMarker[1]) === 1 ? Number(rootMarker[2]) : 1;
  for (let attempt = 0; attempt < 30 && cards.length < total; attempt++) {
    await nap(180);
    cards = Array.from(document.querySelectorAll('[data-pressable-container="true"]'));
  }
  const parts = cards.slice(0, Math.min(total, 15)).map((el, i) => {
    const spans = Array.from(el.querySelectorAll('span[dir="auto"]'));
    const marked = spans.find(s => /(?:^|\n)\d+\s*\n\/\s*\n\d+\s*$/.test(s.innerText));
    const longest = spans.filter(s => !/^\d\d\.\d\d\.\d\d\d\d$/.test(s.innerText.trim()))
      .sort((a,b) => b.innerText.length - a.innerText.length)[0];
    const textNode = marked || longest;
    const raw = textNode?.innerText || "";
    const m = marker(el.innerText);
    return {
      index: m ? Number(m[1]) : i+1,
      total: m ? Number(m[2]) : total,
      text: raw.replace(/\s*\d+\s*\/\s*\d+\s*$/, "").trim(),
      permalink: Array.from(el.querySelectorAll('a[href*="/post/"]')).map(a => a.href)
        .find(url => url.includes('/@mirpottera/post/')) || null,
      media: Array.from(el.querySelectorAll('a[href*="/media"]')).map(a => a.href).slice(0,12)
    };
  });
  return { total, parts, available: cards.length,
    verified_url: location.href, success: parts.length === total &&
      parts.every((p,i) => p.index === i+1 && p.total === total && Boolean(p.permalink)) };
}