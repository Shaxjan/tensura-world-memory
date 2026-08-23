from __future__ import annotations

from typing import Any

from v03_engine import DAY, dumps, loads


class MemoryCanonMixin:
    def remember(self, actor_id: str, key: str, summary: str, *, salience: int, emotional: int = 0) -> None:
        salience = max(0, min(100, int(salience)))
        emotional = max(0, min(100, int(emotional)))
        decay = 0 if salience >= 80 or emotional >= 75 else max(1, 7 - salience // 20)
        self.db.execute(
            """
            INSERT INTO memories(actor_id,memory_key,summary,salience,emotional,decay_per_day,created_at,last_recalled_at,status)
            VALUES(?,?,?,?,?,?,?,?, 'active')
            ON CONFLICT(actor_id,memory_key) DO UPDATE SET
              summary=excluded.summary,
              salience=MAX(memories.salience,excluded.salience),
              emotional=MAX(memories.emotional,excluded.emotional),
              decay_per_day=MIN(memories.decay_per_day,excluded.decay_per_day),
              last_recalled_at=excluded.last_recalled_at,
              status='active'
            """,
            (actor_id, key, summary, salience, emotional, decay, self.now, self.now),
        )

    def recall(self, actor_id: str, key: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM memories WHERE actor_id=? AND memory_key=? AND status='active'",
            (actor_id, key),
        ).fetchone()
        if row is None:
            return None
        self.db.execute(
            "UPDATE memories SET salience=MIN(100,salience+3),last_recalled_at=? WHERE id=?",
            (self.now, row["id"]),
        )
        return {"key": str(row["memory_key"]), "summary": str(row["summary"]), "salience": min(100, int(row["salience"]) + 3)}

    def _decay_memories(self) -> None:
        rows = self.db.execute("SELECT * FROM memories WHERE status='active'").fetchall()
        for m in rows:
            decay = int(m["decay_per_day"])
            if decay <= 0:
                continue
            new = max(0, int(m["salience"]) - decay)
            status = "forgotten" if new < 10 else "active"
            self.db.execute("UPDATE memories SET salience=?,status=? WHERE id=?", (new, status, m["id"]))

    def schedule_canon_event(
        self,
        key: str,
        origin_region_id: str,
        due_at: int,
        payload: dict[str, Any],
        *,
        significance: int = 80,
        spread_mode: str = "courier",
    ) -> int:
        if due_at <= self.now:
            raise ValueError("canon event must be in the future")
        cur = self.db.execute(
            "INSERT INTO canon_events(event_key,origin_region_id,due_at,payload_json,significance,spread_mode,status) "
            "VALUES(?,?,?,?,?,?,'scheduled')",
            (key, origin_region_id, due_at, dumps(payload), significance, spread_mode),
        )
        return int(cur.lastrowid)

    def _process_canon_events(self) -> None:
        rows = self.db.execute(
            "SELECT * FROM canon_events WHERE status='scheduled' AND due_at<=? ORDER BY due_at,id",
            (self.now,),
        ).fetchall()
        for ce in rows:
            fact_key = f"canon:{ce['event_key']}"
            self.create_fact(
                fact_key,
                loads(ce["payload_json"], {}),
                str(ce["origin_region_id"]),
                int(ce["significance"]),
                mode=str(ce["spread_mode"]),
            )
            self.db.execute("UPDATE canon_events SET status='occurred' WHERE id=?", (ce["id"],))
            self.event(
                "canon_event_occurred",
                region=str(ce["origin_region_id"]),
                significance=int(ce["significance"]),
                payload={"event_key": str(ce["event_key"]), "fact_key": fact_key},
            )

    def observe_local_fact(self, actor_id: str, fact_key: str) -> bool:
        region = str(self.actor(actor_id)["region_id"])
        belief = self.db.execute(
            "SELECT confidence FROM region_beliefs WHERE region_id=? AND fact_key=?",
            (region, fact_key),
        ).fetchone()
        if belief is None:
            return False
        self.db.execute(
            """
            INSERT INTO actor_knowledge(actor_id,fact_key,confidence,learned_at,source)
            VALUES(?,?,?,?,?)
            ON CONFLICT(actor_id,fact_key) DO UPDATE SET
              confidence=MAX(confidence,excluded.confidence),
              learned_at=excluded.learned_at,
              source=excluded.source
            """,
            (actor_id, fact_key, int(belief["confidence"]), self.now, f"local_observation:{region}"),
        )
        return True

    def start_actor_travel(self, actor_id: str, destination: str) -> int:
        actor = self.actor(actor_id)
        if self.db.execute(
            "SELECT 1 FROM actor_travel WHERE actor_id=? AND status='traveling'",
            (actor_id,),
        ).fetchone():
            raise ValueError("actor is already traveling")
        origin = str(actor["region_id"])
        duration = self.route_minutes(origin, destination)
        due = self.now + duration
        self.db.execute(
            """
            INSERT INTO actor_travel(actor_id,from_region_id,to_region_id,started_at,due_at,status)
            VALUES(?,?,?,?,?,'traveling')
            ON CONFLICT(actor_id) DO UPDATE SET
              from_region_id=excluded.from_region_id,to_region_id=excluded.to_region_id,
              started_at=excluded.started_at,due_at=excluded.due_at,status='traveling'
            """,
            (actor_id, origin, destination, self.now, due),
        )
        self.db.execute("UPDATE actors SET status='traveling' WHERE id=?", (actor_id,))
        self.event(
            "actor_travel_started",
            region=origin,
            actor=actor_id,
            significance=35,
            payload={"destination": destination, "due_at": due},
        )
        return due

    def _complete_actor_travel(self) -> None:
        rows = self.db.execute(
            "SELECT * FROM actor_travel WHERE status='traveling' AND due_at<=? ORDER BY due_at,actor_id",
            (self.now,),
        ).fetchall()
        for tr in rows:
            self.db.execute(
                "UPDATE actors SET region_id=?,status='idle' WHERE id=?",
                (tr["to_region_id"], tr["actor_id"]),
            )
            self.db.execute("UPDATE actor_travel SET status='completed' WHERE actor_id=?", (tr["actor_id"],))
            self.event(
                "actor_travel_arrived",
                region=str(tr["to_region_id"]),
                actor=str(tr["actor_id"]),
                significance=35,
                payload={"from": str(tr["from_region_id"])},
            )
