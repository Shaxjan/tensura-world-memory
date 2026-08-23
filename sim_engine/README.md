# Tensura Simulation Engine

A deterministic local simulation core for a long-running AI-assisted D&D world.

The language model must **not** be the database, calculator, clock, economy, or sole source of world causality. SQLite and simulation rules own state transitions; the future LLM layer should receive a small relevance-filtered read model and narrate the result.

## Current versions

### v0.2 — current autonomous-world lab
See `V02.md`.

Core files:
- `v02_schema.sql` — SQLite model for needs, goals, plans, inventory/resources, knowledge, rumors, economy and events;
- `v02_base.py` — storage, geometry, actors, exact economy, inventory/resources and continuous needs;
- `v02_social.py` — relationships, knowledge, rumor propagation and contextual reactions;
- `v02_planning.py` — persistent goals, initiative and rule plans;
- `v02_autonomy.py` — autonomous scheduler/runtime;
- `v02_engine.py` — composed engine;
- `v02_seed.py` — isolated Blumund sandbox;
- `test_v02.py` — regression suite;
- `v02_probe.py` — multi-day no-player autonomy probe;
- `v02_benchmark.py` — SQLite checkpoint benchmark.

Quick validation:

```bash
cd sim_engine
python -m unittest -v test_v02.py
python v02_probe.py --days 7
python v02_benchmark.py
```

Current local validation after the continuous-needs fix: **14/14 tests pass**. The seven-day deterministic probe leaves the player untouched while NPCs create goals, eat/sleep, travel, socialize, spread rumors, investigate, trade, publish, craft and react to resource shortages.

### v0.1 — preserved foundation
The original files remain for comparison:
- `schema.sql`
- `sim.py`
- `seed_blumund.py`
- `test_sim.py`

## Architectural rule

The live Arlequino campaign has **not** been migrated into the engine. `sim_engine` is an isolated lab until the next gate is passed. GitHub remains source/history for development, but a future game runtime should persist ordinary state in SQLite rather than performing remote GitHub saves for each action.

## Gate before live-campaign migration

The next engine layer must prove:
1. factions/institutions act autonomously;
2. events propagate between locations with realistic delay;
3. routine simulation can use level-of-detail compression instead of ticking every NPC continuously;
4. local prices respond to supply/demand without arithmetic drift;
5. the LLM receives only relevant world context rather than the whole database.
