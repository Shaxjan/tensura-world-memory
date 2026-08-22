# Full GitHub Memory Audit — 2026-08-22

## Result
Repository memory was audited and normalized by categories without replacing the current delta-pointer SAVE architecture.

Current canonical pointer after audit: **v125**, `T+130 ~19:29`, big training yard in Eurazania capital, personal cash **26g21s67c**.

## Category layer
Created/normalized:
- `memory/AUDIT_INDEX.md`
- `memory/money.json`
- `memory/places.json`
- `memory/words.json`
- `memory/relationships.json`
- `memory/actions.json`
- `memory/songs.json`

## Save architecture finding
The old MASTER protocol described a large one-write `live_state.json`, while the actual repository already used:
1. `live_vNNN/delta.json`
2. compact `live_state.json` pointer

The architecture itself was not changed. `MASTER_SAVE_PROTOCOL.md` was corrected to document the existing delta-pointer architecture and the normal sequential two-write checkpoint.

## Canon/retcon problems caught
- LIVE v101 external-warrior room scene is non-canon; v102 invalidates it.
- Older statements that Arlequino lacked a personal violin are superseded by v121.
- Meira knowledge leakage is corrected by v116.
- Palace-guard impossible expertise is corrected by v107.
- Vern's Dwargon task must never be linked to Oren.
- Exact family-inn name remains UNKNOWN to GM even though Gareth/Vern know it in-world.
- Exact local calendar label for the festival was spoken in-world but is not textually recoverable; do not invent it.

## Money audit
Current saved personal cash: **26g21s67c**.

Since saved v124 baseline `24g86s53c`:
- Герои: +64s12c
- Головы с плеч: +29s74c after retcon/economy review
- От копья: +21s86c
- Заклинатель и осёл: +19s42c
- total: +1g35s14c

Separate money boundaries remain:
- promo: 27s36c last explicit record
- Oren project fund: 4g
- Lissa project fund: 4g
- Gareth: 25s paid
- Vern: 1g20s fee paid + 50s purchase float held; actual remainder UNKNOWN
- Meira: 1g20s total fee, 20s advance paid, 1g remaining obligation

## Song audit
Master registry: `memory/songs.json`.

### FULL_CANONICAL — physically verified one-file text
Count: **6**
- Герои
- Оракул
- Тьмы Князь
- Созвездие Ангела
- Мои враги
- Принцесса

### FULL_LEGACY_SHARDS — full exact text survives, but only in checked historical shards
Count: **3**
- Космос
- Вьюга
- Та, что

Attempts to create new one-file copies for these were physically truncated by the write path. Those incomplete top-level copies were removed and are not canonical.

### PARTIAL_EXACT
Count: **7**
- Наблюдатель
- Головы с плеч
- От копья
- Заклинатель и осёл
- Для мира на земле
- С щитами не рождаются
- Авантюрист

Exact surviving material is under `song_fragments/`. Missing lines are not reconstructed.

### TEXT_LOST / TITLE_ONLY
Count: **22**
Includes Rena's fully original lost song for Arlequino, the self-elegiac departure song, several street/concert titles, Rena's bear/rabbit songs, and other performances whose exact full text was not durably preserved.

### INSTRUMENTAL
- Asturias

## Serious song-storage errors caught
### Наблюдатель
Historical commit names said “full exact lyrics”, but the actual stored file was only a tiny fragment ending at `Я чувств`. The incomplete file was deleted from canonical `song_archive/` and quarantined as `song_fragments/nablyudatel.partial.txt`.

### Та, что
The top-level file was truncated. Full exact text still survives across `song_archive/ta_chto/001.txt..046.txt`; status is `FULL_LEGACY_SHARDS` until a one-file write can be physically verified.

### Космос / Вьюга
Full exact text survives in historical shards, but audit one-file writes did not survive intact. Truncated copies were removed instead of being mislabeled as full.

## Rena original song
Canon preserved:
- Rena wrote it completely herself.
- She worked on it for several weeks.
- She performed it for Arlequino T+129.
- Exact old title and lyrics are lost.
- User memory anchor `Не быть великим , прийти домой. Ждут.` is not lyrics and must never be presented as recovered text.
- v125 preserves the current continuity: do not fake the old text; a new/reworked Rena song may be created in-world later and must then be saved immediately in full if technically possible.

## Persistent song rule
`rules/SONG_ARCHIVE_WRITE_RULE.md` and `MASTER_SAVE_PROTOCOL.md` now require:
- one full file per song when technically possible;
- exact user wording without silent corrections;
- fetch/read-back verification after write;
- never trust a “full” commit label without checking actual content;
- no reconstruction of missing adaptations from original songs/web/guessing;
- truncated files are removed/quarantined, not called canonical.

## Current continuation
v125 ends immediately after resolved `Заклинатель и осёл` at about T+130 19:29. Arlequino currently has Rena's guitar for his part of the concert. Rena and Borga are nearby. The next words/song/action belong only to the user.