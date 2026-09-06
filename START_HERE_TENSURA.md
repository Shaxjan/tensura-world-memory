# START HERE — Tensura World Memory

Status: `PRIMARY ENTRYPOINT FOR A NEW CHAT`

If you are a new ChatGPT conversation continuing this Tensura world, **read this file first**. Do not try to reconstruct the project from filenames, old chat memory, or a random `live_v###` directory.

## 1. What this repository is

This repository is the durable memory system for the user's Tensura / Maestro Arlequino world.

It stores several different kinds of truth:
- the **current physical scene**;
- authoritative runtime transitions/checkpoints;
- persistent NPC character memory;
- creative exposure/familiarity;
- autonomous canon/world rules;
- news and rumor propagation;
- historical saves and evidence;
- reconciled recovery work for older damaged or compressed continuity.

These layers are intentionally separate. Do not flatten them into one undifferentiated canon dump.

## 2. Mandatory reading order for a new chat

### Always read first

1. **`START_HERE_TENSURA.md`** — this file.
2. **`runtime/current_scene.json`** — current physical scene while `status = ACTIVE`.
3. **`MEMORY_MAP_v1.md`** — layer meanings and authority/source priority.
4. **`runtime/rules/LIVING_WORLD_SIMULATION_v1.md`** — mandatory autonomy/realism rule for normal play.
5. **`runtime/rules/CANON_TIMELINE_SYNC_v1.md`** — autonomous progression of Tensura canon and divergence rules.
6. **`runtime/rules/NEWS_RUMOR_PROPAGATION_v1.md`** — autonomous movement of news, rumors and public information.

### Then, depending on the task

7. **Historical event / old concert / old city / lost continuity:**
   - `recovery/RECOVERY_INDEX.md`
   - then the dedicated recovery file linked there.

8. **High-level public works, concerts, poetry, cultural spread:**
   - `PUBLIC_CULTURAL_CANON_REGISTRY.md`

9. **What is still missing and must not be guessed:**
   - `UNRESOLVED_RECOVERY.md`

10. **Chronology / “what happened around T+X?”:**
   - `TIMELINE_INDEX.md`

11. **NPC personality, relationships and remembered experiences:**
   - `memory/characters/CHARACTER_SYSTEM_v1.md`
   - `memory/characters/`
   - `CHARACTER_MEMORY_RULES_v1.md` where relevant.

12. **Whether someone has heard/read/watched a work before:**
   - `memory/creative_exposure/`
   - follow `memory/creative_exposure/CREATIVE_EXPOSURE_PROTOCOL_v1.md`.

13. **Engine/runtime mechanics or transition disputes:**
   - `MASTER_SAVE_PROTOCOL.md`
   - `runtime/runtime_state.json`
   - relevant `runtime/journal/`, checkpoint, correction or clarification files.

## 3. Current-scene rule

`runtime/current_scene.json` is the single durable current-frame overlay while it is ACTIVE.

At the time this entrypoint was created, it records:
- **T+162 ~10:07**;
- **Dwargon**;
- student meeting/casting discussion for **«Гвазимодо»** in progress;
- Rena present;
- Arlequino has delegated to Rena: find an organizer/coordinator, investigate where Eurazania evacuees were sent, and begin gathering new-home options;
- Arlequino's deliberate next action remains **USER_CONTROLLED_ONLY**.

This paragraph is only a creation-time snapshot. **Future chats must fetch `runtime/current_scene.json` again.** If that file has advanced, the newer active overlay wins.

Do not reset current play to an older checkpoint or to this snapshot.

## 4. Living-world rule — mandatory during normal play

The world does not wait for Arlequino.

Every substantial scene transition must respect `runtime/rules/LIVING_WORLD_SIMULATION_v1.md`.

