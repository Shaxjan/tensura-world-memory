from __future__ import annotations

from typing import Any


class WitnessRelationshipRoutineMixin:
    def ensure_bond(self, actor_id: str, target_id: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO social_bonds(actor_id,target_id,affinity,trust,respect,fear,obligation,updated_at) VALUES(?,?,0,0,0,0,0,?)",
            (actor_id,target_id,self.now),
        )

    def set_bond(self, actor_id: str, target_id: str, *, affinity=0, trust=0, respect=0, fear=0, obligation=0) -> None:
        vals=[max(-100,min(100,int(affinity))),max(-100,min(100,int(trust))),max(-100,min(100,int(respect))),max(0,min(100,int(fear))),max(-100,min(100,int(obligation)))]
        self.db.execute(
            "INSERT INTO social_bonds(actor_id,target_id,affinity,trust,respect,fear,obligation,updated_at) VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(actor_id,target_id) DO UPDATE SET affinity=excluded.affinity,trust=excluded.trust,respect=excluded.respect,fear=excluded.fear,obligation=excluded.obligation,updated_at=excluded.updated_at",
            (actor_id,target_id,*vals,self.now),
        )

    def bond(self, actor_id: str, target_id: str) -> dict[str,int]:
        self.ensure_bond(actor_id,target_id)
        r=self.db.execute("SELECT affinity,trust,respect,fear,obligation FROM social_bonds WHERE actor_id=? AND target_id=?",(actor_id,target_id)).fetchone()
        return {k:int(r[k]) for k in ("affinity","trust","respect","fear","obligation")}

    def relationship_event(self, actor_id: str, target_id: str, event_key: str, summary: str, *,
                           affinity=0, trust=0, respect=0, fear=0, obligation=0, salience: int | None = None) -> None:
        b=self.bond(actor_id,target_id)
        new={
            "affinity":max(-100,min(100,b["affinity"]+int(affinity))),
            "trust":max(-100,min(100,b["trust"]+int(trust))),
            "respect":max(-100,min(100,b["respect"]+int(respect))),
            "fear":max(0,min(100,b["fear"]+int(fear))),
            "obligation":max(-100,min(100,b["obligation"]+int(obligation))),
        }
        self.set_bond(actor_id,target_id,**new)
        memory_key=f"rel:{target_id}:{event_key}:{self.now}"
        self.db.execute(
            "INSERT INTO relationship_events(world_minute,actor_id,target_id,event_key,summary,affinity_delta,trust_delta,respect_delta,fear_delta,obligation_delta,memory_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (self.now,actor_id,target_id,event_key,summary,affinity,trust,respect,fear,obligation,memory_key),
        )
        impact=max(abs(int(x)) for x in (affinity,trust,respect,fear,obligation))
        self.remember(actor_id,memory_key,summary,salience=salience if salience is not None else min(95,35+impact*2),emotional=min(100,impact*3))

    def decision_score(self, actor_id: str, target_id: str, action: str) -> dict[str,Any]:
        b=self.bond(actor_id,target_id)
        weights={
            "help": (0.25,0.35,0.20,-0.25,0.30),
            "cooperate": (0.15,0.40,0.25,-0.15,0.20),
            "report_crime": (-0.10,-0.30,0.25,-0.10,-0.15),
            "take_risk": (0.15,0.25,0.30,-0.45,0.20),
        }
        w=weights.get(action,(0.2,0.2,0.2,-0.2,0.2))
        vals=[b["affinity"],b["trust"],b["respect"],b["fear"],b["obligation"]]
        score=round(sum(a*x for a,x in zip(vals,w)))
        recent=self.db.execute(
            "SELECT summary,salience FROM memories WHERE actor_id=? AND memory_key LIKE ? AND status='active' ORDER BY salience DESC,last_recalled_at DESC LIMIT 2",
            (actor_id,f"rel:{target_id}:%"),
        ).fetchall()
        reasons=[f"{k}={b[k]}" for k in ("affinity","trust","respect","fear","obligation") if b[k]]
        reasons += [f"memory:{str(r['summary'])}" for r in recent]
        return {"score":max(-100,min(100,score)),"reasons":reasons,"bond":b}

    def resolve_social_attempt(self, actor_id: str, target_id: str, *, approach: str, goal_text: str) -> dict[str,Any]:
        if approach not in {"persuasion","deception","intimidation"}:
            raise ValueError("invalid social approach")
        a=self.actor(actor_id); t=self.actor(target_id)
        if str(a["region_id"])!=str(t["region_id"]):
            raise ValueError("target is not co-located")
        b=self.bond(target_id,actor_id)
        base=12
        if approach=="persuasion":
            dc=base-max(-4,min(4,(b["trust"]+b["affinity"])//25)); skill="persuasion"
        elif approach=="deception":
            dc=base+max(-3,min(6,b["trust"]//20)); skill="deception"
        else:
            dc=base+max(-4,min(6,b["fear"]//-20 if b["fear"] else b["respect"]//20)); skill="intimidation"
        check=self.skill_check(actor_id,skill,max(6,min(22,dc)),namespace=f"social:{target_id}:{approach}")
        if check["success"]:
            if approach=="persuasion": self.relationship_event(target_id,actor_id,"persuaded",f"Agreed after: {goal_text}",trust=2,respect=1)
            elif approach=="deception": self.relationship_event(target_id,actor_id,"deceived",f"Accepted claim: {goal_text}",trust=1)
            else: self.relationship_event(target_id,actor_id,"intimidated",f"Was pressured: {goal_text}",fear=6,affinity=-3)
        else:
            self.relationship_event(target_id,actor_id,"social_failed",f"Rejected approach: {goal_text}",trust=-2,affinity=-1)
        decision=self.decision_score(target_id,actor_id,"cooperate")
        return {"success":bool(check["success"]),"check":check,"target_decision":decision,"goal_text":goal_text}

    def _named_witnesses(self, offender_id: str, region: str) -> list[str]:
        rows=self.db.execute(
            "SELECT a.id FROM actors a JOIN actor_stats s ON s.actor_id=a.id "
            "WHERE a.id<>? AND a.is_player=0 AND a.region_id=? AND s.alive=1 ORDER BY a.id",
            (offender_id,region),
        ).fetchall()
        return [str(r["id"]) for r in rows]

    def record_crime(self, actor_id: str, code: str, *, witnessed: bool | None = None) -> dict[str,Any]:
        actor=self.actor(actor_id); region=str(actor["region_id"])
        law=self.db.execute("SELECT * FROM laws WHERE region_id=? AND code=?",(region,code)).fetchone()
        if law is None: raise ValueError(f"no such law in {region}: {code}")
        witnesses=[]; testimony_strength=0
        candidates=self._named_witnesses(actor_id,region)
        if witnessed is False: candidates=[]
        if witnessed is True and not candidates:
            raise ValueError("forced witnessed crime requires a named co-located witness")
        stealth=self.skill_bonus(actor_id,"stealth")
        for wid in candidates:
            rng=self._rng(f"crime_witness:{actor_id}:{wid}:{code}")
            perception=rng.randint(1,20)+self.skill_bonus(wid,"perception")
            dc=10+max(0,stealth)
            if witnessed is True or perception>=dc:
                b=self.bond(wid,actor_id)
                confidence=max(20,min(100,45+(perception-dc)*5))
                willingness=max(0,min(100,55+b["respect"]//3-b["affinity"]//3-b["fear"]//2))
                witnesses.append((wid,perception,confidence,willingness))
                if willingness>=40: testimony_strength+=round(confidence*0.6)
        rng=self._rng(f"crime_evidence:{actor_id}:{code}")
        physical=max(0,min(100,rng.randint(10,45)+int(law["severity"])//5))
        # Physical traces may exist without the authorities knowing they exist.
        # Immediate reporting requires at least one willing named witness/testimony.
        reported=bool(testimony_strength>=35 and testimony_strength+physical>=55)
        cur=self.db.execute(
            "INSERT INTO crimes(actor_id,region_id,code,witnessed,evidence,fine_copper,status,occurred_at) VALUES(?,?,?,?,?,?,?,?)",
            (actor_id,region,code,int(bool(witnesses)),max(physical,min(100,testimony_strength)),int(law["fine_copper"]) if reported else 0,"reported" if reported else "unreported",self.now),
        )
        crime_id=int(cur.lastrowid)
        for wid,perception,confidence,willingness in witnesses:
            self.db.execute("INSERT INTO crime_witnesses VALUES(?,?,?,?,?,'observed')",(crime_id,wid,perception,confidence,willingness))
            if willingness>=40:
                self.db.execute("INSERT INTO testimonies(crime_id,witness_id,credibility,submitted_at,status) VALUES(?,?,?,?, 'active')",(crime_id,wid,confidence,self.now))
        self.db.execute("INSERT INTO evidence_items(crime_id,kind,strength,decay_per_day,created_at,last_decay_at,status) VALUES(?,?,?,?,?,?,'active')",(crime_id,"physical_trace",physical,6,self.now,self.now))
        if reported:
            severity=int(law["severity"]); self._change_reputation(actor_id,region,authority=-max(1,severity//4),public=-max(0,severity//12))
            guard=self.db.execute("SELECT id FROM factions WHERE kind='guard' AND home_region_id=? ORDER BY id LIMIT 1",(region,)).fetchone()
            security=int(self.db.execute("SELECT security FROM regions WHERE id=?",(region,)).fetchone()[0]); delay=max(20,240-security*2)
            self.db.execute("INSERT INTO legal_cases(crime_id,authority_faction_id,due_at,status) VALUES(?,?,?,'pending')",(crime_id,str(guard[0]) if guard else None,self.now+delay))
            self.event("crime_reported",region=region,actor=actor_id,faction=str(guard[0]) if guard else None,significance=max(50,severity),payload={"crime_id":crime_id,"code":code,"named_witnesses":[x[0] for x in witnesses],"evidence":physical})
        else:
            self.event("crime_unreported",region=region,actor=actor_id,significance=25,payload={"crime_id":crime_id,"code":code,"named_witnesses":[x[0] for x in witnesses]},visibility="hidden_engine")
        return {"crime_id":crime_id,"reported":reported,"witnesses":[x[0] for x in witnesses],"evidence_strength":physical,"testimony_strength":testimony_strength}

    def _decay_evidence(self) -> None:
        rows=self.db.execute("SELECT * FROM evidence_items WHERE status='active'").fetchall()
        for e in rows:
            days=max(0,(self.now-int(e["last_decay_at"]))//1440)
            if not days: continue
            strength=max(0,int(e["strength"])-days*int(e["decay_per_day"])); status="expired" if strength<=0 else "active"
            self.db.execute("UPDATE evidence_items SET strength=?,last_decay_at=?,status=? WHERE id=?",(strength,int(e["last_decay_at"])+days*1440,status,e["id"]))

    def add_routine(self, actor_id: str, region_id: str, start_minute_of_day: int, end_minute_of_day: int, activity: str, priority: int=40) -> int:
        cur=self.db.execute("INSERT INTO npc_routines(actor_id,region_id,start_minute_of_day,end_minute_of_day,activity,priority,active) VALUES(?,?,?,?,?,?,1)",(actor_id,region_id,start_minute_of_day,end_minute_of_day,activity,priority))
        return int(cur.lastrowid)

    def add_travel_plan(self, actor_id: str, destination: str, depart_at: int, purpose: str, priority: int=50) -> int:
        cur=self.db.execute("INSERT INTO npc_travel_plans(actor_id,destination_region_id,depart_at,purpose,priority,status,created_at) VALUES(?,?,?,?,?,'planned',?)",(actor_id,destination,depart_at,purpose,priority,self.now))
        return int(cur.lastrowid)

    def _process_named_plans(self) -> None:
        plans=self.db.execute("SELECT * FROM npc_travel_plans WHERE status='planned' AND depart_at<=? ORDER BY priority DESC,depart_at,id",(self.now,)).fetchall()
        for p in plans:
            actor_id=str(p["actor_id"]); actor=self.actor(actor_id)
            if int(actor["is_player"]):
                self.db.execute("UPDATE npc_travel_plans SET status='invalid',resolution='player_autonomy_guard' WHERE id=?",(p["id"],)); continue
            if str(actor["status"])=="traveling": continue
            try: duration=self.route_minutes(str(actor["region_id"]),str(p["destination_region_id"]))
            except ValueError:
                self.db.execute("UPDATE npc_travel_plans SET status='failed',resolution='no_route' WHERE id=?",(p["id"],)); continue
            conflict=self.db.execute(
                "SELECT id FROM appointments WHERE (actor_id=? OR counterpart_id=?) AND status IN ('scheduled','waiting') AND due_at BETWEEN ? AND ? ORDER BY due_at LIMIT 1",
                (actor_id,actor_id,self.now,self.now+duration+60),
            ).fetchone()
            if conflict:
                self.db.execute("UPDATE npc_travel_plans SET status='deferred',resolution=? WHERE id=?",(f"appointment:{int(conflict[0])}",p["id"])); continue
            self.start_actor_travel(actor_id,str(p["destination_region_id"])); self.db.execute("UPDATE npc_travel_plans SET status='traveling',resolution='started' WHERE id=?",(p["id"],))

    def _sync_travel_plans(self) -> None:
        rows=self.db.execute("SELECT * FROM npc_travel_plans WHERE status='traveling'").fetchall()
        for p in rows:
            tr=self.db.execute("SELECT status FROM actor_travel WHERE actor_id=?",(p["actor_id"],)).fetchone()
            if tr and str(tr["status"])=="completed": self.db.execute("UPDATE npc_travel_plans SET status='completed',resolution='arrived' WHERE id=?",(p["id"],))

    @staticmethod
    def _routine_active(now_mod: int, start: int, end: int) -> bool:
        if start < end:
            return start <= now_mod < end
        return now_mod >= start or now_mod < end

    def _process_routines(self) -> None:
        now_mod=self.now%1440
        actors=self.db.execute("SELECT id,status,region_id FROM actors WHERE is_player=0 ORDER BY id").fetchall()
        for a in actors:
            aid=str(a["id"])
            if str(a["status"])=="traveling":
                continue
            routines=self.db.execute(
                "SELECT * FROM npc_routines WHERE actor_id=? AND active=1 ORDER BY priority DESC,id",(aid,)
            ).fetchall()
            chosen=None
            for r in routines:
                if self._routine_active(now_mod,int(r["start_minute_of_day"]),int(r["end_minute_of_day"])):
                    chosen=r; break
            if chosen is None:
                if str(a["status"]).startswith("routine:"):
                    self.db.execute("UPDATE actors SET status='idle' WHERE id=?",(aid,))
                continue
            region=str(chosen["region_id"]); activity=str(chosen["activity"])
            upcoming=self.db.execute(
                "SELECT id,due_at FROM appointments WHERE (actor_id=? OR counterpart_id=?) "
                "AND status IN ('scheduled','waiting') AND due_at BETWEEN ? AND ? ORDER BY due_at LIMIT 1",
                (aid,aid,self.now,self.now+90),
            ).fetchone()
            if upcoming:
                continue
            if str(a["region_id"])==region:
                self.db.execute("UPDATE actors SET status=? WHERE id=?",(f"routine:{activity}",aid))
                continue
            try:
                duration=self.route_minutes(str(a["region_id"]),region)
            except ValueError:
                continue
            end=int(chosen["end_minute_of_day"]); remaining=(end-now_mod)%1440
            if remaining==0: remaining=1440
            if duration>remaining:
                continue
            conflict=self.db.execute(
                "SELECT id FROM appointments WHERE (actor_id=? OR counterpart_id=?) AND status IN ('scheduled','waiting') "
                "AND due_at BETWEEN ? AND ? ORDER BY due_at LIMIT 1",
                (aid,aid,self.now,self.now+duration+30),
            ).fetchone()
            if conflict:
                continue
            self.start_actor_travel(aid,region)
            self.event("npc_routine_departure",region=str(a["region_id"]),actor=aid,significance=20,payload={"activity":activity,"destination":region},visibility="hidden_engine")
