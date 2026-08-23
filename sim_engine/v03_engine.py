from __future__ import annotations
import heapq, json, random, sqlite3
from pathlib import Path
from typing import Any

DAY = 1440
MACRO_TICK = 360

def dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))

def loads(v: str | None, default: Any) -> Any:
    return default if not v else json.loads(v)

class WorldV03:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")

    def close(self): self.db.close()
    def __enter__(self): return self
    def __exit__(self, *exc): self.close()

    @classmethod
    def create(cls, db_path, schema_path, *, seed: int, start_minute: int):
        p = Path(db_path); p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists(): p.unlink()
        w = cls(p)
        w.db.executescript(Path(schema_path).read_text(encoding="utf-8"))
        for k,v in {"world_seed":seed,"world_minute":start_minute,"rng_counter":0,"next_macro_at":start_minute+MACRO_TICK}.items():
            w.set_meta(k, str(v))
        for k in ["macro_ticks","faction_actions","packets_delivered","caravans_completed","context_builds"]:
            w.db.execute("INSERT INTO metrics(key,value) VALUES(?,0)", (k,))
        w.db.commit(); return w

    def set_meta(self,k,v):
        self.db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
    def get_meta(self,k):
        r=self.db.execute("SELECT value FROM meta WHERE key=?",(k,)).fetchone()
        if not r: raise KeyError(k)
        return str(r[0])
    @property
    def now(self): return int(self.get_meta("world_minute"))
    @property
    def seed(self): return int(self.get_meta("world_seed"))
    def _set_now(self,m): self.set_meta("world_minute",m)
    def _rng(self,ns):
        n=int(self.get_meta("rng_counter"))+1; self.set_meta("rng_counter",n)
        return random.Random(f"{self.seed}:{n}:{ns}")
    def metric(self,k,delta=0):
        if delta: self.db.execute("UPDATE metrics SET value=value+? WHERE key=?",(delta,k))
        r=self.db.execute("SELECT value FROM metrics WHERE key=?",(k,)).fetchone(); return int(r[0])

    def event(self,t,*,region=None,actor=None,faction=None,significance=40,payload=None,visibility="world"):
        self.db.execute(
            "INSERT INTO events(world_minute,event_type,region_id,actor_id,faction_id,significance,payload_json,visibility) VALUES(?,?,?,?,?,?,?,?)",
            (self.now,t,region,actor,faction,significance,dumps(payload or {}),visibility)
        )

    def add_region(self,id,name,kind,population,security=50,prosperity=50):
        self.db.execute("INSERT INTO regions VALUES(?,?,?,?,?,?)",(id,name,kind,population,security,prosperity))

    def connect(self,a,b,minutes,capacity=100,risk=10):
        for x,y in [(a,b),(b,a)]:
            self.db.execute("INSERT INTO routes VALUES(?,?,?,?,?)",(x,y,minutes,capacity,risk))

    def route_minutes(self,start,goal):
        if start==goal:return 0
        g={}
        for r in self.db.execute("SELECT * FROM routes"):
            g.setdefault(r['a'],[]).append((r['b'],int(r['travel_minutes'])))
        q=[(0,start)]; best={}
        while q:
            c,n=heapq.heappop(q)
            if n==goal:return c
            if n in best and best[n]<=c:continue
            best[n]=c
            for nxt,w in g.get(n,[]):heapq.heappush(q,(c+w,nxt))
        raise ValueError(f"no route {start}->{goal}")

    def neighbors(self,region):
        return [dict(r) for r in self.db.execute("SELECT * FROM routes WHERE a=? ORDER BY b",(region,))]

    def add_actor(self,id,name,region,cash=0,is_player=False):
        self.db.execute("INSERT INTO actors VALUES(?,?,?,?,?,?)",(id,name,int(is_player),region,cash,"idle"))

    def actor(self,id):
        r=self.db.execute("SELECT * FROM actors WHERE id=?",(id,)).fetchone()
        if not r: raise KeyError(id)
        return r

    def set_actor_region(self,id,region):
        self.db.execute("UPDATE actors SET region_id=? WHERE id=?",(region,id))

    def add_commodity(self,id,name,base,essential=False):
        self.db.execute("INSERT INTO commodities VALUES(?,?,?,?)",(id,name,base,int(essential)))

    def set_market(self,region,commodity,*,supply,target,demand,production,consumption,price=None):
        base=int(self.db.execute("SELECT base_price_copper FROM commodities WHERE id=?",(commodity,)).fetchone()[0])
        self.db.execute(
            "INSERT INTO markets VALUES(?,?,?,?,?,?,?,?,?)",
            (region,commodity,supply,target,demand,production,consumption,price or base,self.now)
        )

    def price(self,region,commodity):
        return int(self.db.execute(
            "SELECT price_copper FROM markets WHERE region_id=? AND commodity_id=?",(region,commodity)
        ).fetchone()[0])

    def _reprice(self,region,commodity):
        m=self.db.execute(
            "SELECT m.*,c.base_price_copper FROM markets m JOIN commodities c ON c.id=m.commodity_id WHERE region_id=? AND commodity_id=?",
            (region,commodity)
        ).fetchone()
        supply=max(1,int(m['supply'])); target=max(1,int(m['target_supply']))
        demand=int(m['demand']); base=int(m['base_price_copper'])
        scarcity=(target+demand)/(supply+target*0.50)
        raw=round(base*(0.65+0.55*scarcity))
        bounded=max(round(base*0.45),min(round(base*3.0),raw))
        old=int(m['price_copper']); new=max(1,round(old*0.65+bounded*0.35))
        self.db.execute(
            "UPDATE markets SET price_copper=?,updated_at=? WHERE region_id=? AND commodity_id=?",
            (new,self.now,region,commodity)
        )
        return new

    def buy_from_market(self,actor_id,commodity,qty):
        if qty<=0: raise ValueError("qty")
        a=self.actor(actor_id); region=str(a['region_id'])
        m=self.db.execute(
            "SELECT * FROM markets WHERE region_id=? AND commodity_id=?",(region,commodity)
        ).fetchone()
        if not m or int(m['supply'])<qty: raise ValueError("insufficient market stock")
        total=int(m['price_copper'])*qty
        if int(a['cash_copper'])<total: raise ValueError("insufficient funds")
        with self.db:
            self.db.execute("UPDATE actors SET cash_copper=cash_copper-? WHERE id=?",(total,actor_id))
            self.db.execute(
                "UPDATE markets SET supply=supply-?, demand=demand+? WHERE region_id=? AND commodity_id=?",
                (qty,max(1,qty//2),region,commodity)
            )
            self.db.execute(
                "INSERT INTO actor_inventory VALUES(?,?,?) ON CONFLICT(actor_id,commodity_id) DO UPDATE SET qty=qty+excluded.qty",
                (actor_id,commodity,qty)
            )
            self._reprice(region,commodity)
        return total

    def add_faction(self,id,name,kind,home,treasury,policy):
        self.db.execute("INSERT INTO factions VALUES(?,?,?,?,?,?,?)",(id,name,kind,home,treasury,dumps(policy),self.now))

    def add_faction_goal(self,faction,kind,target,priority):
        self.db.execute(
            "INSERT INTO faction_goals(faction_id,kind,target_region_id,priority,progress,status,created_at,updated_at) VALUES(?,?,?,?,0,'active',?,?)",
            (faction,kind,target,priority,self.now,self.now)
        )

    def _faction_action(self,fid):
        f=self.db.execute("SELECT * FROM factions WHERE id=?",(fid,)).fetchone()
        rng=self._rng(f"faction:{fid}")
        home=str(f['home_region_id'])
        goal=self.db.execute(
            "SELECT * FROM faction_goals WHERE faction_id=? AND status='active' ORDER BY priority DESC,id LIMIT 1",(fid,)
        ).fetchone()
        if goal is None:
            kind = "secure_home" if f['kind']=='guard' else "trade_profit" if f['kind']=='merchant' else "influence"
            self.add_faction_goal(fid,kind,home,rng.randint(45,70))
            goal=self.db.execute(
                "SELECT * FROM faction_goals WHERE faction_id=? AND status='active' ORDER BY id DESC LIMIT 1",(fid,)
            ).fetchone()

        action="observe"
        if goal['kind']=="secure_home":
            threat=self.db.execute(
                "SELECT COUNT(*) FROM region_beliefs rb JOIN facts f ON f.key=rb.fact_key "
                "WHERE rb.region_id=? AND f.significance>=70 AND rb.confidence>=45",(home,)
            ).fetchone()[0]
            if threat:
                cost=min(5000,int(f['treasury_copper']))
                if cost>0:
                    self.db.execute("UPDATE factions SET treasury_copper=treasury_copper-? WHERE id=?",(cost,fid))
                    self.db.execute("UPDATE regions SET security=MIN(100,security+?) WHERE id=?",(max(1,cost//1000),home))
                    action="security_spend"

        elif goal['kind']=="trade_profit":
            best=None
            regions=[str(r['id']) for r in self.db.execute("SELECT id FROM regions WHERE id<>? ORDER BY id",(home,))]
            for m in self.db.execute("SELECT * FROM markets WHERE region_id=?",(home,)):
                src_supply=int(m['supply']); src_target=int(m['target_supply'])
                if src_supply <= max(10, round(src_target*0.45)):
                    continue
                for dst_region in regions:
                    dm=self.db.execute(
                        "SELECT * FROM markets WHERE region_id=? AND commodity_id=?",(dst_region,m['commodity_id'])
                    ).fetchone()
                    if not dm:
                        continue
                    try:
                        travel=self.route_minutes(home,dst_region)
                    except ValueError:
                        continue
                    margin=int(dm['price_copper'])-int(m['price_copper'])
                    shortage=max(0,int(dm['target_supply'])-int(dm['supply']))
                    score=margin*6 + shortage - travel//20
                    if shortage>0 and margin>=0:
                        score += shortage
                    if score>0 and (best is None or score>best[0]):
                        best=(score,m,dm,dst_region,travel)
            if best:
                _,src,dst,dst_region,travel=best
                available=max(0,int(src['supply'])-round(int(src['target_supply'])*0.40))
                shortage=max(10,int(dst['target_supply'])-int(dst['supply']))
                qty=min(200,available,shortage)
                if qty>0:
                    cost=qty*int(src['price_copper'])
                    if int(f['treasury_copper'])>=cost:
                        self.db.execute("UPDATE factions SET treasury_copper=treasury_copper-? WHERE id=?",(cost,fid))
                        self.db.execute(
                            "UPDATE markets SET supply=supply-? WHERE region_id=? AND commodity_id=?",
                            (qty,home,src['commodity_id'])
                        )
                        self.db.execute(
                            "INSERT INTO caravans(faction_id,commodity_id,qty,from_region_id,to_region_id,depart_at,due_at,purchase_cost_copper,status) "
                            "VALUES(?,?,?,?,?,?,?,?,'traveling')",
                            (fid,src['commodity_id'],qty,home,dst_region,self.now,self.now+travel,cost)
                        )
                        self._reprice(home,src['commodity_id']); action="dispatch_caravan"

        else:
            self.db.execute(
                "UPDATE faction_goals SET progress=MIN(100,progress+5),updated_at=? WHERE id=?",
                (self.now,goal['id'])
            )
            action="advance_influence"

        self.db.execute("UPDATE factions SET next_action_at=? WHERE id=?",(self.now+rng.randint(240,600),fid))
        self.event("faction_action",region=home,faction=fid,significance=55,payload={"action":action,"goal":goal['kind']})
        self.metric("faction_actions",1)

    def create_fact(self,key,value,origin,significance=50,confidence=100,mode="courier"):
        self.db.execute("INSERT INTO facts VALUES(?,?,?,?,?)",(key,dumps(value),origin,self.now,significance))
        self.db.execute("INSERT INTO region_beliefs VALUES(?,?,?,?,?,?)",(origin,key,dumps(value),confidence,self.now,origin))
        self._fanout_fact(key,origin,value,confidence,mode)
        self.event("fact_originated",region=origin,significance=significance,payload={"fact_key":key})

    def _fanout_fact(self,key,source,claim,confidence,mode,exclude=None):
        factor=0.60 if mode=="courier" else 1.25
        for r in self.neighbors(source):
            if exclude and r['b']==exclude:
                continue
            due=self.now+max(1,round(int(r['travel_minutes'])*factor))
            exists=self.db.execute(
                "SELECT 1 FROM info_packets WHERE fact_key=? AND from_region_id=? AND to_region_id=? AND status='pending'",
                (key,source,r['b'])
            ).fetchone()
            if exists:
                continue
            self.db.execute(
                "INSERT INTO info_packets(fact_key,from_region_id,to_region_id,claim_json,confidence,depart_at,due_at,mode,status) "
                "VALUES(?,?,?,?,?,?,?,?,'pending')",
                (key,source,r['b'],dumps(claim),max(5,confidence-(3 if mode=='courier' else 10)),self.now,due,mode)
            )

    def _deliver_packets(self):
        rows=self.db.execute(
            "SELECT * FROM info_packets WHERE status='pending' AND due_at<=? ORDER BY due_at,id",(self.now,)
        ).fetchall()
        for p in rows:
            prior=self.db.execute(
                "SELECT confidence FROM region_beliefs WHERE region_id=? AND fact_key=?",(p['to_region_id'],p['fact_key'])
            ).fetchone()
            old_conf=int(prior['confidence']) if prior else -1
            self.db.execute(
                "INSERT INTO region_beliefs VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(region_id,fact_key) DO UPDATE SET "
                "confidence=MAX(confidence,excluded.confidence), received_at=MIN(received_at,excluded.received_at), "
                "claim_json=CASE WHEN excluded.confidence>confidence THEN excluded.claim_json ELSE claim_json END",
                (p['to_region_id'],p['fact_key'],p['claim_json'],p['confidence'],self.now,p['from_region_id'])
            )
            self.db.execute("UPDATE info_packets SET status='delivered' WHERE id=?",(p['id'],))
            self.metric("packets_delivered",1)
            self.event("information_arrived",region=p['to_region_id'],significance=35,payload={"fact_key":p['fact_key'],"from":p['from_region_id']})
            if int(p['confidence'])>old_conf and int(p['confidence'])>=25:
                self._fanout_fact(
                    str(p['fact_key']),str(p['to_region_id']),loads(p['claim_json'],{}),
                    int(p['confidence']),str(p['mode']),exclude=str(p['from_region_id'])
                )

    def _complete_caravans(self):
        rows=self.db.execute(
            "SELECT * FROM caravans WHERE status='traveling' AND due_at<=? ORDER BY due_at,id",(self.now,)
        ).fetchall()
        for c in rows:
            m=self.db.execute(
                "SELECT * FROM markets WHERE region_id=? AND commodity_id=?",(c['to_region_id'],c['commodity_id'])
            ).fetchone()
            if m:
                qty=int(c['qty']); revenue=qty*int(m['price_copper'])
                self.db.execute(
                    "UPDATE markets SET supply=supply+?, demand=MAX(0,demand-?) WHERE region_id=? AND commodity_id=?",
                    (qty,max(1,qty//2),c['to_region_id'],c['commodity_id'])
                )
                if c['faction_id']:
                    self.db.execute("UPDATE factions SET treasury_copper=treasury_copper+? WHERE id=?",(revenue,c['faction_id']))
                self._reprice(c['to_region_id'],c['commodity_id'])
            self.db.execute("UPDATE caravans SET status='completed' WHERE id=?",(c['id'],))
            self.metric("caravans_completed",1)
            self.event("caravan_arrived",region=c['to_region_id'],faction=c['faction_id'],significance=45,payload={"commodity":c['commodity_id'],"qty":c['qty']})

    def detail_level(self,region,player_id="player"):
        prow=self.db.execute("SELECT region_id FROM actors WHERE id=? AND is_player=1",(player_id,)).fetchone()
        if not prow:return "macro"
        p=str(prow['region_id'])
        if region==p:return "full"
        if self.db.execute("SELECT 1 FROM routes WHERE a=? AND b=?",(p,region)).fetchone():return "active"
        return "macro"

    def _macro_tick(self):
        for m in self.db.execute("SELECT * FROM markets").fetchall():
            produced=int(m['production_per_day'])*MACRO_TICK//DAY
            consumed=int(m['consumption_per_day'])*MACRO_TICK//DAY
            new=max(0,int(m['supply'])+produced-consumed)
            demand=max(0,int(m['demand']) + max(0,consumed-produced)//2 - max(0,produced-consumed)//4)
            self.db.execute(
                "UPDATE markets SET supply=?,demand=? WHERE region_id=? AND commodity_id=?",
                (new,demand,m['region_id'],m['commodity_id'])
            )
            self._reprice(str(m['region_id']),str(m['commodity_id']))

        for g in self.db.execute("SELECT * FROM population_groups").fetchall():
            region=str(g['region_id']); level=self.detail_level(region)
            essential=self.db.execute(
                "SELECT AVG(CASE WHEN m.supply < m.target_supply/3 THEN 1.0 ELSE 0.0 END) "
                "FROM markets m JOIN commodities c ON c.id=m.commodity_id WHERE m.region_id=? AND c.essential=1",
                (region,)
            ).fetchone()[0] or 0.0
            unrest=max(0,min(100,int(g['unrest']) + (3 if essential>0.4 else -1)))
            wealth=max(0,min(100,int(g['wealth']) + (1 if essential<0.2 else -1 if essential>0.5 else 0)))
            self.db.execute(
                "UPDATE population_groups SET wealth=?,unrest=?,last_macro_at=? WHERE id=?",
                (wealth,unrest,self.now,g['id'])
            )
            if unrest>=70:
                self.event("population_unrest",region=region,significance=65,payload={"role":g['role'],"level":level,"unrest":unrest})
        self.metric("macro_ticks",1)

    def advance(self,minutes):
        if minutes<0: raise ValueError("time backwards")
        target=self.now+minutes
        while self.now<target:
            candidates=[target,int(self.get_meta("next_macro_at"))]
            for q in [
                "SELECT MIN(due_at) FROM info_packets WHERE status='pending'",
                "SELECT MIN(due_at) FROM caravans WHERE status='traveling'",
                "SELECT MIN(next_action_at) FROM factions"
            ]:
                r=self.db.execute(q).fetchone()[0]
                if r is not None and int(r)>self.now:candidates.append(int(r))
            nxt=min(x for x in candidates if x>self.now)
            self._set_now(nxt)
            self._deliver_packets()
            self._complete_caravans()
            for f in self.db.execute("SELECT id FROM factions WHERE next_action_at<=? ORDER BY id",(self.now,)).fetchall():
                self._faction_action(str(f['id']))
            if self.now>=int(self.get_meta("next_macro_at")):
                self._macro_tick()
                self.set_meta("next_macro_at",self.now+MACRO_TICK)
        self.db.commit()

    def build_context(self,player_id="player",max_events=8):
        p=self.actor(player_id); region=str(p['region_id']); self.metric("context_builds",1)
        reg=dict(self.db.execute("SELECT * FROM regions WHERE id=?",(region,)).fetchone())
        markets=[]
        for m in self.db.execute(
            "SELECT m.commodity_id,c.name,m.supply,m.target_supply,m.demand,m.price_copper "
            "FROM markets m JOIN commodities c ON c.id=m.commodity_id "
            "WHERE m.region_id=? ORDER BY c.essential DESC,c.name",(region,)
        ):
            d=dict(m); d['scarce']=int(d['supply']) < int(d['target_supply'])*0.35; markets.append(d)
        factions=[dict(r) for r in self.db.execute("SELECT id,name,kind FROM factions WHERE home_region_id=? ORDER BY id",(region,))]
        known=[]
        for r in self.db.execute(
            "SELECT f.key,f.value_json,k.confidence FROM actor_knowledge k JOIN facts f ON f.key=k.fact_key "
            "WHERE k.actor_id=? ORDER BY f.significance DESC,f.created_at DESC LIMIT 12",(player_id,)
        ):
            known.append({"key":r['key'],"value":loads(r['value_json'],None),"confidence":r['confidence']})
        ev=[]
        rows=self.db.execute(
            "SELECT * FROM events WHERE visibility='world' AND significance>=50 AND (region_id=? OR region_id IS NULL) "
            "ORDER BY world_minute DESC,significance DESC,id DESC LIMIT ?",
            (region,max_events)
        ).fetchall()
        for r in rows:
            ev.append({"time":r['world_minute'],"type":r['event_type'],"significance":r['significance'],"payload":loads(r['payload_json'],{})})
        return {
            "world_minute":self.now,
            "player":{"id":player_id,"region":region,"cash_copper":int(p['cash_copper'])},
            "region":reg,
            "markets":markets,
            "local_factions":factions,
            "known_facts":known,
            "recent_relevant_events":ev
        }
