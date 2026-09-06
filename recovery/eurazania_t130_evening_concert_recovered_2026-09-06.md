# Eurazania T+130 — recovered evening concert ledger

Status: `RECOVERED / CONFIRMED FROM LIVE CHECKPOINTS`

This file separates the T+130 evening concert from the distinct T+129 free concert and preserves the uncertain boundary between the opening/warm-up block and Arlequino's main set.

## Event identity

- Day: **T+130**
- Place: **Borga's big training yard, Eurazania capital**
- Main concert was publicly advertised for **19:00**.
- Musical portion ended at **~20:29**.
- Arlequino and Rena left the yard at **~20:31**.
- Rena and Borga were present through the main concert.

## Pre-concert promotion

T+130 17:45-18:40:
- Arlequino walked the capital with his personal violin.
- He played songs from the **previous day's concert**, proving T+129 and T+130 are separate concert events.
- After street performances he promoted the 19:00 concert, the king-approved festival/tournament, and the winner's right to fight King Carrion.
- Street-music income: **+18s66c**.
- Cash after promotion: **24g86s53c**.

## Opening / warm-up block

Direct LIVE v125 continuity lists these performances before Arlequino's main sequence:

1. **«Наблюдатель»** — Arlequino + Rena.
   - Explicitly described in accounting as **warm-up**.
   - No separate collection resolved.
   - Exact full durable text is unavailable in the surviving canonical archive.
2. **Rena song about bears**.
   - Exact title/text: `UNKNOWN`.
3. **Rena song about hares/rabbits**.
   - Exact title/text: `UNKNOWN`.
4. **«Вьюга»** — performed by Rena.

Boundary rule: only «Наблюдатель» is explicitly labelled warm-up in the surviving checkpoint. The following Rena performances are clearly part of the opening sequence, but surviving data does not explicitly name each one as warm-up. Therefore do **not** retroactively number them as Arlequino's official main set.

Cash arithmetic confirms the opening block produced **no recorded increase in Arlequino's cash**: cash at v124 was 24g86s53c, while the v124→v125 increase of exactly 1g35s14c is fully explained by the four subsequent Arlequino songs below.

## Main Arlequino set — 16 performances

### Bloody first half

1. **«Герои»** — **+64s12c**
2. **«Головы с плеч»** — **+29s74c**
3. **«От копья»** — **+21s86c**
4. **«Заклинатель и осёл»** — **+19s42c**
5. **«С щитами не рождаются»** — **+18s68c** `DERIVED_FROM_CASH_DELTA`
6. **«Мечник»** — **+16s92c**
7. **«Ночь перед боем»** — **+15s36c**
8. **«Шаг в темноту»** — **+14s72c**
9. **«Штиль»** — **+13s88c**

LIVE v129 explicitly states that «Штиль» **closed the bloody first half** and that the promised cute half was next.

Derivation for «С щитами не рождаются»:
- cash after v125 = 26g21s67c
- cash after «Мечник» v126 = 26g57s27c
- delta = 35s60c
- minus direct «Мечник» income 16s92c
- therefore «С щитами не рождаются» = **18s68c**, assuming no unrecorded transaction between the two adjacent checkpoints.

### Cute second half

10. **«Космос»** — **+16s24c** `DERIVED_FROM_CASH_DELTA`
11. **«Созвездие Ангела»** — **+17s80c**
12. **«Приключения»** — instrumental, Gravity Falls motif; **+11s42c**
13. **«Невеста палача»** — **+15s34c**
14. **«Самый лучший день»** — **+13s16c**
15. **«Эурозанская ночь»** — first performance; **+18s66c**
16. **«Эурозанская ночь»** — immediate repeat; **+12s08c**

Direct v130 continuity says Arlequino stayed with Rena after «Космос» and **immediately continued with «Созвездие Ангела»**, fixing their order.

Derivation for «Космос»:
- cash after «Штиль» = 27g01s23c
- cash after «Созвездие Ангела» = 27g35s27c
- delta = 34s04c
- minus direct «Созвездие Ангела» income 17s80c
- therefore «Космос» = **16s24c**, assuming no unrecorded transaction between adjacent checkpoints.

## Main-set money ledger

Cash immediately before the four first recorded Arlequino main-set songs: **24g86s53c**.

Cash after the final repeat of «Эурозанская ночь»: **28g05s93c**.

Total increase: **3g19s40c**.

Sum of all 16 main-set song incomes above: **3g19s40c** exactly.

Therefore:
- confirmed main-set income: **+3g19s40c**
- recorded expenses in these performance checkpoints: **0**
- confirmed main-set net: **+3g19s40c**

This exact cash reconciliation is also evidence that the opening/Rena block did not add a separate amount to Arlequino's recorded cash before «Герои».

## Audience size

Status: **UNKNOWN**.

The surviving T+130 LIVE checkpoints repeatedly mention the gathered crowd/public and describe reactions, but no reliable numeric audience count has been located. Do **not** borrow the T+129 ~300-320 figure, and do **not** assign remembered figures such as ~18,000 or ~100,000 to this event without a direct source.

## Ending

At ~20:29, after the repeat of «Эурозанская ночь»:
- Arlequino bowed;
- approached Rena;
- embraced her from behind and kissed her neck;
- publicly said: **«На сегодня мое терпение исчерпано. Я люблю музыку.... Но есть та которую я люблю больше.»**
- musical part was explicitly over.

At ~20:31 Arlequino and Rena left the training yard together; Borga remained at the yard.

## Primary sources

- LIVE v122 — pre-concert street promotion: `d8655a486b98757687016d53b8ac51f0d53453df`
- LIVE v124 — public tournament announcement / pre-main-yard state: `908831ca2d8fddefea624f7741b5a33f8f9f1de2`
- LIVE v125 — opening block + early main set through «Заклинатель и осёл»: `5f17d270fe42d42ec45019b7b87c8c8cb9f81616`
- LIVE v126 — «Мечник» after «С щитами не рождаются»: `159401569625d41fa6a22c1e9987c5976d326015`
- LIVE v127 — «Ночь перед боем»: `3934c8f2481de27ce048b27f85a1ef559ddaf6f5`
- LIVE v128 — «Шаг в темноту»: `c3835f3315a4ec8908a8ffb7c2787bbe4dc755a0`
- LIVE v129 — «Штиль» closes bloody half: `ab929122ae9a1bf0edc119d565a2a79ba72c7c07`
- `live_v130/delta.json` — «Созвездие Ангела» immediately after «Космос»
- `live_v131/delta.json` — «Приключения»
- `live_v132/delta.json` — «Невеста палача»
- `live_v133/delta.json` — «Самый лучший день»
- `live_v134/delta.json` — first «Эурозанская ночь»
- `live_v135/delta.json` — repeat «Эурозанская ночь»
- `live_v136/delta.json` — musical ending ~20:29
- `live_v137/delta.json` — departure ~20:31
