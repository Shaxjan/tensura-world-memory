# Tensura Chat Important Memory Protocol v1.1

## Purpose

`runtime/important_memory/` is a compact durable index of gameplay facts that are important enough to survive hundreds of turns and be easy for a new game chat to recover.

It is **not** a transcript and must never be used to persist ordinary gameplay line by line.

## FAST PLAY rule — highest priority

Normal gameplay must stay fast.

During an already-open synchronized game chat:

- ordinary dialogue, movement, observation, small purchases, routine combat beats and other normal turns MUST NOT cause a GitHub read solely for important-memory evaluation;
- ordinary turns MUST NOT create an important-memory file;
- the chat keeps the current working gameplay context in the conversation/session context;
- important-memory thresholds are evaluated from facts already available in the current turn/session context;
- `runtime/important_memory/state.json` is read at game-session/bootstrap time, recovery time, or immediately before a triggered important-memory write if dedupe/counter confirmation is actually needed — not after every turn;
- GitHub persistence for important memory happens only when a significance rule below actually triggers, when the user explicitly asks to save, or during an intentional session checkpoint;
- lack of an important-memory GitHub round-trip must never delay an otherwise answerable ordinary gameplay response.

If a required cumulative counter cannot be determined safely from the in-chat working state, do not scan GitHub during the player's ordinary turn. Carry the unresolved counter check to the next real persistence/checkpoint opportunity. Never fabricate a threshold crossing.

## Economic significance rules

Currency normalization follows the world economy model:

- `100c = 1s`
- `100s = 1g`
- therefore `1g = 10,000c`

### A. Cumulative realized earnings checkpoint

Create an important-memory event whenever confirmed **realized external earnings** accumulated since the previous earnings checkpoint reach or pass `10,000c` (`1g`).

Count only money that actually became the player's money, for example:

- wages and payment for completed work;
- quest/job rewards paid in money;
- confirmed sale proceeds;
- other genuinely external earned income.

Do **not** count:

- transfers between the player's own pockets/accounts/holders;
- loans or borrowed money;
- refunds or return of the player's own money;
- earmarked project/family/promo funds that are not personal money;
- merely promised or expected income.

If one turn crosses several full-gold checkpoints, write one event containing the number of checkpoints crossed. Carry the remainder toward the next `1g` checkpoint.

### B. Major expenditure

Create an important-memory event for a confirmed personal outflow when either condition is met:

1. absolute spend is at least `5,000c` (`0.5g`); or
2. spend is at least `20%` of the player's liquid personal funds immediately before the spend **and** at least `1,000c` (`10s`).

Do not classify transfers between the player's own accounts/holders as spending.

For a major purchase, store what was obtained when that fact is authoritative. For a payment with no durable asset, store the reason/recipient only when confirmed.

## Other durable-significance rules

The chat should also create an important-memory event when a confirmed turn establishes a durable fact of similar importance, including:

- acquisition or loss of a major/unique asset, property, rare artifact, business or other long-lived resource;
- a substantial debt, binding contract, ownership stake or long-term financial obligation;
- a new rank, title, office, faction membership/status or comparable formal standing;
- a major persistent injury, permanent capability change, or other long-lived character-state change;
- a major durable relationship/faction-state change;
- another event whose consequences are expected to matter across many future sessions.

Routine dialogue, travel, small purchases, ordinary meals, minor loot, temporary mood, speculative interpretation and unconfirmed promises do not belong here.

## Bundling and anti-spam

If one or more significance rules trigger in the same gameplay beat, create **one bundled important-memory event**, not one file per fact.

Multiple ordinary turns may pass with zero GitHub important-memory writes. This is the expected case.

## Authority and anti-fabrication rules

1. Never create an important-memory entry for an unconfirmed or speculative fact.
2. Never infer an amount, ownership, relationship, injury, title or consequence that gameplay did not establish.
3. `UNKNOWN` stays `UNKNOWN`.
4. Every persisted entry must contain enough source/session information for deduplication and audit.
5. Do not write the same significant event twice.
6. Important memory is a durable checkpoint/index, not a verbose gameplay log.

## Storage

State/config:

`runtime/important_memory/state.json`

Append-only significant events:

`runtime/important_memory/mNNNNNN.json`

Recommended event shape:

```json
{
  "format": "TENSURA_IMPORTANT_MEMORY_EVENT",
  "schema_version": 1,
  "memory_seq": 1,
  "source": {
    "journal_seq": null,
    "event_key": "...",
    "session_checkpoint": "..."
  },
  "world_minute": 0,
  "kinds": ["major_spend"],
  "summary": "Краткий подтвержденный факт.",
  "facts": [],
  "economy": {
    "realized_earned_copper": 0,
    "spent_copper": 0,
    "earnings_checkpoint_gold_crossed": 0
  },
  "dedupe_key": "..."
}
```

Keep summaries factual and compact. Narrative prose belongs in gameplay, not in this index.

## Baseline

This protocol starts from the baseline recorded in `runtime/important_memory/state.json`. No retroactive reconstruction is performed unless the user explicitly requests it. Current cash at baseline is not assumed to have been earned during the tracked period.
