# Tensura — Timeline Index

Status: `NAVIGATION TIMELINE / NOT A FULL TRANSCRIPT`

Purpose: let a future chat jump from an in-world day to the correct durable source without searching all `live_v*` directories.

This file summarizes significant anchors only. Exact current state always comes from `runtime/current_scene.json` while its status is ACTIVE.

| World time | Place | Anchor | Status / source |
|---|---|---|---|
| pre-T+111 | Dwargon | Arlequino's early active-world phase: student school, two distinct concerts, «Маэстро Арлекино и не только», public «Газель и Эмилия» premiere, later «Тод» staging | `PARTIAL` — `recovery/dwargon_early_concerts_and_school_recovery_2026-09-06.md` |
| T+111–T+113 | Blumund | early palace / city cultural layer develops; Arlequino becomes locally recognizable | `PARTIAL` — old T+113 context + recovery patch |
| T+112 | Blumund | large daytime public performance round; **+49s18c**, cash **6g05s06c** | `CONFIRMED AGGREGATE / DETAILS UNKNOWN` — `PUBLIC_CULTURAL_CANON_REGISTRY.md` |
| T+113 morning | Blumund | hotel `Gravity Falls`; Free Guild adventurer set; palace music; palace-gate readings of «Газель и Эмилия» and «Последний день…» | `CONFIRMED` — `PUBLIC_CULTURAL_CANON_REGISTRY.md` |
| T+113 20:00 planned | Blumund | announced hotel poetry evening | `PLANNED / SPECIFIC COMPLETION UNCONFIRMED` — `UNRESOLVED_RECOVERY.md` |
| T+116 evening → T+117 ~01:35 | Blumund | Great Blumund Concert; full **47-number** ledger; King Drum opening; public departure announcement | `CONFIRMED` — `recovery/public_cultural_footprint_patch_2026-09-06.md` |
| T+117 | Blumund | departure-day publishing/instrument projects continue autonomously; later save confirms poetry evenings as a continuing system | `CONFIRMED BROAD CONTINUITY` — historical save / audit |
| T+129 | Eurazania | free courtyard concert; official **16-number** Arlequino set; ~295 at end; **+4g10s22c** | `CONFIRMED` — `recovery/eurazania_t129_free_concert_recovered_2026-09-06.md` |
| T+130 daytime/evening | Eurazania | street reuse of prior-day songs; festival promotion; Rena opening layer; distinct main 19:00 concert with Arlequino **16-number** set; **+3g19s40c** | `CONFIRMED MAIN SET / AUDIENCE UNKNOWN` — `recovery/eurazania_t130_evening_concert_recovered_2026-09-06.md` |
| T+131 daytime | Eurazania | citywide street-performance / festival publicity campaign; «Герои», «Оракул», «Тьмы Князь»; **+1g38s20c** | `CONFIRMED` — `PUBLIC_CULTURAL_CANON_REGISTRY.md` |
| T+131 ~18:36 | Eurazania | performer recruitment for Week of Strength; public claim of potential **hundreds of thousands of spectators** | `CONFIRMED PROMOTIONAL CLAIM, NOT ATTENDANCE` — `recovery/eurazania_week_of_strength_status_2026-09-06.md` |
| T+131 evening → ~23:49 | Eurazania | first poetry evening; recovered Arlequino archive sequence; collective Eurazania poem; future weekly/comedic evening proposed | `CONFIRMED FIRST EVENING / LATER CONTINUATION UNCONFIRMED` — `recovery/eurazania_t131_first_poetry_evening_recovered_2026-09-06.md` |
| T+138 ~20:00 | Eurazania | formal large concert; **18,000 safe capacity**, ~12–14k pre-show estimate; retcon-aware partial set recovered | `PARTIAL` — `recovery/eurazania_t138_formal_concert_recovered_2026-09-06.md` |
| T+153 | Eurazania | Week of Strength still treated as future; plan to travel to Tempest after festival | `CONFIRMED FUTURE PLAN` — `recovery/eurazania_week_of_strength_status_2026-09-06.md` |
| T+154 | Eurazania | Milim war / evacuation crisis; wartime public gathering with **thousands of refugees** | `CONFIRMED SEPARATE EVENT` — festival status recovery |
| ~T+160 intended | Eurazania / Dwargon | nominal Week of Strength start window; no completed festival found; Arlequino already in Dwargon | `DERAILED_BY_WAR / COMPLETION_UNCONFIRMED` — festival status recovery |
| T+160 | Dwargon | direct surviving continuity places Arlequino and Rena in Dwargon | `CONFIRMED` — runtime/checkpoints referenced by recovery |
| T+162 ~10:07 | Dwargon | **current active frame**: student meeting/casting discussion for «Гвазимодо»; Rena present and delegated organizer/evacuee/home-search tasks | `CURRENT` — `runtime/current_scene.json` |

## Current-frame note

At the time this index was created, the active overlay is:
- **T+162 ~10:07**
- **Dwargon, student meeting hall**
- meeting/casting discussion for **«Гвазимодо»** in progress
- Rena present
- almost all 22 students had earlier been established in the hall, but exact currently present count is not silently upgraded to 22
- Arlequino's deliberate next action remains user-controlled.

This current-frame summary is only a navigation convenience. If `runtime/current_scene.json` later advances, that file outranks this row. Future chats must read the live current-scene file rather than freezing play at T+162 because this timeline exists.

## How to use this timeline

- Historical question: locate the day here, then open the linked recovery/canon file.
- Current gameplay: ignore historical rows as state setters; read `runtime/current_scene.json`.
- Character familiarity: use `memory/characters/` and `memory/creative_exposure/` in addition to event history.
- If a date is missing here, search the repo/history; absence from this index does not mean the day contained no events.

## Important version warning

Directories such as `live_v71`, `live_v130`, `live_v159`, etc. are **save-frame/runtime versions**, not in-world T+ day numbers. Never infer world chronology from the `v###` number alone.
