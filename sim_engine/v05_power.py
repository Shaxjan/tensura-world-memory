from __future__ import annotations

from typing import Any

from v03_engine import dumps, loads

RANK_VALUE = {"F":0,"E":1,"D":2,"C":3,"B":4,"A":5,"A+":6,"S":7,"S+":8,"SPECIAL":9}


class TensuraPowerHealingMixin:
    def set_power_profile(self, actor_id: str, *, threat_rank: str, magicules: int, physical: int,
                          magic: int, control: int, durability: int, regeneration: int = 0,
                          resistances: dict[str, int] | None = None) -> None:
        if threat_rank not in RANK_VALUE:
            raise ValueError("unknown threat rank")
        self.db.execute(
            """INSERT INTO power_profiles(actor_id,threat_rank,magicules,physical,magic,control,durability,regeneration,resistances_json)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(actor_id) DO UPDATE SET threat_rank=excluded.threat_rank,magicules=excluded.magicules,
               physical=excluded.physical,magic=excluded.magic,control=excluded.control,durability=excluded.durability,
               regeneration=excluded.regeneration,resistances_json=excluded.resistances_json""",
            (actor_id, threat_rank, int(magicules), int(physical), int(magic), int(control), int(durability), int(regeneration), dumps(resistances or {})),
        )

    def power_profile(self, actor_id: str):
        row = self.db.execute("SELECT * FROM power_profiles WHERE actor_id=?", (actor_id,)).fetchone()
        if row is None:
            raise KeyError(f"missing power profile for {actor_id}")
        return row

    def add_condition(self, actor_id: str, code: str, severity: int, *, source: str, expires_at: int | None = None) -> int:
        cur = self.db.execute(
            "INSERT INTO conditions(actor_id,code,severity,source,applied_at,expires_at,status) VALUES(?,?,?,?,?,?,'active')",
            (actor_id, code, max(1,min(100,int(severity))), source, self.now, expires_at),
        )
        return int(cur.lastrowid)

    def has_condition(self, actor_id: str, code: str) -> bool:
        return self.db.execute(
            "SELECT 1 FROM conditions WHERE actor_id=? AND code=? AND status='active' LIMIT 1", (actor_id, code)
        ).fetchone() is not None

    def _rank_gap(self, attacker_id: str, target_id: str) -> int:
        return RANK_VALUE[str(self.power_profile(attacker_id)["threat_rank"])] - RANK_VALUE[str(self.power_profile(target_id)["threat_rank"])]

    def resolve_tensura_attack(self, attacker_id: str, target_id: str, *, mode: str = "lethal") -> dict[str, Any]:
        if mode not in {"lethal","nonlethal"}:
            raise ValueError("invalid attack mode")
        if attacker_id == target_id:
            raise ValueError("cannot attack self")
        a = self.actor(attacker_id); t = self.actor(target_id)
        if str(a["region_id"]) != str(t["region_id"]):
            raise ValueError("target is not in the same region")
        ast = self.stats(attacker_id); tst = self.stats(target_id)
        if not int(ast["alive"]) or not int(tst["alive"]):
            raise ValueError("attacker or target is not alive")
        if self.has_condition(attacker_id, "incapacitated") or self.has_condition(attacker_id, "unconscious"):
            raise ValueError("attacker is incapacitated")

        ap = self.power_profile(attacker_id); tp = self.power_profile(target_id)
        gap = self._rank_gap(attacker_id, target_id)
        rng = self._rng(f"v05_attack:{attacker_id}:{target_id}:{mode}")
        roll = rng.randint(1,20)
        attack_total = roll + self.skill_bonus(attacker_id,"melee") + int(ap["control"])//12 + max(-12,min(12,gap*3))
        defense = 10 + int(tst["armor"]) + int(tp["control"])//15 + max(0,-gap*2)
        hit = roll == 20 or (roll != 1 and attack_total >= defense)

        ineffective = gap <= -4 and roll != 20
        damage = 0
        state = "unhurt"
        if hit and not ineffective:
            base = rng.randint(1,8) + int(ast["power"]) + int(ap["physical"])//8 + max(0,gap*3)
            mitigation = int(tp["durability"])//12 + max(0,-gap*2)
            damage = max(1, base - mitigation)
            if roll == 20:
                damage += max(2, base//2)
            before = int(tst["hp"])
            after = max(0, before-damage)

            if mode == "nonlethal" and after <= 0:
                after = 1
                self.db.execute("UPDATE actor_stats SET hp=1,alive=1 WHERE actor_id=?", (target_id,))
                if not self.has_condition(target_id,"unconscious"):
                    self.add_condition(target_id,"unconscious", min(100,45+damage), source=f"nonlethal:{attacker_id}", expires_at=self.now+60)
                state = "unconscious"
            elif after <= 0:
                overwhelming = damage >= int(tst["max_hp"]) or self.has_condition(target_id,"incapacitated")
                if overwhelming:
                    self.db.execute("UPDATE actor_stats SET hp=0,alive=0 WHERE actor_id=?", (target_id,))
                    state = "dead"
                else:
                    self.db.execute("UPDATE actor_stats SET hp=0 WHERE actor_id=?", (target_id,))
                    self.add_condition(target_id,"incapacitated", min(100,55+damage), source=f"combat:{attacker_id}")
                    state = "incapacitated"
            else:
                self.db.execute("UPDATE actor_stats SET hp=? WHERE actor_id=?", (after,target_id))
                ratio = damage/max(1,int(tst["max_hp"]))
                if ratio >= .25:
                    self.add_condition(target_id,"wounded", min(100,round(ratio*100)), source=f"combat:{attacker_id}")
                    state = "wounded"
                else:
                    state = "hurt"

        region = str(a["region_id"])
        payload = {"target":target_id,"mode":mode,"roll":roll,"attack_total":attack_total,"defense":defense,
                   "hit":hit,"ineffective":ineffective,"rank_gap":gap,"damage":damage,"target_state":state}
        self.event("v05_combat_attack",region=region,actor=attacker_id,significance=90 if state=="dead" else 60,payload=payload)
        if state == "dead":
            self.event("actor_death",region=region,actor=target_id,significance=95,payload={"caused_by":attacker_id})
        return payload

    def treat_actor(self, healer_id: str, target_id: str, *, method: str) -> dict[str, Any]:
        if method not in {"first_aid","magic"}:
            raise ValueError("invalid treatment method")
        h=self.actor(healer_id); t=self.actor(target_id)
        if str(h["region_id"]) != str(t["region_id"]):
            raise ValueError("target is not co-located")
        st=self.stats(target_id)
        if not int(st["alive"]):
            raise ValueError("cannot treat dead actor")
        skill = "healing_magic" if method=="magic" else "medicine"
        dc = 13 if self.has_condition(target_id,"incapacitated") else 10
        check=self.skill_check(healer_id,skill,dc,namespace=f"treat:{target_id}:{method}")
        healed=0; removed=[]
        if check["success"]:
            rng=self._rng(f"heal:{healer_id}:{target_id}:{method}")
            prof=self.power_profile(healer_id)
            healed=rng.randint(2,6)+(int(prof["magic"])//10 if method=="magic" else max(0,self.skill_bonus(healer_id,"medicine")//2))
            before=int(self.stats(target_id)["hp"]); after=min(int(st["max_hp"]),before+max(1,healed))
            healed=after-before
            self.db.execute("UPDATE actor_stats SET hp=? WHERE actor_id=?",(after,target_id))
            for code in ("bleeding","incapacitated","unconscious"):
                row=self.db.execute("SELECT id FROM conditions WHERE actor_id=? AND code=? AND status='active' ORDER BY severity DESC LIMIT 1",(target_id,code)).fetchone()
                if row and (code!="incapacitated" or after>0):
                    self.db.execute("UPDATE conditions SET status='resolved' WHERE id=?",(row["id"],)); removed.append(code)
        cid=self.db.execute("SELECT id FROM checks ORDER BY id DESC LIMIT 1").fetchone()
        self.db.execute(
            "INSERT INTO treatments(world_minute,healer_id,target_id,method,check_id,healed_hp,conditions_removed_json,success) VALUES(?,?,?,?,?,?,?,?)",
            (self.now,healer_id,target_id,method,int(cid[0]) if cid else None,healed,dumps(removed),int(check["success"])),
        )
        return {"success":bool(check["success"]),"healed_hp":healed,"conditions_removed":removed,"check":check}

    def _process_v05_conditions(self) -> None:
        self.db.execute("UPDATE conditions SET status='resolved' WHERE status='active' AND expires_at IS NOT NULL AND expires_at<=?",(self.now,))
        rows=self.db.execute("SELECT actor_id,regeneration FROM power_profiles WHERE regeneration>0").fetchall()
        for r in rows:
            st=self.stats(str(r["actor_id"]))
            if int(st["alive"]) and int(st["hp"])<int(st["max_hp"]):
                heal=max(0,int(r["regeneration"])//20)
                if heal:
                    self.db.execute("UPDATE actor_stats SET hp=MIN(max_hp,hp+?) WHERE actor_id=?",(heal,r["actor_id"]))
