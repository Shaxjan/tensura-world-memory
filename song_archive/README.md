# Canonical song archive

`song_archive/` top-level text files are canonical only when `memory/songs.json` marks them `FULL_CANONICAL` after a physical fetch/check.

Current verified one-file canonical songs:
- `geroi.txt` — Герои
- `orakul_machete_tensura.txt` — Оракул
- `tmy_knyaz.txt` — Тьмы Князь
- `sozvezdie_angela.txt` — Созвездие Ангела
- `moji_vragi.txt` — Мои враги
- `princessa.txt` — Принцесса

Full exact text that still exists only in historical shards is listed in `memory/songs.json` as `FULL_LEGACY_SHARDS` and must not be confused with a verified one-file archive.

Incomplete exact material lives under `song_fragments/`. Missing lines must never be reconstructed from source songs, web lyrics, summaries or guesses.

Legacy shard directories remain for historical recovery/audit and are not the preferred working format.