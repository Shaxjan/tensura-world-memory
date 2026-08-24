from __future__ import annotations

from typing import Any
from v03_engine import dumps
from v100_handoff import runtime_state_hash_v100

ENGINE_VERSION_V109 = "1.0.9"
READMODEL_VERSION_V109 = "authoritative_pending_projection_v1"


class V109RuntimeMixin:
    """v1.0.9: session read-model must be current and read-only."""

    def _current_pending_rows_v109(self, player_id: str = "player") -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT p.id,p.resolution_kind,p.target_text,p.status "
            "FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id "
            "WHERE a.actor_id=? AND p.status='pending' ORDER BY p.id",
            (player_id,),
        ).fetchall()
        return [
            {
                "id": int(r["id"]),
                "kind": str(r["resolution_kind"]),
                "target": str(r["target_text"]) if r["target_text"] is not None else None,
                "status": str(r["status"]),
            }
            for r in rows
        ]

    def _current_pending_ids_v109(self, player_id: str = "player") -> set[int]:
        return {int(row["id"]) for row in self._current_pending_rows_v109(player_id)}

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

    def _session_readonly_packet_v109(self, player_id: str = "player") -> dict[str, Any]:
        """Minimal current packet for session projection; performs reads only.

        Historical build_gm_packet() intentionally records telemetry. Session-state
        construction must not invoke it merely to refresh the read model.
        """
        living = self._scene103(player_id)
        named = self._visible_named103(player_id)
        pending = self._current_pending_rows_v109(player_id)
        return {
            "hud": self.build_hud_v102(player_id),
            "scene": {
                "visible_actors": [],
                "visible_events": [],
                "position_claims": [],
                "recent_player_actions": [],
                "pending_resolutions": pending,
                "ambient": list((living or {}).get("population") or [])[:10],
                "named_observations": named,
            },
            "player_known": {"facts": [], "memories": []},
            "constraints": {
                "session_readmodel": "Read-only current projection; not a gameplay GM-packet emission."
            },
            "runtime": {"engine": ENGINE_VERSION_V109, "packet_kind": "session_readonly_projection"},
        }

    def _event_with_session_packet_v109(self, last_event, journal_seq: int):
        packet = self._session_readonly_packet_v109("player")
        if isinstance(last_event, dict):
            event = dict(last_event)
            public = dict(event.get("result") or {}) if isinstance(event.get("result"), dict) else {}
            stored = public.get("gm_packet")
            if not isinstance(stored, dict) or "hud" not in stored:
                public["gm_packet"] = packet
            event["result"] = public
            return event, False, packet
        return {
            "seq": int(journal_seq),
            "event_key": "internal-v109-session-readonly-projection",
            "event_type": "readmodel_projection",
            "result": {"gm_packet": packet},
        }, True, packet

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
        event_for_super, synthetic_event, readonly_packet = self._event_with_session_packet_v109(last_event, journal_seq)
        state = super().build_session_state_v108(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=event_for_super,
            preserved_last_turn=preserved_last_turn,
        )
        if synthetic_event and preserved_last_turn is None:
            state["last_turn"] = None
        state["engine_version"] = ENGINE_VERSION_V109
        state["last_turn"] = self._sanitize_last_turn_v109(state.get("last_turn"), "player")
        scene = dict(state.get("scene") or {})
        current_scene = readonly_packet["scene"]
        scene["ambient"] = list(current_scene.get("ambient") or [])
        scene["named_observations"] = list(current_scene.get("named_observations") or [])
        scene["pending_resolutions"] = list(current_scene.get("pending_resolutions") or [])
        state["scene"] = scene
        state["readmodel_runtime"] = {
            "version": READMODEL_VERSION_V109,
            "pending_source": "authoritative_scene_pending_resolution_status_pending",
            "historical_repaired_pending_filtered": True,
            "session_builder_read_only": True,
            "gm_packet_fallback": "read_only_projection_no_telemetry",
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
