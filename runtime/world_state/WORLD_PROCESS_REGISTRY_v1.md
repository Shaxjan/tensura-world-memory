# World Process Registry v1

Status: ACTIVE RUNTIME STATE PROTOCOL.

## Purpose

This layer stores the parts of the world that continue to move when Arlequino is not looking at them.

Rules alone are not enough. A living world also needs explicit durable state for:
- active NPC assignments;
- projects already in motion;
- canon/world events that have become due;
- institutions and material processes with their own clocks;
- deadlines and waiting conditions;
- information that is moving between regions or groups;
- unresolved outcomes that must not be invented.

Primary files:
- `runtime/world_state/active_processes.json`
- `runtime/world_state/information_frontier.json`

These are operational state, not narration and not a replacement for `runtime/current_scene.json`.

## Authority boundary

`runtime/current_scene.json` remains authoritative for the current physical frame.

`runtime/world_state/active_processes.json` is authoritative for registered off-screen or cross-scene processes after its latest valid update, unless superseded by a newer direct player correction, runtime event, correction, retcon, or completed process event.

`runtime/world_state/information_frontier.json` tracks what information exists, where it has plausibly reached, and what remains unexposed to Arlequino.

A world-state file must never reveal hidden GM information to the player merely because the model can read it.

## Process statuses

Use only explicit statuses such as:
- `ASSIGNED`
- `READY_TO_START`
- `IN_PROGRESS`
- `WAITING_ON_DEPENDENCY`
- `BLOCKED`
- `DUE`
- `COMPLETED`
- `FAILED`
- `CANCELLED`
- `SUPERSEDED`
- `OUTCOME_UNRESOLVED`

Do not silently convert `ASSIGNED` into `COMPLETED` just because time passed.

## Process fields

A durable process should record, where applicable:
- `process_id`
- `category`
- `status`
- `started_at` or assignment time
- responsible actor(s)
- location or region
- objective
- current known state
- constraints
- dependencies
- deadline or next review condition
- what can advance it
- what cannot be assumed
- source/evidence
- player visibility
- persistence target when it resolves

## Advancement rule

Before a substantial scene transition, compare elapsed world time against active processes.

For each relevant process:
1. check whether enough time and opportunity existed;
2. check actor location, character, knowledge, resources and competing obligations;
3. check dependencies and institutional/material constraints;
4. resolve only the amount of progress causally justified;
5. persist material progress or completion;
6. move newly created information into `information_frontier.json`;
7. expose only information that has causally reached Arlequino.

Progress can be partial. A realistic state such as `contacted two possible organizers; no agreement yet` is preferable to instant success.

## Deadlines

A deadline is not an automatic outcome.

When a deadline arrives:
- the process must be checked;
- success, failure, delay, cancellation or transformation must follow from actual state;
- missed deadlines have consequences;
- canonical deadlines cannot be paused for the player's convenience.

If a date is uncertain, store a trigger condition instead of inventing an exact hour.

## NPC autonomy

Assignments do not make an NPC a servant process.

An NPC may:
- choose their own method;
- prioritize another obligation;
- refuse a later expansion of scope;
- make mistakes;
- return partial information;
- ask someone else for help;
- discover something unexpected;
- abandon a path that proves impractical.

Off-screen progress must be compatible with `memory/characters/<npc>.json` and the NPC's causal knowledge.

## Information frontier

Information is tracked separately from objective world state.

An event may be objectively true while:
- Arlequino does not know it;
- Rena does not know it;
- Dwargon has only a distorted rumor;
- officials know more than the public;
- a courier is still in transit.

Use the chain:

`EVENT/CLAIM -> SOURCE -> CHANNEL -> DEPARTURE/ORIGIN -> DELAY -> REGION/GROUP -> INDIVIDUAL EXPOSURE`

Never jump directly from world fact to NPC dialogue.

## Hidden-state discipline

Fields may contain `GM_ONLY` or `NOT_YET_PLAYER_KNOWN` state when needed for causal simulation.

Narration must not surface such content until a valid exposure event exists.

If even the world-side result is not yet established, use `UNKNOWN` or `OUTCOME_UNRESOLVED`; do not create hidden canon simply because it would be convenient later.

## Completion and history

When an active process resolves materially:
- write a significant event/journal entry when future continuity needs it;
- update affected character memory if a durable trait/memory/relationship changed;
- update creative exposure if applicable;
- update information frontier for facts/claims that can spread;
- remove or archive the active process only after the durable result exists elsewhere.

## Anti-freeze requirement

A process present in `active_processes.json` must not remain unchanged across meaningful elapsed time without a reason.

Valid reasons include:
- not enough time elapsed;
- actor remained physically occupied;
- dependency not met;
- travel/transmission delay;
- lack of resources or authority;
- deliberate postponement by the responsible actor;
- the process is waiting on player-controlled input.

If none applies, progress should be considered.

## Anti-fabrication requirement

The registry is not a story generator by itself.

Do not fill it with speculative background outcomes. Register only:
- explicit assignments;
- already-established projects;
- due canon/world processes;
- material systems directly relevant to continuity;
- information items whose source event exists.

Exact unresolved results remain unresolved until causally determined.