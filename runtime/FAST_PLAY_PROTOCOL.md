# Tensura Fast Play Protocol v1.1

## Goal

Normal gameplay must feel like a live conversation. GitHub is durable storage, not a per-message database call. At the same time, one short dialogue turn must never cause the narrator to reconstruct and reset the scene.

This protocol overrides older per-turn GitHub transport requirements for an already-open synchronized game chat.

## 1. Three-layer effective state

During an active game chat the effective state is:

1. **persisted runtime baseline** — checkpoint/journal state safely stored in GitHub;
2. **durable current-frame overlay** — `runtime/current_scene.json` when `status = ACTIVE`;
3. **session-local turn deltas** — ordinary gameplay after that current-frame file which has not yet been flushed.

The effective current scene is the combination in that order. Newer layers override stale older layers only for the facts they actually update.

The active/current overlay must never be silently discarded merely because `runtime/session_state.json` or an older checkpoint still contains a previous time, location, balance or NPC position.

## 2. Current-scene continuity

Normal turns use:

`NEXT_SCENE = CURRENT_SCENE + EXACT_PLAYER_INPUT + CAUSALLY_JUSTIFIED_AUTONOMOUS_WORLD_DELTA`

Unchanged scene fields are inherited, not regenerated.

Follow `runtime/continuity/SCENE_CONTINUITY_PROTOCOL_v1.md`.

In particular:
- a short reply cannot change the T+ day;
- NPC physical state cannot reset without an actual transition;
- location cannot change without movement/timeskip;
- money cannot change without a causal ledger event/reconciliation;
- no voluntary Arlequino action can be added unless present in user input.

## 3. Bootstrap / recovery

On a new game chat, explicit load, recovery, or when active in-chat state is unavailable:

- read `runtime/current_scene.json` first if it exists and is ACTIVE;
- read `runtime/runtime_state.json` and `runtime/session_state.json` for the persisted baseline/history;
- if those are older than the active current-scene overlay, do not overwrite the overlay;
- read important-memory state only if needed for resumed counters;
- establish the effective scene once, then continue normal play from in-chat deltas without rereading GitHub on every message.

## 4. Ordinary turns — NO GitHub I/O

Ordinary dialogue, nearby observation, local micro-movement, routine NPC initiative, small routine economic changes and temporary scene details normally stay in the active session delta.

For these turns:
- do not create `runtime/requests/q-*.json` solely to process the turn;
- do not wait for GitHub Actions;
- do not reread runtime files on every line;
- do not create a journal commit for every line;
- resolve immediately from current scene + new delta.

The narrator must retain the current frame in context. A new prose response is not a new world initialization.

## 5. Unresolved exact player input

If the player spoke/acted but the assistant response is invalidated before a valid world/NPC outcome is accepted, preserve that exact user input as unresolved.

Do not make the player repeat it. Do not execute it twice. Resume by resolving that one input from the last valid current scene.

## 6. Sleep

`Сплю` never produces a visible intermediate `you are sleeping` turn.

Use `runtime/rules/SLEEP_SCENE_RESOLUTION_v1.md`: jump directly to natural wake, causal interruption, danger, or other meaningful sleep outcome. That result becomes the new current scene.

After wake, the next ordinary line inherits the exact wake frame. Do not reroll room/NPC states.

## 7. When GitHub persistence IS required

Flush durable state when at least one occurs:

1. important-memory significance trigger;
2. player explicitly asks to save/checkpoint/reconcile repository;
3. chat intentionally closes/changes session and continuity would otherwise be lost;
4. recovery/ambiguity requires synchronization;
5. a continuity repair/current-scene reconciliation must survive across chats.

Important economic triggers are defined by `runtime/IMPORTANT_MEMORY_PROTOCOL.md`.

### Mandatory durable creative/canonical content

Persist supplied full songs/works, major relationship changes, promises, contracts, debts, ownership changes, unique purchases, titles, permissions, discoveries, permanent decisions, major project/festival decisions, and comparable hard-to-reconstruct facts.

Do not reduce a supplied full work to a summary when exact text is the durable content.

## 8. Bundled persistence

When persistence triggers, do not replay each chat line as a commit. Store a bundled checkpoint/continuity update containing only the durable effects needed to reconstruct the effective state.

For scene continuity, a durable flush may update `runtime/current_scene.json` plus one meaningful turn-delta/repair file instead of producing dozens of journal entries for dialogue.

## 9. Corrections versus retcons

Use `runtime/corrections/CORRECTION_TAXONOMY_v1.md`.

- player intentionally rewrites accepted canon -> `PLAYER_RETCON`;
- assistant contradicted the active scene -> `ASSISTANT_CONTINUITY_ERROR`, discard invalid output;
- compatible detail becomes more precise -> `CLARIFICATION`;
- technical files disagree about current state -> `STATE_RECONCILIATION`.

Do not turn narrator mistakes into fictional events or NPC memories.

## 10. Failure behavior

If a required GitHub persistence attempt fails:
- never claim it was saved;
- report failure briefly;
- keep safe in-chat current state;
- retry only at a real checkpoint/reconciliation opportunity.

## 11. Intentional tradeoff

Fast play trades per-line durability for responsiveness, but not for continuity. Ordinary turns may be unflushed, yet the currently active chat must still preserve exact scene inheritance.

## 12. Priority

For active synchronized play, this protocol and `SCENE_CONTINUITY_PROTOCOL_v1` have priority over older instructions that treat stale session/checkpoint files as the current frame or require GitHub round-trips for every ordinary message.
