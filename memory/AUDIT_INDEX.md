# Tensura World Memory — Canon Audit Index

Audit date: 2026-09-04

## Purpose
This directory is a consolidated audit/index layer. It does **not** replace the LIVE runtime. The repository is now split conceptually into current runtime state, character memory, and historical/audit evidence.

## Source priority
1. Latest direct user correction / explicit retcon.
2. Current `runtime/runtime_state.json` pointer and matching `runtime/session_state.json` when synchronized.
3. Latest applicable runtime journal/checkpoint state.
4. Later explicit correction/retcon files.
5. Specialized category/character memory.
6. Older history and GitHub commit history.

`UNKNOWN` must remain unknown. A cancelled or superseded scene is never promoted into canon.

## Main navigation
- `../MEMORY_MAP_v1.md` — repository-wide guide and source-of-truth rules.
- `characters/CHARACTER_SYSTEM_v1.md` — persistent NPC characterization system.
- `characters/index.json` — named NPC registry and depth map.
- `characters/<npc>.json` — one durable profile per named NPC.
- `characters/students/README.md` — individual registry rules for the 22 Dwargon students.

## Categories
- `money.json` — cash, separate funds, paid fees, floats and obligations.
- `places.json` — known locations, exact/unknown names, venues and festival site.
- `words.json` — important exact wording, letters, public promises/announcements and remembered anchors that are explicitly not lyrics.
- `relationships.json` — durable relationship facts; does not replace individual character profiles.
- `actions.json` — active/resolved tasks, festival/tournament commitments, mail and current concert checkpoint.
- `songs.json` — master song registry and factual status of every known performance/text.

## Character memory rule
`relationships.json` answers **what relationship is established**. `characters/<npc>.json` answers **who this person is becoming**. Runtime answers **what is true right now**. Do not collapse these layers into one generic NPC description.

Character depth is earned through repeated actual story exposure. Frequently encountered NPCs may become highly detailed; rarely encountered NPCs remain shallow. No biography, preference, habit, emotion or motive is invented merely to make dialogue easier.

## Status vocabulary
- `SAVED_CANON` — durable saved canonical fact.
- `SUPERSEDED` — older fact explicitly corrected/retconned.
- `UNKNOWN` — no reliable exact fact available.
- `not_yet_authored` — no grounded character detail has been established yet.

## Song status vocabulary
- `FULL_CANONICAL` — complete text physically checked in one UTF-8 file under `song_archive/`.
- `FULL_LEGACY_SHARDS` — complete exact text survives in checked historical shards, but no verified one-file copy currently exists.
- `PARTIAL_EXACT` — some exact lines survive, but full text does not.
- `TEXT_LOST` — song/performance survives in continuity but exact full text cannot currently be recovered.
- `TITLE_ONLY` — title/performance known; no durable exact lyric text.
- `INSTRUMENTAL` — no lyric archive required.

## Critical song rule
A summary, remembered theme, title, source song, web lyrics or commit message saying “full” is not enough. Missing user-adapted lines are never reconstructed. A one-file song is canonical only after it is fetched back and verified not to be truncated.

## Current durable audit boundary
The older audit entry that named `live_state.json` as v125 is historical. The active runtime pointer currently uses the newer runtime system; always resolve current time/state from `runtime/runtime_state.json` + synchronized session state rather than assuming the 2026-08-22 snapshot is current.

The current fast-play runtime protocol remains authoritative for ordinary synchronized gameplay. Technical system activations must not replace the last real gameplay turn. HUD fields are mandatory in normal gameplay output.
