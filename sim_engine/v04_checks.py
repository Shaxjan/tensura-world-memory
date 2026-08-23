from __future__ import annotations

from typing import Any


class SkillsCombatMixin:
    def ensure_profile(self, actor_id: str, *, max_hp: int = 20, hp: int | None = None, armor: int = 0, power: int = 0) -> None:
        if hp is None:
            hp = max_hp
        self.db.execute(
            """
            INSERT INTO actor_stats(actor_id,hp,max_hp,armor,power,alive)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(actor_id) DO UPDATE SET
              hp=excluded.hp,max_hp=excluded.max_hp,armor=excluded.armor,
              power=excluded.power,alive=excluded.alive
            """,
            (actor_id, max(0, hp), max_hp, armor, power, int(hp > 0)),
        )

    def set_skill(self, actor_id: str, skill: str, bonus: int) -> None:
        self.db.execute(
            "INSERT INTO actor_skills(actor_id,skill,bonus) VALUES(?,?,?) "
            "ON CONFLICT(actor_id,skill) DO UPDATE SET bonus=excluded.bonus",
            (actor_id, skill, int(bonus)),
        )

    def stats(self, actor_id: str):
        row = self.db.execute("SELECT * FROM actor_stats WHERE actor_id=?", (actor_id,)).fetchone()
        if row is None:
            raise KeyError(f"missing actor_stats for {actor_id}")
        return row

    def skill_bonus(self, actor_id: str, skill: str) -> int:
        row = self.db.execute(
            "SELECT bonus FROM actor_skills WHERE actor_id=? AND skill=?",
            (actor_id, skill),
        ).fetchone()
        return int(row["bonus"]) if row else 0

    def skill_check(self, actor_id: str, skill: str, dc: int, *, namespace: str) -> dict[str, Any]:
        if not 1 <= int(dc) <= 40:
            raise ValueError("dc out of range")
        if not int(self.stats(actor_id)["alive"]):
            raise ValueError("actor is not alive")
        bonus = self.skill_bonus(actor_id, skill)
        rng = self._rng(f"check:{namespace}:{actor_id}:{skill}:{dc}")
        roll = rng.randint(1, 20)
        total = roll + bonus
        success = roll == 20 or (roll != 1 and total >= dc)
        self.db.execute(
            "INSERT INTO checks(world_minute,actor_id,skill,dc,roll,bonus,total,success,namespace) VALUES(?,?,?,?,?,?,?,?,?)",
            (self.now, actor_id, skill, dc, roll, bonus, total, int(success), namespace),
        )
        self.event(
            "skill_check",
            region=str(self.actor(actor_id)["region_id"]),
            actor=actor_id,
            significance=20,
            payload={"skill": skill, "dc": dc, "roll": roll, "bonus": bonus, "total": total, "success": success},
            visibility="hidden_engine",
        )
        return {"roll": roll, "bonus": bonus, "total": total, "dc": dc, "success": bool(success)}

    def resolve_attack(self, attacker_id: str, target_id: str) -> dict[str, Any]:
        if attacker_id == target_id:
            raise ValueError("cannot attack self")
        attacker = self.actor(attacker_id)
        target = self.actor(target_id)
        if str(attacker["region_id"]) != str(target["region_id"]):
            raise ValueError("target is not in the same region")
        if not int(self.stats(attacker_id)["alive"]) or not int(self.stats(target_id)["alive"]):
            raise ValueError("attacker or target is not alive")

        defense = 10 + int(self.stats(target_id)["armor"])
        check = self.skill_check(attacker_id, "melee", defense, namespace=f"attack:{target_id}")
        damage = 0
        injury_id = None
        dead = False

        if check["success"]:
            rng = self._rng(f"damage:{attacker_id}:{target_id}")
            damage = max(1, rng.randint(1, 6) + int(self.stats(attacker_id)["power"]))
            if check["roll"] == 20:
                damage *= 2
            before = int(self.stats(target_id)["hp"])
            after = max(0, before - damage)
            dead = after == 0
            self.db.execute("UPDATE actor_stats SET hp=?,alive=? WHERE actor_id=?", (after, int(not dead), target_id))

            max_hp = int(self.stats(target_id)["max_hp"])
            if damage >= max(3, max_hp // 5):
                severity = min(100, max(1, round(damage * 100 / max_hp)))
                kind = "severe_wound" if severity >= 50 else "wound" if severity >= 25 else "bruise"
                cur = self.db.execute(
                    "INSERT INTO injuries(actor_id,kind,severity,applied_at,status) VALUES(?,?,?,?, 'active')",
                    (target_id, kind, severity, self.now),
                )
                injury_id = int(cur.lastrowid)

        region = str(attacker["region_id"])
        self.event(
            "combat_attack",
            region=region,
            actor=attacker_id,
            significance=75 if dead else 55,
            payload={"target": target_id, "check": check, "damage": damage, "injury_id": injury_id, "target_dead": dead},
        )
        if dead:
            self.event("actor_death", region=region, actor=target_id, significance=95, payload={"caused_by": attacker_id})
        return {"hit": bool(check["success"]), "damage": damage, "injury_id": injury_id, "target_dead": dead, "check": check}
