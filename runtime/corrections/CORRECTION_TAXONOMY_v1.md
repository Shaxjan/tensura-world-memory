# Correction Taxonomy v1

Status: ACTIVE repository rule.

The repository must distinguish changes to canon from repairs of narrator mistakes. Not every contradiction is a retcon.

## 1. PLAYER_RETCON

Use only when the player intentionally changes something that was previously accepted as canon.

Examples:
- player states that an earlier established custody/location fact is now canonically different;
- player explicitly rewrites a past event, relationship fact, identity, outcome or chronology.

Storage: `runtime/retcons/`.

Effect: the newer player-established canon supersedes the older accepted canon. Preserve enough audit information to know what was replaced.

## 2. ASSISTANT_CONTINUITY_ERROR

Use when the assistant contradicts the current accepted scene or invents an impossible reset without the player changing canon.

Examples:
- NPC was awake, dressed and sitting nearby; next response suddenly places them asleep in bed with no transition;
- one spoken word causes a day jump;
- a manuscript appears in the room despite already established custody elsewhere;
- known money is overwritten by a stale checkpoint.

Storage: `runtime/corrections/` and, when it affects the active frame, the repair is reflected in `runtime/current_scene.json`.

Effect: the invalid assistant output is discarded. It is NOT an in-world event. It does NOT need a fictional explanation. It does NOT become part of NPC memory.

## 3. CLARIFICATION

Use when new information makes an existing fact more precise without contradicting it.

Examples:
- exact instrument is identified after previously only knowing the NPC is a musician;
- a known approximate location becomes more specific through causal observation;
- an approximate amount becomes exact after real reconciliation.

Storage: `runtime/clarifications/` for durable clarifications, or the relevant current/character file when ordinary.

Effect: enriches existing canon; does not invalidate the prior compatible fact.

## 4. STATE_RECONCILIATION

Use when multiple technical layers disagree about the same current value and the newest valid evidence is selected without changing the fictional past.

Examples:
- old session checkpoint says 26g but active overlay says the family purse is about 358g;
- legacy `session_state.json` is at T+138 while active fast-play continuity is already T+162.

Storage: `runtime/corrections/` or continuity delta.

Effect: establishes which layer is current. Old files remain audit/history and are marked stale/superseded for the current question.

## 5. NORMAL_STATE_UPDATE

A normal in-world transition is not a correction at all.

Examples:
- Rena stands up and walks to the door;
- money changes because somebody pays;
- time advances because the group travels for two hours.

Storage: runtime/active scene delta/checkpoint as appropriate.

## Priority rule

When deciding what happened:

1. direct player's newest explicit correction/retcon;
2. last valid current scene + causal deltas;
3. latest valid persisted runtime state;
4. older history/audit.

An assistant continuity error never wins merely because it was the latest piece of prose.

## Language rule

Do not tell the player that an assistant mistake was a `retcon` unless the player actually chose to rewrite canon. Call it what it is: a continuity error/correction.
