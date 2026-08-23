from __future__ import annotations

import random
import sqlite3

from v02_base import dumps, loads


class PlanningMixin:
    def add_goal(self, actor_id: str, kind: str, priority: int, target: dict | None = None, *, deadline_minute: int | None = None, source: str = "seed") -> int:
            cur = self.db.execute(
                "INSERT INTO goals(actor_id,kind,priority,target_json,progress,status,created_at,completed_at,deadline_minute,source) VALUES(?,?,?,?,0,'active',?,NULL,?,?)",
                (actor_id, kind, max(1, min(100, priority)), dumps(target or {}), self.now, deadline_minute, source),
            )
            gid = int(cur.lastrowid)
            self.event("goal_created", actor_id=actor_id, payload={"goal_id": gid, "kind": kind, "priority": priority, "source": source})
            return gid

    def active_goals(self, actor_id: str) -> list[sqlite3.Row]:
            return self.db.execute("SELECT * FROM goals WHERE actor_id=? AND status='active' ORDER BY priority DESC,created_at,id", (actor_id,)).fetchall()

    def _goal_exists(self, actor_id: str, kind: str) -> bool:
            return self.db.execute("SELECT 1 FROM goals WHERE actor_id=? AND kind=? AND status='active' LIMIT 1", (actor_id, kind)).fetchone() is not None

    def _recent_completion(self, actor_id: str, kind: str, within_minutes: int) -> bool:
            row = self.db.execute("SELECT MAX(completed_at) AS m FROM goals WHERE actor_id=? AND kind=? AND status='completed'", (actor_id, kind)).fetchone()
            return bool(row and row["m"] is not None and self.now - int(row["m"]) < within_minutes)

    def _ensure_plan(self, goal: sqlite3.Row) -> int:
            row = self.db.execute("SELECT id FROM plans WHERE goal_id=? AND status='active'", (goal["id"],)).fetchone()
            if row:
                return int(row["id"])
            kind = str(goal["kind"]); target = loads(goal["target_json"], {})
            templates = {
                "train": [("travel_to_target", target), ("practice", target), ("recover", {})],
                "publish": [("travel_to_work", {}), ("consume_materials", {"paper": 1, "ink": 1}), ("produce", {"publication": 1})],
                "produce_instrument": [("travel_to_work", {}), ("consume_materials", {"wood": 2, "string": 1}), ("produce", {"instrument": 1})],
                "profit": [("travel_to_work", {}), ("trade", {})],
                "security": [("patrol", {}), ("observe", {})],
                "investigate_rumor": [("travel_to_target", target), ("observe", {}), ("report", {})],
                "restock_food": [("source_goods", {}), ("restock", {"food": 12})],
                "restock_materials": [("travel_to_market", {}), ("buy_materials", target), ("deliver_materials", target)],
            }
            cur = self.db.execute("INSERT INTO plans(actor_id,goal_id,status,created_at,rationale) VALUES(?,?,'active',?,?)", (goal["actor_id"], goal["id"], self.now, f"rule plan for {kind}"))
            plan_id = int(cur.lastrowid)
            for seq, (action, params) in enumerate(templates.get(kind, [("work_on_goal", target)]), start=1):
                self.db.execute("INSERT INTO plan_steps(plan_id,seq,action,params_json,status) VALUES(?,?,?,?,'pending')", (plan_id, seq, action, dumps(params)))
            self.event("plan_created", actor_id=goal["actor_id"], payload={"plan_id": plan_id, "goal_id": int(goal["id"]), "kind": kind})
            return plan_id

    def _progress_goal(self, goal: sqlite3.Row, amount: int) -> int:
            progress = min(100, int(goal["progress"]) + max(0, int(amount)))
            status = "completed" if progress >= 100 else "active"
            self.db.execute("UPDATE goals SET progress=?,status=?,completed_at=? WHERE id=?", (progress, status, self.now if status == "completed" else None, goal["id"]))
            if status == "completed":
                self.db.execute("UPDATE plans SET status='completed' WHERE goal_id=?", (goal["id"],))
                self.event("goal_completed", actor_id=goal["actor_id"], payload={"goal_id": int(goal["id"]), "kind": goal["kind"]})
            return progress

    def _consider_initiative(self, actor_id: str, rng: random.Random) -> None:
            actor = self.actor(actor_id); p = loads(actor["personality_json"], {}); role = str(p.get("role", "civilian"))
            if role == "guard" and not self._goal_exists(actor_id, "investigate_rumor") and not self._recent_completion(actor_id, "investigate_rumor", 1440):
                for belief in self.rumor_beliefs(actor_id):
                    claim = loads(belief["claim_json"], {})
                    if int(claim.get("severity", 0)) >= 60 and int(belief["confidence"]) >= 40:
                        self.add_goal(actor_id, "investigate_rumor", 88, {"location_id": claim.get("location_id", "south_gate"), "rumor_id": int(belief["rumor_id"])}, source="initiative_from_rumor")
                        self.event("npc_initiative", actor_id=actor_id, payload={"reason": "security_rumor"}); break
            if role == "merchant" and self.resource_qty("market", "food") <= 10 and not self._goal_exists(actor_id, "restock_food") and not self._recent_completion(actor_id, "restock_food", 480):
                self.add_goal(actor_id, "restock_food", 82, {"location_id": "market"}, source="initiative_low_stock")
                self.event("npc_initiative", actor_id=actor_id, payload={"reason": "market_food_low"})
            if role == "publisher" and not self._goal_exists(actor_id, "restock_materials"):
                work = str(actor["work_location_id"] or actor["location_id"])
                if (self.resource_qty(work, "paper") < 2 or self.resource_qty(work, "ink") < 2) and not self._recent_completion(actor_id, "restock_materials", 360):
                    self.add_goal(actor_id, "restock_materials", 92, {"work_location": work, "bundle": "publishing"}, source="initiative_material_shortage")
                    self.event("npc_initiative", actor_id=actor_id, payload={"reason": "publishing_material_shortage"})
            if role == "craftsman" and not self._goal_exists(actor_id, "restock_materials"):
                work = str(actor["work_location_id"] or actor["location_id"])
                if (self.resource_qty(work, "wood") < 4 or self.resource_qty(work, "string") < 2) and not self._recent_completion(actor_id, "restock_materials", 360):
                    self.add_goal(actor_id, "restock_materials", 92, {"work_location": work, "bundle": "craft"}, source="initiative_material_shortage")
                    self.event("npc_initiative", actor_id=actor_id, payload={"reason": "craft_material_shortage"})
            if not self.active_goals(actor_id):
                fallback = {"guard": ("security", 55, {}), "merchant": ("profit", 55, {}), "publisher": ("publish", 60, {}), "craftsman": ("produce_instrument", 60, {}), "traveler": ("train", 55, {"location_id": "west_yard"})}.get(role, ("social", 40, {}))
                kind, priority, target = fallback
                cooldowns = {"train": 720, "publish": 1440, "produce_instrument": 720, "profit": 360, "security": 480, "social": 240}
                if not self._recent_completion(actor_id, kind, cooldowns.get(kind, 360)):
                    self.add_goal(actor_id, kind, priority, target, source="self_generated")
                    self.event("npc_initiative", actor_id=actor_id, payload={"reason": "no_active_goal"})
