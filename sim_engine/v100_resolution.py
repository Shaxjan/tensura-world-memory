from __future__ import annotations

from typing import Any

from v03_engine import dumps, loads

RESOLUTION_AUTHORITY = "PROSPECTIVE_ENGINE_RESOLUTION"
LOCAL_NAV_OUTCOMES = {"located", "not_found", "blocked", "deferred"}
NPC_OUTCOMES = {"accepted", "declined", "neutral", "deferred"}
WORLD_OUTCOMES = {"succeeded", "failed", "partial", "blocked", "deferred"}


class V100ResolutionMixin:
    @staticmethod
    def _bounded_text(value: Any, name: str, *, max_len: int = 2000, allow_none: bool = True) -> str | None:
        if value is None and allow_none:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{name} must be string")
        text = value.strip()
        if not text and not allow_none:
            raise ValueError(f"{name} must not be empty")
        if len(text) > max_len:
            raise ValueError(f"{name} too long")
        return text or None

    def _handoff_object_for_action(self, scene_action_id: int) -> str | None:
        row = self.db.execute("SELECT components_json FROM scene_actions WHERE id=?", (int(scene_action_id),)).fetchone()
        if row is None:
            return None
        components = loads(row[0], [])
        if not isinstance(components, list):
            return None
        for component in components:
            if not isinstance(component, dict) or component.get("kind") != "handoff_offer":
                continue
            obj = component.get("object")
            if isinstance(obj, dict) and isinstance(obj.get("key"), str):
                return str(obj["key"])
        return None

    def _validate_scene_resolution(self, row: Any, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("resolution payload must be object")
        kind = str(row["resolution_kind"])
        outcome = payload.get("outcome")
        if not isinstance(outcome, str):
            raise ValueError("resolution outcome required")
        out: dict[str, Any] = {"outcome": outcome}
        if kind == "local_navigation":
            if outcome not in LOCAL_NAV_OUTCOMES:
                raise ValueError("invalid local_navigation outcome")
            place = self._bounded_text(payload.get("place_text"), "place_text", max_len=500)
            note = self._bounded_text(payload.get("note"), "note", max_len=1000)
            if outcome == "located" and row["target_key"] is None:
                raise ValueError("located requires grounded target")
            out.update({"place_text": place, "note": note})
        elif kind in {"npc_response", "npc_or_world_response", "handoff_acceptance"}:
            if outcome not in NPC_OUTCOMES:
                raise ValueError("invalid npc outcome")
            out["response_text"] = self._bounded_text(payload.get("response_text"), "response_text", max_len=4000)
            if kind == "handoff_acceptance" and outcome == "accepted" and row["target_key"] is None:
                raise ValueError("accepted handoff requires grounded recipient")
        elif kind == "world_resolution_required":
            if outcome not in WORLD_OUTCOMES:
                raise ValueError("invalid world outcome")
            out["effect_text"] = self._bounded_text(payload.get("effect_text"), "effect_text", max_len=2000)
        else:
            raise ValueError("unsupported resolution kind")
        evidence = payload.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, list) or len(evidence) > 20 or any(not isinstance(x, str) or len(x) > 500 for x in evidence):
                raise ValueError("invalid evidence")
            out["evidence"] = list(evidence)
        else:
            out["evidence"] = []
        return out

    def resolve_scene_pending(self, pending_id: int, payload: dict[str, Any], *, resolver: str = "gm") -> dict[str, Any]:
        row = self.db.execute(
            "SELECT p.*,a.turn_key,a.actor_id,a.id AS scene_action_id FROM scene_pending_resolution p "
            "JOIN scene_actions a ON a.id=p.scene_action_id WHERE p.id=?", (int(pending_id),)
        ).fetchone()
        if row is None:
            raise ValueError("unknown pending resolution")
        if str(row["status"]) not in {"pending", "deferred"}:
            old = self.db.execute(
                "SELECT * FROM scene_resolution_log WHERE pending_id=? ORDER BY id DESC LIMIT 1", (int(pending_id),)
            ).fetchone()
            return {"accepted": False, "reason": "already_resolved", "resolution": dict(old) if old else None}
        clean = self._validate_scene_resolution(row, payload)
        kind, outcome = str(row["resolution_kind"]), str(clean["outcome"])
        target_key = str(row["target_key"]) if row["target_key"] is not None else None
        if kind == "local_navigation" and outcome == "located":
            region = str(self.actor(str(row["actor_id"]))["region_id"])
            place = clean.get("place_text")
            if target_key:
                existing = self.db.execute("SELECT display_name FROM actor_position_claims WHERE actor_key=?", (target_key,)).fetchone()
                if existing is not None:
                    self.db.execute(
                        "UPDATE actor_position_claims SET region_id=?,location_text=?,precision='prospective_observed',status='active',"
                        "source_path='runtime:v1.0',note=?,as_of_version=NULL WHERE actor_key=?",
                        (region, place, "Resolved prospectively from a local-navigation encounter; not retrospective canon.", target_key),
                    )
            if place:
                self.db.execute(
                    "INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
                    (str(row["actor_id"]), place, "prospective_resolved", "runtime:v1.0", self.now),
                )
        if kind == "handoff_acceptance" and outcome == "accepted":
            object_key = self._handoff_object_for_action(int(row["scene_action_id"]))
            if object_key is None:
                raise ValueError("handoff object not recoverable from grounded action")
            obj = self.db.execute("SELECT holder_key FROM scene_objects WHERE object_key=?", (object_key,)).fetchone()
            if obj is None or str(obj["holder_key"]) != str(row["actor_id"]):
                raise ValueError("handoff source no longer holds object")
            self.db.execute(
                "UPDATE scene_objects SET holder_key=?,certainty='prospective_resolved',source_path='runtime:v1.0',updated_at=? WHERE object_key=?",
                (target_key, self.now, object_key),
            )
            clean["object_key"] = object_key
        new_status = "deferred" if outcome == "deferred" else "resolved"
        self.db.execute(
            "UPDATE scene_pending_resolution SET status=?,state_json=?,resolved_at=? WHERE id=?",
            (new_status, dumps(clean), None if new_status == "deferred" else self.now, int(pending_id)),
        )
        cur = self.db.execute(
            "INSERT INTO scene_resolution_log(pending_id,world_minute,resolution_kind,outcome,payload_json,resolver,authority,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (int(pending_id), self.now, kind, outcome, dumps(clean), str(resolver), RESOLUTION_AUTHORITY, self.now),
        )
        unresolved = int(self.db.execute(
            "SELECT COUNT(*) FROM scene_pending_resolution WHERE scene_action_id=? AND status IN ('pending','deferred')",
            (int(row["scene_action_id"]),),
        ).fetchone()[0])
        action_status, turn_status = ("pending", "scene_pending") if unresolved else ("resolved", "executed")
        self.db.execute(
            "UPDATE scene_actions SET status=?,effect_json=? WHERE id=?",
            (action_status, dumps({"last_resolution_id": int(cur.lastrowid), "last_outcome": outcome}), int(row["scene_action_id"])),
        )
        self.db.commit()
        checkpoint = self.write_checkpoint(str(row["actor_id"]), kind="scene_resolution")
        packet = self.build_gm_packet(str(row["actor_id"]))
        self.db.execute(
            "UPDATE gm_turns SET status=?,gm_packet_json=?,checkpoint_hash=?,completed_at=? WHERE turn_key=?",
            (turn_status, dumps(packet), checkpoint["state_hash"], self.now, str(row["turn_key"])),
        )
        self.db.commit()
        return {
            "accepted": True, "pending_id": int(pending_id), "resolution_id": int(cur.lastrowid),
            "kind": kind, "outcome": outcome, "status": new_status, "scene_status": turn_status,
            "payload": clean, "checkpoint": checkpoint, "gm_packet": packet,
        }

    def record_narration(self, turn_key: str, narration_text: str, *, player_id: str = "player") -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if row is None:
            raise ValueError("unknown turn")
        status = str(row["status"])
        if status not in {"executed", "narrated", "scene_pending"}:
            raise ValueError("turn has no narratable engine result")
        current = self._state_hash(self.critical_state_snapshot(player_id))
        expected = str(row["checkpoint_hash"])
        if current != expected:
            raise RuntimeError("state_changed_after_packet")
        final_status = "scene_pending" if status == "scene_pending" else "narrated"
        self.db.execute("UPDATE gm_turns SET narration_text=?,status=? WHERE id=?", (str(narration_text), final_status, row["id"]))
        self.db.commit()
        return {"recorded": True, "turn_key": turn_key, "state_hash": current, "status": final_status}

    def build_gm_packet(self, player_id: str = "player"):
        packet = super().build_gm_packet(player_id)
        packet["scene_bridge"]["unresolved_resolutions"] = [
            {"id": int(r["id"]), "kind": str(r["resolution_kind"]), "target": r["target_text"], "status": str(r["status"])}
            for r in self.db.execute(
                "SELECT p.id,p.resolution_kind,p.target_text,p.status FROM scene_pending_resolution p "
                "JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.actor_id=? AND p.status IN ('pending','deferred') ORDER BY p.id LIMIT 8",
                (player_id,),
            ).fetchall()
        ]
        packet["scene_bridge"]["recent_resolutions"] = [
            {"id": int(r["id"]), "pending_id": int(r["pending_id"]), "kind": str(r["resolution_kind"]),
             "outcome": str(r["outcome"]), "payload": loads(r["payload_json"], {})}
            for r in self.db.execute("SELECT * FROM scene_resolution_log ORDER BY id DESC LIMIT 6").fetchall()
        ]
        packet["constraints"]["resolution_authority"] = (
            "Pending scene outcomes may change only through the typed v1.0 resolution API. Narration itself is never a state mutation."
        )
        mode_row = self.db.execute("SELECT value_json FROM campaign_metadata WHERE key='runtime_mode'").fetchone()
        packet["runtime"] = {
            "engine": "1.0", "mode": loads(mode_row[0], None) if mode_row else None,
            "journal_entries": int(self.db.execute("SELECT COUNT(*) FROM runtime_journal").fetchone()[0]),
        }
        return packet
