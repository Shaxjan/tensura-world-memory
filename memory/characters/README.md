# Character memory workspace

This directory is the durable, human-readable character layer.

## Read order

1. `CHARACTER_SYSTEM_v1.md` — rules and depth model.
2. `index.json` — registry, depth and profile links.
3. `<npc>.json` — individual character record.
4. `students/README.md` — the 22-student roster and individualization rules.
5. `runtime/` records — authoritative gameplay state/events when resolving current-time facts.

## Important distinction

Character profiles preserve personality and continuity. They do not replace runtime state. A profile may say an NPC is capable of initiative; it must not invent that the NPC is currently in a particular place or performing a particular action.

## Updating a character

When an NPC does something meaningful in a scene:

- preserve the original event in runtime/journal or the appropriate durable event record;
- determine whether the behavior is evidence of a stable trait, preference, boundary, relationship tendency, habit or goal;
- add only the smallest grounded character update;
- record the source/event reference;
- increase depth only when repeated evidence justifies it;
- leave everything else `UNKNOWN` or `not_yet_authored`.

## Do not compress people into archetypes

“guard”, “merchant”, “student”, “wife”, “coordinator” and similar role labels describe function, not personality. The character record is the place where repeated behavior becomes individuality.
