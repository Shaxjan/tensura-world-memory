# SLEEP_SCENE_RESOLUTION_v1

Effective from T+152 after explicit player correction. Integrated with Current Scene continuity.

When Arlequino goes to sleep and the player says he sleeps / continues sleeping, do NOT spend a turn narrating that he is still asleep or gradually waking up.

Resolve sleep as a time-skip directly to the next meaningful outcome:
- he wakes naturally;
- someone/something wakes him;
- a dangerous event interrupts sleep;
- or, if causally justified, a severe outcome occurs.

The next narrated scene begins at the actual wake/interruption/outcome. There is no separate visible `sleeping` scene between the player's `Сплю` and that outcome.

Hidden events during sleep remain hidden until causally learned. Do not narrate off-screen activity as player knowledge merely because the simulation advanced.

Do not invent vague pre-wake awareness unless the actual wake event requires it.

## Current-scene handoff

A resolved wake/interruption creates one new current-frame anchor under `runtime/current_scene.json` / the active in-chat overlay.

Every later ordinary turn must inherit that exact frame through `runtime/continuity/SCENE_CONTINUITY_PROTOCOL_v1.md`.

Therefore, after a wake scene establishes that an NPC is awake/dressed/sitting in a particular place, the next response may not re-roll them as asleep/in bed unless an explicit transition actually occurred.

This rule overrides prior sleep narration patterns.
