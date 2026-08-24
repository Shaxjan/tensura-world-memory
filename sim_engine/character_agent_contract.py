from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

CONTEXT_FORMAT = "TENSURA_CHARACTER_AGENT_CONTEXT"
DECISION_FORMAT = "TENSURA_CHARACTER_AGENT_DECISION"
SCHEMA_VERSION = 1

ALLOWED_DECISION_KINDS = {
    "speak",
    "act",
    "speak_and_act",
    "wait",
    "ignore",
    "leave",
}

ALLOWED_SPEECH_ACTS = {
    "none",
    "greet",
    "farewell",
    "answer",
    "ask",
    "tease",
    "joke",
    "reassure",
    "refuse",
    "accept_simple",
    "report",
    "comment",
}

ALLOWED_ACTION_KINDS = {
    "none",
    "gesture",
    "continue_current_activity",
    "pause_current_activity",
    "approach_visible_target",
    "leave_scene",
}

RELATIONSHIP_AXES = {"trust", "respect", "affection", "irritation"}
ALLOWED_PRIVATE_EMOTIONS = {
    "neutral",
    "amused",
    "warm",
    "annoyed",
    "guarded",
    "curious",
    "embarrassed",
    "concerned",
    "angry",
    "sad",
}

FORBIDDEN_TOP_LEVEL_DECISION_KEYS = {
    "world_state",
    "runtime_state",
    "database_patch",
    "cash_delta",
    "inventory_delta",
    "spawn",
    "despawn",
    "teleport",
    "global_event",
}


class CharacterAgentContractError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...]
    decision_digest: str | None = None
    sanitized: dict[str, Any] | None = None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decision_digest(decision: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(decision).encode("utf-8")).hexdigest()


def _string_set(values: Iterable[Any]) -> set[str]:
    return {str(value) for value in values if isinstance(value, str) and value}


def build_agent_context(
    *,
    actor_key: str,
    source_turn_key: str,
    world_minute: int,
    player_utterance: str,
    self_core: dict[str, Any],
    causal_fact_keys: Iterable[str],
    observations: list[dict[str, Any]],
    visible_target_keys: Iterable[str],
    current_plan: dict[str, Any] | None = None,
    relationship_state: dict[str, Any] | None = None,
    unresolved_keys: Iterable[str] = (),
) -> dict[str, Any]:
    """Build the only context a character agent is allowed to receive.

    The character may see its own private state, but it receives no global world
    state and no private state belonging to other characters. UNKNOWN remains
    explicit. Current observations and known facts are the only external sources
    an agent decision may cite.
    """
    if not actor_key or not source_turn_key:
        raise CharacterAgentContractError("actor_key and source_turn_key are required")
    if not isinstance(self_core, dict) or str(self_core.get("actor_key") or "") != actor_key:
        raise CharacterAgentContractError("self_core actor does not match actor_key")
    if not isinstance(player_utterance, str):
        raise CharacterAgentContractError("player_utterance must be a string")

    clean_observations: list[dict[str, Any]] = []
    observation_fact_keys: set[str] = set()
    for item in observations:
        if not isinstance(item, dict):
            raise CharacterAgentContractError("observations must contain objects")
        fact_key = str(item.get("fact_key") or "")
        if not fact_key:
            raise CharacterAgentContractError("every observation needs a fact_key")
        observation_fact_keys.add(fact_key)
        clean_observations.append(dict(item))

    known = _string_set(causal_fact_keys)
    visible = _string_set(visible_target_keys)
    unresolved = _string_set(unresolved_keys)

    return {
        "format": CONTEXT_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "actor_key": actor_key,
        "source_turn_key": source_turn_key,
        "world_minute": int(world_minute),
        "player_input": {
            "utterance": player_utterance,
            "observation_key": f"turn:{source_turn_key}:player_utterance",
        },
        "self": {
            "character_core": dict(self_core),
            "current_plan": dict(current_plan or {}),
            "relationship_state": dict(relationship_state or {}),
        },
        "knowledge": {
            "causal_fact_keys": sorted(known),
            "current_observation_fact_keys": sorted(observation_fact_keys),
            "unresolved_keys": sorted(unresolved),
            "unknown_policy": "UNKNOWN_STAYS_UNKNOWN",
        },
        "observations": clean_observations,
        "visible_target_keys": sorted(visible),
        "agent_rules": {
            "no_global_state": True,
            "no_other_character_private_state": True,
            "all_external_claims_require_fact_refs": True,
            "decision_is_proposal_not_authority": True,
            "replay_must_use_journaled_decision_not_recall_agent": True,
        },
    }


