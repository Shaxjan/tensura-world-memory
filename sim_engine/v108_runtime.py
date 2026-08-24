from __future__ import annotations

from typing import Any
from v03_engine import dumps
from v100_handoff import runtime_state_hash_v100
from v101_runtime import _norm

ENGINE_VERSION_V108 = "1.0.8"
BAD_APPROACH_TURNS_V108 = (
    "chat-20260824-approach-borga-r000011",
    "chat-20260824-approach-r000012",
)


class V108RuntimeMixin:
    """Finite same-scene approach to one explicitly named, directly visible NPC."""

    def _visible_approach_target_v108(self, player_id: str, raw_text: str) -> dict[str, Any] | None:
        low = _norm(raw_text)
        if not any(x in low for x in ("подхож", "подой", "приближа")):
            return None
        mentions = self._safe_named_mentions_v106(raw_text)
        if len(mentions) != 1:
            return None
        mention = mentions[0]
        visible = {str(x.get("actor")): x for x in self._visible_named103(player_id) if x.get("status") == "visible"}
        if str(mention["id"]) not in visible:
            return None
        place = self._place103(player_id)
        if not place:
            return None
        return {
            "actor_key": str(mention["id"]), "name": str(mention["name"]),
            "place_key": str(place["key"]), "place_text": str(place["name"]),
        }

    def _execute_visible_approach_v108(self, turn_key: str, raw_text: str, player_id: str, target: dict[str, Any]):
        old = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if old:
            return self._load_turn_public(old, replayed=True)
        if self._visible_approach_target_v108(player_id, raw_text) is None:
            return super().process_player_turn(turn_key, raw_text, player_id=player_id, external_intent=None)

        turn = self.db.execute(
            "INSERT INTO gm_turns(turn_key,player_id,raw_text,status,created_at) VALUES(?,?,?,?,?)",
            (turn_key, player_id, raw_text, "received", self.now),
        )
        turn_id = int(turn.lastrowid)
        components = [{
            "kind": "visible_named_approach",
            "target": {"id": target["actor_key"], "name": target["name"]},
            "place_key": target["place_key"], "place_text": target["place_text"],
            "grounding": "explicit_named_mention_plus_direct_visibility", "clock_minutes": 0,
        }]
        action = self.db.execute(
            "INSERT INTO scene_actions(turn_key,world_minute,actor_id,action_kind,raw_text,components_json,resolution_mode,status,effect_json,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (turn_key, self.now, player_id, "visible_named_approach", raw_text, dumps(components),
             "engine_resolved_visible_named_approach", "in_progress", "{}", self.now),
        )
        action_id = int(action.lastrowid)
        effect = {
            "outcome": "approached_visible_named_actor", "target_key": target["actor_key"],
            "target_name": target["name"], "place_key": target["place_key"], "place_text": target["place_text"],
            "approach_minutes": 0, "started_at": int(self.now), "finished_at": int(self.now),
            "time_basis": "same_scene_subminute_not_rounded_to_world_clock",
            "does_not_assert": ["exact distance", "NPC reply", "NPC attention", "NPC emotion", "consent", "relationship change", "reciprocal memory"],
        }
        self.db.execute("UPDATE scene_actions SET status='resolved',effect_json=? WHERE id=?", (dumps(effect), action_id))
        self.db.commit()
        packet = self.build_gm_packet(player_id)
        contract = {
            "state_authority": "engine_v1.0.8_visible_local_approach", "player_text_verbatim": raw_text,
            "must_preserve": ["same-scene approach completed", "target was directly visible", "world minute unchanged", "HUD"],
            "forbidden": ["invent exact distance", "invent NPC reply/attention/emotion/consent", "invent relationship change", "create reciprocal memory from movement alone"],
        }
        checkpoint = self.write_checkpoint(player_id, turn_id=turn_id, kind="v108_visible_named_approach")
        public = {"status": "executed", "accepted": True, "turn_key": turn_key, "scene_action_id": action_id,
                  "result": effect, "gm_packet": packet, "narration_contract": contract, "checkpoint": checkpoint}
        self.db.execute(
            "UPDATE gm_turns SET status='executed',proposal_json=?,validation_json=?,engine_result_json=?,gm_packet_json=?,narration_contract_json=?,checkpoint_hash=?,public_result_json=?,completed_at=? WHERE id=?",
            (dumps({"action_kind":"visible_named_approach","components":components}), dumps({"valid":True,"reason":"v108_visible_named_target"}),
             dumps(effect), dumps(packet), dumps(contract), checkpoint["state_hash"], dumps(public), self.now, turn_id),
        )
        self.db.commit()
        return public

    def _repair_stale_approaches_v108(self) -> dict[str, Any]:
        rows_out = []
        for turn_key in BAD_APPROACH_TURNS_V108:
            action = self.db.execute("SELECT * FROM scene_actions WHERE turn_key=?", (turn_key,)).fetchone()
            if not action:
                rows_out.append({"turn_key":turn_key,"status":"not_present","cancelled_pending_ids":[]})
                continue
            pending = self.db.execute(
                "SELECT * FROM scene_pending_resolution WHERE scene_action_id=? AND status='pending' ORDER BY id", (int(action["id"]),)
            ).fetchall()
            cancelled = []
            for row in pending:
                if str(row["resolution_kind"] or "") == "local_navigation":
                    self.db.execute(
                        "UPDATE scene_pending_resolution SET status='cancelled_visible_approach_parser_repair',resolved_at=? WHERE id=?",
                        (self.now, int(row["id"])),
                    )
                    cancelled.append(int(row["id"]))
            if cancelled:
                self.db.execute(
                    "UPDATE scene_actions SET status='superseded_parser_repair',effect_json=? WHERE id=?",
                    (dumps({"outcome":"no_retroactive_effect","reason":"v108_stale_approach_pending","time_advanced":0}), int(action["id"])),
                )
                self.db.execute("UPDATE gm_turns SET status='superseded_parser_repair',completed_at=? WHERE turn_key=?", (self.now, turn_key))
            rows_out.append({"turn_key":turn_key,"status":"repaired" if cancelled else "nothing_to_repair","cancelled_pending_ids":cancelled})
        self.db.commit()
        return {"turns":rows_out,"cancelled_pending_ids":[i for r in rows_out for i in r["cancelled_pending_ids"]],
                "time_advanced":0,"player_choice":False,"retroactive_movement_asserted":False}

    def activate_visible_local_approach_repair_v108(self):
        start = int(self.now)
        repair = self._repair_stale_approaches_v108()
        if int(self.now) != start:
            raise RuntimeError("v1.0.8 activation advanced world time")
        return {"status":"executed","accepted":True,"activation":"visible_local_approach_repair_v108",
                "world_minute":int(self.now),"repair":repair,"time_advanced":0,"player_choice":False,
                "does_not_assert":["retroactive approach success","Borga response or attention","new player action","relationship change"]}

    def process_player_turn(self, turn_key: str, raw_text: str, *, player_id="player", external_intent=None):
        old = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if old:
            return self._load_turn_public(old, replayed=True)
        target = self._visible_approach_target_v108(player_id, raw_text)
        if target:
            if external_intent is not None:
                return {"status":"needs_clarification","accepted":False,"reason":"external_intent_not_needed_for_visible_named_approach","turn_key":turn_key}
            return self._execute_visible_approach_v108(turn_key, raw_text, player_id, target)
        return super().process_player_turn(turn_key, raw_text, player_id=player_id, external_intent=external_intent)

    def build_gm_packet(self, player_id="player"):
        base = super().build_gm_packet(player_id)
        base.setdefault("constraints", {})["visible_local_approach"] = (
            "Explicit approach to a directly visible named NPC is finite same-scene movement; it does not imply NPC attention, reply, emotion, consent, relationship change or memory."
        )
        base["runtime"] = {"engine": ENGINE_VERSION_V108}
        return base

    def build_session_state_v108(self, *, journal_seq:int, head_state_hash:str, last_event=None, preserved_last_turn=None):
        state = super().build_session_state_v107(
            journal_seq=journal_seq, head_state_hash=head_state_hash,
            last_event=None if (last_event or {}).get("event_type") == "visible_local_approach_repair_activation" else last_event,
            preserved_last_turn=preserved_last_turn,
        )
        state["engine_version"] = ENGINE_VERSION_V108
        parser = dict(state.get("parser_runtime") or {})
        parser.update({"visible_local_approach":True,"explicit_named_target_required":True,"bare_approach_auto_binding":False,"same_scene_clock_minutes":0})
        state["parser_runtime"] = parser
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type != "visible_local_approach_repair_activation":
            return super().execute_runtime_event(seq, event_key, event_type, request)
        old = self.db.execute("SELECT * FROM runtime_journal WHERE event_key=? OR seq=?", (event_key, int(seq))).fetchone()
        if old:
            if str(old["event_key"]) != event_key or int(old["seq"]) != int(seq):
                raise RuntimeError("journal sequence collision")
            return {"accepted":True,"replayed":True,"journal":self.export_runtime_journal_entry(event_key)}
        source_v = self._source_live_version_v100()
        before = runtime_state_hash_v100(self, source_v)
        result = self.activate_visible_local_approach_repair_v108()
        after = runtime_state_hash_v100(self, source_v)
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before, after, self.now),
        )
        self.db.commit()
        return {"accepted":True,"replayed":False,"result":result,"journal":self.export_runtime_journal_entry(event_key)}
