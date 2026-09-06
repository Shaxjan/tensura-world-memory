# Eurazania T+131 — first poetry evening recovery

Status: `CONFIRMED COMPLETED / LATER CONTINUATION UNCONFIRMED`

Purpose: reconstruct the first Eurazania poetry evening from the surviving T+131 archive/checkpoint chain without inventing a start time, full participant-by-participant running order, attendance, or later recurring evenings.

## Event identity

- Day: **T+131**
- Place: **small training arena, Eurazania capital**
- Event: **first poetry evening in Eurazania**
- Completion: **CONFIRMED**
- Exact start time: **UNKNOWN / not recovered from a direct durable source**
- Near-close checkpoint: **~23:49**
- Numeric audience size: **UNKNOWN**
- Poetry-evening revenue/tips: **UNKNOWN**

The balances preserved near the end of the evening (personal 27g47s13c; family purse 15s69c) are balances, not a poetry-event earnings ledger. Do not derive poetry-evening income from them.

## Established participants

The close checkpoint establishes these readers/authors/participants as present or established for the evening:

- Elira
- Marena
- Tyren
- Saila
- Doren
- Kern
- Leyna
- Reven
- Mirael
- Harn
- Neira

Spelling note: one festival checkpoint renders Neyra while the close checkpoint renders Neira. Treat this as the same established participant unless a later identity correction distinguishes them.

## Arlequino's archived performances — confirmed relative order

The Git first-parent archive chain gives the following **relative order among Arlequino's surviving archived poetry performances**.

This is **not** proof that no participant poem or discussion occurred between these items. Do not convert it into a complete minute-by-minute running order for the entire evening.

1. **Untitled poem about four eye colors** — archive opening anchor: «Серые глаза — рассвет…»
   - exact text preserved in `poetry_archive/t131_four_eye_colors_untitled.txt`
2. **«Любви все возрасты покорны»**
   - exact performed text archived
3. **«Приходи на меня посмотреть»**
   - exact performed text archived
4. **«Человеку надо мало»**
   - exact performed text archived
5. **`Sevaman deyilmasdi bizning paytlari`**
   - long Uzbek-language archive text preserved in `poetry_archive/t131_sevaman_deyilmasdi_bizning_paytlari.txt`
   - later that same evening Arlequino publicly referred to this poem in Russian as **«В наше время не говорили люблю»**
6. **«Кто жизнью бит…»**
   - exact four-line performed text archived
7. **«Лейла и Безумец»** — long adapted Eurazania performance
   - completed by approximately **23:42**
   - Arlequino called it **«жемчужина моего творчества»**
   - publicly dedicated the performed Eurazania-adapted version to **Eurazania and its people**
   - the exact full adapted performance text was **not supplied verbatim** in the durable event record and must **not** be reconstructed as exact canon

## «Лейла и Безумец» — public framing

After completing the long adapted performance, Arlequino publicly framed it as an example of complete love and linked the idea of eternal love to loving the One who is eternal, gesturing upward. The durable event record explicitly treats this as Arlequino's personal/public interpretation rather than objective cosmological fact.

He also referred back to **«В наше время не говорили люблю»**, confirming that the archived `Sevaman deyilmasdi bizning paytlari` poem had already been part of the evening's public poetic context before the Layla dedication.

His line about doing the next week without tragedy was a public intention/joke, not a confirmed booking.

## Collective poem about Eurazania

At approximately **23:45**:

- the gathered authors/readers had completed a collective poem about/praising Eurazania;
- the audience approved it for future festival performance;
- Arlequino publicly declared that it would be performed at **«Фестиваль Эуразании: Неделя силы»**;
- audience reaction favored the authors reading their own parts on the future large festival stage.

Authors/readers named in the festival-commitment checkpoint:
- Tyren
- Saila
- Doren
- Kern
- Leyna
- Marena
- Reven
- Mirael
- Harn
- Neyra/Neira
- Elira

Strict boundary:
- the existence and approval of the collective poem are CONFIRMED;
- a complete exact text of the collective poem is **NOT RECOVERED** from the currently verified source chain;
- festival performance was an announced future program intention, not a completed performance.

## Next poetry evening — status

At approximately **23:47** Arlequino publicly proposed:

- another poetry evening **next week, at the same time**;
- venue still **to be arranged**;
- expected theme: **comedy / without tragedy**;
- if people continued to participate, the evening could become regular.

The checkpoint explicitly states:
- the venue had not yet been secured;
- regular/institutional status had not yet been established.

Repository history searches for later `poetry`, `poetry evening`, and `comedy` checkpoints currently locate the T+131 evening and its planning statements, but **no direct later Eurazania poetry-evening completion checkpoint**.

Therefore the safe later-status rule is:

`NEXT_WEEK_POETRY_EVENING = PLANNED / COMPLETION_UNCONFIRMED`

Do not call it cancelled; do not call it completed without another direct source.

## Close of first evening

At approximately **23:49** the first poetry evening was explicitly recorded as nearing close.

Durable outcomes at close:
- first evening itself occurred and was completed;
- collective Eurazania poem existed and had audience approval for intended festival use;
- «Лейла и Безумец» had been performed and dedicated to Eurazania and its people;
- next-week poetry evening remained an intention with no secured venue;
- regular status remained unconfirmed.

## Publication-name precedence observed in the same close checkpoint

The close checkpoint records the user correction:
- **«Под сенью пера»** = daily publication
- **«Муза»** = weekly publication

These names take precedence over older superseded Blumund working names when current continuity refers to the publishing system.

## Source chain

Primary first-parent sequence for archived Arlequino performances and close:

1. four-eye-colors poem — `79ffbb5b97bc2ef25287063488dc05d01dbb9c93`
2. «Любви все возрасты покорны» — `046632b7a014679ab778496826825c077df72904`
3. «Приходи на меня посмотреть» — `dc0a61eb80a1398bf17be7636f52128e1b3fbd0e`
4. «Человеку надо мало» — `3d959f794c5e8cdbc088c52ea01470e54ab41f4c`
5. `Sevaman deyilmasdi bizning paytlari` — `8f23af473e24c2f9e821ad83059eba359daeb650`
6. «Кто жизнью бит…» — `8f807c198ee53c0f7603c80ea6f753f7fbff1cda`
7. «Лейла и Безумец» dedication/completion framing — `d19e2aa022aeae13239dcdf4bbc46508efffa307`
8. collective poem festival commitment — `1137ed416474f887dd8d87a451331d8789284845`
9. next-week plan/festival timing — `148c21ceb054833543966100b1c684926a3d176e`
10. first-evening close — `778dc9dd79749a3cb0b11451557e627b5620593d`

## Canon-use rules

For future simulation:
- NPCs who were present may remember the evening and individual performances they actually witnessed;
- do not invent an exact opening time;
- do not invent a numeric audience count;
- do not invent poetry-evening income;
- do not reconstruct exact lost/intermediate participant poems;
- do not claim the archived Arlequino sequence was the uninterrupted total program;
- do not reconstruct an exact full Eurazania-adapted «Лейла и Безумец» text;
- do not treat next week's comedy evening as completed unless a later direct source is found;
- do not treat the collective poem's intended festival performance as completed because the Week of Strength itself has no confirmed completion.