def _validate_context(context: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(context, dict):
        return ["context must be an object"]
    if context.get("format") != CONTEXT_FORMAT or context.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported character-agent context format")
    actor_key = str(context.get("actor_key") or "")
    core = ((context.get("self") or {}).get("character_core") or {}) if isinstance(context.get("self"), dict) else {}
    if not actor_key or not isinstance(core, dict) or str(core.get("actor_key") or "") != actor_key:
        errors.append("context self_core actor mismatch")
    for forbidden in ("world_state", "runtime_state", "other_character_private_state"):
        if forbidden in context:
            errors.append(f"forbidden context key: {forbidden}")
    return errors


def _allowed_fact_refs(context: dict[str, Any]) -> set[str]:
    knowledge = context.get("knowledge") if isinstance(context.get("knowledge"), dict) else {}
    refs = _string_set(knowledge.get("causal_fact_keys") or [])
    refs |= _string_set(knowledge.get("current_observation_fact_keys") or [])
    player_input = context.get("player_input") if isinstance(context.get("player_input"), dict) else {}
    utterance_key = player_input.get("observation_key")
    if isinstance(utterance_key, str) and utterance_key:
        refs.add(utterance_key)
    return refs


def _validate_relationship_proposal(value: Any, errors: list[str]) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append("private.relationship_delta must be an object")
        return {}
    out: dict[str, int] = {}
    for axis, delta in value.items():
        if axis not in RELATIONSHIP_AXES:
            errors.append(f"unsupported relationship axis: {axis}")
            continue
        if not isinstance(delta, int) or isinstance(delta, bool) or not -2 <= delta <= 2:
            errors.append(f"relationship delta for {axis} must be integer -2..2")
            continue
        out[axis] = delta
    return out


def validate_agent_decision(context: dict[str, Any], decision: dict[str, Any]) -> ValidationResult:
    """Fail-closed validation for an untrusted character-agent proposal.

    This function deliberately does not execute the decision. The runtime must
    journal the validated decision and separately translate it into authoritative
    effects. Replay consumes that journaled proposal; it must never call the AI
    agent again for an already committed turn.
    """
    errors = _validate_context(context)
    if not isinstance(decision, dict):
        return ValidationResult(False, tuple(errors + ["decision must be an object"]))

    forbidden_found = sorted(FORBIDDEN_TOP_LEVEL_DECISION_KEYS.intersection(decision))
    if forbidden_found:
        errors.append("forbidden direct authority keys: " + ", ".join(forbidden_found))

    if decision.get("format") != DECISION_FORMAT or decision.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported character-agent decision format")

    actor_key = str(context.get("actor_key") or "")
    if str(decision.get("actor_key") or "") != actor_key:
        errors.append("decision actor_key does not match context")
    if str(decision.get("source_turn_key") or "") != str(context.get("source_turn_key") or ""):
        errors.append("decision source_turn_key does not match context")

    kind = str(decision.get("decision_kind") or "")
    if kind not in ALLOWED_DECISION_KINDS:
        errors.append(f"unsupported decision_kind: {kind}")

    observable = decision.get("observable")
    if not isinstance(observable, dict):
        errors.append("observable must be an object")
        observable = {}

    speech_act = str(observable.get("speech_act") or "none")
    if speech_act not in ALLOWED_SPEECH_ACTS:
        errors.append(f"unsupported speech_act: {speech_act}")
    surface_text = observable.get("surface_text")
    if surface_text is not None and (not isinstance(surface_text, str) or len(surface_text) > 2000):
        errors.append("observable.surface_text must be null or <=2000 character string")

    action_kind = str(observable.get("action_kind") or "none")
    if action_kind not in ALLOWED_ACTION_KINDS:
        errors.append(f"unsupported action_kind: {action_kind}")

    target_key = observable.get("target_key")
    visible_targets = _string_set(context.get("visible_target_keys") or [])
    if target_key is not None and str(target_key) not in visible_targets:
        errors.append("observable target is not currently visible/grounded")

    clock_minutes = observable.get("clock_minutes", 0)
    if not isinstance(clock_minutes, int) or isinstance(clock_minutes, bool) or not 0 <= clock_minutes <= 30:
        errors.append("observable.clock_minutes must be integer 0..30")

    allowed_refs = _allowed_fact_refs(context)
    grounding = decision.get("grounding")
    if not isinstance(grounding, dict):
        errors.append("grounding must be an object")
        grounding = {}
    fact_refs = _string_set(grounding.get("fact_refs") or [])
    unknown_refs = sorted(fact_refs - allowed_refs)
    if unknown_refs:
        errors.append("decision cites facts unavailable to actor: " + ", ".join(unknown_refs))

    asserted_claims = grounding.get("asserted_claims") or []
    if not isinstance(asserted_claims, list):
        errors.append("grounding.asserted_claims must be a list")
        asserted_claims = []
    clean_claims: list[dict[str, Any]] = []
    for idx, claim in enumerate(asserted_claims):
        if not isinstance(claim, dict):
            errors.append(f"asserted_claims[{idx}] must be an object")
            continue
        refs = _string_set(claim.get("fact_refs") or [])
        if not refs:
            errors.append(f"asserted_claims[{idx}] has no causal fact_refs")
            continue
        bad = sorted(refs - allowed_refs)
        if bad:
            errors.append(f"asserted_claims[{idx}] cites unavailable facts: " + ", ".join(bad))
            continue
        clean_claims.append(dict(claim))

    private = decision.get("private")
    if private is None:
        private = {}
    if not isinstance(private, dict):
        errors.append("private must be an object")
        private = {}

    emotion = private.get("emotion_state")
    if emotion is not None and emotion not in ALLOWED_PRIVATE_EMOTIONS:
        errors.append(f"unsupported private emotion_state: {emotion}")
    relationship_delta = _validate_relationship_proposal(private.get("relationship_delta"), errors)

    memory_proposals = private.get("memory_proposals") or []
    if not isinstance(memory_proposals, list):
        errors.append("private.memory_proposals must be a list")
        memory_proposals = []
    clean_memories: list[dict[str, Any]] = []
    for idx, memory in enumerate(memory_proposals):
        if not isinstance(memory, dict):
            errors.append(f"memory_proposals[{idx}] must be an object")
            continue
        refs = _string_set(memory.get("source_fact_refs") or [])
        if not refs:
            errors.append(f"memory_proposals[{idx}] has no source_fact_refs")
            continue
        bad = sorted(refs - allowed_refs)
        if bad:
            errors.append(f"memory_proposals[{idx}] cites unavailable facts: " + ", ".join(bad))
            continue
        clean_memories.append(dict(memory))

    if errors:
        return ValidationResult(False, tuple(errors))

    sanitized = {
        "format": DECISION_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "actor_key": actor_key,
        "source_turn_key": str(context.get("source_turn_key")),
        "decision_kind": kind,
        "observable": {
            "speech_act": speech_act,
            "surface_text": surface_text,
            "action_kind": action_kind,
            "target_key": target_key,
            "clock_minutes": int(clock_minutes),
        },
        "grounding": {
            "fact_refs": sorted(fact_refs),
            "asserted_claims": clean_claims,
        },
        "private": {
            "emotion_state": emotion,
            "relationship_delta": relationship_delta,
            "memory_proposals": clean_memories,
            "rationale": private.get("rationale") if isinstance(private.get("rationale"), str) else None,
        },
        "authority": "AGENT_PROPOSAL_REQUIRES_ENGINE_COMMIT",
    }
    return ValidationResult(True, (), decision_digest(sanitized), sanitized)


def public_observable(validated: ValidationResult) -> dict[str, Any]:
    """Return only narrator/player-visible semantics from a validated proposal."""
    if not validated.ok or not isinstance(validated.sanitized, dict):
        raise CharacterAgentContractError("cannot expose an invalid agent decision")
    return dict(validated.sanitized.get("observable") or {})
