# CHARACTER SYSTEM v1 — persistent NPC characterization

Status: canonical memory architecture; applies to future gameplay and character authoring.

## Goal

Every persistent named NPC has an individual character record. NPC depth grows from actual story exposure instead of being filled with invented biography.

## Character record

Each character record is organized into:
- identity and role;
- stable personality traits with evidence;
- values, preferences and boundaries;
- goals and obligations;
- relationships, kept separate from obedience or ownership;
- memories, each tied to a causal event/source;
- knowledge boundary: what the NPC knows, when they learned it and by what channel;
- habits and initiative patterns, only after observed enough times;
- speech/interaction tendencies, only when established by repeated scenes;
- unknown / not-yet-authored fields;
- depth level and exposure history.

## Depth model

`D0 — placeholder`: identity only; no authored psychology.

`D1 — functional`: role, known duties, a few source-grounded traits.

`D2 — recurring`: repeated behavior/choices establish stable preferences or boundaries.

`D3 — developed`: multiple interactions establish contradictions, habits, relationship tendencies and independent goals.

`D4 — major`: character has substantial screen time; personality can support nuanced responses, initiative and conflict without inventing biography.

`D5 — core`: long-running major character. Characterization is maintained across scenes through accumulated memories, relationships, values, habits, goals and observed change over time.

Depth can increase only from actual evidence: player scenes, NPC actions, explicit user corrections, authoritative saved facts, or repeated consistent behavior. Never increase depth merely because a character is important in the source material.

## Anti-flattening rules

1. No NPC is a generic assistant, servant, therapist, narrator or comedy device by default.
2. No two NPCs share a personality merely because they fill similar roles.
3. An NPC can disagree, refuse, initiate, leave, make mistakes, misunderstand, or pursue another goal when source-grounded or causally justified.
4. Existing relationship status never implies obedience, consent, constant affection, jealousy, or availability.
5. Current emotion is a scene-level inference, not a permanent trait.
6. Unknown preferences remain unknown until causally established.
7. Private thoughts are not player knowledge unless explicitly revealed in-world.
8. Player actions control Arlequino only. NPCs retain their own agency.

## Knowledge rule

Use:
`SOURCE -> TRANSMISSION EVENT -> TIME -> RECIPIENT`.

An NPC does not automatically know what the player knows, what another NPC knows, or what the GM knows.

## Story-growth rule

After each significant recurring NPC scene, ask:
- Did this reveal a stable trait?
- Did this reveal a preference/boundary?
- Did the NPC make an independent choice?
- Did the NPC relationship change in an observable way?
- Did this add a durable memory?
- Did a prior trait gain stronger evidence?

Only then update the character record.

## File layout

`memory/characters/index.json` — registry and depth map.

`memory/characters/<npc>.json` — one canonical profile per persistent named NPC.

`memory/characters/students/README.md` — roster for the 22 Dwargon students until names are causally re-established.

`runtime/` remains authoritative for runtime state. Character files are source-grounded character memory and must not silently override runtime facts.

## Conflict resolution

Priority for character facts:
1. latest direct user correction / explicit retcon;
2. latest authoritative runtime event;
3. later explicit character correction;
4. earlier saved character profile;
5. broad historical memory.

When evidence conflicts, mark the older fact `SUPERSEDED`; do not silently merge contradictory traits.
