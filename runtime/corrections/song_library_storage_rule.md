# T+160 — Dedicated song library storage rule

User directive: all canonical song texts must be stored/updated under top-level `songs/` so lyric retrieval never requires searching the whole repository.

## Hard rules

- `songs/` is the FIRST lookup location for lyrics.
- Every future song whose exact/full text is supplied or canonized must be created or updated in `songs/` in the SAME persistence cycle.
- One song per file where technically possible. If a text must be split, use a dedicated subdirectory with an explicit ordered index/README.
- Preserve exact user wording. Do not silently normalize spelling, punctuation, capitalization, repetition, meaningful spacing, or elongated endings.
- The latest explicit user correction or retcon overrides older versions.
- Never reconstruct missing lyrics from the web, the source song, summaries, model memory, semantic similarity, or inference.
- Keep old event/correction/`song_archive/` files as historical provenance; do not delete them merely because the text is centralized in `songs/`.
- `songs/_partial/` is for incomplete/lost material and must NEVER be treated as full canonical lyrics.
- When asked to find or reproduce an existing song, check `songs/` before any repository-wide search.

This rule is durable and applies to all future RP song persistence unless the user explicitly changes it.