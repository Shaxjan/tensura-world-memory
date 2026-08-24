from __future__ import annotations

from typing import Any
from v03_engine import dumps
from v100_handoff import runtime_state_hash_v100

ENGINE_VERSION_V109 = "1.0.9"
READMODEL_VERSION_V109 = "authoritative_pending_projection_v1"


class V109RuntimeMixin:
    """v1.0.9: session read-model must project current pending state, not stale turn snapshots."""

    def _current_pending_ids_v109(self, player_id: str = "player") -> set[int]:
        rows = self.db.execute(
            "SELECT p.id FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id "
            "WHERE a.actor_id=? AND p.status='pending' ORDER BY p.id",
            (player_id,),
        ).fetchall()
        return {int(r[0]) for r in rows}

    def _sanitize_last_turn_v109(self, last_turn: dict[str, Any] | None, player_id: str = "player"):
        if not isinstance(last_turn, dict):
            return last_turn
        out = dict(last_turn)
        current_ids = self._current_pending_ids_v109(player_id)
        old_pending = list(out.get("pending_resolutions") or [])
        out["pending_resolutions"] = [
            dict(row) for row in old_pending
            if isinstance(row, dict) and isinstance(row.get("id"), int) and int(row["id"]) in current_ids
        ]
        contract = out.get("narration_contract")
        if isinstance(contract, dict):
            contract = dict(contract)
            must = [x for x in list(contract.get("must_preserve") or []) if x != "pending outcomes remain pending"]
            if old_pending and len(out["pending_resolutions"]) < len(old_pending):
                must.append("historical repaired pending are not current pending")
            contract["must_preserve"] = must
            out["narration_contract"] = contract
        return out

    def activate_session_readmodel_repair_v109(self):
        return {
            "status": "executed",
            "accepted": True,
            "activation": "session_readmodel_repair_v109",
            "world_minute": int(self.now),
            "time_advanced": 0,
            "player_choice": False,
            "db_gameplay_mutation": False,
            "does_not_assert": ["new player action", "new NPC action", "movement", "relationship change", "memory change"],
        }

    def build_gm_packet(self, player_id="player"):
        base = super().build_gm_packet(player_id)
        base.setdefault("constraints", {})["session_readmodel"] = (
            "Session pending lists are projections of currently pending authoritative rows; repaired/cancelled historical pending must not remain current."
        )
        base["runtime"] = {"engine": ENGINE_VERSION_V109}
        return base

    def build_session_state_v109(self, *, journal_seq: int, head_state_hash: str, last_event=None, preserved_last_turn=None):
        state = super().build_session_state_v108(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=None if (last_event or {}).get("event_type") == "session_readmodel_repair_activation" else last_event,
            preserved_last_turn=preserved_last_turn,
        )
        state["engine_version"] = ENGINE_VERSION_V109
        state["last_turn"] = self._sanitize_last_turn_v109(state.get("last_turn"), "player")
        state["readmodel_runtime"] = {
            "version": READMODEL_VERSION_V109,
            "pending_source": "authoritative_scene_pending_resolution_status_pending",
            "historical_repaired_pending_filtered": True,
        }
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type != "session_readmodel_repair_activation":
            return super().execute_runtime_event(seq, event_key, event_type, request)
        old = self.db.execute("SELECT * FROM runtime_journal WHERE event_key=? OR seq=?", (event_key, int(seq))).fetchone()
        if old:
            if str(old["event_key"]) != event_key or int(old["seq"]) != int(seq):
                raise RuntimeError("journal sequence collision")
            return {"accepted": True, "replayed": True, "journal": self.export_runtime_journal_entry(event_key)}
        source_v = self._source_live_version_v100()
        before = runtime_state_hash_v100(self, source_v)
        result = self.activate_session_readmodel_repair_v109()
        after = runtime_state_hash_v100(self, source_v)
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before, after, self.now),
        )
        self.db.commit()
        return {"accepted": True, "replayed": False, "result": result, "journal": self.export_runtime_journal_entry(event_key)}
