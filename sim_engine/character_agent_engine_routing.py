from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from v03_engine import loads
from v106_runtime import _single_name_forms_v106, _tokens_v106

ROUTING_MODEL = "character_agent_engine_owned_routing_v1"
RECIPROCAL_PREFIX = "v113:reciprocal_awareness:rena:"
VISIBLE_RENA_KEY = "v103:visible_named:rena"
DIRECT_KNOWLEDGE_MIN_CONFIDENCE = 100
MAX_CAUSAL_FACTS = 64


@dataclass(frozen=True)
class RoutingResult:
    eligible: bool
    reason: str
    context: dict[str, Any] | None = None


class CharacterAgentRoutingError(RuntimeError):
    pass


def _explicit_rena_address(raw_text: str) -> bool:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return False
    return bool(_tokens_v106(raw_text) & _single_name_forms_v106("Рена"))


def _current_place(world, player_id: str = "player") -> dict[str, Any] | None:
    place = world._place103(player_id)
    return dict(place) if isinstance(place, dict) else None


def _current_rena_visibility(world, player_id: str = "player") -> dict[str, Any] | None:
    """Return only a current same-place player observation of Rena.

    Player visibility is intentionally NOT treated as reciprocal awareness.
    A separate causal awareness fact is required before the Character Agent may
    receive the player's action/utterance as an observed interaction.
    """
    place = _current_place(world, player_id)
    visible = world._get_fact103(VISIBLE_RENA_KEY)
    if not place or not isinstance(visible, dict):
        return None
    if str(visible.get("actor_key") or "") != "rena":
        return None
    if str(visible.get("place_key") or "") != str(place.get("key") or ""):
        return None
    if int(visible.get("valid_until", -1)) < int(world.now):
        return None
    return {
        "fact_key": VISIBLE_RENA_KEY,
        "actor_key": "rena",
        "display_name": str(visible.get("name") or "Рена"),
        "place_key": str(place["key"]),
        "place_text": str(place["name"]),
        "observed_at": int(visible.get("observed_at", world.now)),
        "valid_until": int(visible.get("valid_until", world.now)),
        "authority": str(visible.get("authority") or "engine_direct_player_observation"),
    }


def reciprocal_key(source_turn_key: str) -> str:
    return RECIPROCAL_PREFIX + str(source_turn_key)


def _reciprocal_awareness(
    world,
    *,
    source_turn_key: str,
    raw_text: str,
    player_id: str = "player",
    allow_candidate_fixture: bool = False,
) -> dict[str, Any] | None:
    place = _current_place(world, player_id)
    fact = world._get_fact103(reciprocal_key(source_turn_key))
    if not place or not isinstance(fact, dict):
        return None
    if str(fact.get("owner_key") or "") != "rena" or str(fact.get("counterpart_key") or "") != player_id:
        return None
    if str(fact.get("source_turn_key") or "") != source_turn_key:
        return None
    if int(fact.get("world_minute", -1)) != int(world.now):
        return None
    if str(fact.get("place_key") or "") != str(place.get("key") or ""):
        return None
    if str(fact.get("observed_player_text_verbatim") or "") != raw_text:
        return None
    authority = str(fact.get("authority") or "")
    allowed = {"ENGINE_CAUSAL_OBSERVATION"}
    if allow_candidate_fixture:
        allowed.add("CANDIDATE_REHEARSAL_FIXTURE")
    if authority not in allowed:
        return None
    return dict(fact)


