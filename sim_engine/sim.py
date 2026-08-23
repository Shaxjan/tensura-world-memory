from __future__ import annotations

import argparse
import heapq
import json
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

COPPER_PER_SILVER = 100
COPPER_PER_GOLD = 10_000


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def format_money(copper: int) -> str:
    if copper < 0:
        return "-" + format_money(-copper)
    g, rem = divmod(copper, COPPER_PER_GOLD)
    s, c = divmod(rem, COPPER_PER_SILVER)
    return f"{g}g {s:02d}s {c:02d}c"


def format_world_minute(world_minute: int) -> str:
    day, rem = divmod(world_minute, 1440)
    hour, minute = divmod(rem, 60)
    return f"T+{day} {hour:02d}:{minute:02d}"


@dataclass(frozen=True)
class Reaction:
    observer_id: str
    attention: int
    score: int
    category: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "observer_id": self.observer_id,
            "attention": self.attention,
            "score": self.score,
            "category": self.category,
        }


class Simulation:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "Simulation":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @classmethod
    def create(cls, db_path: str | Path, schema_path: str | Path, *, seed: int, start_minute: int) -> "Simulation":
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()
        sim = cls(db_path)
        schema = Path(schema_path).read_text(encoding="utf-8")
        sim.db.executescript(schema)
        sim.set_meta("world_seed", str(seed))
        sim.set_meta("world_minute", str(start_minute))
        sim.set_meta("tick_counter", "0")
        sim.db.commit()
        return sim

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def get_meta(self, key: str) -> str:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if not row:
            raise KeyError(key)
        return str(row["value"])

    @property
    def now(self) -> int:
        return int(self.get_meta("world_minute"))

    @property
    def world_seed(self) -> int:
        return int(self.get_meta("world_seed"))

    def _set_now(self, minute: int) -> None:
        self.set_meta("world_minute", str(minute))

    def _next_rng(self, namespace: str) -> random.Random:
        counter = int(self.get_meta("tick_counter")) + 1
        self.set_meta("tick_counter", str(counter))
        return random.Random(f"{self.world_seed}:{counter}:{namespace}")

    def event(
        self,
        event_type: str,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        location_id: str | None = None,
        payload: dict[str, Any] | None = None,
        visibility: str = "world",
    ) -> int:
        cur = self.db.execute(
            "INSERT INTO events(world_minute,event_type,actor_id,target_id,location_id,payload_json,visibility) "
            "VALUES(?,?,?,?,?,?,?)",
            (self.now, event_type, actor_id, target_id, location_id, dumps(payload or {}), visibility),
        )
        return int(cur.lastrowid)

    # ---------- World geometry ----------

    def add_location(self, location_id: str, name: str, kind: str = "place") -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO locations(id,name,kind) VALUES(?,?,?)",
            (location_id, name, kind),
        )

    def connect(self, a: str, b: str, travel_minutes: int) -> None:
        if travel_minutes <= 0:
            raise ValueError("travel_minutes must be positive")
        self.db.execute(
            "INSERT OR REPLACE INTO location_edges(a,b,travel_minutes) VALUES(?,?,?)",
            (a, b, travel_minutes),
        )
        self.db.execute(
            "INSERT OR REPLACE INTO location_edges(a,b,travel_minutes) VALUES(?,?,?)",
            (b, a, travel_minutes),
        )

    def shortest_path(self, start: str, goal: str) -> tuple[int, list[str]]:
        if start == goal:
            return 0, [start]
        graph: dict[str, list[tuple[str, int]]] = {}
        for row in self.db.execute("SELECT a,b,travel_minutes FROM location_edges"):
            graph.setdefault(row["a"], []).append((row["b"], int(row["travel_minutes"])))
        heap: list[tuple[int, str, list[str]]] = [(0, start, [start])]
        seen: dict[str, int] = {}
        while heap:
            cost, node, path = heapq.heappop(heap)
            if node in seen and seen[node] <= cost:
                continue
            seen[node] = cost
            if node == goal:
                return cost, path
            for nxt, weight in graph.get(node, []):
                heapq.heappush(heap, (cost + weight, nxt, path + [nxt]))
        raise ValueError(f"No route from {start} to {goal}")

    # ---------- Actors ----------

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
        goals: list[str] | None = None,
    ) -> None:
        self.db.execute(
            """
            INSERT OR REPLACE INTO actors(
              id,name,is_player,location_id,home_location_id,work_location_id,status,
              energy,mood,cash_copper,personality_json,goals_json,next_action_at
            ) VALUES(?,?,?,?,?,?,'idle',?,?,?,?,?,?)
            """,
            (
                actor_id, name, int(is_player), location_id, home_location_id, work_location_id,
                energy, mood, cash_copper, dumps(personality or {}), dumps(goals or []), self.now,
            ),
        )
        if cash_copper:
            self.db.execute(
                "INSERT INTO ledger(world_minute,actor_id,delta_copper,reason,balance_after) VALUES(?,?,?,?,?)",
                (self.now, actor_id, cash_copper, "initial_balance", cash_copper),
            )

    def actor(self, actor_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM actors WHERE id=?", (actor_id,)).fetchone()
        if not row:
            raise KeyError(actor_id)
        return row

    def set_preference(self, actor_id: str, tag: str, weight: int) -> None:
        weight = max(-100, min(100, int(weight)))
        self.db.execute(
            "INSERT INTO preferences(actor_id,tag,weight) VALUES(?,?,?) "
            "ON CONFLICT(actor_id,tag) DO UPDATE SET weight=excluded.weight",
            (actor_id, tag, weight),
        )

    def set_relationship(
        self,
        actor_id: str,
        target_id: str,
        *,
        affinity: int = 0,
        trust: int = 0,
        fear: int = 0,
        respect: int = 0,
    ) -> None:
        vals = (
            max(-100, min(100, affinity)),
            max(-100, min(100, trust)),
            max(0, min(100, fear)),
            max(-100, min(100, respect)),
        )
        self.db.execute(
            """
            INSERT INTO relationships(actor_id,target_id,affinity,trust,fear,respect,updated_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(actor_id,target_id) DO UPDATE SET
              affinity=excluded.affinity,trust=excluded.trust,fear=excluded.fear,
              respect=excluded.respect,updated_at=excluded.updated_at
            """,
            (actor_id, target_id, *vals, self.now),
        )

    # ---------- Economy: deterministic and atomic ----------

    def _change_cash(self, actor_id: str, delta: int, reason: str) -> int:
        row = self.actor(actor_id)
        before = int(row["cash_copper"])
        after = before + int(delta)
        if after < 0:
            raise ValueError(
                f"Insufficient funds for {actor_id}: {format_money(before)}; "
                f"requested {format_money(-delta)}"
            )
        self.db.execute("UPDATE actors SET cash_copper=? WHERE id=?", (after, actor_id))
        self.db.execute(
            "INSERT INTO ledger(world_minute,actor_id,delta_copper,reason,balance_after) VALUES(?,?,?,?,?)",
            (self.now, actor_id, delta, reason, after),
        )
        return after

    def credit(self, actor_id: str, amount: int, reason: str) -> int:
        if amount < 0:
            raise ValueError("credit amount must be >= 0")
        with self.db:
            return self._change_cash(actor_id, amount, reason)

    def debit(self, actor_id: str, amount: int, reason: str) -> int:
        if amount < 0:
            raise ValueError("debit amount must be >= 0")
        with self.db:
            return self._change_cash(actor_id, -amount, reason)

    def transfer(self, payer_id: str, payee_id: str, amount: int, reason: str) -> tuple[int, int]:
        if amount <= 0:
            raise ValueError("transfer amount must be > 0")
        with self.db:
            payer = self._change_cash(payer_id, -amount, f"payment:{reason}:to:{payee_id}")
            payee = self._change_cash(payee_id, amount, f"receipt:{reason}:from:{payer_id}")
            self.event(
                "money_transfer",
                actor_id=payer_id,
                target_id=payee_id,
                payload={"amount_copper": amount, "reason": reason},
            )
            return payer, payee

    # ---------- Truth vs character knowledge ----------

    def set_fact(self, key: str, value: Any, *, source: str = "world") -> None:
        self.db.execute(
            """
            INSERT INTO facts(key,value_json,created_at,source) VALUES(?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,source=excluded.source
            """,
            (key, dumps(value), self.now, source),
        )

    def teach_fact(self, actor_id: str, fact_key: str, *, source: str, confidence: int = 100) -> None:
        if not self.db.execute("SELECT 1 FROM facts WHERE key=?", (fact_key,)).fetchone():
            raise KeyError(f"Unknown world fact: {fact_key}")
        self.db.execute(
            """
            INSERT INTO knowledge(actor_id,fact_key,learned_at,source,confidence)
            VALUES(?,?,?,?,?)
            ON CONFLICT(actor_id,fact_key) DO UPDATE SET
              learned_at=excluded.learned_at,source=excluded.source,confidence=excluded.confidence
            """,
            (actor_id, fact_key, self.now, source, max(0, min(100, confidence))),
        )

    def known_fact(self, actor_id: str, fact_key: str) -> Any | None:
        row = self.db.execute(
            """
            SELECT f.value_json FROM knowledge k
            JOIN facts f ON f.key=k.fact_key
            WHERE k.actor_id=? AND k.fact_key=?
            """,
            (actor_id, fact_key),
        ).fetchone()
        return loads(row["value_json"], None) if row else None

    # ---------- Travel ----------

    def start_travel(self, actor_id: str, destination: str, *, reason: str = "self_directed") -> int:
        actor = self.actor(actor_id)
        if actor["travel_destination"]:
            raise ValueError(f"{actor_id} is already traveling")
        origin = str(actor["location_id"])
        duration, path = self.shortest_path(origin, destination)
        arrival = self.now + duration
        self.db.execute(
            "UPDATE actors SET status='traveling',travel_destination=?,travel_arrival_at=?,next_action_at=? WHERE id=?",
            (destination, arrival, arrival, actor_id),
        )
        self.event(
            "travel_started",
            actor_id=actor_id,
            location_id=origin,
            payload={"destination": destination, "duration": duration, "path": path, "reason": reason},
        )
        return arrival

    def _process_arrivals(self) -> None:
        rows = self.db.execute(
            """
            SELECT id,location_id,travel_destination,travel_arrival_at FROM actors
            WHERE travel_destination IS NOT NULL AND travel_arrival_at<=?
            """,
            (self.now,),
        ).fetchall()
        for row in rows:
            dest = str(row["travel_destination"])
            self.db.execute(
                """
                UPDATE actors SET location_id=?,status='idle',travel_destination=NULL,
                  travel_arrival_at=NULL,next_action_at=?
                WHERE id=?
                """,
                (dest, self.now, row["id"]),
            )
            self.event("travel_arrived", actor_id=row["id"], location_id=dest)

    # ---------- Reactions: structured outcome, no prose ----------

    def resolve_reaction(
        self,
        observer_id: str,
        *,
        source_actor_id: str | None,
        tags: Iterable[str],
        intensity: int = 50,
    ) -> Reaction:
        observer = self.actor(observer_id)
        tags = list(tags)
        pref_rows = self.db.execute(
            f"SELECT tag,weight FROM preferences WHERE actor_id=? AND tag IN ({j,'.join('?' for _ in tags)})",
            (observer_id, *tags),
        ).fetchall() if tags else []
        pref = sum(int(r["weight"]) for r in pref_rows) / max(1, len(tags))
        personality = loads(observer["personality_json"], {})
        curiosity = int(personality.get("curiosity", 50))
        sociability = int(personality.get("sociability", 50))

        affinity = trust = respect = fear = 0
        if source_actor_id:
            rel = self.db.execute(
                "SELECT * FROM relationships WHERE actor_id=? AND target_id=?",
                (observer_id, source_actor_id),
            ).fetchone()
            if rel:
                affinity, trust, respect, fear = (
                    int(rel["affinity"]), int(rel["trust"]), int(rel["respect"]), int(rel["fear"])
                )

        rng = self._next_rng(f"reaction:{observer_id}:{source_actor_id}:{','.join(sorted(tags))}")
        attention_noise = rng.randint(-25, 25)
        score_noise = rng.randint(-22, 22)

        attention = round(
            max(0, min(100,
                intensity * 0.45 + curiosity * 0.25 + sociability * 0.10
                + min(25, abs(pref) * 0.25) + attention_noise
            ))
        )
        score = round(
            max(-100, min(100,
                pref * 0.55 + affinity * 0.18 + trust * 0.08 + respect * 0.10
                - fear * 0.08 + int(observer["mood"]) * 0.10 + score_noise
            ))
        )

        if attention < 25:
            category = "ignore"
        elif score <= -50:
            category = "strong_negative"
        elif score <= -15:
            category = "negative"
        elif score < 20:
            category = "neutral"
        elif score < 55:
            category = "positive"
        else:
            category = "strong_positive"

        result = Reaction(observer_id, attention, score, category)
        self.event(
            "reaction",
            actor_id=observer_id,
            target_id=source_actor_id,
            location_id=observer["location_id"],
            payload={"tags": tags, "intensity": intensity, **result.as_dict()},
            visibility="hidden_engine",
        )
        return result

    # ---------- Autonomous world ----------

    def _schedule_next(self, actor_id: str, minutes: int) -> None:
        self.db.execute(
            "UPDATE actors SET next_action_at=? WHERE id=?",
            (self.now + max(1, minutes), actor_id),
        )

    def _pick_same_location_npc(self, actor_id: str, location_id: str, rng: random.Random) -> str | None:
        rows = self.db.execute(
            """
            SELECT id FROM actors
            WHERE id<>? AND is_player=0 AND location_id=? AND travel_destination IS NULL
            ORDER BY id
            """,
            (actor_id, location_id),
        ).fetchall()
        return str(rng.choice(rows)["id"]) if rows else None

    def _free_time_action(self, actor: sqlite3.Row, rng: random.Random) -> None:
        p = loads(actor["personality_json"], {})
        curiosity = int(p.get("curiosity", 50))
        sociability = int(p.get("sociability", 50))
        discipline = int(p.get("discipline", 50))
        options = [
            ("rest", 20 + max(0, 50 - int(actor["energy"]))),
            ("wander", 10 + curiosity),
            ("socialize", 10 + sociability),
            ("home", 10 + discipline // 2),
        ]
        total = sum(weight for _, weight in options)
        roll = rng.uniform(0, total)
        upto = 0.0
        choice = "rest"
        for name, weight in options:
            upto += weight
            if roll <= upto:
                choice = name
                break

        location = str(actor["location_id"])
        if choice == "home" and actor["home_location_id"] and location != actor["home_location_id"]:
            self.start_travel(actor["id"], str(actor["home_location_id"]), reason="autonomous_home")
            return
        if choice == "wander":
            edges = self.db.execute(
                "SELECT b FROM location_edges WHERE a=? ORDER BY b", (location,)
            ).fetchall()
            if edges:
                destination = str(rng.choice(edges)["b"])
                self.start_travel(actor["id"], destination, reason="autonomous_wander")
                return
        if choice == "socialize":
            other = self._pick_same_location_npc(str(actor["id"]), location, rng)
            if other:
                delta = rng.choice([-2, -1, 1, 1, 2, 3])
                rel = self.db.execute(
                    "SELECT affinity,trust,fear,respect FROM relationships WHERE actor_id=? AND target_id=?",
                  (actor["id"], other),
                ).fetchone()
                affinity = (int(rel["affinity"]) if rel else 0) + delta
                trust = (int(rel["trust"]) if rel else 0) + (1 if delta > 0 else 0)
                self.set_relationship(
                    str(actor["id"]), other,
                    affinity=max(-100, min(100, affinity)),
                    trust=max(-100, min(100, trust)),
                    fear=int(rel["fear"]) if rel else 0,
                    respect=int(rel["respect"]) if rel else 0,
                )
                self.event(
                    "npc_socialized",
                    actor_id=actor["id"], target_id=other, location_id=location,
                    payload={"affinity_delta": delta},
                    visibility="hidden_engine",
                )
                self._schedule_next(str(actor["id"]), rng.randint(25, 70))
                return

        # rest / fallback
        new_energy = min(100, int(actor["energy"]) + rng.randint(5, 15))
        self.db.execute("UPDATE actors SET energy=? WHERE id=?", (new_energy, actor["id"]))
        self.event("npc_rest", actor_id=actor["id"], location_id=location, visibility="hidden_engine")
        self._schedule_next(str(actor["id"]), rng.randint(30, 90))

    def _autonomous_action(self, actor_id: str) -> None:
        actor = self.actor(actor_id)
        if actor["is_player"] or actor["travel_destination"]:
            return
        rng = self._next_rng(f"npc:{actor_id}")
        hour = (self.now % 1440) // 60
        location = str(actor["location_id"])
        energy = int(actor["energy"])

        if energy <= 20:
            home = actor["home_location_id"]
            if home and location != home:
                self.start_travel(actor_id, str(home), reason="autonomous_exhaustion")
            else:
                restored = min(100, energy + rng.randint(25, 45))
                self.db.execute("UPDATE actors SET energy=? WHERE id=?", (restored, actor_id))
                self.event("npc_deep_rest", actor_id=actor_id, location_id=location, visibility="hidden_engine")
                self._schedule_next(actor_id, rng.randint(90, 180))
            return

        if hour >= 22 or hour < 6:
            home = actor["home_location_id"]
            if home and location != home:
                self.start_travel(actor_id, str(home), reason="autonomous_night_home")
            else:
                restored = min(100, energy + rng.randint(20, 35))
                self.db.execute("UPDATE actors SET energy=? WHERE id=?", (restored, actor_id))
                self.event("npc_sleep", actor_id=actor_id, location_id=location, visibility="hidden_engine")
                self._schedule_next(actor_id, rng.randint(120, 240))
            return
        if 8 <= hour < 17 and actor["work_location_id"]:
            work = str(actor["work_location_id"])
            if location != work:
                self.start_travel(actor_id, work, reason="autonomous_work")
            else:
                self.db.execute(
                    "UPDATE actors SET energy=? WHERE id=?",
                    (max(0, energy - rng.randint(3, 9)), actor_id),
                )
                self.event("npc_worked", actor_id=actor_id, location_id=location, visibility="hidden_engine")
                self._schedule_next(actor_id, rng.randint(45, 90))
            return

        self._free_time_action(actor, rng)

    def _process_scheduled(self) -> None:
        rows = self.db.execute(
            """
            SELECT * FROM scheduled_events
            WHERE status='pending' AND due_minute<=?
            ORDER BY due_minute,id
            """,
            (self.now,),
        ).fetchall()
        for row in rows:
            self.event(
                str(row["event_type"]),
                actor_id=row["actor_id"],
                target_id=row["target_id"],
                location_id=row["location_id"],
                payload=loads(row["payload_json"], {}),
            )
            self.db.execute("UPDATE scheduled_events SET status='done' WHERE id=?", (row["id"],))

    def schedule_event(
        self,
        due_minute: int,
        event_type: str,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        location_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO scheduled_events(due_minute,event_type,actor_id,target_id,location_id,payload_json,status)
            VALUES(?,?,?,?,?,?,'pending')
            """,
            (due_minute, event_type, actor_id, target_id, location_id, dumps(payload or {})),
        )
        return int(cur.lastrowid)

    def advance(self, minutes: int) -> None:
        if minutes < 0:
            raise ValueError("Cannot move world time backwards")
        target = self.now + minutes
        while self.now < target:
            candidates = [target]
            row = self.db.execute(
                "SELECT MIN(next_action_at) AS m FROM actors WHERE is_player=0"
            ).fetchone()
            if row and row["m"] is not None and int(row["m"]) > self.now:
                candidates.append(int(row["m"]))
            row = self.db.execute(
                "SELECT MIN(travel_arrival_at) AS m FROM actors WHERE travel_destination IS NOT NULL"
            ).fetchone()
            if row and row["m"] is not None and int(row["m"]) > self.now:
                candidates.append(int(row["m"]))
            row = self.db.execute(
                "SELECT MIN(due_minute) AS m FROM scheduled_events WHERE status='pending'"
            ).fetchone()
            if row and row["m"] is not None and int(row["m"]) > self.now:
                candidates.append(int(row["m"]))

            next_minute = min(candidates)
            self._set_now(next_minute)
            self._process_arrivals()
            self._process_scheduled()

            due = self.db.execute(
                """
                SELECT id FROM actors
                WHERE is_player=0 AND travel_destination IS NULL AND next_action_at<=?
                ORDER BY id
                """,
                (self.now,),
            ).fetchall()
            for row in due:
                self._autonomous_action(str(row["id"]))

        self.db.commit()

    # ---------- Read models for an LLM/UI ----------

    def status(self) -> dict[str, Any]:
        actors = []
        for row in self.db.execute(
            "SELECT id,name,is_player,location_id,status,energy,mood,cash_copper,travel_destination,travel_arrival_at FROM actors ORDER BY id"
        ):
            item = dict(row)
            item["cash"] = format_money(int(item.pop("cash_copper")))
            if item["travel_arrival_at"] is not None:
                item["travel_arrival"] = format_world_minute(int(item["travel_arrival_at"]))
            actors.append(item)
        return {
            "world_minute": self.now,
            "world_time": format_world_minute(self.now),
            "actors": actors,
        }

    def recent_events(self, limit: int = 20, *, include_hidden: bool = False) -> list[dict[str, Any]]:
        if include_hidden:
            rows = self.db.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM events WHERE visibility<>'hidden_engine' ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for row in reversed(rows):
            d = dict(row)
            d["time"] = format_world_minute(int(d["world_minute"]))
            d["payload"] = loads(d.pop("payload_json"), {})
            result.append(d)
        return result


def cli() -> None:
    parser = argparse.ArgumentParser(description="Tensura simulation core v0.1")
    parser.add_argument("--db", default="world.db")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status")
    p = sub.add_parser("advance")
    p.add_argument("minutes", type=int)

    p = sub.add_parser("events")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--hidden", action="store_true")

    p = sub.add_parser("transfer")
    p.add_argument("payer")
    p.add_argument("payee")
    p.add_argument("copper", type=int)
    p.add_argument("reason")

    args = parser.parse_args()
    with Simulation(args.db) as sim:
        if args.cmd == "status":
            print(json.dumps(sim.status(), ensure_ascii=False, indent=2))
        elif args.cmd == "advance":
            sim.advance(args.minutes)
            print(json.dumps(sim.status(), ensure_ascii=False, indent=2))
        elif args.cmd == "events":
            print(json.dumps(sim.recent_events(args.limit, include_hidden=args.hidden), ensure_ascii=False, indent=2))
        elif args.cmd == "transfer":
            before = format_money(int(sim.actor(args.payer)["cash_copper"]))
            payer_after, payee_after = sim.transfer(args.payer, args.payee, args.copper, args.reason)
            print(json.dumps({
                "payer_before": before,
                "payer_after": format_money(payer_after),
                "payee_after": format_money(payee_after),
            }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
