from __future__ import annotations

import random
from typing import Any

from v02_base import dumps, loads, format_money, format_world_minute


class AutonomyMixin:
    def start_travel(self, actor_id: str, destination: str, reason: str) -> int:
            actor = self.actor(actor_id)
            if int(actor["is_player"]):
                raise PermissionError("Engine may not autonomously move the player")
            if actor["travel_destination"]:
                return int(actor["travel_arrival_at"])
            origin = str(actor["location_id"])
            duration, path = self.shortest_path(origin, destination)
            arrival = self.now + duration
            self.db.execute("UPDATE actors SET status='traveling',travel_destination=?,travel_arrival_at=?,next_action_at=? WHERE id=?", (destination, arrival, arrival, actor_id))
            self.event("travel_started", actor_id=actor_id, location_id=origin, payload={"to": destination, "duration": duration, "path": path, "reason": reason})
            return arrival

    def _arrivals(self) -> None:
            rows = self.db.execute("SELECT id,travel_destination FROM actors WHERE travel_destination IS NOT NULL AND travel_arrival_at<=?", (self.now,)).fetchall()
            for row in rows:
                dest = str(row["travel_destination"])
                self.db.execute("UPDATE actors SET location_id=?,status='idle',travel_destination=NULL,travel_arrival_at=NULL,next_action_at=? WHERE id=?", (dest, self.now, row["id"]))
                self.event("travel_arrived", actor_id=row["id"], location_id=dest)

    def _schedule(self, actor_id: str, minutes: int) -> None:
            self.db.execute("UPDATE actors SET next_action_at=? WHERE id=?", (self.now + max(1, minutes), actor_id))

    def _same_location_npcs(self, actor_id: str, location_id: str) -> list[str]:
            rows = self.db.execute("SELECT id FROM actors WHERE id<>? AND is_player=0 AND location_id=? AND travel_destination IS NULL ORDER BY id", (actor_id, location_id)).fetchall()
            return [str(r["id"]) for r in rows]

    def _eat(self, actor_id: str, rng: random.Random) -> bool:
            if self.item_qty(actor_id, "food_ration") > 0:
                self.adjust_item(actor_id, "food_ration", -1); self._adjust_need(actor_id, "hunger", -55)
                self.event("npc_ate", actor_id=actor_id, location_id=self.actor(actor_id)["location_id"], payload={"source": "inventory"})
                self._schedule(actor_id, rng.randint(20, 35)); return True
            actor = self.actor(actor_id); location = str(actor["location_id"]); food = self.resource_qty(location, "food")
            if food > 0 and int(actor["cash_copper"]) >= 18:
                self.adjust_resource(location, "food", -1); self._change_cash(actor_id, -18, f"meal_at:{location}"); self._adjust_need(actor_id, "hunger", -60)
                self.event("npc_bought_meal", actor_id=actor_id, location_id=location, payload={"price_copper": 18}); self._schedule(actor_id, rng.randint(20, 40)); return True
            market = self.location_by_kind("market", location)
            if market and market != location:
                self.start_travel(actor_id, market, "seek_food"); return True
            return False

    def _rest(self, actor_id: str, rng: random.Random, deep: bool = False) -> None:
            fatigue_drop = rng.randint(45, 65) if deep else rng.randint(18, 35)
            self._adjust_need(actor_id, "fatigue", -fatigue_drop)
            energy = min(100, int(self.actor(actor_id)["energy"]) + (35 if deep else 15))
            self.db.execute("UPDATE actors SET energy=? WHERE id=?", (energy, actor_id))
            self.event("npc_slept" if deep else "npc_rested", actor_id=actor_id, location_id=self.actor(actor_id)["location_id"])
            self._schedule(actor_id, rng.randint(180, 300) if deep else rng.randint(45, 90))

    def _socialize(self, actor_id: str, rng: random.Random) -> bool:
            actor = self.actor(actor_id); others = self._same_location_npcs(actor_id, str(actor["location_id"]))
            if not others:
                square = self.location_by_kind("square", str(actor["location_id"]))
                if square and square != actor["location_id"]:
                    self.start_travel(actor_id, square, "seek_company"); return True
                return False
            other = rng.choice(others)
            rel = self.db.execute("SELECT * FROM relationships WHERE actor_id=? AND target_id=?", (actor_id, other)).fetchone()
            affinity = (int(rel["affinity"]) if rel else 0) + rng.choice([-2, -1, 1, 2, 3]); trust = (int(rel["trust"]) if rel else 0) + rng.choice([0, 0, 1])
            self.set_relationship(actor_id, other, affinity=max(-100, min(100, affinity)), trust=max(-100, min(100, trust)), respect=int(rel["respect"]) if rel else 0, fear=int(rel["fear"]) if rel else 0)
            shared = self._share_rumor(actor_id, other, rng); self._adjust_need(actor_id, "loneliness", -rng.randint(22, 45))
            self.event("npc_socialized", actor_id=actor_id, target_id=other, location_id=actor["location_id"], payload={"rumor_shared": shared}); self._schedule(actor_id, rng.randint(30, 70)); return True

    def _goal_action(self, actor_id: str, goal, rng: random.Random) -> None:
            self._ensure_plan(goal); actor = self.actor(actor_id); kind = str(goal["kind"]); target = loads(goal["target_json"], {}); location = str(actor["location_id"])
            target_location = target.get("location_id")
            if kind in {"publish", "produce_instrument", "profit"}: target_location = actor["work_location_id"]
            if kind == "restock_materials": target_location = "market"
            if target_location and location != target_location:
                self.start_travel(actor_id, str(target_location), f"goal:{kind}"); return
            if kind == "social":
                if self._socialize(actor_id, rng):
                    fresh = self.db.execute("SELECT * FROM goals WHERE id=?", (goal["id"],)).fetchone()
                    if fresh is not None: self._progress_goal(fresh, rng.randint(18, 35))
                    return
                self._schedule(actor_id, rng.randint(30, 60)); return
            if kind == "train":
                self._progress_goal(goal, rng.randint(13, 23)); self._adjust_need(actor_id, "fatigue", rng.randint(6, 10)); self._adjust_need(actor_id, "hunger", rng.randint(2, 5))
                self.db.execute("UPDATE actors SET energy=? WHERE id=?", (max(0, int(actor["energy"]) - rng.randint(5, 10)), actor_id))
                self.event("npc_trained", actor_id=actor_id, location_id=location, payload={"goal_id": int(goal["id"])}); self._schedule(actor_id, rng.randint(45, 75)); return
            if kind == "publish":
                if self.resource_qty(location, "paper") >= 1 and self.resource_qty(location, "ink") >= 1:
                    self.adjust_resource(location, "paper", -1); self.adjust_resource(location, "ink", -1); progress = self._progress_goal(goal, 25)
                    self.event("npc_published_work", actor_id=actor_id, location_id=location, payload={"progress": progress})
                    if progress >= 100: self.adjust_resource(location, "publication", 1)
                    self._schedule(actor_id, 60); return
                self.event("npc_blocked_by_resources", actor_id=actor_id, location_id=location, payload={"goal": "publish"})
                if not self._goal_exists(actor_id, "restock_materials"): self.add_goal(actor_id, "restock_materials", 92, {"work_location": location, "bundle": "publishing"}, source="blocked_by_resources")
                self._schedule(actor_id, 30); return
            if kind == "produce_instrument":
                if self.resource_qty(location, "wood") >= 2 and self.resource_qty(location, "string") >= 1:
                    self.adjust_resource(location, "wood", -2); self.adjust_resource(location, "string", -1); progress = self._progress_goal(goal, 20)
                    self.event("npc_crafted", actor_id=actor_id, location_id=location, payload={"progress": progress})
                    if progress >= 100: self.adjust_resource(location, "instrument", 1)
                    self._schedule(actor_id, 75); return
                self.event("npc_blocked_by_resources", actor_id=actor_id, location_id=location, payload={"goal": "produce_instrument"})
                if not self._goal_exists(actor_id, "restock_materials"): self.add_goal(actor_id, "restock_materials", 92, {"work_location": location, "bundle": "craft"}, source="blocked_by_resources")
                self._schedule(actor_id, 30); return
            if kind == "profit":
                earning = rng.randint(8, 65); self._change_cash(actor_id, earning, "autonomous_trade_income"); self._progress_goal(goal, rng.randint(6, 14))
                self.event("npc_traded", actor_id=actor_id, location_id=location, payload={"income_copper": earning}); self._schedule(actor_id, rng.randint(35, 80)); return
            if kind == "restock_food":
                row = self.db.execute("SELECT qty,capacity FROM location_resources WHERE location_id='market' AND resource='food'").fetchone()
                if row:
                    add = min(12, int(row["capacity"]) - int(row["qty"]))
                    if add > 0:
                        self.adjust_resource("market", "food", add); self._change_cash(actor_id, -min(int(actor["cash_copper"]), add * 6), "wholesale_food_restock")
                    self._progress_goal(goal, 100); self.event("market_restocked", actor_id=actor_id, location_id="market", payload={"food_added": add})
                self._schedule(actor_id, 90); return
            if kind == "restock_materials":
                bundle = str(target.get("bundle", "")); work = str(target.get("work_location") or actor["work_location_id"] or location)
                package = [("paper", 10, 5), ("ink", 6, 8)] if bundle == "publishing" else [("wood", 14, 7), ("string", 8, 9)]
                total_cost = sum(qty * unit for _, qty, unit in package)
                if int(actor["cash_copper"]) < total_cost:
                    self.event("npc_cannot_afford_materials", actor_id=actor_id, location_id=location, payload={"cost": total_cost, "bundle": bundle}); self._schedule(actor_id, 180); return
                self._change_cash(actor_id, -total_cost, f"material_purchase:{bundle}"); delivered = {}
                for resource, qty, _ in package:
                    row = self.db.execute("SELECT qty,capacity FROM location_resources WHERE location_id=? AND resource=?", (work, resource)).fetchone()
                    if row is None: continue
                    add = min(qty, int(row["capacity"]) - int(row["qty"]))
                    if add > 0: self.adjust_resource(work, resource, add)
                    delivered[resource] = add
                self._progress_goal(goal, 100); self.event("materials_restocked", actor_id=actor_id, location_id=work, payload={"bundle": bundle, "cost": total_cost, "delivered": delivered}); self._schedule(actor_id, 90); return
            if kind in {"security", "investigate_rumor"}:
                self._progress_goal(goal, rng.randint(12, 25)); self._adjust_need(actor_id, "fatigue", 4)
                self.event("npc_patrolled" if kind == "security" else "npc_investigated_rumor", actor_id=actor_id, location_id=location, payload={"goal_id": int(goal["id"])}); self._schedule(actor_id, rng.randint(40, 75)); return
            self._progress_goal(goal, rng.randint(8, 18)); self.event("npc_worked_on_goal", actor_id=actor_id, location_id=location, payload={"goal": kind}); self._schedule(actor_id, rng.randint(45, 90))

    def _autonomous_action(self, actor_id: str) -> None:
            actor = self.actor(actor_id)
            if int(actor["is_player"]) or actor["travel_destination"]: return
            rng = self._rng(f"npc:{actor_id}"); self._consider_initiative(actor_id, rng); actor = self.actor(actor_id); n = self.needs(actor_id); hour = (self.now % 1440) // 60; location = str(actor["location_id"])
            if int(n["fatigue"]) >= 82 or hour >= 23 or hour < 6:
                home = actor["home_location_id"]
                if home and location != home: self.start_travel(actor_id, str(home), "need:sleep")
                else: self._rest(actor_id, rng, deep=True)
                return
            if int(n["hunger"]) >= 68 and self._eat(actor_id, rng): return
            if int(n["loneliness"]) >= 68 and self._socialize(actor_id, rng): return
            goals = self.active_goals(actor_id)
            if goals:
                pool = goals[: min(3, len(goals))]; goal = rng.choice(pool) if len(pool) > 1 and rng.random() < 0.18 else pool[0]
                self._goal_action(actor_id, goal, rng); return
            roll = rng.random()
            if roll < 0.22 and self._socialize(actor_id, rng): return
            if roll < 0.52:
                edges = self.db.execute("SELECT b FROM location_edges WHERE a=? ORDER BY b", (location,)).fetchall()
                if edges: self.start_travel(actor_id, str(rng.choice(edges)["b"]), "idle_wander"); return
            self._rest(actor_id, rng)

    def advance(self, minutes: int, *, tick_minutes: int = 15) -> None:
            if minutes < 0: raise ValueError("cannot move time backwards")
            target = self.now + minutes
            while self.now < target:
                step = min(tick_minutes, target - self.now); old = self.now; self._set_now(self.now + step); self._age_needs(self.now - old); self._arrivals()
                due = self.db.execute("SELECT id FROM actors WHERE is_player=0 AND travel_destination IS NULL AND next_action_at<=? ORDER BY id", (self.now,)).fetchall()
                for row in due: self._autonomous_action(str(row["id"]))
            self.db.commit()

    def status(self) -> dict[str, Any]:
            actors = []
            for row in self.db.execute("SELECT * FROM actors ORDER BY id"):
                item = dict(row); item["personality"] = loads(item.pop("personality_json"), {}); item["cash"] = format_money(int(item.pop("cash_copper"))); item["needs"] = dict(self.needs(str(row["id"]))); actors.append(item)
            return {"world_minute": self.now, "world_time": format_world_minute(self.now), "actors": actors}

    def recent_events(self, limit: int = 50, include_hidden: bool = True) -> list[dict[str, Any]]:
            rows = self.db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall() if include_hidden else self.db.execute("SELECT * FROM events WHERE visibility<>'hidden_engine' ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            result = []
            for row in reversed(rows):
                d = dict(row); d["payload"] = loads(d.pop("payload_json"), {}); d["time"] = format_world_minute(d["world_minute"]); result.append(d)
            return result

    def autonomy_report(self) -> dict[str, Any]:
            counts = {str(r["event_type"]): int(r["n"]) for r in self.db.execute("SELECT event_type,COUNT(*) n FROM events GROUP BY event_type ORDER BY event_type")}
            goals = {str(r["status"]): int(r["n"]) for r in self.db.execute("SELECT status,COUNT(*) n FROM goals GROUP BY status")}
            rumor_spread = int(self.db.execute("SELECT COUNT(*) n FROM rumor_beliefs").fetchone()["n"]); initiated = int(self.db.execute("SELECT COUNT(*) n FROM events WHERE event_type='npc_initiative'").fetchone()["n"])
            player_events = int(self.db.execute("SELECT COUNT(*) n FROM events WHERE actor_id IN (SELECT id FROM actors WHERE is_player=1) AND event_type NOT IN ('world_seeded')").fetchone()["n"])
            resources = [dict(r) for r in self.db.execute("SELECT * FROM location_resources ORDER BY location_id,resource")]
            return {"world_time": format_world_minute(self.now), "event_counts": counts, "goal_status": goals, "rumor_beliefs": rumor_spread, "npc_initiatives": initiated, "player_autonomous_events": player_events, "resources": resources}
