from __future__ import annotations

import hashlib
import json
from typing import Any

from v03_engine import WorldV03, dumps, loads


class V06GMLoopMixin:
    def _capability(self, command: str) -> tuple[bool, str]:
        row = self.db.execute(
            "SELECT enabled,reason FROM migration_capabilities WHERE command=?", (command,)
        ).fetchone()
        if row is None:
            return True, "lab_default"
        return bool(row["enabled"]), str(row["reason"])

    def _optional_stats(self, actor_id: str) -> dict[str, Any] | None:
        try:
            row = self.db.execute("SELECT * FROM actor_stats WHERE actor_id=?", (actor_id,)).fetchone()
        except Exception:
            return None
        if row is None:
            return None
        return {"hp": int(row["hp"]), "max_hp": int(row["max_hp"]), "alive": bool(row["alive"])}

    def build_gm_packet(self, player_id: str = "player") -> dict[str, Any]:
        base = WorldV03.build_context(self, player_id, max_events=6)
        player = self.actor(player_id)
        region = str(player["region_id"])
        mode_row = self.db.execute(
            "SELECT value_json FROM campaign_metadata WHERE key='runtime_mode'"
        ).fetchone()
        migration_rehearsal = bool(mode_row and loads(mode_row["value_json"], None) == "migration_rehearsal")
        if migration_rehearsal:
            base["region"] = {k: base["region"][k] for k in ("id", "name", "kind") if k in base["region"]}
            base["markets"] = []
            base["recent_relevant_events"] = []
        stats = self._optional_stats(player_id)
        if stats:
            base["player"].update(stats)
        base["player"]["status"] = str(player["status"])

        visible = [
            {"id": str(r["id"]), "name": str(r["name"]), "status": str(r["status"])}
            for r in self.db.execute(
                "SELECT id,name,status FROM actors WHERE region_id=? AND id<>? ORDER BY id LIMIT 12",
                (region, player_id),
            )
        ]
        known_memories = []
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memories'").fetchone():
            known_memories = [
                {"key": str(r["memory_key"]), "summary": str(r["summary"]), "salience": int(r["salience"])}
                for r in self.db.execute(
                    "SELECT memory_key,summary,salience FROM memories WHERE actor_id=? AND status='active' ORDER BY salience DESC LIMIT 6",
                    (player_id,),
                )
            ]
        blockers = [
            str(r["code"]) for r in self.db.execute(
                "SELECT code FROM migration_blockers WHERE status='active' ORDER BY code"
            )
        ]
        capabilities = {
            str(r["command"]): {"enabled": bool(r["enabled"]), "reason": str(r["reason"])}
            for r in self.db.execute("SELECT command,enabled,reason FROM migration_capabilities ORDER BY command")
        }
        packet = {
            "time": self.now,
            "player": base["player"],
            "perceivable": {
                "region": base["region"],
                "actors": visible,
                "markets": base.get("markets", []),
                "events": base.get("recent_relevant_events", []),
            },
            "known": {"facts": base.get("known_facts", []), "memories": known_memories},
            "migration": {"active_blockers": blockers, "capabilities": capabilities},
            "constraints": {
                "unknown_policy": "UNKNOWN stays UNKNOWN; do not infer hidden state",
                "player_control": "Narrator may not choose player dialogue, feelings, decisions or significant actions",
                "state_authority": "Only engine command results may change authoritative world state",
            },
        }
        raw = dumps(packet)
        if len(raw) > 8000:
            packet["perceivable"]["events"] = packet["perceivable"]["events"][:3]
            packet["known"]["memories"] = packet["known"]["memories"][:3]
            raw = dumps(packet)
        if len(raw) > 8000:
            raise RuntimeError("GM packet exceeds guardrail")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        self.db.execute(
            "INSERT INTO gm_packet_log(world_minute,player_id,chars,packet_hash) VALUES(?,?,?,?)",
            (self.now, player_id, len(raw), digest),
        )
        self.db.commit()
        packet["packet_meta"] = {"chars": len(raw), "hash": digest}
        return packet

    def critical_state_snapshot(self, player_id: str = "player") -> dict[str, Any]:
        p = self.actor(player_id)
        region = str(p["region_id"])
        travel = self.db.execute(
            "SELECT from_region_id,to_region_id,started_at,due_at,status FROM actor_travel WHERE actor_id=?",
            (player_id,),
        ).fetchone()
        inventory = [tuple(r) for r in self.db.execute(
            "SELECT commodity_id,qty FROM actor_inventory WHERE actor_id=? ORDER BY commodity_id", (player_id,)
        )]
        market = [tuple(r) for r in self.db.execute(
            "SELECT commodity_id,supply,demand,price_copper FROM markets WHERE region_id=? ORDER BY commodity_id", (region,)
        )]
        snapshot = {
            "world_minute": self.now,
            "player": {"region": region, "cash": int(p["cash_copper"]), "status": str(p["status"])},
            "travel": dict(travel) if travel else None,
            "inventory": inventory,
            "local_market": market,
        }
        if self._optional_stats(player_id):
            snapshot["stats"] = self._optional_stats(player_id)
        return snapshot

    @staticmethod
    def _state_hash(snapshot: dict[str, Any]) -> str:
        return hashlib.sha256(dumps(snapshot).encode("utf-8")).hexdigest()

    def write_checkpoint(self, player_id: str = "player", *, turn_id: int | None = None, kind: str = "gm_turn") -> dict[str, Any]:
        state = self.critical_state_snapshot(player_id)
        digest = self._state_hash(state)
        cur = self.db.execute(
            "INSERT INTO checkpoints(world_minute,player_id,turn_id,kind,state_hash,state_json) VALUES(?,?,?,?,?,?)",
            (self.now, player_id, turn_id, kind, digest, dumps(state)),
        )
        self.db.commit()
        return {"checkpoint_id": int(cur.lastrowid), "state_hash": digest, "world_minute": self.now}

    def verify_latest_checkpoint(self, player_id: str = "player") -> dict[str, Any]:
        row = self.db.execute(
            "SELECT * FROM checkpoints WHERE player_id=? ORDER BY id DESC LIMIT 1", (player_id,)
        ).fetchone()
        if row is None:
            return {"ok": False, "reason": "no_checkpoint"}
        current = self._state_hash(self.critical_state_snapshot(player_id))
        return {"ok": current == str(row["state_hash"]), "expected": str(row["state_hash"]), "current": current, "checkpoint_id": int(row["id"])}

    @staticmethod
    def _validate_against_proposal(proposal: dict[str, Any], external: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("status") != "ready":
            return {"valid": False, "reason": proposal.get("status", "not_ready")}
        command = external.get("command")
        params = external.get("params")
        if command != proposal.get("command"):
            return {"valid": False, "reason": "command_not_grounded"}
        if not isinstance(params, dict) or set(params) != set(proposal.get("params", {})):
            return {"valid": False, "reason": "parameter_schema_mismatch"}
        for key, value in proposal.get("params", {}).items():
            if params.get(key) != value:
                return {"valid": False, "reason": f"parameter_not_grounded:{key}"}
        return {"valid": True, "reason": "exact_grounding_match"}

    def _load_turn_public(self, row: Any, *, replayed: bool) -> dict[str, Any]:
        result = loads(row["public_result_json"], {})
        result["replayed"] = replayed
        return result

    def process_player_turn(
        self,
        turn_key: str,
        raw_text: str,
        *,
        player_id: str = "player",
        external_intent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not turn_key or len(turn_key) > 160:
            raise ValueError("invalid turn_key")
        old = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if old is not None:
            return self._load_turn_public(old, replayed=True)

        cur = self.db.execute(
            "INSERT INTO gm_turns(turn_key,player_id,raw_text,status,created_at) VALUES(?,?,?,?,?)",
            (turn_key, player_id, str(raw_text), "received", self.now),
        )
        turn_id = int(cur.lastrowid)
        self.db.commit()

        proposal = self.propose_text_intent(player_id, raw_text)
        validation = {"valid": True, "reason": "deterministic_parser_only"}
        if external_intent is not None:
            validation = self._validate_against_proposal(proposal, external_intent)
            if not validation["valid"]:
                public = {"status": "needs_clarification", "accepted": False, "proposal": proposal, "validation": validation, "turn_key": turn_key}
                self.db.execute(
                    "UPDATE gm_turns SET status=?,proposal_json=?,validation_json=?,public_result_json=?,completed_at=? WHERE id=?",
                    ("needs_clarification", dumps(proposal), dumps(validation), dumps(public), self.now, turn_id),
                )
                self.db.commit(); return public

        if proposal["status"] != "ready":
            public = {"status": proposal["status"], "accepted": False, "proposal": proposal, "validation": validation, "turn_key": turn_key}
            self.db.execute(
                "UPDATE gm_turns SET status=?,proposal_json=?,validation_json=?,public_result_json=?,completed_at=? WHERE id=?",
                (proposal["status"], dumps(proposal), dumps(validation), dumps(public), self.now, turn_id),
            )
            self.db.commit(); return public

        command = str(proposal["command"])
        allowed, reason = self._capability(command)
        if not allowed:
            public = {"status": "blocked_by_migration", "accepted": False, "proposal": proposal, "reason": reason, "turn_key": turn_key}
            self.db.execute(
                "UPDATE gm_turns SET status=?,proposal_json=?,validation_json=?,public_result_json=?,completed_at=? WHERE id=?",
                ("blocked_by_migration", dumps(proposal), dumps(validation), dumps(public), self.now, turn_id),
            )
            self.db.commit(); return public

        before = self._state_hash(self.critical_state_snapshot(player_id))
        engine = self.submit_player_command(player_id, command, dict(proposal["params"]))
        if not engine.get("accepted"):
            after = self._state_hash(self.critical_state_snapshot(player_id))
            public = {"status": "engine_rejected", "accepted": False, "proposal": proposal, "engine": engine, "state_unchanged": before == after, "turn_key": turn_key}
            self.db.execute(
                "UPDATE gm_turns SET status=?,proposal_json=?,validation_json=?,engine_result_json=?,public_result_json=?,completed_at=? WHERE id=?",
                ("engine_rejected", dumps(proposal), dumps(validation), dumps(engine), dumps(public), self.now, turn_id),
            )
            self.db.commit(); return public

        packet = self.build_gm_packet(player_id)
        checkpoint = self.write_checkpoint(player_id, turn_id=turn_id, kind="accepted_player_turn")
        contract = {
            "state_authority": "engine_result_and_checkpoint_only",
            "player_text_verbatim": str(raw_text),
            "must_preserve": ["engine outcome", "money/time/location from GM packet", "UNKNOWN values"],
            "may_add": ["sensory description consistent with perceivable packet", "NPC dialogue/actions supported by engine/world state"],
            "forbidden": ["new state mutation", "hidden fact leak", "invented UNKNOWN", "choosing player dialogue/feelings/decisions"],
        }
        public = {
            "status": "executed", "accepted": True, "turn_key": turn_key,
            "proposal": proposal, "engine": engine, "gm_packet": packet,
            "narration_contract": contract, "checkpoint": checkpoint,
        }
        self.db.execute(
            "UPDATE gm_turns SET status=?,proposal_json=?,validation_json=?,engine_result_json=?,gm_packet_json=?,narration_contract_json=?,checkpoint_hash=?,public_result_json=?,completed_at=? WHERE id=?",
            ("executed", dumps(proposal), dumps(validation), dumps(engine), dumps(packet), dumps(contract), checkpoint["state_hash"], dumps(public), self.now, turn_id),
        )
        self.db.commit()
        return public

    def record_narration(self, turn_key: str, narration_text: str, *, player_id: str = "player") -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if row is None:
            raise ValueError("unknown turn")
        if str(row["status"]) not in {"executed", "narrated"}:
            raise ValueError("turn has no executable engine result")
        current = self._state_hash(self.critical_state_snapshot(player_id))
        expected = str(row["checkpoint_hash"])
        if current != expected:
            raise RuntimeError("state_changed_after_packet")
        self.db.execute(
            "UPDATE gm_turns SET narration_text=?,status='narrated' WHERE id=?",
            (str(narration_text), row["id"]),
        )
        self.db.commit()
        return {"recorded": True, "turn_key": turn_key, "state_hash": current}
