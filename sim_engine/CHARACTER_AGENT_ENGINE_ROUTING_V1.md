# Playable Alpha — Engine-Owned Character Agent Routing v1

Status: candidate development layer. **No LIVE activation.**

## Goal

A language model must never decide what Rena can see, where she is, or what she knows. The engine owns those prerequisites and either builds a causal context or refuses to route the interaction.

## Eligibility

Rena is eligible for an agent decision only when all of the following are true:

1. the v1.0.13 candidate Character Agent state has been prospectively activated;
2. the player explicitly addresses Rena by her name/inflected form;
3. the engine has a current same-place direct player observation of Rena;
4. a separate causal reciprocal-awareness fact proves that Rena observed this exact player turn;
5. the awareness fact matches the exact source turn, player text, world minute and place.

Player visibility alone is deliberately insufficient. This preserves the v1.0.7 causal rule that one-way observation does not silently become NPC awareness.

## Knowledge boundary

`collect_actor_causal_facts()` reads only an actor's own existing:

```text
actor_knowledge(actor_id=<actor>) JOIN facts
```

v1 exposes only confidence `100` facts to the language agent. Lower-confidence beliefs stay in authoritative engine state until an uncertainty-aware semantic claim verifier exists.

### Rena identity migration boundary

The current authoritative SQLite `actors` table contains only the player. Rena exists in the newer runtime as a region-level `actor_position_claim`, autonomous commitment owner and now a prospective Character Core, but **not yet as an `actors` row**.

`actor_knowledge.actor_id` has a foreign key to `actors(id)`. Therefore this candidate does **not** invent a Rena actor row with `cash_copper=0` merely to satisfy that foreign key: doing so would create a false economic fact about Rena and could later leak into simulation logic.

Until a proper actor-identity/economy migration exists, Rena's language-agent context gets:

- her source-grounded Character Core as private self-state;
- causal current reciprocal observations;
- any future knowledge storage that is explicitly attached to her Character Core/private continuity;
- zero facts from another actor's `actor_knowledge`.

If/when Rena is honestly materialized into `actors`, `collect_actor_causal_facts()` can consume her confidence-100 `actor_knowledge` rows without changing the routing contract.

## Current activity

Rena does not yet have a full current scheduler in v1.0.13. Routing therefore records her current activity as unresolved rather than inventing a plan. Exact place is taken only from the grounded current scene prerequisite.

## Candidate fixture

`install_candidate_reciprocal_fixture()` exists only for isolated tests/rehearsals. Fixture awareness carries `CANDIDATE_REHEARSAL_FIXTURE` authority and is rejected by the production-default route unless `allow_candidate_fixture=True` is explicitly supplied by test code.

It must never be called by production player-turn routing.

## Fail-closed outcomes

The router returns an ineligible result when any prerequisite is missing, including:

- Character Agent not activated;
- Rena not explicitly addressed;
- current place unresolved;
- Rena not directly visible;
- no causal reciprocal awareness for the exact turn.

No missing prerequisite is inferred or fabricated.

## Next integration gate

The next candidate step is to create reciprocal awareness from an accepted, explicitly Rena-addressed real scene action inside the authoritative player-turn pipeline, then pass the engine-built context to the shadow/provider boundary. That step must preserve deterministic journal replay and must not retroactively resolve old Rena interactions.
