# Tensura Fast Play Protocol v1

## Goal

Normal gameplay must feel like a live conversation. GitHub is durable storage, not a per-message database call.

This protocol overrides the older per-turn GitHub transport requirement for an already-open synchronized game chat.

## 1. Two-layer active state

During an active game chat the effective state is:

1. **persisted checkpoint** — the last state safely stored in GitHub;
2. **session-local overlay** — confirmed ordinary gameplay that happened in the current chat after that checkpoint and has not yet been flushed.

The game uses the combined effective state for subsequent ordinary turns.

The local overlay is authoritative for the currently active chat until the next persistence checkpoint. It must not be silently discarded merely because GitHub still contains an older persisted checkpoint.

## 2. Bootstrap / recovery

On a new game chat, explicit load, recovery, or when the active in-chat state is unavailable:

- read `runtime/runtime_state.json` and `runtime/session_state.json` once;
- read important-memory state only if needed for the resumed counters;
- establish that persisted state as the session baseline;
- then continue normal play from in-chat state without rereading GitHub on every message.

A synchronized active chat must not perform a GitHub preflight merely because the player sent another ordinary line of dialogue or action.

## 3. Ordinary turns — NO GitHub I/O

The following normally stay only in the active session overlay:

- ordinary dialogue;
- observation and questions to nearby characters;
- local movement and routine travel beats;
- small purchases and ordinary expenses below significance thresholds;
- ordinary income below the cumulative durable checkpoint;
- routine combat/training beats;
- temporary scene details, mood and short-lived state;
- other gameplay whose consequences do not require durable persistence yet.

For these turns:

- do not create `runtime/requests/q-*.json` solely to process the turn;
- do not wait for GitHub Actions;
- do not read `runtime/runtime_state.json` or `runtime/session_state.json` again;
- do not create a journal commit for each line;
- answer from the current session state immediately.

## 4. When GitHub persistence IS required

Flush the active session to durable storage only when at least one of these occurs:

1. an important-memory significance trigger fires;
2. the player explicitly asks to save/checkpoint;
3. the chat intentionally closes/changes session and a checkpoint is appropriate;
4. recovery or ambiguity makes durable synchronization necessary before safe continuation.

Important economic triggers are defined by `runtime/IMPORTANT_MEMORY_PROTOCOL.md`, including cumulative realized personal earnings of `1g` and major spending thresholds.

Other major durable events such as a unique asset, title, binding contract, permanent capability/state change, or comparable long-lived consequence can also trigger persistence.

### Mandatory durable creative/canonical content

The following are significance triggers and must be persisted rather than left only in the chat-local overlay:

- when the player performs or supplies the **full text of a song**, preserve that full supplied text in the appropriate durable song/canonical memory together with the in-world context needed to identify it;
- other player-supplied creative works or exact canonical texts that would be costly or impossible to reconstruct later;
- major relationship changes, promises, contracts, debts, ownership changes, unique purchases, titles, permissions, discoveries, permanent decisions, major project/festival decisions, and comparable facts whose loss would materially damage continuity.

Do not reduce a supplied full song to a summary if the full text itself is the important memory. If a song persistence trigger fires, save it at that gameplay beat rather than waiting for many unrelated later turns.

## 5. Bundled persistence

When a persistence trigger occurs, do not replay every ordinary chat line as a separate GitHub commit.

Persist one bundled checkpoint/event containing the durable effects necessary to reconstruct the effective state since the previous checkpoint. Important-memory indexing should likewise produce at most one bundled memory event for the triggering gameplay beat.

After successful persistence:

- the new persisted state becomes the baseline;
- the flushed local overlay is cleared;
- subsequent ordinary play again proceeds locally without GitHub I/O.

## 6. Failure behavior

If a required GitHub persistence attempt fails:

- never claim that it was saved;
- report the persistence failure separately and briefly;
- keep the current in-chat state available for continued play when it is safe to do so;
- retry only at a real save/checkpoint opportunity, not on every subsequent ordinary line.

## 7. Intentional tradeoff

Fast play deliberately trades per-line durability for responsiveness. Ordinary unflushed turns may be lost if the active chat/session context itself is lost before a checkpoint.

That risk is preferable to making every normal conversation wait on GitHub. Important durable milestones and explicit saves remain the persistence boundary.

## 8. Priority

For an active synchronized game chat, this FAST PLAY protocol has priority over older instructions that require GitHub request/journal/receipt round-trips for every normal gameplay turn.

GitHub remains the durable source for persisted checkpoints. It is not consulted as a live database for every player message.
