# Tensura World Memory — Memory Map v1

New-chat entrypoint: **`START_HERE_TENSURA.md`**.

This repository contains seven logically different layers. Keep them separate.

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

## F. Reconciled recovery navigation — recovered old history

The `recovery/` layer exists for historical material that was omitted from active memory, compressed in older saves, scattered across `live_v*`, or affected by later corrections/retcons.

Primary navigation:
- `recovery/RECOVERY_INDEX.md` — event-by-event recovery index;
- `PUBLIC_CULTURAL_CANON_REGISTRY.md` — consolidated high-level public cultural canon;
- `UNRESOLVED_RECOVERY.md` — known gaps that must remain UNKNOWN unless evidence is recovered;
- `TIMELINE_INDEX.md` — chronological navigation;
- `START_HERE_TENSURA.md` — single entrypoint for a new chat.

Dedicated recovery files under `recovery/` preserve detailed reconciled evidence for specific events.

Older broad files such as:
- `recovery/public_cultural_footprint_audit_in_progress.md`
- `recovery/public_cultural_footprint_patch_2026-09-06.md`

remain useful as provenance/evidence. Once a dedicated recovery file and the consolidated registry have reconciled a contradiction or retcon, the older `in_progress` hypothesis is not the preferred answer source.

Recovery authority is **historical**, not current-state authority. A recovered T+129/T+138 fact must never overwrite a newer active T+162 physical scene.

Important recovery distinctions:
- capacity is not attendance;
- promotional crowd claims are not observed attendance;
- a stored creative artifact is not by itself proof that a retconned performance completed;
- `live_v###` version numbers are not in-world T+ day numbers;
- similarly named events are not automatically the same event.

## G. Active world state — what keeps moving off-screen

`runtime/world_state/WORLD_PROCESS_REGISTRY_v1.md` defines the active-process protocol.

`runtime/world_state/active_processes.json` stores current cross-scene/off-screen processes such as:
- NPC assignments;
- investigations;
- projects;
- world/canon aftermaths;
- dependencies, delays and deadlines;
- unresolved outcomes that must survive scene changes.

`runtime/world_state/information_frontier.json` stores the current information boundary:
- objective world fact or claim;
- source;
- transmission channel;
- propagation state by region/group;
- individual recipient exposure/knowledge;
- uncertainty/distortion.

This layer exists to prevent the world from freezing between scenes.

It is not permission to reveal hidden GM state. A fact can exist world-side while remaining unknown to Arlequino.

It is also not permission to fabricate background outcomes. If the result is unresolved, keep it unresolved and advance it only when time, character, resources and circumstances justify progress.

## Source priority for current facts

1. newest direct player correction that applies to the current fact;
2. `runtime/current_scene.json` while ACTIVE for current physical scene facts;
3. newer in-chat delta not yet flushed;
4. latest matching runtime/session checkpoint/journal state;
5. explicit correction/clarification files;
6. specialized active state (`runtime/world_state/`, character memory, creative exposure) for its own domain;
7. older history.

For unresolved values, preserve `UNKNOWN` or an explicit approximation. Never recover a current exact number by grabbing a precise but stale checkpoint value.

`active_processes.json` does not override a newer current physical frame; it preserves work and consequences that continue across frames.

## Source priority for recovered historical facts

1. newest direct player correction about the historical fact;
2. later explicit retcon/correction/clarification that applies to it;
3. dedicated reconciled recovery file linked from `recovery/RECOVERY_INDEX.md`;
4. direct runtime/checkpoint/event evidence consistent with later corrections;
5. raw archive/save/Git history;
6. older audit hypotheses.

A recovery summary is only as authoritative as the evidence it reconciles. If new direct evidence appears, update the dedicated recovery file and indexes rather than silently preserving an obsolete conclusion.

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

## Source priority for world processes and information

For an active task/process:
1. newest direct player instruction/correction;
2. newest authoritative runtime/significant-event change;
3. `runtime/world_state/active_processes.json`;
4. responsible character's established memory/goals;
5. older plan/history.

For whether someone knows a world fact/rumor:
1. direct player correction about that knowledge;
2. explicit exposure/transmission event;
3. `runtime/world_state/information_frontier.json`;
4. causally valid scene evidence;
5. older broad assumptions.

Repository knowledge is not NPC knowledge.

## Scene rules

### Player agency
Arlequino's words, thoughts, feelings and deliberate actions are controlled by the user. Never write them on the user's behalf.

### NPC agency
NPCs are autonomous. They can initiate movement, conversation, work, refusal, plans, conflict or other actions when causally justified. Autonomy creates transitions; it does not permit unexplained resets.

### Active-process continuity
Before a substantial time jump or scene transition, consult `runtime/world_state/active_processes.json`. A registered assignment/project must not silently freeze or disappear.

### Information continuity
Before asserting that an NPC knows a major external fact, consult `runtime/world_state/information_frontier.json` and the news/rumor propagation rule.

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

## New-chat bootstrap

A new chat should not browse the repository at random. It should:
1. read `START_HERE_TENSURA.md`;
2. fetch `runtime/current_scene.json`;
3. read this `MEMORY_MAP_v1.md`;
4. read `runtime/rules/LIVING_WORLD_SIMULATION_v1.md`;
5. fetch `runtime/world_state/active_processes.json`;
6. fetch `runtime/world_state/information_frontier.json`;
7. use `runtime/rules/CANON_TIMELINE_SYNC_v1.md` and `runtime/rules/NEWS_RUMOR_PROPAGATION_v1.md` during normal play;
8. use `recovery/RECOVERY_INDEX.md` for old-history questions;
9. use the appropriate specialized memory/runtime layer for the task.

This bootstrap path is intentionally stable even as gameplay advances.