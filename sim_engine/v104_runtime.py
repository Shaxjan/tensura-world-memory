from __future__ import annotations

from typing import Any

from v03_engine import dumps, loads
from v100_handoff import runtime_state_hash_v100
from v103_runtime import _stable

ENGINE_VERSION_V104 = "1.0.4"
CHARACTER_CORE_AUTHORITY = "NON_CANON_MECHANICAL_PROSPECTIVE"
BORGA_CORE_KEY = "v104:character_core:borga"
BORGA_WORK_PLACES = (
    "eurazania_borga_big_training_yard",
    "eurazania_small_training_yard",
    "eurazania_west_training_field",
)


class V104RuntimeMixin:
    """v1.0.4 persistent Character Core for the first calibrated named NPC."""

    def _latest_borga_anchor_v104(self) -> dict[str, Any] | None:
        rows = self.db.execute(
            "SELECT key,value_json,created_at FROM facts "
            "WHERE key LIKE 'v103:named_presence:borga:%' ORDER BY created_at DESC,key DESC"
        ).fetchall()
        for row in rows:
            value = loads(row["value_json"], {})
            if not isinstance(value, dict):
                continue
            place_key = value.get("place_key")
            if place_key in BORGA_WORK_PLACES:
                return {
                    "place_key": place_key,
                    "place_text": value.get("place_text"),
                    "slot_start": value.get("slot_start"),
                    "slot_end": value.get("slot_end"),
                    "source_fact_key": str(row["key"]),
                }
        return None

    def character_core_v104(self, actor_key: str) -> dict[str, Any] | None:
        if actor_key != "borga":
            return None
        return self._get_fact103(BORGA_CORE_KEY)

    def ensure_character_core_v104(self, actor_key: str = "borga") -> dict[str, Any] | None:
        if actor_key != "borga":
            return None
        old = self.character_core_v104(actor_key)
        if old:
            return old

        anchor = self._latest_borga_anchor_v104()
        core = {
            "format": "TENSURA_CHARACTER_CORE",
            "schema_version": 1,
            "actor_key": "borga",
            "display_name": "Борга",
            "autonomy_tier": "tier_1_prototype",
            "authority": CHARACTER_CORE_AUTHORITY,
            "historical_claim": False,
            "materialized_at": int(self.now),
            "identity": {
                "status": "persistent_named_character",
                "region_id": "eurazania",
            },
            "personality": {
                "status": "not_yet_authored",
                "traits": [],
                "values": [],
                "fears": [],
                "preferences": [],
            },
            "goals": [
                {
                    "goal_key": "fulfill_training_duties",
                    "kind": "role_duty",
                    "status": "active",
                    "priority": 70,
                    "basis": "v103_calibrated_training_work_context",
                }
            ],
            "obligations": [
                {
                    "obligation_key": "eurazania_training_work",
                    "kind": "work",
                    "status": "active",
                    "place_scope": list(BORGA_WORK_PLACES),
                    "basis": "v103_calibrated_training_work_context",
                }
            ],
            "relationships": {},
            "memories": [],
            "knowledge_policy": {
                "rule": "SOURCE -> TRANSMISSION -> TIME -> RECIPIENT",
                "private_unknown_stays_unknown": True,
            },
            "needs": {"status": "not_yet_modeled"},
            "resources": {"status": "not_yet_modeled"},
            "planning": {
                "model": "v104_daily_role_plan",
                "current_plan_key": None,
                "migration_anchor": anchor,
            },
            "does_not_assert": [
                "unsupported personality traits",
                "unsupported private memories",
                "unsupported relationships",
                "unsupported possessions",
                "exact location during unresolved or travel blocks",
            ],
        }
        self._put_fact103(
            BORGA_CORE_KEY,
            core,
            "engine:v104_character_core",
            significance=60,
            origin_region_id="eurazania",
        )
        self.db.execute(
            "INSERT INTO events(world_minute,event_type,region_id,actor_id,faction_id,significance,payload_json,visibility) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                self.now,
                "character_core_materialized",
                "eurazania",
                None,
                None,
                60,
                dumps(
                    {
                        "actor_key": "borga",
                        "authority": CHARACTER_CORE_AUTHORITY,
                        "personality_status": "not_yet_authored",
                        "historical_claim": False,
                    }
                ),
                "world",
            ),
        )
        self.db.commit()
        return core

    def _ordered_work_places_v104(self, day: int, anchor_place: str | None) -> list[str]:
        places = list(BORGA_WORK_PLACES)
        if anchor_place in places:
            places.remove(anchor_place)
            ordered = [anchor_place]
        else:
            ordered = []
        while places:
            idx = _stable(
                f"v104-borga-place-order|{day}|{len(ordered)}|{self._source_live_version_v100()}",
                len(places),
            )
            ordered.append(places.pop(idx))
        return ordered

    def _plan_key_v104(self, actor_key: str, day: int) -> str:
        return f"v104:character_plan:{actor_key}:day:{int(day)}"

    def ensure_character_plan_v104(self, actor_key: str = "borga", at_minute: int | None = None) -> dict[str, Any] | None:
        if actor_key != "borga":
            return None
        core = self.ensure_character_core_v104(actor_key)
        minute = int(self.now if at_minute is None else at_minute)
        day = minute // 1440
        key = self._plan_key_v104(actor_key, day)
        old = self._get_fact103(key)
        if old:
            return old

        day_start = day * 1440
        anchor = (core.get("planning") or {}).get("migration_anchor")
        anchor_place = None
        if isinstance(anchor, dict):
            anchor_minute = anchor.get("slot_start")
            if isinstance(anchor_minute, int) and anchor_minute // 1440 == day:
                anchor_place = anchor.get("place_key")
        ordered = self._ordered_work_places_v104(day, anchor_place)
        p1, p2, p3 = ordered

        blocks = [
            {"start": 420, "end": 540, "kind": "role_duty", "place_key": p1},
            {"start": 540, "end": 552, "kind": "local_travel", "from_place_key": p1, "to_place_key": p2},
            {"start": 552, "end": 660, "kind": "role_duty", "place_key": p2},
            {"start": 660, "end": 690, "kind": "unresolved_personal_time"},
            {"start": 690, "end": 810, "kind": "role_duty", "place_key": p3},
            {"start": 810, "end": 840, "kind": "unresolved_personal_time"},
            {"start": 840, "end": 960, "kind": "role_duty", "place_key": p1},
            {"start": 960, "end": 972, "kind": "local_travel", "from_place_key": p1, "to_place_key": p2},
            {"start": 972, "end": 1080, "kind": "role_duty", "place_key": p2},
        ]
        plan = {
            "format": "TENSURA_CHARACTER_PLAN",
            "schema_version": 1,
            "actor_key": "borga",
            "day": day,
            "day_start": day_start,
            "authority": CHARACTER_CORE_AUTHORITY,
            "historical_claim": False,
            "generated_at": int(self.now),
            "goal_key": "fulfill_training_duties",
            "blocks": blocks,
            "outside_blocks": {
                "kind": "unresolved_region_activity",
                "region_id": "eurazania",
                "exact_place": None,
            },
            "migration_anchor_used": anchor_place,
            "does_not_assert": [
                "personality",
                "dialogue",
                "private motivation",
                "exact travel geometry",
                "exact place outside role-duty blocks",
            ],
        }
        self._put_fact103(
            key,
            plan,
            "engine:v104_character_plan",
            significance=45,
            origin_region_id="eurazania",
        )
        core = dict(core)
        planning = dict(core.get("planning") or {})
        planning["current_plan_key"] = key
        core["planning"] = planning
        self._put_fact103(
            BORGA_CORE_KEY,
            core,
            "engine:v104_character_core",
            significance=60,
            origin_region_id="eurazania",
        )
        self.db.commit()
        return plan

    @staticmethod
    def _plan_block_v104(plan: dict[str, Any], minute_of_day: int) -> dict[str, Any]:
        for block in list(plan.get("blocks") or []):
            if int(block.get("start", -1)) <= minute_of_day < int(block.get("end", -1)):
                return dict(block)
        return dict(plan.get("outside_blocks") or {"kind": "unresolved_region_activity"})

    def _borga_presence103(self, start_minute):
        minute = int(start_minute)
        plan = self.ensure_character_plan_v104("borga", minute)
        if not plan:
            return super()._borga_presence103(start_minute)
        minute_of_day = minute % 1440
        block = self._plan_block_v104(plan, minute_of_day)
        kind = str(block.get("kind") or "unresolved_region_activity")
        place_key = block.get("place_key") if kind == "role_duty" else None
        place_text = None
        if place_key:
            from v101_runtime import EURAZANIA_PLACES
            place_text = EURAZANIA_PLACES[place_key]["name"]
        return {
            "actor_key": "borga",
            "display_name": "Борга",
            "region_id": "eurazania",
            "place_key": place_key,
            "place_text": place_text,
            "certainty": "prospective_hidden_character_plan_exact" if place_key else "prospective_hidden_region_only",
            "authority": CHARACTER_CORE_AUTHORITY,
            "historical_claim": False,
            "plan_key": self._plan_key_v104("borga", minute // 1440),
            "plan_block_kind": kind,
            "block_start": block.get("start"),
            "block_end": block.get("end"),
            "does_not_assert": [
                "Borga remains there after the current plan block",
                "exact location during travel/unresolved blocks",
            ],
        }

    def character_debug_snapshot_v104(self, actor_key: str = "borga") -> dict[str, Any] | None:
        core = self.ensure_character_core_v104(actor_key)
        if not core:
            return None
        plan = self.ensure_character_plan_v104(actor_key)
        presence = self._borga_presence103(self.now)
        return {
            "actor_key": actor_key,
            "core": core,
            "plan": plan,
            "presence_now": presence,
        }

    def activate_character_core_v104(self) -> dict[str, Any]:
        core = self.ensure_character_core_v104("borga")
        plan = self.ensure_character_plan_v104("borga")
        presence = self._borga_presence103(self.now)
        return {
            "status": "executed",
            "accepted": True,
            "activation": "character_core_v104",
            "world_minute": int(self.now),
            "actor_key": "borga",
            "core_materialized": core is not None,
            "plan_materialized": plan is not None,
            "presence_certainty": (presence or {}).get("certainty"),
            "time_advanced": 0,
            "player_choice": False,
            "does_not_assert": [
                "new player action",
                "unsupported Borga personality",
                "unsupported Borga memories",
                "unsupported Borga relationships",
            ],
        }

    def build_gm_packet(self, player_id="player"):
        base = super().build_gm_packet(player_id)
        base.setdefault("constraints", {})
        base["constraints"]["character_core"] = (
            "Hidden Character Core and plans are engine state, not narrator knowledge. "
            "Expose only causally observed facts; do not reveal hidden plan, invented traits, memories or relationships."
        )
        base["runtime"] = {"engine": ENGINE_VERSION_V104}
        return base

    def build_session_state_v104(
        self,
        *,
        journal_seq: int,
        head_state_hash: str,
        last_event: dict[str, Any] | None = None,
        preserved_last_turn: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = super().build_session_state_v103(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=last_event if (last_event or {}).get("event_type") != "character_core_activation" else None,
        )
        state["engine_version"] = ENGINE_VERSION_V104
        if preserved_last_turn is not None:
            state["last_turn"] = preserved_last_turn
        state["character_runtime"] = {
            "version": "character_core_v1",
            "calibrated_named_characters": ["borga"],
            "hidden_plans_not_narrator_knowledge": True,
        }
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type != "character_core_activation":
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
        start = int(self.now)
        result = self.activate_character_core_v104()
        if int(self.now) != start:
            raise RuntimeError("character core activation advanced world time")
        after = runtime_state_hash_v100(self, source_v)
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before, after, self.now),
        )
        self.db.commit()
        return {
            "accepted": True,
            "replayed": False,
            "result": result,
            "journal": self.export_runtime_journal_entry(event_key),
        }