Operationally this means:
- enough elapsed time can advance NPC assignments, travel, work, institutions, markets, roads, preparations, wars, evacuations and other independent processes;
- canonical actors continue on the synchronized canon timeline unless a real causally sufficient divergence changes it;
- news and rumors travel after events occur through plausible channels and with plausible delay;
- recurring NPCs act from their own personality, knowledge, obligations, relationships, resources and goals rather than serving as generic assistants;
- physical and social reality constrains outcomes: time, distance, money, availability, logistics, authority, fatigue, capacity and consequences matter;
- only the causally visible subset of world changes is shown to Arlequino.

The player controls Arlequino. The player does **not** control whether the rest of the world continues to exist and act.

## 5. Canon progression

`runtime/rules/CANON_TIMELINE_SYNC_v1.md` is ACTIVE.

Canon is an autonomous baseline, not a railroad and not a paused script.

Rules:
- canonical events do not wait for Arlequino's personal plans;
- canonical actors keep their own goals, capabilities and knowledge;
- Arlequino may cause a real divergence if he learns enough and acts in time;
- the GM may not protect canon by making NPCs irrational;
- the GM may not protect Arlequino by delaying the world;
- true divergence must be persisted and its consequences propagated forward.

Future canon is GM/runtime knowledge until causally exposed in-world.

## 6. News and rumor propagation

`runtime/rules/NEWS_RUMOR_PROPAGATION_v1.md` is ACTIVE.

Information must move autonomously through plausible channels: officials, guilds, merchants, travelers, refugees, inns, streets, messengers, guards, diplomats, performers, students, craftsmen and other established networks.

Important distinctions:
- official statement is not automatically objective truth;
- eyewitness is not infallible;
- rumor may distort;
- secret information stays secret until leaked;
- public information is not universal NPC knowledge;
- Arlequino does not need to explicitly ask “what are the news?” for relevant public information to reach him naturally.

For any important NPC knowledge claim, there must be a plausible answer to:
`SOURCE -> TRANSMISSION -> TIME/DELAY -> RECIPIENT`.

## 7. Character autonomy and persistence

Use `memory/characters/CHARACTER_SYSTEM_v1.md` before flattening a recurring NPC into a convenient scene role.

Persistent named NPCs accumulate:
- evidence-grounded traits;
- values and boundaries;
- goals and obligations;
- relationships;
- causal memories;
- knowledge boundaries;
- habits and initiative patterns when actually established.

NPCs may disagree, refuse, misunderstand, initiate, leave, fail, change their mind, pursue private goals and be unavailable.

Marriage, friendship, affection, employment, gratitude or rank never implies automatic obedience.

Private thoughts are not player knowledge unless revealed in-world.

## 8. Source authority

Use the full priority rules in `MEMORY_MAP_v1.md`.

Operational shorthand:

1. newest direct user/player correction applicable to the fact;
2. active `runtime/current_scene.json` for current physical facts;
3. newer valid runtime delta/checkpoint/journal state;
4. explicit correction / clarification / retcon records;
5. specialized memory or reconciled recovery files;
6. older saves/history as evidence.

For historical recovered facts, dedicated recovery files are preferred over old speculative `in_progress` hypotheses **after** retcons and contradictions have been reconciled.

A recovery file never licenses overwriting a newer current fact.

## 9. Recovery navigation

Primary recovery index:
- **`recovery/RECOVERY_INDEX.md`**

Dedicated recovered history currently includes:
- early Dwargon school/concert/theatre layer;
- Eurazania T+129 free concert;
- Eurazania T+130 evening concert;
- Eurazania T+131 first poetry evening;
- Eurazania T+138 formal concert with retcon-aware handling;
- status of «Фестиваль Эуразании: Неделя силы»;
- Blumund cultural footprint and the complete T+116 Great Concert ledger.

Older files:
- `recovery/public_cultural_footprint_audit_in_progress.md`
- `recovery/public_cultural_footprint_patch_2026-09-06.md`

remain **provenance/evidence**, not the preferred single entrypoint once the index and final registry exist.

## 10. Cultural canon navigation

For public cultural history, start with:
- **`PUBLIC_CULTURAL_CANON_REGISTRY.md`**

It distinguishes:
- `CONFIRMED`
- `PARTIAL`
- `PLANNED`
- `SUPERSEDED`
- `UNKNOWN`

