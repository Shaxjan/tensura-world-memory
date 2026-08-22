# Tensura World Memory — Canon Audit Index

Audit date: 2026-08-22

## Purpose
This directory is a consolidated audit/index layer. It does **not** replace `live_state.json`, `live_vNNN/delta.json`, or `world_save.json`.

## Source priority
1. Latest direct user correction / explicit retcon.
2. Current `live_state.json` pointer and its referenced delta.
3. Later LIVE deltas that explicitly correct older facts.
4. `world_save.json` for broad history.
5. GitHub commit history for old exact facts/wording.
6. Category memory as an audit/index and contradiction map.

`UNKNOWN` must remain unknown. A cancelled or superseded scene is never promoted into canon.

## Categories
- `money.json` — cash, separate funds, paid fees, floats and obligations.
- `places.json` — known locations, exact/unknown names, venues and festival site.
- `words.json` — important exact wording, letters, public promises/announcements and remembered anchors that are explicitly not lyrics.
- `relationships.json` — Rena, Carrion, Borga, Meira, Gareth, Vern and other durable relationship states.
- `actions.json` — active/resolved tasks, festival/tournament commitments, mail and current concert checkpoint.
- `songs.json` — master song registry and factual status of every known performance/text.

## Status vocabulary
- `SAVED_CANON` — durable saved canonical fact.
- `SUPERSEDED` — older fact explicitly corrected/retconned.
- `UNKNOWN` — no reliable exact fact available.

## Song status vocabulary
- `FULL_CANONICAL` — complete text physically checked in one UTF-8 file under `song_archive/`.
- `FULL_LEGACY_SHARDS` — complete exact text survives in checked historical shards, but no verified one-file copy currently exists.
- `PARTIAL_EXACT` — some exact lines survive, but full text does not.
- `TEXT_LOST` — song/performance survives in continuity but exact full text cannot currently be recovered.
- `TITLE_ONLY` — title/performance known; no durable exact lyric text.
- `INSTRUMENTAL` — no lyric archive required.

## Critical song rule
A summary, remembered theme, title, source song, web lyrics or commit message saying “full” is not enough. Missing user-adapted lines are never reconstructed. A one-file song is canonical only after it is fetched back and verified not to be truncated.

## Current live boundary after audit
`live_state.json` now points to **v125**.

- time: `T+130 ~19:29`
- location: big training yard, Eurazania capital
- last resolved performance: `Заклинатель и осёл`
- personal cash: `26g21s67c`
- user alone controls Arlequino's next words/song/action

The previously unsaved post-v124 concert tail is now included in `live_v125/delta.json`; it is no longer pending chat-only state.