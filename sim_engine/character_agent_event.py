from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Iterable

from character_agent_contract import ValidationResult, decision_digest, public_observable
from character_agent_shadow import context_digest

EVENT_FORMAT = "TENSURA_CHARACTER_DECISION_EVENT"
EVENT_SCHEMA_VERSION = 1
STATE_FORMAT = "TENSURA_CHARACTER_DECISION_STATE"
STATE_SCHEMA_VERSION = 1
EVENT_AUTHORITY = "CANDIDATE_AUTHORITATIVE_CHARACTER_EVENT"
EFFECT_POLICY = "character_agent_effects_v1"
RELATIONSHIP_AXES = ("trust", "respect", "affection", "irritation")


class CharacterDecisionEventError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def initial_character_decision_state() -> dict[str, Any]:
    return {
        "format": STATE_FORMAT,
        "schema_version": STATE_SCHEMA_VERSION,
        "last_seq": 0,
        "event_keys": [],
        "committed_turns": {},
        "actors": {},
        "public_observations": [],
    }


def character_decision_state_hash(state: dict[str, Any]) -> str:
    if not isinstance(state, dict) or state.get("format") != STATE_FORMAT:
        raise CharacterDecisionEventError("invalid Character Decision state")
    return _digest(state)


def _validate_state_shape(state: dict[str, Any]) -> None:
    if not isinstance(state, dict):
        raise CharacterDecisionEventError("Character Decision state must be an object")
    if state.get("format") != STATE_FORMAT or state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise CharacterDecisionEventError("unsupported Character Decision state format")
    if not isinstance(state.get("last_seq"), int) or isinstance(state.get("last_seq"), bool):
        raise CharacterDecisionEventError("state.last_seq must be an integer")
    if not isinstance(state.get("event_keys"), list):
        raise CharacterDecisionEventError("state.event_keys must be a list")
    if not isinstance(state.get("committed_turns"), dict):
        raise CharacterDecisionEventError("state.committed_turns must be an object")
    if not isinstance(state.get("actors"), dict):
        raise CharacterDecisionEventError("state.actors must be an object")
    if not isinstance(state.get("public_observations"), list):
        raise CharacterDecisionEventError("state.public_observations must be a list")


def _actor_state(state: dict[str, Any], actor_key: str) -> dict[str, Any]:
    actors = state.setdefault("actors", {})
    actor = actors.get(actor_key)
    if not isinstance(actor, dict):
        actor = {
            "relationship_delta_since_agent_activation": {axis: 0 for axis in RELATIONSHIP_AXES},
            "episodic_memories": [],
            "last_private_emotion": None,
            "last_decision_digest": None,
            "last_source_turn_key": None,
        }
        actors[actor_key] = actor
    return actor


def _memory_id(actor_key: str, source_turn_key: str, memory: dict[str, Any], decision_hash: str) -> str:
    return _digest(
        {
            "actor_key": actor_key,
            "source_turn_key": source_turn_key,
            "memory": memory,
            "decision_digest": decision_hash,
        }
    )


def _event_core(event: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in event.items() if key not in {"before_state_hash", "after_state_hash"}}


def _validate_event_integrity(event: dict[str, Any]) -> None:
    if not isinstance(event, dict):
        raise CharacterDecisionEventError("Character Decision event must be an object")
    if event.get("format") != EVENT_FORMAT or event.get("schema_version") != EVENT_SCHEMA_VERSION:
        raise CharacterDecisionEventError("unsupported Character Decision event format")
    if event.get("authority") != EVENT_AUTHORITY:
        raise CharacterDecisionEventError("Character Decision event authority mismatch")
    if event.get("effect_policy") != EFFECT_POLICY:
        raise CharacterDecisionEventError("Character Decision effect policy mismatch")

    seq = event.get("seq")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq <= 0:
        raise CharacterDecisionEventError("event.seq must be a positive integer")
    for field in ("event_key", "actor_key", "source_turn_key", "context_digest", "decision_digest"):
        if not isinstance(event.get(field), str) or not event.get(field):
            raise CharacterDecisionEventError(f"event.{field} is required")

    decision = event.get("decision")
    if not isinstance(decision, dict):
        raise CharacterDecisionEventError("event.decision must be an object")
    if decision_digest(decision) != event.get("decision_digest"):
        raise CharacterDecisionEventError("Character Decision digest mismatch")
    if str(decision.get("actor_key") or "") != event.get("actor_key"):
        raise CharacterDecisionEventError("decision actor mismatch")
    if str(decision.get("source_turn_key") or "") != event.get("source_turn_key"):
        raise CharacterDecisionEventError("decision source turn mismatch")
    if dict(decision.get("observable") or {}) != event.get("public_observable"):
        raise CharacterDecisionEventError("event public observable does not match decision")


