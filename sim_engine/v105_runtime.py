from __future__ import annotations

from typing import Any

from v03_engine import dumps, loads
from v100_handoff import runtime_state_hash_v100
from v103_runtime import _stable
from v104_runtime import BORGA_CORE_KEY, CHARACTER_CORE_AUTHORITY

ENGINE_VERSION_V105 = "1.0.5"
BORGA_COMMITMENT_KEY = "task:borga"
BORGA_AUTONOMY_KEY = "v105:character_autonomy:borga"
CHARACTER_AUTONOMY_HANDLER = "character_task_v105"

_WORKSTREAM_MARKERS = (
    ("combat_rules", "combat rules"),
    ("admissions", "admissions"),
    ("judges", "judges"),
    ("testing", "testing"),
    ("tournament_operations", "tournament operations"),
)


class V105RuntimeMixin:
    """v1.0.5: execute a persistent named character's existing commitment through the shared scheduler."""

    def _borga_commitment_v105(self):
        return self.db.execute(
            "SELECT * FROM autonomous_commitments WHERE commitment_key=?",
            (BORGA_COMMITMENT_KEY,),
        ).fetchone()

    @staticmethod
    def _workstreams_from_commitment_v105(state: dict[str, Any]) -> list[str]:
        task = str(state.get("task") or "").casefold()
        return [key for key, marker in _WORKSTREAM_MARKERS if marker in task]

    def character_autonomy_v105(self, actor_key: str = "borga") -> dict[str, Any] | None:
        if actor_key != "borga":
            return None
        return self._get_fact103(BORGA_AUTONOMY_KEY)

    def ensure_character_autonomy_v105(self, actor_key: str = "borga") -> dict[str, Any] | None:
        if actor_key != "borga":
            return None
        old = self.character_autonomy_v105(actor_key)
        if old:
            return old

        core = self.ensure_character_core_v104(actor_key)
        row = self._borga_commitment_v105()
        if not core or row is None:
            return None
        if str(row["owner_key"] or "") != "borga" or str(row["kind"]) != "npc_task":
            return None

        commitment_state = loads(row["state_json"], {})
        workstreams = self._workstreams_from_commitment_v105(commitment_state)
        state = {
            "format": "TENSURA_CHARACTER_AUTONOMY",
            "schema_version": 1,
            "actor_key": "borga",
            "authority": CHARACTER_CORE_AUTHORITY,
            "historical_claim": False,
            "provenance": "engine:v105_character_autonomy",
            "materialized_at": int(self.now),
            "commitment_key": BORGA_COMMITMENT_KEY,
            "scheduler": "existing_v10_autonomy_runtime",
            "handler": CHARACTER_AUTONOMY_HANDLER,
            "goal_key": "fulfill_training_duties",
            "grounded_workstreams": workstreams,
            "decision_ticks": 0,
            "work_ticks": 0,
            "deferred_ticks": 0,
            "workstream_effort": {key: 0 for key in workstreams},
            "last_decision": None,
            "completion_policy": "never_auto_complete_without_grounded_completion_condition",
            "knowledge_visibility": "engine_hidden_until_causal_observation",
            "does_not_assert": [
                "task completion",
                "new Borga personality",
                "new Borga memories",
                "new Borga relationships",
                "exact location outside a grounded role-duty block",
            ],
        }
        self._put_fact103(
            BORGA_AUTONOMY_KEY,
            state,
            "engine:v105_character_autonomy",
            significance=55,
            origin_region_id="eurazania",
        )

        core = dict(core)
        core["autonomy"] = {
            "model": "v105_commitment_executor",
            "commitment_key": BORGA_COMMITMENT_KEY,
            "state_key": BORGA_AUTONOMY_KEY,
            "scheduler": "existing_v10_autonomy_runtime",
            "completion_policy": state["completion_policy"],
        }
        self._put_fact103(
            BORGA_CORE_KEY,
            core,
            "engine:v104_character_core",
            significance=60,
            origin_region_id="eurazania",
        )
        self.db.commit()
        return state

    def _wire_character_autonomy_v105(self) -> dict[str, Any]:
        state = self.ensure_character_autonomy_v105("borga")
        row = self.db.execute(
            "SELECT handler,next_due_at,cadence_minutes,tick_count,status FROM autonomy_runtime WHERE commitment_key=?",
            (BORGA_COMMITMENT_KEY,),
        ).fetchone()
        if state is None or row is None:
            raise RuntimeError("Borga Character Autonomy requires the preserved task:borga scheduler row")
        due = int(row["next_due_at"])
        cadence = int(row["cadence_minutes"])
        ticks = int(row["tick_count"])
        status = str(row["status"])
        self.db.execute(
            "UPDATE autonomy_runtime SET handler=? WHERE commitment_key=?",
            (CHARACTER_AUTONOMY_HANDLER, BORGA_COMMITMENT_KEY),
        )
        self.db.commit()
        return {
            "commitment_key": BORGA_COMMITMENT_KEY,
            "old_handler": str(row["handler"]),
            "new_handler": CHARACTER_AUTONOMY_HANDLER,
            "next_due_at_preserved": due,
            "cadence_minutes_preserved": cadence,
            "tick_count_preserved": ticks,
            "status_preserved": status,
        }

    def _character_work_tick_v105(self, row: Any) -> dict[str, Any]:
        key = str(row["commitment_key"])
        owner = str(row["owner_key"]) if row["owner_key"] is not None else None
        tick = int(row["tick_count"]) + 1
        state = self.ensure_character_autonomy_v105("borga")
        if state is None:
            raise RuntimeError("character autonomy state unavailable")

        plan = self.ensure_character_plan_v104("borga", self.now)
        block = self._plan_block_v104(plan, self.now % 1440) if plan else {"kind": "unresolved_region_activity"}
        block_kind = str(block.get("kind") or "unresolved_region_activity")
        presence = self._borga_presence103(self.now)
        workstreams = list(state.get("grounded_workstreams") or [])

        next_state = dict(state)
        next_state["decision_ticks"] = int(state.get("decision_ticks") or 0) + 1
        if block_kind == "role_duty" and workstreams and (presence or {}).get("place_key"):
            index = _stable(
                f"v105-borga-work|{self.now}|{tick}|{self._source_live_version_v100()}",
                len(workstreams),
            )
            workstream = workstreams[index]
            effort = dict(state.get("workstream_effort") or {})
            effort[workstream] = int(effort.get(workstream) or 0) + 1
            next_state["workstream_effort"] = effort
            next_state["work_ticks"] = int(state.get("work_ticks") or 0) + 1
            outcome = {
                "code": "character_work_progressed",
                "tick": tick,
                "actor_key": "borga",
                "commitment_key": key,
                "goal_key": "fulfill_training_duties",
                "plan_block_kind": block_kind,
                "place_key": presence.get("place_key"),
                "workstream": workstream,
                "effect": "scheduled effort applied to an already assigned Borga responsibility",
                "completion_asserted": False,
                "visible_to_player": False,
            }
        else:
            next_state["deferred_ticks"] = int(state.get("deferred_ticks") or 0) + 1
            outcome = {
                "code": "character_work_deferred",
                "tick": tick,
                "actor_key": "borga",
                "commitment_key": key,
                "goal_key": "fulfill_training_duties",
                "plan_block_kind": block_kind,
                "place_key": None,
                "reason": "current Character Plan block does not ground work at an exact duty site",
                "completion_asserted": False,
                "visible_to_player": False,
            }

        next_state["last_decision"] = {
            "world_minute": int(self.now),
            "outcome_code": outcome["code"],
            "plan_block_kind": block_kind,
            "workstream": outcome.get("workstream"),
            "place_key": outcome.get("place_key"),
        }
        self._put_fact103(
            BORGA_AUTONOMY_KEY,
            next_state,
            "engine:v105_character_autonomy",
            significance=55,
            origin_region_id="eurazania",
        )
        self.db.execute(
            "INSERT INTO autonomy_execution_log(world_minute,commitment_key,owner_key,handler,outcome_code,outcome_json,visible_to_player) "
            "VALUES(?,?,?,?,?,?,0)",
            (self.now, key, owner, CHARACTER_AUTONOMY_HANDLER, outcome["code"], dumps(outcome)),
        )
        self.db.execute(
            "UPDATE autonomy_runtime SET handler=?,tick_count=?,last_run_at=?,next_due_at=?,last_outcome_json=? WHERE commitment_key=?",
            (
                CHARACTER_AUTONOMY_HANDLER,
                tick,
                self.now,
                self.now + int(row["cadence_minutes"]),
                dumps(outcome),
                key,
            ),
        )
        self.db.execute(
            "INSERT INTO events(world_minute,event_type,region_id,actor_id,faction_id,significance,payload_json,visibility) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                self.now,
                "character_autonomy_decision",
                "eurazania",
                None,
                None,
                45,
                dumps(outcome),
                "engine_hidden",
            ),
        )
        return outcome

    def _run_commitment(self, row: Any) -> dict[str, Any]:
        if (
            str(row["commitment_key"]) == BORGA_COMMITMENT_KEY
            and str(row["owner_key"] or "") == "borga"
            and str(row["handler"]) in {"task_progress", CHARACTER_AUTONOMY_HANDLER}
            and self.character_core_v104("borga") is not None
        ):
            return self._character_work_tick_v105(row)
        return super()._run_commitment(row)

    def activate_character_autonomy_v105(self) -> dict[str, Any]:
        start = int(self.now)
        wiring = self._wire_character_autonomy_v105()
        if int(self.now) != start:
            raise RuntimeError("Character Autonomy wiring advanced world time")
        return {
            "status": "executed",
            "accepted": True,
            "activation": "character_autonomy_v105",
            "world_minute": int(self.now),
            "actor_key": "borga",
            "commitment_key": BORGA_COMMITMENT_KEY,
            "wiring": wiring,
            "time_advanced": 0,
            "player_choice": False,
            "does_not_assert": [
                "new player action",
                "task completion",
                "unsupported Borga personality",
                "unsupported private knowledge",
            ],
        }

    def build_gm_packet(self, player_id="player"):
        base = super().build_gm_packet(player_id)
        base.setdefault("constraints", {})
        base["constraints"]["character_autonomy"] = (
            "Character Autonomy decisions are hidden engine state. Narrate them only after causal observation or transmission; "
            "never expose private scheduler state, hidden workstreams or hidden location."
        )
        base["runtime"] = {"engine": ENGINE_VERSION_V105}
        return base

    def build_session_state_v105(
        self,
        *,
        journal_seq: int,
        head_state_hash: str,
        last_event: dict[str, Any] | None = None,
        preserved_last_turn: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = super().build_session_state_v104(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=last_event if (last_event or {}).get("event_type") != "character_autonomy_activation" else None,
            preserved_last_turn=preserved_last_turn,
        )
        state["engine_version"] = ENGINE_VERSION_V105
        state["character_runtime"] = {
            "version": "character_autonomy_v1",
            "calibrated_named_characters": ["borga"],
            "shared_scheduler": True,
            "hidden_plans_not_narrator_knowledge": True,
            "hidden_autonomy_not_narrator_knowledge": True,
        }
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type != "character_autonomy_activation":
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
        result = self.activate_character_autonomy_v105()
        if int(self.now) != start:
            raise RuntimeError("Character Autonomy activation advanced world time")
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
