# Tensura Chat Important Memory Protocol v1

## Purpose

`runtime/important_memory/` is a compact durable index of gameplay facts that are important enough to survive hundreds of turns and be easy for a new game chat to recover.

It is **not** a second source of gameplay truth. The authoritative runtime journal remains authoritative. Important-memory entries may only summarize facts already confirmed by a committed runtime event/session state and must reference their source journal event(s).

## When the game chat must evaluate it

After every **confirmed gameplay turn**, after the authoritative journal event and fresh `runtime/session_state.json` are available, the chat performs an important-memory postflight check.

If no rule below triggers, create no important-memory event.

If one or more rules trigger in the same turn, create **one bundled important-memory event** for that turn. Do not spam one file per fact.

If GitHub write access is unavailable or the write fails, never claim that the memory was saved. Report the persistence failure separately from the gameplay result.

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
- a major durable relationship/faction-state change that the authoritative runtime actually confirms;
- another event whose consequences are expected to matter across many future sessions.

Routine dialogue, travel, small purchases, ordinary meals, minor loot, temporary mood, speculative interpretation and unconfirmed promises do not belong here.

## Authority and anti-fabrication rules

1. Never create an important-memory entry before the gameplay turn is confirmed.
2. Never infer an amount, ownership, relationship, injury, title or consequence that the authoritative event/session does not establish.
3. `UNKNOWN` stays `UNKNOWN`.
4. Important memory may summarize; it may not mutate or override canonical runtime state.
5. Every entry must include source journal sequence/event key(s) sufficient for audit and deduplication.
6. A source gameplay event may produce at most one important-memory entry.
7. If the source event was already indexed, do not write it again.

## Storage

State/config:

`runtime/important_memory/state.json`

Append-only events:

`runtime/important_memory/mNNNNNN.json`

Recommended event shape:

```json
{
  "format": "TENSURA_IMPORTANT_MEMORY_EVENT",
  "schema_version": 1,
  "memory_seq": 1,
  "source": {
    "journal_seq": 22,
    "event_key": "..."
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
  "dedupe_key": "journal:22"
}
```

Keep summaries factual and compact. Narrative prose belongs in gameplay, not in this index.

## Baseline

This protocol starts from the baseline recorded in `runtime/important_memory/state.json`. No retroactive reconstruction is performed unless the user explicitly requests it. Current cash at baseline is not assumed to have been earned during the tracked period.