def _apply_event_core(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    _validate_state_shape(state)
    _validate_event_integrity(event)
    next_state = deepcopy(state)

    seq = int(event["seq"])
    if seq != int(next_state["last_seq"]) + 1:
        raise CharacterDecisionEventError("Character Decision sequence gap or collision")
    event_key = str(event["event_key"])
    if event_key in next_state["event_keys"]:
        raise CharacterDecisionEventError("duplicate Character Decision event_key")

    actor_key = str(event["actor_key"])
    source_turn_key = str(event["source_turn_key"])
    turn_identity = f"{actor_key}:{source_turn_key}"
    existing = next_state["committed_turns"].get(turn_identity)
    if existing is not None:
        raise CharacterDecisionEventError("Character Decision already committed for actor/source turn")

    decision = event["decision"]
    private = decision.get("private") if isinstance(decision.get("private"), dict) else {}
    relationship_delta = private.get("relationship_delta") if isinstance(private.get("relationship_delta"), dict) else {}
    actor = _actor_state(next_state, actor_key)
    cumulative = actor["relationship_delta_since_agent_activation"]
    for axis in RELATIONSHIP_AXES:
        delta = relationship_delta.get(axis, 0)
        if not isinstance(delta, int) or isinstance(delta, bool) or not -2 <= delta <= 2:
            raise CharacterDecisionEventError(f"invalid committed relationship delta for {axis}")
        cumulative[axis] = int(cumulative.get(axis, 0)) + int(delta)

    memories = private.get("memory_proposals") if isinstance(private.get("memory_proposals"), list) else []
    seen_memory_ids = {str(item.get("memory_id")) for item in actor["episodic_memories"] if isinstance(item, dict)}
    for memory in memories:
        if not isinstance(memory, dict):
            raise CharacterDecisionEventError("committed memory proposal must be an object")
        memory_id = _memory_id(actor_key, source_turn_key, memory, str(event["decision_digest"]))
        if memory_id in seen_memory_ids:
            continue
        actor["episodic_memories"].append(
            {
                "memory_id": memory_id,
                "source_turn_key": source_turn_key,
                "decision_digest": str(event["decision_digest"]),
                "memory": deepcopy(memory),
            }
        )
        seen_memory_ids.add(memory_id)

    emotion = private.get("emotion_state")
    actor["last_private_emotion"] = emotion if isinstance(emotion, str) else None
    actor["last_decision_digest"] = str(event["decision_digest"])
    actor["last_source_turn_key"] = source_turn_key

    next_state["public_observations"].append(
        {
            "seq": seq,
            "event_key": event_key,
            "actor_key": actor_key,
            "source_turn_key": source_turn_key,
            "world_minute": int(event.get("world_minute") or 0),
            "decision_digest": str(event["decision_digest"]),
            "observable": deepcopy(event["public_observable"]),
        }
    )
    next_state["committed_turns"][turn_identity] = str(event["decision_digest"])
    next_state["event_keys"].append(event_key)
    next_state["last_seq"] = seq
    return next_state


def build_character_decision_event(
    state: dict[str, Any],
    *,
    context: dict[str, Any],
    validation: ValidationResult,
    seq: int,
    event_key: str,
) -> dict[str, Any]:
    _validate_state_shape(state)
    if not validation.ok or not isinstance(validation.sanitized, dict) or not validation.decision_digest:
        raise CharacterDecisionEventError("cannot build event from invalid agent decision")
    actor_key = str(context.get("actor_key") or "")
    source_turn_key = str(context.get("source_turn_key") or "")
    if str(validation.sanitized.get("actor_key") or "") != actor_key:
        raise CharacterDecisionEventError("validated decision actor does not match context")
    if str(validation.sanitized.get("source_turn_key") or "") != source_turn_key:
        raise CharacterDecisionEventError("validated decision turn does not match context")

    before_hash = character_decision_state_hash(state)
    event = {
        "format": EVENT_FORMAT,
        "schema_version": EVENT_SCHEMA_VERSION,
        "authority": EVENT_AUTHORITY,
        "effect_policy": EFFECT_POLICY,
        "seq": int(seq),
        "event_key": str(event_key),
        "actor_key": actor_key,
        "source_turn_key": source_turn_key,
        "world_minute": int(context.get("world_minute") or 0),
        "context_digest": context_digest(context),
        "decision_digest": validation.decision_digest,
        "decision": deepcopy(validation.sanitized),
        "public_observable": public_observable(validation),
        "effect_notes": {
            "relationship_values_are_delta_since_agent_activation_not_absolute_relationship": True,
            "memory_proposals_become_private_episodic_memories": True,
            "private_emotion_is_not_public_observable": True,
            "no_cash_inventory_or_global_world_effects": True,
        },
    }
    candidate = _apply_event_core(state, event)
    event["before_state_hash"] = before_hash
    event["after_state_hash"] = character_decision_state_hash(candidate)
    return event


def apply_character_decision_event(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    _validate_state_shape(state)
    _validate_event_integrity(event)
    current_hash = character_decision_state_hash(state)
    if str(event.get("before_state_hash") or "") != current_hash:
        raise CharacterDecisionEventError("Character Decision before-state hash mismatch")
    next_state = _apply_event_core(state, event)
    next_hash = character_decision_state_hash(next_state)
    if str(event.get("after_state_hash") or "") != next_hash:
        raise CharacterDecisionEventError("Character Decision after-state hash mismatch")
    return next_state


def replay_character_decision_events(
    events: Iterable[dict[str, Any]],
    *,
    initial_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = deepcopy(initial_state or initial_character_decision_state())
    for event in events:
        state = apply_character_decision_event(state, event)
    return state
