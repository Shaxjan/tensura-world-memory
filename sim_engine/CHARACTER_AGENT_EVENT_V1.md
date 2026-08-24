# Playable Alpha — Character Decision Event v1

Status: candidate authoritative social-state layer. **Not activated in LIVE v1.0.12.**

## Purpose

The shadow layer proves that a non-deterministic provider can be called once and converted into a stable structured decision. This layer proves that the accepted decision itself can become a deterministic append-only event with before/after hashes and replayable private/public effects.

## Candidate state

The candidate Character Decision state deliberately does not replace historical relationship canon.

For each actor it stores only:

- cumulative relationship **delta since Character Agent activation** on trust/respect/affection/irritation;
- episodic memories committed from grounded memory proposals;
- last private emotion for agent continuity;
- last decision/source turn;
- public observable history.

It does **not** assign an absolute relationship score to Rena and Arlequino. Engagement and pre-existing relationship history stay as canonical facts from the old save/current memory layer.

## Event integrity

`TENSURA_CHARACTER_DECISION_EVENT` contains:

- monotonically increasing candidate sequence;
- unique event key;
- actor and source turn;
- causal context digest;
- sanitized structured decision;
- decision digest;
- public observable projection;
- before-state hash;
- after-state hash;
- explicit candidate authority/effect policy.

Replay rejects:

- sequence gaps/collisions;
- duplicate actor/source-turn commits;
- changed decision content;
- changed public projection;
- wrong before hash;
- wrong after hash;
- unsupported event authority/policy.

## Private effects

A validated event may apply only the bounded private proposals already allowed by Character Agent v1:

- relationship delta per axis remains bounded to -2..2 per event;
- memory proposals become private episodic memories with deterministic IDs;
- private emotion may update the actor's private continuity state.

No cash, inventory, spawning, teleport, global-world mutation or narrator-visible private emotion is available through this event layer.

## Rehearsal

`character_agent_event_rehearsal.py` chains the complete development pipeline:

1. build grounded Rena causal context;
2. call scripted shadow provider once per new turn;
3. validate and record sanitized shadow decision;
4. prove duplicate shadow turns do not recall provider;
5. revalidate the recorded decision;
6. build deterministic Character Decision events;
7. serialize/read events back;
8. apply two sequential candidate events;
9. replay the same event list from empty candidate state;
10. require identical final state and hash;
11. require LIVE runtime pointer/session to remain byte-for-byte unchanged.

The rehearsal currently uses two fixtures: a playful response and an independent refusal over Rena's guitar. These are test fixtures only, not canonical dialogue.

## Remaining gate before v1.0.13 candidate runtime

The next step is to bridge this event semantics into an isolated copy of the existing v1.0.12 repository runtime:

- materialize Rena Character Core/profile prospectively;
- route eligible visible direct interactions to Character Agent decision requests;
- translate accepted Character Decision event effects into the authoritative SQLite/checkpoint model;
- add journal event type and session projection;
- run full checkpoint import -> event -> export -> replay -> hash equality;
- prove activation creates no retroactive Rena response or relationship mutation;
- retain fallback to current v1.0.12 behavior when no valid agent decision is available.

Only after that isolated candidate passes can a real `v1.0.13` activation PR be considered.
