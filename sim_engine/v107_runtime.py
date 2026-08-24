from __future__ import annotations

from typing import Any

from v03_engine import dumps
from v100_handoff import runtime_state_hash_v100
from v104_runtime import BORGA_CORE_KEY

ENGINE_VERSION_V107 = "1.0.7"
BORGA_MEMORY_MODEL_V107 = "causal_encounter_memory_v1"
_MEMORY_COMPONENTS_V107 = {"speech_or_request", "interaction_attempt", "handoff_offer", "performance"}


class V107RuntimeMixin:
    """v1.0.7: fact-backed causal encounter memory for persistent named characters.

    This first calibration is intentionally limited to Borga. A memory is created
    only from a newly accepted, explicitly Borga-addressed player scene action while
    Borga is already causally visible. Direct player observation alone is one-way and
    never creates a Borga memory.
    """

    def _borga_visible_to_player_v107(self, player_id: str = "player") -> bool:
        return any(
            str(row.get("actor") or "") == "borga" and str(row.get("status") or "") == "visible"
            for row in self._visible_named103(player_id)
        )

    def _explicit_borga_mention_v107(self, raw_text: str) -> bool:
        return any(str(row.get("id") or "") == "borga" for row in self._safe_named_mentions_v106(raw_text))

    @staticmethod
    def _observable_components_v107(result: dict[str, Any]) -> list[dict[str, Any]]:
        proposal = result.get("proposal") if isinstance(result, dict) else None
        rows = list((proposal or {}).get("components") or []) if isinstance(proposal, dict) else []
        return [dict(row) for row in rows if isinstance(row, dict) and row.get("kind") in _MEMORY_COMPONENTS_V107]

    def _eligible_borga_encounter_memory_v107(
        self,
        raw_text: str,
        result: dict[str, Any],
        *,
        player_id: str,
    ) -> list[dict[str, Any]]:
        if player_id != "player":
            return []
        if not isinstance(result, dict) or not result.get("accepted"):
            return []
        if str(result.get("status") or "") not in {"scene_pending", "executed"}:
            return []
        if not self._explicit_borga_mention_v107(raw_text):
            return []
        if not self._borga_visible_to_player_v107(player_id):
            return []
        return self._observable_components_v107(result)

    def _record_borga_encounter_memory_v107(
        self,
        turn_key: str,
        raw_text: str,
        components: list[dict[str, Any]],
        *,
        player_id: str = "player",
    ) -> dict[str, Any] | None:
        memory_key = f"v107:character_memory:borga:{turn_key}"
        old = self._get_fact103(memory_key)
        if old:
            return old

        place = self._place103(player_id)
        if not place or not self._borga_visible_to_player_v107(player_id):
            return None
        core = self.ensure_character_core_v104("borga")
        if core is None:
            return None

        component_kinds = [str(row.get("kind")) for row in components if row.get("kind")]
        memory = {
            "format": "TENSURA_CHARACTER_MEMORY",
            "schema_version": 1,
            "memory_key": memory_key,
            "owner_key": "borga",
            "kind": "direct_encounter_observation",
            "counterpart_key": player_id,
            "world_minute": int(self.now),
            "region_id": str(place["region_id"]),
            "place_key": str(place["key"]),
            "place_text": str(place["name"]),
            "source_turn_key": str(turn_key),
            "observed_player_text_verbatim": str(raw_text),
            "observed_component_kinds": component_kinds,
            "causal_basis": "Borga was already directly visible in the same local scene and the accepted action explicitly addressed Borga",
            "confidence": 100,
            "emotional_interpretation": None,
            "relationship_delta": None,
            "response_or_consent": "UNRESOLVED_UNLESS_SEPARATELY_ENGINE_RESOLVED",
            "authority": "ENGINE_CAUSAL_OBSERVATION",
            "provenance": "engine:v107_causal_encounter_memory",
            "does_not_assert": [
                "Borga approval or disapproval",
                "Borga emotion",
                "relationship change",
                "Borga reply",
                "consent or acceptance",
                "truth of any proposition spoken by the player",
            ],
        }
        self._put_fact103(
            memory_key,
            memory,
            "engine:v107_causal_encounter_memory",
            significance=60,
            origin_region_id=str(place["region_id"]),
        )

        next_core = dict(core)
        refs = list(next_core.get("memories") or [])
        if not any(isinstance(row, dict) and row.get("memory_key") == memory_key for row in refs):
            refs.append({
                "memory_key": memory_key,
                "kind": "direct_encounter_observation",
                "counterpart_key": player_id,
                "observed_at": int(self.now),
                "source_turn_key": str(turn_key),
            })
        next_core["memories"] = refs
        next_core["memory_model"] = {
            "version": BORGA_MEMORY_MODEL_V107,
            "storage": "authoritative_facts_with_character_core_references",
            "retroactive_inference": False,
            "emotion_inference": False,
            "relationship_mutation": False,
        }
        self._put_fact103(
            BORGA_CORE_KEY,
            next_core,
            "engine:v104_character_core",
            significance=60,
            origin_region_id="eurazania",
        )
        self.db.execute(
            "INSERT INTO events(world_minute,event_type,region_id,actor_id,faction_id,significance,payload_json,visibility) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                self.now,
                "character_memory_recorded",
                str(place["region_id"]),
                None,
                None,
                45,
                dumps({"owner_key": "borga", "memory_key": memory_key, "source_turn_key": turn_key}),
                "engine_hidden",
            ),
        )
        self.db.commit()
        return memory

    def _refresh_public_turn_after_memory_v107(
        self,
        turn_key: str,
        public: dict[str, Any],
        *,
        player_id: str,
    ) -> dict[str, Any]:
        turn = self.db.execute("SELECT id FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if turn is None:
            return public
        packet = self.build_gm_packet(player_id)
        checkpoint = self.write_checkpoint(player_id, turn_id=int(turn["id"]), kind="v107_causal_encounter_memory")
        out = dict(public)
        out["gm_packet"] = packet
        out["checkpoint"] = checkpoint
        self.db.execute(
            "UPDATE gm_turns SET gm_packet_json=?,checkpoint_hash=?,public_result_json=? WHERE id=?",
            (dumps(packet), checkpoint["state_hash"], dumps(out), int(turn["id"])),
        )
        self.db.commit()
        return out

    def process_player_turn(
        self,
        turn_key: str,
        raw_text: str,
        *,
        player_id: str = "player",
        external_intent: dict[str, Any] | None = None,
    ):
        preexisting = self.db.execute("SELECT 1 FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone() is not None
        result = super().process_player_turn(
            turn_key,
            raw_text,
            player_id=player_id,
            external_intent=external_intent,
        )
        if preexisting:
            return result
        components = self._eligible_borga_encounter_memory_v107(raw_text, result, player_id=player_id)
        if not components:
            return result
        memory = self._record_borga_encounter_memory_v107(
            turn_key,
            raw_text,
            components,
            player_id=player_id,
        )
        if memory is None:
            return result
        return self._refresh_public_turn_after_memory_v107(turn_key, result, player_id=player_id)

    def activate_causal_encounter_memory_v107(self) -> dict[str, Any]:
        start = int(self.now)
        core = self.ensure_character_core_v104("borga")
        if core is None:
            raise RuntimeError("v1.0.7 activation requires Borga Character Core")
        memories_before = list(core.get("memories") or [])
        next_core = dict(core)
        next_core["memory_model"] = {
            "version": BORGA_MEMORY_MODEL_V107,
            "storage": "authoritative_facts_with_character_core_references",
            "retroactive_inference": False,
            "emotion_inference": False,
            "relationship_mutation": False,
        }
        self._put_fact103(
            BORGA_CORE_KEY,
            next_core,
            "engine:v104_character_core",
            significance=60,
            origin_region_id="eurazania",
        )
        self.db.commit()
        if int(self.now) != start:
            raise RuntimeError("v1.0.7 memory activation advanced world time")
        if list(next_core.get("memories") or []) != memories_before:
            raise RuntimeError("v1.0.7 activation created retroactive character memory")
        return {
            "status": "executed",
            "accepted": True,
            "activation": "causal_encounter_memory_v107",
            "world_minute": int(self.now),
            "actor_key": "borga",
            "existing_memory_count_preserved": len(memories_before),
            "time_advanced": 0,
            "player_choice": False,
            "retroactive_memory_created": False,
            "does_not_assert": [
                "Borga noticed the player during prior one-way search",
                "Borga emotion",
                "relationship change",
                "new player action",
            ],
        }

    def build_gm_packet(self, player_id="player"):
        base = super().build_gm_packet(player_id)
        base.setdefault("constraints", {})["character_memory"] = (
            "A named character remembers only causally observed encounters. Player observation is not reciprocal awareness. "
            "Memory does not imply emotion, relationship change, reply, consent or belief in spoken claims."
        )
        base["runtime"] = {"engine": ENGINE_VERSION_V107}
        return base

    def build_session_state_v107(
        self,
        *,
        journal_seq: int,
        head_state_hash: str,
        last_event=None,
        preserved_last_turn=None,
    ) -> dict[str, Any]:
        state = super().build_session_state_v106(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=None if (last_event or {}).get("event_type") == "causal_encounter_memory_activation" else last_event,
            preserved_last_turn=preserved_last_turn,
        )
        state["engine_version"] = ENGINE_VERSION_V107
        state["memory_runtime"] = {
            "version": BORGA_MEMORY_MODEL_V107,
            "calibrated_named_characters": ["borga"],
            "storage": "authoritative_facts_with_character_core_references",
            "reciprocal_awareness_required": True,
            "retroactive_inference": False,
            "emotion_inference": False,
            "relationship_mutation": False,
            "private_memory_not_narrator_knowledge": True,
        }
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type != "causal_encounter_memory_activation":
            return super().execute_runtime_event(seq, event_key, event_type, request)
        old = self.db.execute(
            "SELECT * FROM runtime_journal WHERE event_key=? OR seq=?",
            (event_key, int(seq)),
        ).fetchone()
        if old:
            if str(old["event_key"]) != event_key or int(old["seq"]) != int(seq):
                raise RuntimeError("journal sequence collision")
            return {"accepted": True, "replayed": True, "journal": self.export_runtime_journal_entry(event_key)}
        source_v = self._source_live_version_v100()
        before = runtime_state_hash_v100(self, source_v)
        result = self.activate_causal_encounter_memory_v107()
        after = runtime_state_hash_v100(self, source_v)
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before, after, self.now),
        )
        self.db.commit()
        return {"accepted": True, "replayed": False, "result": result, "journal": self.export_runtime_journal_entry(event_key)}
