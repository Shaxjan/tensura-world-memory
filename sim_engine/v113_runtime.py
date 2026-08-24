from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from character_agent_contract import build_agent_context, public_observable, validate_agent_decision
from rena_character_profile import rena_profile_v1, validate_rena_profile_v1
from v03_engine import dumps
from v100_handoff import runtime_state_hash_v100

ENGINE_VERSION_V113 = "1.0.13"
CHARACTER_AGENT_RUNTIME_V113 = "character_agent_candidate_v1"
RENA_CORE_KEY_V113 = "v113:character_core:rena"
RENA_STATE_KEY_V113 = "v113:character_agent_state:rena"
RENA_DECISION_PREFIX_V113 = "v113:character_agent_decision:rena:"
RENA_RESPONSE_PREFIX_V113 = "v113:character_agent_response:rena:"
CANDIDATE_AUTHORITY_V113 = "SOURCE_GROUNDED_PROSPECTIVE_CANDIDATE"
RELATIONSHIP_AXES_V113 = ("trust", "respect", "affection", "irritation")


def _stable_digest_v113(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class V113RuntimeMixin:
    """v1.0.13 candidate Character Agent bridge.

    This mixin is development-only until an explicit activation cutover. It uses
    only existing production tables so a v1.0.12 checkpoint can be imported with
    an identical pre-activation state hash.

    The only Character Agent decision route in this candidate is an explicitly
    marked rehearsal fixture. Production gameplay routing is intentionally not
    enabled yet; a client cannot submit arbitrary context as authoritative truth.
    """

    def _rena_core_payload_v113(self) -> dict[str, Any]:
        profile = rena_profile_v1()
        errors = validate_rena_profile_v1(profile)
        if errors:
            raise RuntimeError("invalid grounded Rena profile: " + "; ".join(errors))
        return {
            "format": "TENSURA_CHARACTER_CORE",
            "schema_version": 1,
            "actor_key": "rena",
            "display_name": "Рена",
            "autonomy_tier": "tier_1_playable_alpha_candidate",
            "authority": CANDIDATE_AUTHORITY_V113,
            "historical_claim": False,
            "provenance": "engine:v113_rena_character_core",
            "materialized_at": int(self.now),
            "identity": deepcopy(profile["identity"]),
            "personality": deepcopy(profile["personality"]),
            "goals": deepcopy(profile["goals"]),
            "interests_and_competence": deepcopy(profile["interests_and_competence"]),
            "relationship_with_player": deepcopy(profile["relationship_with_player"]),
            "music_continuity": deepcopy(profile["music_continuity"]),
            "known_unknowns": deepcopy(profile["known_unknowns"]),
            "knowledge_policy": deepcopy(profile["knowledge_policy"]),
            "agent_policy": deepcopy(profile["agent_policy"]),
            "does_not_assert": deepcopy(profile["does_not_assert"]),
            "evidence_registry": deepcopy(profile["evidence_registry"]),
        }

    def character_core_v113(self, actor_key: str = "rena") -> dict[str, Any] | None:
        if actor_key != "rena":
            return None
        return self._get_fact103(RENA_CORE_KEY_V113)

    def ensure_character_core_v113(self, actor_key: str = "rena") -> dict[str, Any] | None:
        if actor_key != "rena":
            return None
        old = self.character_core_v113(actor_key)
        if old:
            return old
        core = self._rena_core_payload_v113()
        self._put_fact103(
            RENA_CORE_KEY_V113,
            core,
            "engine:v113_rena_character_core",
            significance=70,
        )
        self.db.commit()
        return self.character_core_v113(actor_key)

    def _empty_rena_agent_state_v113(self) -> dict[str, Any]:
        return {
            "format": "TENSURA_CHARACTER_AGENT_STATE",
            "schema_version": 1,
            "actor_key": "rena",
            "authority": CANDIDATE_AUTHORITY_V113,
            "activated_at": int(self.now),
            "relationship_delta_since_activation": {axis: 0 for axis in RELATIONSHIP_AXES_V113},
            "episodic_memories": [],
            "last_private_emotion": None,
            "last_decision_digest": None,
            "last_source_turn_key": None,
            "does_not_assert": [
                "absolute relationship score",
                "current emotion before a causally committed decision",
                "retroactive memory",
                "retroactive NPC response",
            ],
        }

    def character_agent_state_v113(self, actor_key: str = "rena") -> dict[str, Any] | None:
        if actor_key != "rena":
            return None
        return self._get_fact103(RENA_STATE_KEY_V113)

    def ensure_character_agent_state_v113(self, actor_key: str = "rena") -> dict[str, Any] | None:
        if actor_key != "rena":
            return None
        old = self.character_agent_state_v113(actor_key)
        if old:
            return old
        state = self._empty_rena_agent_state_v113()
        self._put_fact103(
            RENA_STATE_KEY_V113,
            state,
            "engine:v113_character_agent_state",
            significance=55,
        )
        self.db.commit()
        return self.character_agent_state_v113(actor_key)

    def activate_character_agent_v113(self) -> dict[str, Any]:
        start = int(self.now)
        cash_before = int(self.actor("player")["cash_copper"])
        region_before = str(self.actor("player")["region_id"])
        decision_count_before = int(
            self.db.execute("SELECT COUNT(*) FROM facts WHERE key LIKE ?", (RENA_DECISION_PREFIX_V113 + "%",)).fetchone()[0]
        )
        response_count_before = int(
            self.db.execute("SELECT COUNT(*) FROM facts WHERE key LIKE ?", (RENA_RESPONSE_PREFIX_V113 + "%",)).fetchone()[0]
        )

        core = self.ensure_character_core_v113("rena")
        state = self.ensure_character_agent_state_v113("rena")
        if core is None or state is None:
            raise RuntimeError("v1.0.13 candidate activation failed to materialize Rena agent state")

        if int(self.now) != start:
            raise RuntimeError("v1.0.13 candidate activation advanced world time")
        if int(self.actor("player")["cash_copper"]) != cash_before:
            raise RuntimeError("v1.0.13 candidate activation changed player cash")
        if str(self.actor("player")["region_id"]) != region_before:
            raise RuntimeError("v1.0.13 candidate activation moved the player")
        if any(int((state.get("relationship_delta_since_activation") or {}).get(axis, 0)) != 0 for axis in RELATIONSHIP_AXES_V113):
            raise RuntimeError("v1.0.13 candidate activation created relationship delta")
        if list(state.get("episodic_memories") or []):
            raise RuntimeError("v1.0.13 candidate activation created retroactive memory")
        if state.get("last_private_emotion") is not None:
            raise RuntimeError("v1.0.13 candidate activation inferred a current Rena emotion")

        decision_count_after = int(
            self.db.execute("SELECT COUNT(*) FROM facts WHERE key LIKE ?", (RENA_DECISION_PREFIX_V113 + "%",)).fetchone()[0]
        )
        response_count_after = int(
            self.db.execute("SELECT COUNT(*) FROM facts WHERE key LIKE ?", (RENA_RESPONSE_PREFIX_V113 + "%",)).fetchone()[0]
        )
        if decision_count_after != decision_count_before or response_count_after != response_count_before:
            raise RuntimeError("v1.0.13 candidate activation created retroactive NPC decision/response")

        return {
            "status": "executed",
            "accepted": True,
            "activation": "character_agent_v113_candidate",
            "actor_key": "rena",
            "world_minute": int(self.now),
            "time_advanced": 0,
            "player_choice": False,
            "core_materialized": True,
            "agent_state_materialized": True,
            "relationship_delta_created": False,
            "retroactive_memory_created": False,
            "retroactive_response_created": False,
            "current_emotion_inferred": False,
            "production_gameplay_routing_enabled": False,
            "does_not_assert": [
                "new player action",
                "new Rena action",
                "current Rena location",
                "current Rena mood",
                "new relationship state",
            ],
        }

    def build_rena_agent_context_v113(
        self,
        *,
        source_turn_key: str,
        player_utterance: str,
        causal_fact_keys: list[str],
        observations: list[dict[str, Any]],
        visible_target_keys: list[str],
        current_plan: dict[str, Any] | None = None,
        unresolved_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        core = self.ensure_character_core_v113("rena")
        if core is None:
            raise RuntimeError("Rena Character Core is unavailable")
        return build_agent_context(
            actor_key="rena",
            source_turn_key=source_turn_key,
            world_minute=int(self.now),
            player_utterance=player_utterance,
            self_core=deepcopy(core),
            causal_fact_keys=causal_fact_keys,
            observations=observations,
            visible_target_keys=visible_target_keys,
            current_plan=current_plan,
            relationship_state=deepcopy(core.get("relationship_with_player") or {}),
            unresolved_keys=unresolved_keys or [
                "rena:exact_wedding_preference",
                "rena:current_exact_mood",
                "rena:current_private_thoughts",
                "rena:unstated_later_knowledge",
            ],
        )

    def _validate_rehearsal_context_v113(self, context: dict[str, Any]) -> None:
        if not isinstance(context, dict):
            raise ValueError("candidate rehearsal context must be an object")
        if context.get("actor_key") != "rena":
            raise ValueError("v1.0.13 candidate currently calibrates only Rena")
        if int(context.get("world_minute", -1)) != int(self.now):
            raise ValueError("candidate Character Agent context is stale")
        stored_core = self.character_core_v113("rena")
        context_core = ((context.get("self") or {}).get("character_core") or {}) if isinstance(context.get("self"), dict) else {}
        if not stored_core or context_core != stored_core:
            raise ValueError("candidate context Character Core is not the engine-owned Rena core")
        if "world_state" in context or "runtime_state" in context or "other_character_private_state" in context:
            raise ValueError("candidate context contains forbidden omniscient/private state")

    def _memory_id_v113(self, source_turn_key: str, memory: dict[str, Any], digest: str) -> str:
        return _stable_digest_v113(
            {
                "actor_key": "rena",
                "source_turn_key": source_turn_key,
                "memory": memory,
                "decision_digest": digest,
            }
        )

    def commit_character_agent_decision_v113(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("mode") != "candidate_rehearsal_fixture":
            raise ValueError("v1.0.13 candidate production gameplay routing is not enabled")
        context = request.get("context")
        decision = request.get("decision")
        if not isinstance(context, dict) or not isinstance(decision, dict):
            raise ValueError("candidate decision requires context and decision objects")
        self._validate_rehearsal_context_v113(context)
        validation = validate_agent_decision(context, decision)
        if not validation.ok or not isinstance(validation.sanitized, dict) or not validation.decision_digest:
            raise ValueError("candidate Character Agent decision rejected: " + "; ".join(validation.errors))

        sanitized = validation.sanitized
        source_turn_key = str(sanitized["source_turn_key"])
        if len(source_turn_key) > 160:
            raise ValueError("candidate source_turn_key too long")
        decision_key = RENA_DECISION_PREFIX_V113 + source_turn_key
        response_key = RENA_RESPONSE_PREFIX_V113 + source_turn_key
        if self._get_fact103(decision_key) is not None or self._get_fact103(response_key) is not None:
            raise RuntimeError("Rena Character Agent decision already committed for source turn")

        state = self.ensure_character_agent_state_v113("rena")
        if state is None:
            raise RuntimeError("Rena Character Agent state missing")
        state = deepcopy(state)
        observable = public_observable(validation)
        private = sanitized.get("private") if isinstance(sanitized.get("private"), dict) else {}
        start = int(self.now)
        clock_minutes = int(observable.get("clock_minutes") or 0)
        if clock_minutes:
            self.advance(clock_minutes)

        cumulative = dict(state.get("relationship_delta_since_activation") or {})
        relationship_delta = private.get("relationship_delta") if isinstance(private.get("relationship_delta"), dict) else {}
        for axis in RELATIONSHIP_AXES_V113:
            delta = relationship_delta.get(axis, 0)
            if not isinstance(delta, int) or isinstance(delta, bool) or not -2 <= delta <= 2:
                raise RuntimeError(f"invalid committed relationship delta for {axis}")
            cumulative[axis] = int(cumulative.get(axis, 0)) + int(delta)
        state["relationship_delta_since_activation"] = cumulative

        memories = list(state.get("episodic_memories") or [])
        seen = {str(item.get("memory_id")) for item in memories if isinstance(item, dict)}
        for memory in list(private.get("memory_proposals") or []):
            if not isinstance(memory, dict):
                raise RuntimeError("invalid committed Rena memory proposal")
            memory_id = self._memory_id_v113(source_turn_key, memory, validation.decision_digest)
            if memory_id in seen:
                continue
            memories.append(
                {
                    "memory_id": memory_id,
                    "source_turn_key": source_turn_key,
                    "decision_digest": validation.decision_digest,
                    "committed_at": int(self.now),
                    "memory": deepcopy(memory),
                }
            )
            seen.add(memory_id)
        state["episodic_memories"] = memories
        emotion = private.get("emotion_state")
        state["last_private_emotion"] = emotion if isinstance(emotion, str) else None
        state["last_decision_digest"] = validation.decision_digest
        state["last_source_turn_key"] = source_turn_key
        state["updated_at"] = int(self.now)

        decision_record = {
            "format": "TENSURA_COMMITTED_CHARACTER_AGENT_DECISION",
            "schema_version": 1,
            "actor_key": "rena",
            "source_turn_key": source_turn_key,
            "context_digest": _stable_digest_v113(context),
            "decision_digest": validation.decision_digest,
            "decision": deepcopy(sanitized),
            "world_minute_start": start,
            "world_minute_end": int(self.now),
            "authority": "CANDIDATE_RUNTIME_COMMITTED",
            "mode": "candidate_rehearsal_fixture",
        }
        response_record = {
            "format": "TENSURA_NPC_RESPONSE",
            "schema_version": 1,
            "response_key": response_key,
            "actor_key": "rena",
            "actor_name": "Рена",
            "counterpart_key": "player",
            "source_turn_key": source_turn_key,
            "world_minute": int(self.now),
            "response_kind": "character_agent_validated_observable",
            "speech_act": observable.get("speech_act"),
            "surface_text": observable.get("surface_text"),
            "action_kind": observable.get("action_kind"),
            "target_key": observable.get("target_key"),
            "clock_minutes": clock_minutes,
            "observation_basis": "candidate_rehearsal_direct_scene_fixture",
            "authority": "CANDIDATE_RUNTIME_COMMITTED",
            "private_state_exposed": False,
            "does_not_assert": [
                "canonical Rena dialogue",
                "production Character Agent routing",
                "Rena private emotion to narrator/player",
                "absolute relationship score",
            ],
        }

        self._put_fact103(RENA_STATE_KEY_V113, state, "engine:v113_character_agent_state", significance=60)
        self._put_fact103(decision_key, decision_record, "engine:v113_character_agent_decision", significance=55)
        self._put_fact103(response_key, response_record, "engine:v113_character_agent_response", significance=50)
        self.db.execute(
            "INSERT OR REPLACE INTO actor_knowledge(actor_id,fact_key,confidence,learned_at,source) VALUES(?,?,?,?,?)",
            ("player", response_key, 100, int(self.now), "direct_character_agent_response_v113_candidate"),
        )
        region_id = str(self.actor("player")["region_id"])
        self.db.execute(
            "INSERT INTO events(world_minute,event_type,region_id,actor_id,faction_id,significance,payload_json,visibility) VALUES(?,?,?,?,?,?,?,?)",
            (
                int(self.now),
                "character_agent_response_committed",
                region_id,
                None,
                None,
                50,
                dumps(
                    {
                        "actor_key": "rena",
                        "source_turn_key": source_turn_key,
                        "decision_digest": validation.decision_digest,
                        "response_key": response_key,
                        "speech_act": observable.get("speech_act"),
                        "mode": "candidate_rehearsal_fixture",
                    }
                ),
                "player",
            ),
        )
        self.db.commit()

        return {
            "status": "executed",
            "accepted": True,
            "outcome": "character_agent_response_committed",
            "actor_key": "rena",
            "source_turn_key": source_turn_key,
            "decision_digest": validation.decision_digest,
            "npc_response": response_record,
            "world_minute_start": start,
            "world_minute_end": int(self.now),
            "clock_minutes": clock_minutes,
            "private_state_exposed": False,
            "production_gameplay_routing_enabled": False,
        }

    def build_gm_packet(self, player_id: str = "player"):
        packet = super().build_gm_packet(player_id)
        packet.setdefault("constraints", {})["character_agent_v113_candidate"] = (
            "Character Agent private state is not narrator knowledge. Only a committed runtime event public observable "
            "may be narrated. v1.0.13 candidate fixture routing is not production gameplay routing."
        )
        packet["runtime"] = {"engine": ENGINE_VERSION_V113}
        return packet

    def build_session_state_v113(
        self,
        *,
        journal_seq: int,
        head_state_hash: str,
        last_event=None,
        preserved_last_turn=None,
    ) -> dict[str, Any]:
        event_type = (last_event or {}).get("event_type")
        hide_candidate_event = event_type in {"character_agent_v113_activation", "character_agent_decision_v113"}
        state = super().build_session_state_v112(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=None if hide_candidate_event else last_event,
            preserved_last_turn=preserved_last_turn,
        )
        state["engine_version"] = ENGINE_VERSION_V113
        state["character_agent_runtime"] = {
            "version": CHARACTER_AGENT_RUNTIME_V113,
            "status": "candidate_not_live",
            "calibrated_named_characters": ["rena"],
            "production_gameplay_routing_enabled": False,
            "private_state_not_narrator_knowledge": True,
            "replay_uses_committed_structured_decision": True,
            "retroactive_resolution": False,
        }
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type not in {"character_agent_v113_activation", "character_agent_decision_v113"}:
            return super().execute_runtime_event(seq, event_key, event_type, request)
        old = self.db.execute(
            "SELECT * FROM runtime_journal WHERE event_key=? OR seq=?", (event_key, int(seq))
        ).fetchone()
        if old:
            if str(old["event_key"]) != event_key or int(old["seq"]) != int(seq):
                raise RuntimeError("journal sequence collision")
            return {"accepted": True, "replayed": True, "journal": self.export_runtime_journal_entry(event_key)}

        source_v = self._source_live_version_v100()
        before = runtime_state_hash_v100(self, source_v)
        start = int(self.now)
        if event_type == "character_agent_v113_activation":
            result = self.activate_character_agent_v113()
            if int(self.now) != start:
                raise RuntimeError("v1.0.13 candidate activation advanced world time")
        else:
            result = self.commit_character_agent_decision_v113(request)
        after = runtime_state_hash_v100(self, source_v)
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, int(self.now), dumps(request), dumps(result), before, after, int(self.now)),
        )
        self.db.commit()
        return {
            "accepted": True,
            "replayed": False,
            "result": result,
            "journal": self.export_runtime_journal_entry(event_key),
        }