It also records important anti-merge rules, including:
- T+129 Eurazania was a small free courtyard concert, not an 18,000-person concert;
- T+138 **18,000** is safe capacity, not confirmed attendance;
- “hundreds of thousands” for Week of Strength is a confirmed **promotional claim**, not observed attendance;
- T+154 “thousands of refugees” belongs to a separate wartime gathering, not the festival.

## 11. Unknown means unknown

Before inventing a plausible historical answer, check:
- **`UNRESOLVED_RECOVERY.md`**

Important unresolved examples at creation time:
- T+112 Blumund exact venues/setlist;
- specific T+113 announced poetry-evening completion;
- early Dwargon concert identity/program/audience details;
- T+130 Eurazania numeric audience;
- later Eurazania poetry-evening completion;
- T+138 «Полегче» replay/completion after rewind;
- T+138 complete setlist, final attendance and revenue;
- formal administrative cancellation/postponement wording for Week of Strength.

Do not turn an `UNKNOWN` into canon just because an answer would be narratively convenient.

## 12. Critical anti-confusion rules

### `live_v###` is not T+###

`live_v71`, `live_v129`, `live_v159`, etc. are runtime/save-frame versions. They are **not in-world day numbers**.

Use explicit world-time fields, checkpoints and chronology evidence.

### Capacity is not attendance

Never equate a site's maximum safe capacity with the observed crowd unless the source explicitly says it filled to that number.

### Promotion is not outcome

An advertised or promised audience size is not a completed-event attendance count.

### Archive artifact is not event completion

A song/poem text existing in `song_archive/` or `poetry_archive/` proves the artifact exists. It does not by itself prove that a specific retconned performance completed.

### Similar event names are not identity proof

Do not merge concerts, premieres, rehearsals or school events merely because dates/participants/titles overlap.

### Old exact number can still be stale

Do not replace a newer `UNKNOWN`/approximation with an old precise number from a checkpoint when the current state has changed.

## 13. Player agency

The user controls Arlequino's:
- spoken words;
- thoughts;
- feelings;
- deliberate meaningful actions and choices.

Do not write them on the user's behalf.

NPCs may act autonomously when causally justified, but autonomy must not create unexplained continuity resets.

## 14. Names, agreements and who heard what

The project requires durable causal memory.

Persist and consult:
- names of recurring people;
- agreements, promises, payments and assignments;
- important details from Arlequino's works;
- **who was present / who was told / who heard or read something**;
- later propagation through realistic channels.

Do not give an NPC knowledge simply because the repository or narrator knows it.

For creative familiarity, consult `memory/creative_exposure/` before narrating novelty.

## 15. Recommended new-chat startup instruction

The user can begin a new conversation with:

> Продолжаем Tensura. Используй подключённый GitHub `Shaxjan/tensura-world-memory`. Сначала прочитай `START_HERE_TENSURA.md`, `runtime/current_scene.json`, `MEMORY_MAP_v1.md` и `runtime/rules/LIVING_WORLD_SIMULATION_v1.md`. Следуй активным правилам канона и слухов. Не додумывай UNKNOWN и не позволяй старым checkpoint'ам перезаписывать новый runtime.

That should be sufficient. The user should not need to paste a giant handoff into every new chat.

## 16. Maintenance rule

Whenever a major recovery item is resolved:
- update its dedicated recovery file;
- update `recovery/RECOVERY_INDEX.md`;
- update `PUBLIC_CULTURAL_CANON_REGISTRY.md` if public cultural canon changed;
- update/remove the matching item in `UNRESOLVED_RECOVERY.md`;
- update `TIMELINE_INDEX.md` if chronology materially changed.

Whenever normal gameplay advances, update runtime/current-scene systems according to the existing save protocol. Do **not** manually freeze `START_HERE_TENSURA.md` to every turn; it is a navigation file, not the live scene store.

Whenever world time advances substantially, apply `LIVING_WORLD_SIMULATION_v1.md` before narrating the new scene so canon progression, NPC autonomy, rumor propagation and material consequences are not accidentally frozen.