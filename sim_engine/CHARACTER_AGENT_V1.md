# Playable Alpha — Character Agent v1 Safety Contract

Status: development layer only. **Not activated in LIVE v1.0.12.**

## Problem

The current authoritative NPC response layer is intentionally narrow: the first calibration is Borga + simple direct greeting. That proved causality and replay safety, but it is not enough for believable long-form social play.

Playable Alpha needs key characters to produce richer decisions from their own identity, memory, knowledge, relationship state, goals and current situation without granting an AI model omniscience or direct write access to the world.

## Architecture

```text
AUTHORITATIVE RUNTIME
  -> causal character context builder
  -> untrusted Character Agent
  -> structured decision proposal
  -> Character Agent contract validator
  -> authoritative effect resolver / journal commit (future integration)
  -> public observable projection
```

The AI agent is **never authoritative**.

## What the agent may receive

A Character Agent context contains only:

- the character's own private Character Core;
- the character's own current plan;
- that character's relationship state;
- causal facts already known to that character;
- direct current observations;
- the player's current observed utterance/action;
- currently grounded visible targets;
- explicit unresolved/UNKNOWN keys.

It must not receive:

- global omniscient world state;
- another NPC's private Character Core;
- narrator-only information;
- facts not causally available to the character.

## Decision boundary

The agent returns `TENSURA_CHARACTER_AGENT_DECISION`.

The proposal separates:

### Observable

What can become visible if the engine accepts it:

- speech act;
- surface text;
- bounded physical action;
- visible target;
- bounded time cost.

### Private

What remains hidden character state unless later causally exposed:

- private emotion state;
- small relationship-change proposal;
- episodic memory proposals;
- private rationale.

The narrator receives only the observable projection.

## Grounding

Every external factual claim and every proposed memory must cite one or more fact references that are already present in the character's causal knowledge or current observations.

An unresolved key is not a known fact. `UNKNOWN` cannot be used as evidence.

This is structural grounding, not a complete semantic truth checker. A future integration layer may add a second semantic verifier before committing complex natural-language claims.

## Fail-closed rules

The validator rejects a proposal when it:

- cites a fact unavailable to the character;
- targets an entity not currently visible/grounded;
- asks for an unsupported action or speech-act class;
- attempts a direct cash/inventory/global-world mutation;
- attempts an unbounded relationship jump;
- attempts an unbounded time skip;
- writes a memory without causal source references;
- mismatches actor or source turn.

## Replay rule

An AI model is called only for a **new unresolved character decision**.

Once a decision is validated and later committed by the authoritative runtime, the exact structured decision must be journaled. Deterministic replay consumes the journaled decision and **must never call the model again** for that committed turn.

This preserves the existing append-only/replay/hash model even though the first generation of the proposal may be non-deterministic.

## Relationship dynamics

Character Agent v1 permits only a small proposal on four axes:

- trust;
- respect;
- affection;
- irritation.

Each single interaction is bounded to `-2..2`. This is a proposal, not an automatic authoritative mutation. The future effect resolver decides whether and how it is committed.

## Initial social vocabulary

The contract supports richer social behavior than the old greeting-only resolver:

- greet / farewell;
- answer / ask;
- tease / joke;
- reassure;
- refuse;
- accept a simple request;
- role-related report;
- comment;
- ignore / wait / leave;
- bounded gesture or approach to a visible target.

This vocabulary is intentionally finite at the authority boundary while surface dialogue remains natural language.

## Rena

Repository canon already contains substantial Rena continuity (engagement, long-term relationship, music history and causal knowledge boundaries). Character Agent v1 does **not** invent a personality profile from that relationship summary.

The next playable-alpha step is to build a grounded Rena Character Core/profile from preserved canonical evidence and historical interactions, then run her through this contract in shadow scenes before any LIVE activation.

## Not in this change

- no LIVE activation;
- no runtime journal migration;
- no external AI provider call;
- no server/VPS dependency;
- no retroactive responses;
- no new claims about Rena/Borga personality;
- no changes to current v1.0.12 authoritative state.
