# Eurazania T+129 — recovered free-concert ledger

Status: `RECOVERED / CONFIRMED FROM LIVE CHECKPOINTS`

This file reconstructs the T+129 evening free concert in the Eurazania capital from LIVE v71-v93-era checkpoints. It is a recovery artifact, not a rewrite of later current-state canon. Where checkpoint times overlap by a minute or two, treat them as approximate scene-boundary timestamps rather than exact stopwatch timing.

## Event identity

- Day: **T+129**
- Place: **Eurazania capital — small combat/training yard**
- Admission: **free**
- Official start: **~19:00**
- Musical end: **~20:51**
- Arlequino performed with the **violin**. The guitar was with Rena during the public concert.
- The number immediately before the official start was **«Черная невеста»** at ~18:56-19:00. LIVE v71 explicitly says its ending carried the yard into the official start. It is therefore a **pre-concert bridge**, not official setlist item #1.
- LIVE v72 explicitly identifies **«Головы с плеч»** as the **first official concert song**.

## Audience scale — recovered correction

The remembered figure of about **18,000** does **not** belong to this T+129 free concert.

Direct LIVE checkpoints put this event in the **hundreds**, not tens of thousands:

- ~19:56: roughly **310** people remained engaged.
- ~20:02: roughly **320** people.
- ~20:08: roughly **320** people.
- «Оракул»: audience roughly **320 -> 310**.
- «Та, что»: roughly **310 -> 305**.
- «Мои враги»: roughly **305 -> 300**.
- End of «Вьюга»: roughly **295** remained.

So the strongest recoverable scale statement for T+129 is: **a dense local yard concert of roughly 300-320 people at its documented late-concert peak, ending around 295**.

The ~18,000 memory anchor may belong to another later/bigger event; this recovery does not assign it without a direct source.

## Official setlist

1. **«Головы с плеч»** — adapted version; for swordsmen. ~19:01-19:06. Tips **+18s72c**.
2. **«От копья»** — for spearmen. ~19:06-19:11. Tips **+17s38c**.
3. **«Танец лучников»** — for archers. Played ~19:11-19:15; reaction/accounting resolved by ~19:17. Tips **+19s64c**.
4. **«С щитами не рождаются»** — adapted from «Солдатами не рождаются»; for shield-bearers. ~19:15-19:20 checkpoint window. Tips **+18s76c**.
5. **«Кукла колдуна»** — for the magic-group block. ~19:21-19:26. Tips **+22s48c**.
6. **«Тяни»** — performed as a metaphorical address toward a healer in the crowd. ~19:27-19:32. Tips **+21s48c**.
7. **«Заклинатель и осёл»** — user adaptation of «Ведьма и осёл»; for enchanters. ~19:33-19:38. Tips **+24s36c**.
8. **«Для мира на земле»** — user-adapted war song, addressed broadly rather than to one specialization. ~19:39-19:45. Tips **+25s14c**.
9. **«Принцесса»** — exact user-adapted text restored by LIVE v82 RETCON; authoritative version. ~19:46-19:50. Tips **+23s64c**.
10. **«Я вам не верю»** — reference: Grigory Leps «Я тебе не верю». ~19:52-19:56. Tips **+24s12c**.
11. **«Космос»** — exact user-adapted version. ~19:56-20:02. Tips **+28s64c**.
12. **«Созвездие Ангела»** — public concert performance, ending ~20:08. Tips **+31s42c**. Audience ~320.
13. **«Оракул»** — Мачете; long theatrical performance, ~23 minutes, ending ~20:34. Tips **+41s68c**. Audience ~320 -> ~310.
14. **«Та, что»** — adapted text. Ending ~20:39. Tips **+27s34c**. Audience ~310 -> ~305.
15. **«Мои враги»** — from Uzbek «Ichimdagi dushmanlarim», performed in common tongue through a direct/literal Russian rendering. Ending ~20:45. Tips **+34s18c**. Audience ~305 -> ~300.
16. **«Вьюга»** — final song. Ending ~20:51. Tips **+31s24c**. Audience **~295 at end**.

## Money ledger

