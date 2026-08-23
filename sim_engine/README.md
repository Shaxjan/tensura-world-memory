# Tensura Simulation Engine v0.1

A deterministic local simulation core for a long-running AI-assisted D&D world.

## Why this exists

The language model must **not** be the database, calculator, clock, or sole source of world causality.

This prototype moves five fragile systems out of the GM model:

1. **Persistence** — SQLite commits state locally and quickly.
2. **Economy** — integer copper ledger with atomic transactions.
3. **Autonomy** — NPCs continue acting while the player does something else.
4. **Knowledge boundaries** — world truth and NPC knowledge are separate tables.
5. **Reactions** — structured outcomes depend on preferences, relationships, mood, attention and deterministic noise.

The LLM should eventually receive a small read-model from this engine and narrate it. It should not invent state that the engine already owns.

## Files

- `schema.sql` — SQLite data model.
- `sim.py` — simulation core and CLI.
- `seed_blumund.py` — tiny Blumund sandbox for testing.
- `test_sim.py` — six regression tests.

No third-party Python dependencies are required.

## Quick start

```bash
cd sim_engine
python seed_blumund.py --db blumund_demo.db
python sim.py --db blumund_demo.db status
python sim.py --db blumund_demo.db advance 180
python sim.py --db blumund_demo.db events --hidden
python -m unittest -v test_sim.py
```

## Current rules

### Time and movement

Locations are a graph with explicit travel time. An NPC cannot arrive before the route duration has elapsed.

### Player control

Actors with `is_player=1` are never autonomously moved or assigned meaningful actions by the scheduler.

### NPC autonomy

NPCs have home/work locations, energy, mood, personality values and goals. During `advance()` they can:

- travel to work/home;
- work;
- rest/sleep;
- wander;
- socialize with another NPC.

The action is selected from time of day, physical state, personality and seeded randomness. Hidden engine events are persisted even if the player never observes them.

This is deliberately simple in v0.1. The important property is that the NPC acts **without waiting for the player or the LLM**.

### Economy

Money is stored only as integer copper.

- `1g = 100s`
- `1s = 100c`
- `1g = 10,000c`

Payments use an SQLite transaction. Insufficient funds abort the transaction; no partial payment can corrupt balances.

### Knowledge

`facts` is objective world truth.

`knowledge` is what a specific actor has actually learned.

An NPC query should use `known_fact(actor_id, fact_key)`, not read `facts` directly.

### Reactions

`resolve_reaction()` does not write prose. It returns:

- attention: `0..100`;
- score: `-100..100`;
- category: `ignore`, `strong_negative`, `negative`, `neutral`, `positive`, `strong_positive`.

The same performance can therefore be ignored by one person, annoy another and strongly interest a third.

### Determinism

Randomness is derived from:

- persistent world seed;
- persistent tick counter;
- action namespace.

The same saved database therefore preserves the causal sequence. Randomness is not delegated to the LLM.

## What v0.1 does not solve yet

This is foundation, not the finished world. Next layers should add:

- needs and long-term plans;
- jobs with real production/consumption instead of abstract `npc_worked`;
- inventory and item ownership;
- injuries, hunger, sleep and travel supplies;
- rumors and information propagation;
- faction agents and political goals;
- crime/law/reputation;
- weather and regional hazards;
- encounters driven by actual co-location and schedules;
- perception checks and hidden rolls;
- LLM context builder that exposes only relevant facts;
- migration of the existing Arlequino campaign from GitHub snapshots into SQLite.

## Acceptance criteria before expanding the world

Do not scale to hundreds of NPCs yet.

v0.1 is successful only if a small sandbox can run several simulated days and satisfy all of these:

- balances never drift;
- the player is never autopiloted;
- NPCs change location and activity independently;
- NPCs do not gain facts without a source;
- identical stimuli produce varied but explainable reactions;
- replay from a copied database remains deterministic;
- saving takes milliseconds/low seconds locally rather than minutes.
