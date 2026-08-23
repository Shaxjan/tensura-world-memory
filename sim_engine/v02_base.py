from __future__ import annotations

import heapq
import json
import random
import sqlite3
from pathlib import Path
from typing import Any

COPPER_PER_SILVER = 100
COPPER_PER_GOLD = 10_000

def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

def loads(value: str | None, default: Any) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)

def format_money(copper: int) -> str:
    sign = "-" if copper < 0 else ""
    copper = abs(int(copper))
    g, rem = divmod(copper, COPPER_PER_GOLD)
    s, c = divmod(rem, COPPER_PER_SILVER)
    return f"{sign}{g}g {s:02d}s {c:02d}c"

def format_world_minute(world_minute: int) -> str:
    day, rem = divmod(int(world_minute), 1440)
    hour, minute = divmod(rem, 60)
    return f"T+{day} {hour:02d}:{minute:02d}"


class BaseWorld:
    def __init__(self, db_path: str | Path):
            self.db_path = str(db_path)
            self.db = sqlite3.connect(self.db_path)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
            self.db.close()

    def __enter__(self) -> "SimulationV02":
            return self

    def __exit__(self, *exc: object) -> None:
            self.close()

    @classmethod
    def create(
            cls,
            db_path: str | Path,
            schema_path: str | Path,
            *,
            seed: int,
            start_minute: int,
        ) -> "SimulationV02":
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                path.unlink()
            sim = cls(path)
            sim.db.executescript(Path(schema_path).read_text(encoding="utf-8"))
            sim.set_meta("world_seed", str(seed))
            sim.set_meta("world_minute", str(start_minute))
            sim.set_meta("rng_counter", "0")
            sim.db.commit()
            return sim

    def set_meta(self, key: str, value: str) -> None:
            self.db.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_meta(self, key: str) -> str:
            row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            if row is None:
                raise KeyError(key)
            return str(row["value"])

    @property
    def now(self) -> int:
            return int(self.get_meta("world_minute"))

    @property
    def world_seed(self) -> int:
            return int(self.get_meta("world_seed"))

    def _set_now(self, minute: int) -> None:
            self.set_meta("world_minute", str(int(minute)))

    def _rng(self, namespace: str) -> random.Random:
            n = int(self.get_meta("rng_counter")) + 1
            self.set_meta("rng_counter", str(n))
            return random.Random(f"{self.world_seed}:{n}:{namespace}")

    def event(
            self,
            event_type: str,
            *,
            actor_id: str | None = None,
            target_id: str | None = None,
            location_id: str | None = None,
            payload: dict[str, Any] | None = None,
            visibility: str = "hidden_engine",
        ) -> int:
            cur = self.db.execute(
                "INSERT INTO events(world_minute,event_type,actor_id,target_id,location_id,payload_json,visibility) VALUES(?,?,?,?,?,?,?)",
                (self.now, event_type, actor_id, target_id, location_id, dumps(payload or {}), visibility),
            )
            return int(cur.lastrowid)

    def add_location(self, location_id: str, name: str, kind: str, tags: list[str] | None = None) -> None:
            self.db.execute(
                "INSERT OR REPLACE INTO locations(id,name,kind,tags_json) VALUES(?,?,?,?)",
                (location_id, name, kind, dumps(tags or [])),
            )

    def connect(self, a: str, b: str, minutes: int) -> None:
            if minutes <= 0:
                raise ValueError("travel time must be positive")
            self.db.execute("INSERT OR REPLACE INTO location_edges VALUES(?,?,?)", (a, b, minutes))
            self.db.execute("INSERT OR REPLACE INTO location_edges VALUES(?,?,?)", (b, a, minutes))

    def shortest_path(self, start: str, goal: str) -> tuple[int, list[str]]:
            if start == goal:
                return 0, [start]
            graph: dict[str, list[tuple[str, int]]] = {}
            for row in self.db.execute("SELECT a,b,travel_minutes FROM location_edges"):
                graph.setdefault(str(row["a"]), []).append((str(row["b"]), int(row["travel_minutes"])))
            queue: list[tuple[int, str, list[str]]] = [(0, start, [start])]
            best: dict[str, int] = {}
            while queue:
                cost, node, path = heapq.heappop(queue)
                if node in best and best[node] <= cost:
                    continue
                best[node] = cost
                if node == goal:
                    return cost, path
                for nxt, weight in graph.get(node, []):
                    heapq.heappush(queue, (cost + weight, nxt, path + [nxt]))
            raise ValueError(f"No route {start}->{goal}")

    def location_by_kind(self, kind: str, from_location: str) -> str | None:
            options = self.db.execute("SELECT id FROM locations WHERE kind=? ORDER BY id", (kind,)).fetchall()
            ranked: list[tuple[int, str]] = []
            for row in options:
                try:
                    minutes, _ = self.shortest_path(from_location, str(row["id"]))
                    ranked.append((minutes, str(row["id"])))
                except ValueError:
                    pass
            return min(ranked)[1] if ranked else None

    def add_actor(
            self,
            actor_id: str,
            name: str,
            *,
            location_id: str,
            is_player: bool = False,
            home_location_id: str | None = None,
            work_location_id: str | None = None,
            cash_copper: int = 0,
            energy: int = 100,
            mood: int = 0,
            personality: dict[str, Any] | None = None,
            needs: dict[str, int] | None = None,
        ) -> None:
            self.db.execute(
                """INSERT INTO actors(id,name,is_player,location_id,home_location_id,work_location_id,status,
                   cash_copper,energy,mood,personality_json,next_action_at)
                   VALUES(?,?,?,?,?,?,'idle',?,?,?,?,?)""",
                (
                    actor_id, name, int(is_player), location_id, home_location_id, work_location_id,
                    cash_copper, energy, mood, dumps(personality or {}), self.now,
                ),
            )
            n = {"hunger": 0, "fatigue": 0, "loneliness": 0, "danger": 0, **(needs or {})}
            self.db.execute(
                "INSERT INTO needs(actor_id,hunger,fatigue,loneliness,danger,updated_at) VALUES(?,?,?,?,?,?)",
                (actor_id, n["hunger"], n["fatigue"], n["loneliness"], n["danger"], self.now),
            )
            if cash_copper:
                self.db.execute(
                    "INSERT INTO ledger(world_minute,actor_id,delta_copper,reason,balance_after) VALUES(?,?,?,?,?)",
                    (self.now, actor_id, cash_copper, "initial_balance", cash_copper),
                )

    def actor(self, actor_id: str) -> sqlite3.Row:
            row = self.db.execute("SELECT * FROM actors WHERE id=?", (actor_id,)).fetchone()
            if row is None:
                raise KeyError(actor_id)
            return row

    def needs(self, actor_id: str) -> sqlite3.Row:
            row = self.db.execute("SELECT * FROM needs WHERE actor_id=?", (actor_id,)).fetchone()
            if row is None:
                raise KeyError(actor_id)
            return row

    def _adjust_need(self, actor_id: str, field: str, delta: int) -> None:
            if field not in {"hunger", "fatigue", "loneliness", "danger"}:
                raise ValueError(field)
            row = self.needs(actor_id)
            value = max(0, min(100, int(row[field]) + int(delta)))
            self.db.execute(f"UPDATE needs SET {field}=?,updated_at=? WHERE actor_id=?", (value, self.now, actor_id))

    def _age_needs(self, elapsed: int) -> None:
            if elapsed <= 0:
                return
            rows = self.db.execute("SELECT actor_id,hunger,fatigue,loneliness,danger FROM needs").fetchall()
            for row in rows:
                actor = self.actor(str(row["actor_id"]))
                hunger = min(100, int(row["hunger"]) + elapsed // 45)
                fatigue_rate = 35 if actor["status"] == "traveling" else 70
                fatigue = min(100, int(row["fatigue"]) + elapsed // fatigue_rate)
                loneliness = min(100, int(row["loneliness"]) + elapsed // 180)
                danger = max(0, int(row["danger"]) - elapsed // 240)
                self.db.execute(
                    "UPDATE needs SET hunger=?,fatigue=?,loneliness=?,danger=?,updated_at=? WHERE actor_id=?",
                    (hunger, fatigue, loneliness, danger, self.now, row["actor_id"]),
                )

    def _change_cash(self, actor_id: str, delta: int, reason: str) -> int:
            before = int(self.actor(actor_id)["cash_copper"])
            after = before + int(delta)
            if after < 0:
                raise ValueError(f"insufficient funds: {actor_id} has {format_money(before)}")
            self.db.execute("UPDATE actors SET cash_copper=? WHERE id=?", (after, actor_id))
            self.db.execute(
                "INSERT INTO ledger(world_minute,actor_id,delta_copper,reason,balance_after) VALUES(?,?,?,?,?)",
                (self.now, actor_id, int(delta), reason, after),
            )
            return after

    def credit(self, actor_id: str, amount: int, reason: str) -> int:
            if amount < 0:
                raise ValueError("amount")
            with self.db:
                return self._change_cash(actor_id, amount, reason)

    def debit(self, actor_id: str, amount: int, reason: str) -> int:
            if amount < 0:
                raise ValueError("amount")
            with self.db:
                return self._change_cash(actor_id, -amount, reason)

    def transfer(self, payer: str, payee: str, amount: int, reason: str) -> tuple[int, int]:
            if amount <= 0:
                raise ValueError("amount")
            with self.db:
                p = self._change_cash(payer, -amount, f"payment:{reason}:to:{payee}")
                r = self._change_cash(payee, amount, f"receipt:{reason}:from:{payer}")
                self.event("money_transfer", actor_id=payer, target_id=payee, payload={"amount": amount, "reason": reason})
                return p, r

    def add_item(self, item_id: str, name: str, kind: str, base_value_copper: int = 0, consumable: bool = False) -> None:
            self.db.execute(
                "INSERT OR REPLACE INTO items(id,name,kind,base_value_copper,consumable) VALUES(?,?,?,?,?)",
                (item_id, name, kind, base_value_copper, int(consumable)),
            )

    def item_qty(self, actor_id: str, item_id: str) -> int:
            row = self.db.execute("SELECT qty FROM inventory WHERE actor_id=? AND item_id=?", (actor_id, item_id)).fetchone()
            return int(row["qty"]) if row else 0

    def adjust_item(self, actor_id: str, item_id: str, delta: int) -> int:
            before = self.item_qty(actor_id, item_id)
            after = before + int(delta)
            if after < 0:
                raise ValueError(f"insufficient item {item_id}")
            self.db.execute(
                "INSERT INTO inventory(actor_id,item_id,qty) VALUES(?,?,?) ON CONFLICT(actor_id,item_id) DO UPDATE SET qty=excluded.qty",
                (actor_id, item_id, after),
            )
            return after

    def set_resource(self, location_id: str, resource: str, qty: int, capacity: int) -> None:
            if qty < 0 or capacity < qty:
                raise ValueError("resource quantity/capacity")
            self.db.execute(
                "INSERT OR REPLACE INTO location_resources(location_id,resource,qty,capacity) VALUES(?,?,?,?)",
                (location_id, resource, qty, capacity),
            )

    def resource_qty(self, location_id: str, resource: str) -> int:
            row = self.db.execute(
                "SELECT qty FROM location_resources WHERE location_id=? AND resource=?",
                (location_id, resource),
            ).fetchone()
            return int(row["qty"]) if row else 0

    def adjust_resource(self, location_id: str, resource: str, delta: int) -> int:
            row = self.db.execute(
                "SELECT qty,capacity FROM location_resources WHERE location_id=? AND resource=?",
                (location_id, resource),
            ).fetchone()
            if row is None:
                raise KeyError((location_id, resource))
            after = int(row["qty"]) + int(delta)
            if after < 0 or after > int(row["capacity"]):
                raise ValueError(f"resource bounds {location_id}:{resource}")
            self.db.execute(
                "UPDATE location_resources SET qty=? WHERE location_id=? AND resource=?",
                (after, location_id, resource),
            )
            return after
