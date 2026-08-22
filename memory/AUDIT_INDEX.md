# Tensura World Memory — Canon Audit Index

Audit date: 2026-08-22

## Purpose
This directory is a consolidated audit/index layer. It does **not** replace `live_state.json`, `live_vNNN/delta.json`, or `world_save.json`.

## Source priority
1. Latest direct user correction / explicit retcon.
2. Current live pointer and its delta.
3. Later LIVE deltas that explicitly correct older facts.
4. `world_save.json` for broad history.
5. GitHub commit history for old exact facts/wording.
6. Chat memory only when marked `CHAT_PENDING_CHECKPOINT`.

`UNKNOWN` must remain unknown. A cancelled scene is never promoted into canon.

## Categories
- `money.json` — cash, separate funds, paid fees, floats, obligations, unsaved accounting tail.
- `places.json` — known locations, exact/unknown names, important venue/site facts.
- `words.json` — important exact wording, letters, public promises/announcements, and remembered anchors that are explicitly **not** lyrics.
- `relationships.json` — Rena, Carrion, Borga, Meira, Gareth, Vern and other durable relationship states.
- `actions.json` — active/resolved tasks, festival/tournament commitments, mail, current concert tail.
- `songs.json` — master song registry and status of every known performance/text.

## Status vocabulary
- `SAVED_CANON` — durable saved canonical fact.
- `CHAT_PENDING_CHECKPOINT` — happened in current chat after saved v124; preserved here by audit but not yet advanced as the RP live pointer.
- `SUPERSEDED` — older fact explicitly corrected/retconned.
- `UNKNOWN` — no reliable exact fact available.

## Song status vocabulary
- `FULL_CANONICAL` — full text physically checked in one canonical UTF-8 file under `song_archive/`.
- `PARTIAL_EXACT` — some exact lines survive, but full text does not.
- `TEXT_LOST` — performance/title survives but the exact full text cannot currently be recovered.
- `TITLE_ONLY` — title/performance known; no durable exact lyric text.
- `INSTRUMENTAL` — no lyric archive required.

## Critical song rule
A summary, remembered theme, title, known original song, web lyrics, or a commit message saying “full” is **not** enough. Missing lines are never reconstructed. Full canonical status is granted only after checking the actual complete stored text.

## Live-pointer boundary
At audit time `live_state.json` still points to v124 (`T+130 ~18:44`, big training yard, personal cash 24g86s53c). The current chat has progressed beyond it; that tail is separately marked `CHAT_PENDING_CHECKPOINT` in category files so it cannot be mistaken for old v124 state.