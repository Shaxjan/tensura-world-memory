# Character System v1 — Tensura World Memory

## Purpose
Every NPC is an individual character, not a placeholder. Characterization grows with on-screen involvement.

## Character depth model
Each NPC has a `depth_tier`:
- `0 — Background`: only identity/role if established. No invented personality.
- `1 — Encountered`: a few grounded traits from observed behavior.
- `2 — Recurring`: stable preferences, speech habits, motives and relationships can accumulate from events.
- `3 — Developed`: contradictions, vulnerabilities, boundaries, personal goals and history are recorded when established.
- `4 — Major`: detailed character core; independent plans, evolving relationships, memories, habits and long-term goals.
- `5 — Core cast`: fully developed recurring character with a continuously maintained character arc.

## Growth rule
Depth is earned by participation in the story. More appearances, conversations, conflicts, decisions and shared events produce more characterization. Never fill empty fields merely because a character has a familiar canonical name.

A character may move upward in depth only from grounded evidence: player interaction, observed action, reliable testimony, explicit backstory, established Tensura canon, or a user correction.

## Character file
Each named NPC gets an individual file under `characters/`. The file is the durable character container and should link to relevant relationship/event records rather than duplicating them.

Required sections:
- Identity
- Depth tier
- Stable traits
- Motivations / goals
- Preferences / dislikes
- Speech / behavior patterns
- Relationships
- Known memories
- Current commitments
- Knowledge boundary
- Autonomy
- Vulnerabilities / boundaries
- Character arc / changes
- Evidence links
- Unknown / not yet authored

## Hard rules
1. Never write the player's thoughts, intentions or unperformed actions into an NPC file.
2. Never make all NPCs react to the player simultaneously.
3. Never make an NPC joke, move, speak, love, hate, fear or feel something without a causal basis.
4. `UNKNOWN` means unknown; it is not permission to invent.
5. NPC autonomy is independent of player dialogue. Characters may act while the player is silent when their existing goals/schedules justify it.
6. Hidden NPC plans remain hidden until the player has a causal way to learn them.
7. Contradictory old facts are marked `SUPERSEDED`; they are not silently blended into the current character.
8. Canonical character knowledge and this world's personal history are separate layers.
9. Characterization should become richer over time, not wider by random invention.
10. When an NPC appears repeatedly, update the same character file instead of creating scattered competing personality notes.

## Runtime separation
`characters/*.md` is the readable character layer. Runtime scheduler/state remains under `runtime/` and authoritative event history remains under `runtime/journal/`. A character file describes what the NPC is like; it does not replace authoritative state.
