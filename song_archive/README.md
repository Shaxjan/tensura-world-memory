# Canonical song archive

`song_archive/` top-level text files are canonical only when `memory/songs.json` marks them `FULL_CANONICAL` after a physical fetch/check.

Current verified one-file canonical songs:
- `geroi.txt` — Герои
- `orakul_machete_tensura.txt` — Оракул
- `tmy_knyaz.txt` — Тьмы Князь
- `sozvezdie_angela.txt` — Созвездие Ангела
- `moji_vragi.txt` — Мои враги
- `princessa.txt` — Принцесса
- `muzyka_dlya_seksa_user_exact.txt` — Музыка для секса
- `konfeta_user_exact.txt` — Конфета

Special canonical override:
- `Полегче` — use `song_archive/palehche_user_exact.txt` only together with `song_archive/palehche_canonical_v2.json`. The v2 manifest supersedes the base text as canonical and restores the user-confirmed 32-line version.

Full exact text that still exists only in historical shards is listed in `memory/songs.json` as `FULL_LEGACY_SHARDS` and must not be confused with a verified one-file archive.

Incomplete exact material lives under `song_fragments/`. Missing lines must never be reconstructed from source songs, web lyrics, summaries or guesses.

Legacy shard directories remain for historical recovery/audit and are not the preferred working format.