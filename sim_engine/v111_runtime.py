from __future__ import annotations

from typing import Any

from v100_handoff import runtime_state_hash_v100

ENGINE_VERSION_V111 = "1.0.11"
FAST_PATH_MODEL_V111 = "runtime_fast_path_v1"


class V111RuntimeMixin:
    """v1.0.11: transport fast path; gameplay semantics remain v1.0.10.

    This layer does not make NPC/world decisions. It only exposes transport
    metadata and a zero-time activation event so repository request processing
    can use auto-sequenced queue requests with an optimistic gameplay-context
    guard.
    """

    def activate_runtime_fast_path_v111(self) -> dict[str, Any]:
        return {
            "status": "executed",
            "accepted": True,
            "activation": "runtime_fast_path_v111",
            "world_minute": int(self.now),
            "time_advanced": 0,
            "player_choice": False,
            "db_gameplay_mutation": False,
            "transport_only": True,
            "does_not_assert": [
                "new player action",
                "new NPC action",
                "movement",
                "memory change",
                "relationship change",
                "personality change",
            ],
        }

    def build_gm_packet(self, player_id: str = "player"):
        packet = super().build_gm_packet(player_id)
        packet.setdefault("constraints", {})["runtime_fast_path"] = (
            "Fast queue transport may allocate journal sequence at execution time, "
            "but it may not bypass authoritative state, replay, player-control, or causal rules."
        )
        packet["runtime"] = {"engine": ENGINE_VERSION_V111}
        return packet

    def build_session_state_v111(
        self,
        *,
        journal_seq: int,
        head_state_hash: str,
        last_event=None,
        preserved_last_turn=None,
    ) -> dict[str, Any]:
        is_activation = (last_event or {}).get("event_type") == "runtime_fast_path_activation"
        state = super().build_session_state_v110(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=None if is_activation else last_event,
            preserved_last_turn=preserved_last_turn,
        )
        state["engine_version"] = ENGINE_VERSION_V111
        state["transport_runtime"] = {
            "version": FAST_PATH_MODEL_V111,
            "normal_request_format": "TENSURA_FAST_TURN_REQUEST",
            "queue_sequence_allocation": "authoritative_processor_at_execution_time",
            "optimistic_guard": "expected_last_gameplay_turn_key",
            "normal_preflight_pointer_read_required": False,
            "fallback_on_guard_conflict": "refresh authoritative session/pointer and retry explicitly",
            "postflight_source": "runtime/session_state.json",
            "github_actions_still_authoritative_transport": True,
        }
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type != "runtime_fast_path_activation":
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
        result = self.activate_runtime_fast_path_v111()
        after = runtime_state_hash_v100(self, source_v)
        if after != before:
            raise RuntimeError("v1.0.11 transport activation mutated authoritative gameplay state")
        from v03_engine import dumps
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before, after, self.now),
        )
        self.db.commit()
        return {"accepted": True, "replayed": False, "result": result, "journal": self.export_runtime_journal_entry(event_key)}
