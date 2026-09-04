# Tensura World Memory — Memory Map v1

This repository contains five logically different layers. Keep them separate.

## A. Current scene — what is physically true in this exact frame

`runtime/current_scene.json` is the single durable current-frame overlay while `status = ACTIVE`.

It stores current time/place, HUD money state, physically present entities and their observable physical state, immediate unresolved player input, and imminent known commitments.

Normal play is delta-only: `next scene = current scene + exact player input + causally justified autonomous-world delta`.

`runtime/continuity/SCENE_CONTINUITY_PROTOCOL_v1.md` defines inheritance and continuity rules.

`runtime/continuity/turn_delta.schema.json` defines stored deltas.

`runtime/continuity/validate_transition.py` is a lightweight machine guard against unexplained day/location/money/NPC-state resets.

If legacy `runtime/session_state.json` is stale relative to an ACTIVE current-scene overlay, it must not overwrite the current frame.

## B. LIVE/runtime history — authoritative transitions and persisted baselines

`runtime/runtime_state.json` is the engine pointer.

`runtime/session_state.json` is a synchronized read-model only when it actually matches the effective active state.

`runtime/checkpoints/` are immutable portable snapshots.

`runtime/journal/` contains append-only authoritative gameplay transitions.

These preserve history and persisted baselines. They do not license resetting a newer current-scene overlay to an older state.

## C. Character memory — who each NPC is becoming

`memory/characters/CHARACTER_SYSTEM_v1.md` defines the character system.

`memory/characters/index.json` is the registry.

`memory/characters/<npc>.json` contains the individual profile of each persistent named NPC.

`memory/characters/students/README.md` handles the 22 Dwargon students individually.

Character profiles accumulate personality, values, habits, goals, boundaries and relationship tendencies from actual story exposure. They never define a character's current physical position or secretly invent current actions.

## D. Creative exposure memory — who has actually heard/read/watched what

`memory/creative_exposure/CREATIVE_EXPOSURE_PROTOCOL_v1.md` defines exposure tracking.

`memory/creative_exposure/index.json` is the quick registry.

`memory/creative_exposure/<work_id>.json` stores chronological exposure events for one creative work.

Use this layer before narrating novelty/recognition reactions to songs, books, scripts, stories, performances or other creative material. A repeat exposure must not be narrated as a first discovery. Unknown first-exposure time stays UNKNOWN instead of being invented.

Audience precision matters: named confirmed listeners/readers are separate from a group whose exact membership is unresolved.

## E. Historical/audit/correction memory — how we got here

`memory/` category files, `live_v*/`, `world_save.json`, old checkpoints and Git history preserve evidence and old states.

Correction types are separated by `runtime/corrections/CORRECTION_TAXONOMY_v1.md`:
- `PLAYER_RETCON` — player intentionally rewrites accepted canon;
- `ASSISTANT_CONTINUITY_ERROR` — invalid assistant output is discarded, not fictionalized;
- `CLARIFICATION` — compatible fact becomes more precise;
- `STATE_RECONCILIATION` — technical layers disagree and the newest valid state is selected;
- normal state updates are not corrections.

Durable compatible clarifications may live under `runtime/clarifications/`.

## Source priority for current facts

1. newest direct player correction that applies to the current fact;
2. `runtime/current_scene.json` while ACTIVE;
3. newer in-chat delta not yet flushed;
4. latest matching runtime/session checkpoint/journal state;
5. explicit correction/clarification files;
6. specialized memory files;
7. older history.

For unresolved values, preserve `UNKNOWN` or an explicit approximation. Never recover a current exact number by grabbing a precise but stale checkpoint value.

## Source priority for character personality

1. newest direct player character correction;
2. latest causally valid observed/authoritative character behavior;
3. existing evidence-grounded character profile;
4. earlier historical characterization.

Frequent meaningful exposure increases character depth. Sparse characters stay sparse rather than receiving invented biography.

## Source priority for creative familiarity

1. newest direct player correction about who has heard/read/watched a work;
2. matching `memory/creative_exposure/<work_id>.json` event;
3. causally valid runtime scene/performance evidence;
4. older historical mentions.

Do not infer full-text recall, meaning, preference or authorship merely from exposure.

## Scene rules

### Player agency
Arlequino's words, thoughts, feelings and deliberate actions are controlled by the user. Never write them on the user's behalf.

### NPC agency
NPCs are autonomous. They can initiate movement, conversation, work, refusal, plans, conflict or other actions when causally justified. Autonomy creates transitions; it does not permit unexplained resets.

### Character growth
After meaningful recurring scenes, persist only genuinely revealed stable traits, preferences, boundaries, goals, memories or changed relationships.

### Creative familiarity
Before reacting to a song/book/play/story, check whether the NPC has encountered it before. Familiar material may still affect them, but novelty is not reset between scenes.

### Group realism
A group is not one voice. Individuals may speak, remain silent, disagree, leave, hesitate, or do something unrelated.

### Sleep
When Arlequino says he sleeps, do not narrate an intermediate `he is sleeping` frame. Resolve directly to wake/interruption under `runtime/rules/SLEEP_SCENE_RESOLUTION_v1.md`; the resulting wake frame becomes the new current scene.

### HUD
Every ordinary gameplay response begins with time, place, on-person money, personal money elsewhere, and family money when known. Current-scene money/active overlay wins over stale historic checkpoint values.
