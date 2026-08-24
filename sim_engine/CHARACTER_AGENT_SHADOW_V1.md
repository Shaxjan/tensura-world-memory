# Playable Alpha — Character Agent Shadow v1

Status: development-only rehearsal layer. **Not activated in LIVE v1.0.12.**

## Purpose

Character Agent v1 already establishes the causal safety contract. The grounded Rena profile restores preserved character depth. This layer proves the missing transport rule between an untrusted/non-deterministic character model and the deterministic authoritative runtime.

The key rule is simple:

> A model may propose a decision once. After validation and recording, replay uses the recorded structured decision and never calls the model again for that turn.

## Flow

```text
causal character context
  -> provider/model called for a NEW turn only
  -> TENSURA_CHARACTER_AGENT_DECISION proposal
  -> Character Agent contract validation
  -> sanitize + digest
  -> write-once SHADOW record
  -> derive public observable

same turn again / replay
  -> load write-once SHADOW record
  -> verify context digest
  -> revalidate structured decision
  -> verify decision digest + observable
  -> return exact journaled decision
  -> provider/model NOT called
```

## Why this matters

A real LLM can produce different text on repeated calls. Calling it again during replay would destroy deterministic history and make state hashes meaningless. The shadow runner converts that non-deterministic first proposal into a stable recorded decision boundary before any authoritative integration is attempted.

## Safety properties

`character_agent_shadow.py` enforces:

- one record per actor + source turn;
- write-once persistence (`O_EXCL`), never silent overwrite;
- exact causal-context digest match on replay;
- full Character Agent contract revalidation on replay;
- stable decision digest;
- stable public observable;
- no raw character context stored in the shadow record;
- no raw provider output stored; only the sanitized validated decision survives;
- provider output has `SHADOW_NON_AUTHORITATIVE` authority;
- no access to runtime DB, cash, inventory, LIVE pointer or runtime journal.

## Rena rehearsal

`character_agent_shadow_rehearsal.py` uses a scripted provider only to exercise the boundary. Its line is a fixture, not canonical Rena dialogue and not evidence that a future production model will choose the same response.

The rehearsal checks:

1. grounded Rena context can be built;
2. first pass calls the provider exactly once;
3. validated decision is recorded;
4. duplicate pass replays the stored decision;
5. a poison provider is not called during replay;
6. decision digest is unchanged;
7. public observable is unchanged;
8. raw context/provider output are not persisted;
9. `runtime/runtime_state.json` and `runtime/session_state.json` remain byte-for-byte unchanged.

## Still missing before LIVE

This is deliberately not enough to activate Character Agents. Remaining gates include:

- authoritative effect adapter from validated decision to world mutations;
- deterministic runtime-journal event format for the accepted agent decision;
- relationship/memory mutation policy and caps inside authoritative state;
- scene eligibility routing (which NPC is asked to decide and when);
- provider interface/timeout/failure policy;
- semantic claim verifier for complex natural-language factual assertions;
- full replay/hash rehearsal through the existing v1.0.12 repository runtime;
- fallback behavior when provider is unavailable or returns an invalid proposal;
- explicit activation migration with no retroactive NPC responses.

Until those gates pass, this layer remains shadow-only.
