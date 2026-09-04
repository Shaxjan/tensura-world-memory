# Tensura World Memory — Memory Map v1

This repository contains three logically different layers. Keep them separate.

## A. LIVE runtime — what is true now

`runtime/runtime_state.json` is the current runtime pointer.

`runtime/session_state.json` is the synchronized read-model when its sequence/hash matches the pointer.

`runtime/checkpoints/` are immutable portable snapshots.

`runtime/journal/` contains append-only authoritative gameplay transitions.

Use this layer for current time, current place, money, inventory, pending effects and gameplay continuity.

## B. Character memory — who the NPC is becoming

`memory/characters/CHARACTER_SYSTEM_v1.md` defines the character system.

`memory/characters/index.json` is the registry.

`memory/characters/<npc>.json` contains the individual profile of each persistent named NPC.

`memory/characters/students/README.md` handles the 22 Dwargon students individually until their names are re-established.

Character profiles may accumulate personality, values, habits, goals and relationship tendencies from repeated scenes. They never invent current location or hidden actions.

## C. Historical/audit memory — how we got here

`memory/` category files, `live_v*/`, `world_save.json`, retcons and Git history preserve evidence, old states and corrections.

Historical files do not automatically override newer runtime state.

## Source priority

For a current factual answer:

1. latest direct user correction / explicit retcon;
2. current runtime pointer + matching session state;
3. latest applicable runtime journal/checkpoint state;
4. later explicit correction files;
5. specialized memory files;
6. older history.

For character personality:

1. latest direct user correction / explicit character retcon;
2. latest authoritative character decision/observed behavior;
3. existing character profile with evidence references;
4. earlier historical characterization.

For unresolved values, preserve `UNKNOWN` rather than filling the gap from an older snapshot or guess.

## Scene rules

### Player agency

Arlequino's words, thoughts, feelings and deliberate actions are controlled by the user. Never write them on the user's behalf.

### NPC agency

NPCs are autonomous. They may initiate movement, conversation and actions when their current duties, relationships, needs and established patterns justify it. Their agency must remain causally bounded by the world state.

### Character growth

Frequent exposure increases characterization depth. A character appearing in many meaningful scenes receives more detailed memory; a character with little exposure stays shallow. Depth is earned by evidence.

### Group realism

A group is not one voice. Individuals may speak, remain silent, disagree, leave, hesitate, or do something unrelated. Never synchronize reactions merely to make a scene entertaining.

### Sleep

When Arlequino sleeps, hidden events are not narrated. Sleep resolves to the next meaningful wake/interruption outcome. No object or NPC state is invented inside the room without a causal bridge.

### HUD

Every ordinary gameplay response begins with the required runtime HUD fields. Never replace known values with `UNKNOWN` merely because the newest accessible file is older. Resolve the effective state first.