- Personal cash immediately after the pre-concert bridge «Черная невеста»: **20g76s24c**.
- Personal cash after final official song «Вьюга»: **24g86s46c**.
- Sum of all 16 official-song tips: **4g10s22c**.
- Concert expenses recorded for these performances: **0**.
- Therefore confirmed official-concert net income: **+4g10s22c**.

This arithmetic exactly matches the cash delta 20g76s24c -> 24g86s46c.

## Important exclusions / continuity boundaries

### «Черная невеста»
Confirmed at ~18:56-19:00 and explicitly bridges into the official 19:00 start. Do not number it as official concert item #1; LIVE v72 calls «Головы с плеч» the first official song.

### Dangerous song about power
After «Принцесса», Arlequino publicly mentioned a very dangerous song about power and **declined to perform it there**, deferring it to a possible larger future concert. It is **NOT** part of the T+129 setlist.

### Rena's original promised song
Separate continuity:
- Rena had worked on an original promised song for Arlequino for several weeks.
- She did perform it to Arlequino on the evening of T+129.
- Exact title and full text are lost in accessible history.
- Memory anchor preserved elsewhere: «Не быть великим , прийти домой. Ждут.» — semantic anchor only, not recoverable lyrics.
- There is no direct source placing Rena's song inside the **public** T+129 concert. Do **not** add it to the 16-song public setlist.

### «Созвездие Ангела»
It was publicly performed during the concert (~20:08), then later **performed again privately for Rena** at the family inn around T+129 ~21:07. These are two distinct performances.

## End of concert

LIVE v89 records:
- time **T+129 ~20:51**;
- «Вьюга» = **resolved final song**;
- audience **~295 at end**;
- Arlequino promised a **bigger, longer concert soon**;
- he said his beloved was waiting at the inn;
- after farewell banter, the concert was ending.

Arlequino was back at the family inn with Rena by about **21:04-21:05**.

## Source checkpoints

Primary recovery chain:
- LIVE v71 — commit `254fca5ea90b3ba218f340a9bd8abda448f3c8ed`
- LIVE v72 — `98634cf5d5345a6dff07da980b537d5c939afe2e`
- LIVE v74 — `548ac593ca38bb9b7dbcb975a95b2eeab918b0dd`
- LIVE v75 — `1d8fc6d1a2af8f3a11d7b926b8dcaabd67c59512`
- LIVE v77 — `e236f014c4a3fd62d55bc15acb3ae3258d8b387e`
- LIVE v78 — `0bb35ff5b4944a3438b2c843d901146df2242de7`
- LIVE v79 — `3d56fafd23c279e6cecaeef837d54ebc90cf1cf7`
- LIVE v80 — `eb4392564ff3d7d441ab42c91fe54a26b75b1c9d`
- LIVE v81 — `76119b0c6aa69929b5123bce8d6568ddc82eebe3`
- LIVE v82 — `b656589fff4a9ecd13b1e684ad688c6f623cddb1`
- LIVE v84 — `876f50c702ef513e96ac1fd443ff6dc151a0559b` plus storage repair `7e5d0d17f0e8fe10957892719774c94724312a92`
- LIVE v85 — `b04c1d0886cef5578a42552b2b1356ab153d6043`
- LIVE v86 delta — `6bcd5aa3215c1c060095b813a70fc9bf49ef7cce`
- LIVE v87 delta — `6933979a12b2f9463270f8d164394a99ac0f7575`
- LIVE v88 delta — `f7b965c6c07d1a9dc080ed5eecd8ee1e8b324e79`
- LIVE v89 final — `648d57904c189cab3193a406572e203a55f29fef`
- LIVE v90-v93 return/private continuity — `cae9a7e9dbe44a1160b7d2e5f0f5182c389f6856`, `b4a34ad33143c88ba56e74aaee109c05dcb6ca43`, `4b107cfc442ecfa21ab40b907465fb25b0c86ddf`, `a5ed8038ac60cb415ae8822005860b1be8b9b2a2`
- Rena lost-song audit — `20eb0ea215d909746a5fac8a2b0b3263805fa9f0`
