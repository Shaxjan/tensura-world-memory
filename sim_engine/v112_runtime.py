from __future__ import annotations

from typing import Any

from v100_handoff import runtime_state_hash_v100

ENGINE_VERSION_V112 = "1.0.12"
TRANSPORT_MODEL_V112 = "runtime_fast_path_reliability_v1"


class V112RuntimeMixin:
    """v1.0.12: transport reliability repair; gameplay semantics stay v1.0.10."""

    def activate_runtime_fast_path_reliability_v112(self) -> dict[str, Any]:
        return {
            "status": "executed",
            "accepted": True,
            "activation": "runtime_fast_path_reliability_v112",
            "world_minute": int(self.now),
            "time_advanced": 0,
            "player_choice": False,
            "db_gameplay_mutation": False,
            "transport_only": True,
            "does_not_assert": [
                "new player action", "new NPC action", "movement",
                "memory change", "relationship change", "personality change",
            ],
        }

    def build_gm_packet(self, player_id: str = "player"):
        packet = super().build_gm_packet(player_id)
        packet.setdefault("constraints", {})["runtime_fast_path_reliability"] = (
            "Transport receipts and request normalization do not change gameplay semantics. "
            "Only a committed runtime journal event changes authoritative gameplay state."
        )
        packet["runtime"] = {"engine": ENGINE_VERSION_V112}
        return packet

    def build_session_state_v112(
        self,
        *,
        journal_seq: int,
        head_state_hash: str,
        last_event=None,
        preserved_last_turn=None,
    ) -> dict[str, Any]:
        is_activation = (last_event or {}).get("event_type") == "runtime_fast_path_reliability_activation"
        state = super().build_session_state_v111(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=None if is_activation else last_event,
            preserved_last_turn=preserved_last_turn,
        )
        state["engine_version"] = ENGINE_VERSION_V112
        state["transport_runtime"] = {
            "version": TRANSPORT_MODEL_V112,
            "normal_request_format": "TENSURA_FAST_TURN_REQUEST",
            "canonical_payload": "request.raw_text",
            "compatibility_payload": "top_level_raw_text_if_request_object_absent",
            "request_id_required": False,
            "queue_sequence_allocation": "authoritative_processor_at_execution_time",
            "optimistic_guard": "expected_last_gameplay_turn_key",
            "normal_preflight_pointer_read_required": False,
            "request_receipts": True,
            "duplicate_enqueue_forbidden": True,
            "github_actions_still_authoritative_transport": True,
        }
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type != "runtime_fast_path_reliability_activation":
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
        result = self.activate_runtime_fast_path_reliability_v112()
        after = runtime_state_hash_v100(self, source_v)
        if after != before:
            raise RuntimeError("v1.0.12 transport activation mutated gameplay state")
        from v03_engine import dumps
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before, after, self.now),
        )
        self.db.commit()
        return {"accepted": True, "replayed": False, "result": result, "journal": self.export_runtime_journal_entry(event_key)}
