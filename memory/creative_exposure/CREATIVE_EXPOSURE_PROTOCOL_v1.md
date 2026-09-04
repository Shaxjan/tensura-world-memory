# Creative Exposure Protocol v1

Status: ACTIVE durable knowledge architecture.

## Goal

Track who has actually heard, read, watched, rehearsed, received, or otherwise experienced each creative work, and when/how that knowledge was acquired.

This exists to prevent NPCs from reacting to a repeated song/book/play as if it were new, and to prevent NPCs from knowing creative material they never encountered.

## Core rule

For every durable creative work, record exposure as:

`WORK -> EXPOSURE EVENT -> TIME -> MODE -> RECIPIENT(S)`

Examples of `MODE`:
- `heard_live_performance`
- `heard_rehearsal`
- `read_manuscript`
- `read_excerpt`
- `received_copy`
- `watched_stage_performance`
- `heard_retelling`

## First exposure vs repeat exposure

A recipient can have multiple exposure events to the same work.

The first confirmed exposure establishes that the work is no longer new to that recipient. Later exposures are marked repeat exposures and must not be narrated as first discovery unless the specific new version materially differs.

If exact first-exposure time is unknown but prior exposure is explicitly confirmed, store the time as `UNKNOWN_BEFORE_<known anchor>` rather than inventing a date.

## Audience precision

Do not upgrade a vague group into exact named recipients.

Use three separate audience fields when needed:
- `named_confirmed`: named recipients definitely present/exposed;
- `group_confirmed`: a causally established group whose exact membership is not fully recovered;
- `unknown_or_unresolved`: possible recipients not safe to assert.

A statement such as 'students present in the hall heard it' does not mean all 22 students heard it unless all 22 were confirmed present.

## Knowledge consequences

Exposure means the recipient knows at least that version of the work to the degree causally available. It does not imply:
- they remember every line;
- they understood the intended meaning;
- they liked it;
- they know authorship/source unless told or obvious;
- they know later revisions.

## Reaction rule

Before narrating a reaction to a creative work, check exposure history.

- `FIRST_CONFIRMED_EXPOSURE`: novelty reactions are possible.
- `REPEAT_EXPOSURE`: NPC may recognize, anticipate, compare, ignore familiar parts, react to context, or simply listen; do not default to first-time amazement.
- `UNKNOWN`: do not assert recognition or novelty without evidence.

## Storage

- `memory/creative_exposure/index.json` — registry and quick lookup.
- `memory/creative_exposure/<work_id>.json` — chronological exposure history for one work.
- canonical creative text remains in its own archive (`song_archive/`, books, scripts, etc.); exposure files never duplicate full copyrighted/user text unnecessarily.

## Interaction with character memory

Exposure records are knowledge evidence. Character profiles may reference them, but should not copy every exposure event into personality files.

Use the same knowledge discipline as the character system:
`SOURCE -> TRANSMISSION EVENT -> TIME -> RECIPIENT`.

## Corrections

If the player says an NPC had already heard/read a work, that directly corrects novelty state. If the exact older scene is not recoverable, preserve the fact with an unknown prior timestamp instead of fabricating one.
