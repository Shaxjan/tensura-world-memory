# Scene Continuity Protocol v1

Status: ACTIVE gameplay continuity architecture.

## Goal

Prevent the narrator from rebuilding the world from memory on every message. A current scene is persistent state. Each turn modifies only what causally changes.

## 1. Single current-frame source

`runtime/current_scene.json` is the durable current-frame overlay while `status = ACTIVE`.

It contains only present-scene facts: time, place, money display state, physically present entities, their observable physical state, unresolved immediate player input, and imminent known commitments.

It does not replace the immutable runtime journal/history. It exists because the legacy `runtime/session_state.json` can lag far behind fast-play chat continuity.

Priority for current-scene facts:

1. latest direct player correction affecting the current scene;
2. `runtime/current_scene.json` while ACTIVE;
3. active in-chat delta newer than that file but not yet flushed;
4. matching runtime/session checkpoint;
5. older checkpoints/history.

An older file can never silently reset a newer current scene.

## 2. Delta-only turns

Every normal turn is resolved as:

`NEXT_SCENE = CURRENT_SCENE + PLAYER_INPUT + AUTONOMOUS_WORLD_DELTA`

Fields that are not changed by a causally justified transition are inherited exactly.

Examples:
- player says one short sentence -> Rena does not teleport to another place;
- NPC was dressed -> clothing does not reset without an action/time passage that could change it;
- NPC was awake -> does not become asleep just because a new answer began;
- money does not change without an economic event;
- a date/day does not change without enough elapsed time or an explicit timeskip.

## 3. Physical-state locks

For each present named NPC, track at least when known:
- presence;
- awake/sleeping state;
- coarse position/posture;
- clothing state only when already established and relevant;
- last valid observable action/speech.

These are not personality traits. They belong only to the scene.

NPC autonomy is preserved: an NPC may independently stand, leave, approach, speak, work, refuse, interrupt, or do something else. But the new state must be represented as an actual transition from the previous one, not as a reset.

## 4. Time continuity

Ordinary conversation usually advances seconds or a few minutes. Do not change the T+ day from a one-line exchange.

Large jumps require a cause such as:
- sleep resolution;
- travel;
- waiting;
- long performance/work;
- explicit player request;
- causally justified interruption/outcome.

A large time jump must record a `time_jump_reason` in its turn delta.

## 5. Money continuity

Money is ledger state, not prose memory.

A balance can change only when a delta contains a causal money event: payment, purchase, earning, transfer, loss, recovery, correction, or explicit reconciliation.

Approximate money remains approximate. `~358g` must not become an exact copper value merely because an older checkpoint contains a precise but stale number.

## 6. Player agency

A turn delta may contain a voluntary Arlequino action only if it is present in the user's actual input.

Never infer:
- getting dressed;
- standing up;
- walking somewhere;
- taking an item;
- remembering/deciding something;
- emotional state;
- speech not written by the user.

## 7. Sleep transition

Sleep is special and follows `runtime/rules/SLEEP_SCENE_RESOLUTION_v1.md`.

When the player says `Сплю`, do not create a visible intermediate scene whose outcome is merely `Arlequino is sleeping`.

Resolve directly to the next meaningful wake/interruption scene. The resulting wake scene becomes the new `CURRENT_SCENE`. Subsequent turns continue from that exact frame.

Hidden events during sleep remain hidden until causally learned.

## 8. Error handling versus retcon

Use `runtime/corrections/CORRECTION_TAXONOMY_v1.md`.

A narrator continuity mistake is not an in-world event and not automatically a retcon. The invalid variant is discarded, and `CURRENT_SCENE` stays anchored to the last valid state.

## 9. Immediate unresolved input

If the player spoke/acted but the assistant's response was invalidated before a valid world/NPC resolution occurred, preserve that exact player input as unresolved in `current_scene.json`.

On resumption, resolve it once. Do not ask the player to repeat it and do not duplicate the action.

## 10. Continuity validation

Before narrating a proposed next scene, conceptually validate:
- day/time jump has cause;
- location change has movement/timeskip cause;
- money change has ledger cause;
- every present NPC state change has an autonomous or externally caused transition;
- no missing state was reset to a default;
- no voluntary Arlequino action was invented;
- all unchanged fields inherit from current scene.

`runtime/continuity/validate_transition.py` provides a lightweight machine check for stored scene transitions. It is a guardrail, not a replacement for causal reasoning.
