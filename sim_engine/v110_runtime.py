from __future__ import annotations

from typing import Any

from v03_engine import dumps, loads
from v100_handoff import runtime_state_hash_v100
from v101_runtime import _norm
from v104_runtime import BORGA_CORE_KEY

ENGINE_VERSION_V110 = "1.0.10"
RESPONSE_MODEL_V110 = "causal_npc_response_v1"
RESPONSE_POLICY_V110 = "v110_borga_minimal_greeting_v1"

_GREETING_SURFACES = (
    ("доброе утро", "Доброе утро."),
    ("добрый день", "Добрый день."),
    ("добрый вечер", "Добрый вечер."),
    ("здравствуйте", "Здравствуйте."),
    ("здравствуй", "Здравствуй."),
    ("привет", "Привет."),
)
_CONTENTFUL_MARKERS = (
    "прошу", "спрашива", "предлага", "можешь", "можете", "почему", "зачем",
    "где ", "когда", "что ", "как дела", "расскажи", "скажи",
)


class V110RuntimeMixin:
    """v1.0.10: first bounded authoritative NPC response resolver.

    Calibration is deliberately narrow: a directly visible Borga may return one
    simple greeting while his current Character Plan grounds him at the same duty
    site. The resolver does not infer personality, emotion, relationship or a
    willingness to continue a conversation.
    """

    @staticmethod
    def _greeting_surface_v110(raw_text: str) -> str | None:
        low = _norm(raw_text)
        if "?" in str(raw_text) or any(marker in low for marker in _CONTENTFUL_MARKERS):
            return None
        matches = [surface for marker, surface in _GREETING_SURFACES if marker in low]
        return matches[0] if len(matches) == 1 else None

    def _borga_response_policy_v110(self) -> dict[str, Any] | None:
        core = self.character_core_v104("borga") or {}
        policy = core.get("response_policy")
        return dict(policy) if isinstance(policy, dict) and policy.get("version") == RESPONSE_POLICY_V110 else None

    def _eligible_borga_greeting_v110(
        self,
        turn_key: str,
        raw_text: str,
        public: dict[str, Any],
        *,
        player_id: str = "player",
    ) -> dict[str, Any] | None:
        if player_id != "player" or not isinstance(public, dict) or not public.get("accepted"):
            return None
        if str(public.get("status") or "") != "executed":
            return None
        proposal = public.get("proposal") if isinstance(public.get("proposal"), dict) else {}
        if list(proposal.get("pending") or []):
            return None
        components = [x for x in list(proposal.get("components") or []) if isinstance(x, dict)]
        if not any(x.get("kind") == "speech_or_request" for x in components):
            return None
        mentions = self._safe_named_mentions_v106(raw_text)
        if len(mentions) != 1 or str(mentions[0].get("id") or "") != "borga":
            return None
        surface = self._greeting_surface_v110(raw_text)
        if surface is None or not self._borga_visible_to_player_v107(player_id):
            return None
        if self._borga_response_policy_v110() is None:
            return None
        memory_key = f"v107:character_memory:borga:{turn_key}"
        if self._get_fact103(memory_key) is None:
            return None
        place = self._place103(player_id)
        presence = self._borga_presence103(self.now)
        if not place or not presence or presence.get("place_key") != place.get("key"):
            return None
        plan = self.ensure_character_plan_v104("borga", self.now)
        block = self._plan_block_v104(plan, self.now % 1440) if plan else {}
        if str(block.get("kind") or "") != "role_duty" or block.get("place_key") != place.get("key"):
            return None
        return {
            "surface_text": surface,
            "place_key": str(place["key"]),
            "place_text": str(place["name"]),
            "memory_key": memory_key,
        }

    def _record_borga_greeting_response_v110(
        self,
        turn_key: str,
        context: dict[str, Any],
        *,
        player_id: str = "player",
    ) -> dict[str, Any]:
        key = f"v110:player_observed_response:borga:{turn_key}"
        old = self._get_fact103(key)
        if old:
            return old
        response = {
            "format": "TENSURA_NPC_RESPONSE",
            "schema_version": 1,
            "response_key": key,
            "actor_key": "borga",
            "actor_name": "Борга",
            "counterpart_key": player_id,
            "source_turn_key": turn_key,
            "world_minute": int(self.now),
            "region_id": "eurazania",
            "place_key": context["place_key"],
            "place_text": context["place_text"],
            "response_kind": "minimal_reciprocal_greeting",
            "speech_act": "return_greeting",
            "surface_text": context["surface_text"],
            "clock_minutes": 0,
            "observation_basis": "direct_same_scene_npc_response",
            "authority": "NON_CANON_MECHANICAL_PROSPECTIVE",
            "emotion": None,
            "relationship_delta": None,
            "conversation_commitment": None,
            "provenance": "engine:v110_causal_npc_response",
            "does_not_assert": [
                "Borga emotion or tone",
                "approval or disapproval",
                "relationship change",
                "willingness to continue talking",
                "hidden reason for responding",
                "hidden Character Plan details",
            ],
        }
        self._put_fact103(
            key,
            response,
            "engine:v110_causal_npc_response",
            significance=45,
            origin_region_id="eurazania",
        )
        self.db.execute(
            "INSERT OR REPLACE INTO actor_knowledge(actor_id,fact_key,confidence,learned_at,source) VALUES(?,?,?,?,?)",
            (player_id, key, 100, self.now, "direct_npc_response_v110"),
        )
        self.db.execute(
            "INSERT INTO events(world_minute,event_type,region_id,actor_id,faction_id,significance,payload_json,visibility) VALUES(?,?,?,?,?,?,?,?)",
            (
                self.now,
                "npc_response_resolved",
                "eurazania",
                None,
                None,
                40,
                dumps({
                    "actor_key": "borga",
                    "counterpart_key": player_id,
                    "response_key": key,
                    "speech_act": "return_greeting",
                    "source_turn_key": turn_key,
                }),
                "player",
            ),
        )
        self.db.commit()
        return response

    def _refresh_public_after_response_v110(
        self,
        turn_key: str,
        public: dict[str, Any],
        response: dict[str, Any],
        *,
        player_id: str = "player",
    ) -> dict[str, Any]:
        turn = self.db.execute("SELECT id FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if turn is None:
            return public
        action = self.db.execute("SELECT id,effect_json FROM scene_actions WHERE turn_key=?", (turn_key,)).fetchone()
        if action is not None:
            effect = loads(action["effect_json"], {})
            if not isinstance(effect, dict):
                effect = {}
            effect["npc_response"] = {
                "response_key": response["response_key"],
                "actor_key": "borga",
                "speech_act": response["speech_act"],
                "surface_text": response["surface_text"],
                "clock_minutes": 0,
            }
            self.db.execute(
                "UPDATE scene_actions SET status='resolved',resolution_mode='engine_v110_causal_npc_response',effect_json=? WHERE id=?",
                (dumps(effect), int(action["id"])),
            )
        out = dict(public)
        out["status"] = "executed"
        out["result"] = {"outcome": "npc_response_resolved", "npc_response": response}
        out["npc_response"] = response
        packet = dict(out.get("gm_packet") or {})
        scene = dict(packet.get("scene") or {})
        scene["npc_response"] = response
        packet["scene"] = scene
        out["gm_packet"] = packet
        contract = dict(out.get("narration_contract") or {})
        must = [x for x in list(contract.get("must_preserve") or []) if x != "pending outcomes remain pending"]
        must.extend([
            "Borga returned the greeting with the engine-provided surface_text",
            "world minute is unchanged because the exchange is sub-minute",
            "no relationship or emotion was inferred",
        ])
        contract["must_preserve"] = list(dict.fromkeys(must))
        contract["may_add"] = [
            "quote the engine-provided Borga greeting verbatim",
            "sensory description already supported by the current scene",
        ]
        contract["forbidden"] = list(dict.fromkeys(list(contract.get("forbidden") or []) + [
            "invent Borga tone, emotion, approval or hostility",
            "invent relationship change",
            "claim Borga agreed to continue the conversation",
            "expose hidden Character Plan or scheduler reasons",
        ]))
        out["narration_contract"] = contract
        checkpoint = self.write_checkpoint(player_id, turn_id=int(turn["id"]), kind="v110_causal_npc_response")
        out["checkpoint"] = checkpoint
        self.db.execute(
            "UPDATE gm_turns SET status='executed',engine_result_json=?,gm_packet_json=?,narration_contract_json=?,checkpoint_hash=?,public_result_json=?,completed_at=? WHERE id=?",
            (
                dumps(out["result"]),
                dumps(packet),
                dumps(contract),
                checkpoint["state_hash"],
                dumps(out),
                self.now,
                int(turn["id"]),
            ),
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
        public = super().process_player_turn(
            turn_key,
            raw_text,
            player_id=player_id,
            external_intent=external_intent,
        )
        if preexisting:
            return public
        context = self._eligible_borga_greeting_v110(turn_key, raw_text, public, player_id=player_id)
        if context is None:
            return public
        response = self._record_borga_greeting_response_v110(turn_key, context, player_id=player_id)
        return self._refresh_public_after_response_v110(turn_key, public, response, player_id=player_id)

    def activate_causal_npc_response_v110(self) -> dict[str, Any]:
        start = int(self.now)
        core = self.ensure_character_core_v104("borga")
        if core is None:
            raise RuntimeError("v1.0.10 activation requires Borga Character Core")
        memories_before = list(core.get("memories") or [])
        relationships_before = dict(core.get("relationships") or {})
        personality_before = dict(core.get("personality") or {})
        response_count_before = int(self.db.execute("SELECT COUNT(*) FROM facts WHERE key LIKE 'v110:player_observed_response:borga:%'").fetchone()[0])
        next_core = dict(core)
        next_core["response_policy"] = {
            "version": RESPONSE_POLICY_V110,
            "authority": "NON_CANON_MECHANICAL_PROSPECTIVE",
            "scope": "simple_direct_greeting_only",
            "requires": [
                "explicit Borga address",
                "direct current visibility",
                "causal encounter memory for this turn",
                "current exact Character Plan role-duty presence at the same place",
                "no contentful request/question markers",
            ],
            "outcome": "minimal_reciprocal_greeting",
            "surface_rule": "mirror one recognized greeting phrase canonically",
            "clock_minutes": 0,
            "retroactive_resolution": False,
            "personality_inference": False,
            "emotion_inference": False,
            "relationship_mutation": False,
            "outside_scope": "remain unresolved until a later response model supports it",
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
            raise RuntimeError("v1.0.10 activation advanced world time")
        if list(next_core.get("memories") or []) != memories_before:
            raise RuntimeError("v1.0.10 activation changed Borga memories")
        if dict(next_core.get("relationships") or {}) != relationships_before:
            raise RuntimeError("v1.0.10 activation changed Borga relationships")
        if dict(next_core.get("personality") or {}) != personality_before:
            raise RuntimeError("v1.0.10 activation changed Borga personality")
        response_count_after = int(self.db.execute("SELECT COUNT(*) FROM facts WHERE key LIKE 'v110:player_observed_response:borga:%'").fetchone()[0])
        if response_count_after != response_count_before:
            raise RuntimeError("v1.0.10 activation created retroactive NPC response")
        return {
            "status": "executed",
            "accepted": True,
            "activation": "causal_npc_response_v110",
            "world_minute": int(self.now),
            "actor_key": "borga",
            "policy_version": RESPONSE_POLICY_V110,
            "existing_response_count_preserved": response_count_before,
            "time_advanced": 0,
            "player_choice": False,
            "retroactive_response_created": False,
            "does_not_assert": [
                "response to any pre-v1.0.10 greeting",
                "Borga personality",
                "Borga emotion",
                "relationship change",
                "new player action",
            ],
        }

    def build_gm_packet(self, player_id: str = "player"):
        base = super().build_gm_packet(player_id)
        base.setdefault("constraints", {})["causal_npc_response"] = (
            "Only engine-resolved NPC response semantics may be narrated as an NPC action. "
            "A minimal greeting response does not imply emotion, relationship change or willingness to continue talking."
        )
        base["runtime"] = {"engine": ENGINE_VERSION_V110}
        return base

    def build_session_state_v110(
        self,
        *,
        journal_seq: int,
        head_state_hash: str,
        last_event=None,
        preserved_last_turn=None,
    ) -> dict[str, Any]:
        state = super().build_session_state_v109(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=None if (last_event or {}).get("event_type") == "causal_npc_response_activation" else last_event,
            preserved_last_turn=preserved_last_turn,
        )
        state["engine_version"] = ENGINE_VERSION_V110
        state["response_runtime"] = {
            "version": RESPONSE_MODEL_V110,
            "calibrated_named_characters": ["borga"],
            "supported_response": "simple_direct_greeting",
            "retroactive_resolution": False,
            "personality_inference": False,
            "emotion_inference": False,
            "relationship_mutation": False,
            "hidden_decision_basis_not_narrator_knowledge": True,
        }
        return state

    def execute_runtime_event(self, seq: int, event_key: str, event_type: str, request: dict[str, Any]):
        if event_type != "causal_npc_response_activation":
            return super().execute_runtime_event(seq, event_key, event_type, request)
        old = self.db.execute("SELECT * FROM runtime_journal WHERE event_key=? OR seq=?", (event_key, int(seq))).fetchone()
        if old:
            if str(old["event_key"]) != event_key or int(old["seq"]) != int(seq):
                raise RuntimeError("journal sequence collision")
            return {"accepted": True, "replayed": True, "journal": self.export_runtime_journal_entry(event_key)}
        source_v = self._source_live_version_v100()
        before = runtime_state_hash_v100(self, source_v)
        result = self.activate_causal_npc_response_v110()
        after = runtime_state_hash_v100(self, source_v)
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before, after, self.now),
        )
        self.db.commit()
        return {"accepted": True, "replayed": False, "result": result, "journal": self.export_runtime_journal_entry(event_key)}