def collect_actor_causal_facts(
    world,
    actor_key: str,
    *,
    min_confidence: int = DIRECT_KNOWLEDGE_MIN_CONFIDENCE,
    limit: int = MAX_CAUSAL_FACTS,
) -> list[dict[str, Any]]:
    """Read only facts explicitly present in this actor's actor_knowledge rows.

    v1 keeps only confidence=100 facts in the prompt context. Lower-confidence
    beliefs remain authoritative engine state but are not yet exposed to the
    language agent until uncertainty-aware claim verification exists.
    """
    rows = world.db.execute(
        "SELECT ak.fact_key,ak.confidence,ak.learned_at,ak.source,f.value_json "
        "FROM actor_knowledge ak JOIN facts f ON f.key=ak.fact_key "
        "WHERE ak.actor_id=? AND ak.confidence>=? "
        "ORDER BY ak.learned_at DESC,ak.fact_key ASC LIMIT ?",
        (actor_key, int(min_confidence), int(limit)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        value = loads(row["value_json"], None)
        if not isinstance(value, dict):
            continue
        out.append(
            {
                "fact_key": str(row["fact_key"]),
                "confidence": int(row["confidence"]),
                "learned_at": int(row["learned_at"]),
                "source": str(row["source"] or ""),
                "value": value,
            }
        )
    return out


def build_engine_owned_rena_context_v113(
    world,
    *,
    source_turn_key: str,
    raw_text: str,
    player_id: str = "player",
    allow_candidate_fixture: bool = False,
) -> RoutingResult:
    """Build Rena's agent context strictly from engine-owned current state.

    This function does not create visibility, awareness or knowledge. It only
    consumes already-authoritative state. Any missing causal prerequisite makes
    the route ineligible instead of being filled with a guess.
    """
    if player_id != "player":
        return RoutingResult(False, "unsupported_player")
    if world.character_agent_state_v113("rena") is None or world.character_core_v113("rena") is None:
        return RoutingResult(False, "character_agent_not_activated")
    if not _explicit_rena_address(raw_text):
        return RoutingResult(False, "rena_not_explicitly_addressed")

    place = _current_place(world, player_id)
    if not place:
        return RoutingResult(False, "current_place_unresolved")
    visibility = _current_rena_visibility(world, player_id)
    if not visibility:
        return RoutingResult(False, "rena_not_directly_visible")

    awareness = _reciprocal_awareness(
        world,
        source_turn_key=source_turn_key,
        raw_text=raw_text,
        player_id=player_id,
        allow_candidate_fixture=allow_candidate_fixture,
    )
    if not awareness:
        return RoutingResult(False, "rena_has_no_causal_awareness_of_this_turn")

    known = collect_actor_causal_facts(world, "rena")
    known_keys = [row["fact_key"] for row in known]
    observation_key = reciprocal_key(source_turn_key)
    observations = [
        {
            "fact_key": observation_key,
            "kind": "direct_reciprocal_scene_observation",
            "subject": player_id,
            "predicate": "explicitly_addressed_rena_in_same_scene",
            "world_minute": int(world.now),
            "place_key": str(place["key"]),
            "place_text": str(place["name"]),
            "authority": str(awareness["authority"]),
        }
    ]

    context = world.build_rena_agent_context_v113(
        source_turn_key=source_turn_key,
        player_utterance=raw_text,
        causal_fact_keys=known_keys,
        observations=observations,
        visible_target_keys=[player_id],
        current_plan={
            "kind": "unresolved_current_activity",
            "exact_plan": None,
            "place_key": str(place["key"]),
            "rule": "no Rena scheduler/current activity is invented by routing v1",
        },
    )
    knowledge = context.get("knowledge") if isinstance(context.get("knowledge"), dict) else {}
    knowledge["causal_facts"] = known
    knowledge["causal_fact_values_source"] = "actor_knowledge_join_facts"
    knowledge["minimum_confidence_exposed"] = DIRECT_KNOWLEDGE_MIN_CONFIDENCE
    context["knowledge"] = knowledge
    context["routing"] = {
        "model": ROUTING_MODEL,
        "engine_owned": True,
        "actor_key": "rena",
        "player_id": player_id,
        "place_key": str(place["key"]),
        "visibility_fact_key": VISIBLE_RENA_KEY,
        "reciprocal_awareness_fact_key": observation_key,
        "explicit_address": True,
        "player_visibility_does_not_imply_reciprocal_awareness": True,
        "candidate_fixture_allowed": bool(allow_candidate_fixture),
        "production_provider_called": False,
    }
    return RoutingResult(True, "eligible", context)


def install_candidate_reciprocal_fixture(
    world,
    *,
    source_turn_key: str,
    raw_text: str,
    player_id: str = "player",
) -> dict[str, str]:
    """Test/rehearsal helper only. Never used by production player-turn routing."""
    place = _current_place(world, player_id)
    if not place:
        raise CharacterAgentRoutingError("candidate fixture requires a grounded current place")
    visible = {
        "actor_key": "rena",
        "name": "Рена",
        "place_key": str(place["key"]),
        "place_text": str(place["name"]),
        "observed_at": int(world.now),
        "valid_until": int(world.now) + 20,
        "authority": "CANDIDATE_REHEARSAL_FIXTURE",
        "historical_claim": False,
    }
    awareness = {
        "format": "TENSURA_RECIPROCAL_AWARENESS",
        "schema_version": 1,
        "owner_key": "rena",
        "counterpart_key": player_id,
        "source_turn_key": source_turn_key,
        "world_minute": int(world.now),
        "place_key": str(place["key"]),
        "place_text": str(place["name"]),
        "observed_player_text_verbatim": raw_text,
        "authority": "CANDIDATE_REHEARSAL_FIXTURE",
        "historical_claim": False,
        "does_not_assert": ["real LIVE Rena presence", "production reciprocal awareness"],
    }
    world._put_fact103(VISIBLE_RENA_KEY, visible, "candidate:v113_routing_fixture", significance=5)
    world._put_fact103(
        reciprocal_key(source_turn_key), awareness, "candidate:v113_routing_fixture", significance=5
    )
    world.db.commit()
    return {"visibility_fact_key": VISIBLE_RENA_KEY, "awareness_fact_key": reciprocal_key(source_turn_key)}
