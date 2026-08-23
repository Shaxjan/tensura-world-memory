from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from v03_engine import DAY, dumps, loads


class V05CommandClockContextImportMixin:
    NEW_COMMANDS={"strike","treat","social"}

    def submit_player_command(self, player_id: str, command: str, params: dict[str,Any] | None=None) -> dict[str,Any]:
        params=dict(params or {})
        if command == "attack":
            actor=self.actor(player_id)
            if not int(actor["is_player"]): raise ValueError("command firewall is for player actors")
            self._action_log(player_id,command,params,False,"deprecated_use_strike_with_explicit_mode")
            self.db.commit()
            return {"accepted":False,"reason":"deprecated_use_strike_with_explicit_mode"}
        if command not in self.NEW_COMMANDS:
            return super().submit_player_command(player_id,command,params)
        actor=self.actor(player_id)
        if not int(actor["is_player"]): raise ValueError("command firewall is for player actors")
        try:
            if command=="strike":
                self._require_exact_keys(params,{"target","mode"}); result=self.resolve_tensura_attack(player_id,str(params["target"]),mode=str(params["mode"]))
            elif command=="treat":
                self._require_exact_keys(params,{"target","method"}); result=self.treat_actor(player_id,str(params["target"]),method=str(params["method"]))
            elif command=="social":
                self._require_exact_keys(params,{"target","approach","goal_text"}); result=self.resolve_social_attempt(player_id,str(params["target"]),approach=str(params["approach"]),goal_text=str(params["goal_text"]))
            else: raise ValueError("unreachable command")
            self._action_log(player_id,command,params,True); self.db.commit(); return {"accepted":True,"result":result}
        except Exception as exc:
            self.db.rollback(); self._action_log(player_id,command,params,False,str(exc)); self.db.commit(); return {"accepted":False,"reason":str(exc)}

    def advance(self, minutes: int) -> None:
        if minutes<0: raise ValueError("time backwards")
        target=self.now+int(minutes)
        while self.now<target:
            step=min(60,target-self.now)
            super().advance(step)
            self._process_v05_conditions(); self._decay_evidence(); self._process_named_plans(); self._sync_travel_plans(); self._process_routines()
        self.db.commit()

    def build_gm_packet(self, player_id: str="player") -> dict[str,Any]:
        base=self.build_context(player_id,max_events=6)
        player=self.actor(player_id); region=str(player["region_id"])
        visible=[]
        for r in self.db.execute("SELECT id,name,status FROM actors WHERE region_id=? AND id<>? ORDER BY id LIMIT 12",(region,player_id)):
            visible.append({"id":str(r["id"]),"name":str(r["name"]),"status":str(r["status"])})
        conditions=[{"code":str(r["code"]),"severity":int(r["severity"])} for r in self.db.execute("SELECT code,severity FROM conditions WHERE actor_id=? AND status='active' ORDER BY severity DESC LIMIT 6",(player_id,))]
        packet={
            "time":self.now,
            "player":base["player"],
            "perceivable":{"region":base["region"],"actors":visible,"markets":base.get("markets",[]),"events":base.get("recent_relevant_events",[])},
            "known":{"facts":base.get("known_facts",[]),"memories":base.get("memories",[])},
            "constraints":{"conditions":conditions,"legal":base.get("legal_status",[]),"appointments":base.get("upcoming_appointments",[]),"unknown_policy":"UNKNOWN must stay UNKNOWN; do not infer hidden state"},
            "command_contract":{"direct":["travel","buy","attempt","attend","wait","strike","treat","social"],"natural_language":"use propose_text_intent; execute only status=ready"},
        }
        raw=json.dumps(packet,ensure_ascii=False,separators=(",",":"))
        if len(raw)>8000:
            packet["perceivable"]["events"]=packet["perceivable"]["events"][:3]
            packet["known"]["memories"]=packet["known"]["memories"][:3]
            raw=json.dumps(packet,ensure_ascii=False,separators=(",",":"))
        if len(raw)>8000: raise RuntimeError("GM packet exceeds guardrail")
        digest=hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        self.db.execute("INSERT INTO gm_packet_log(world_minute,player_id,chars,packet_hash) VALUES(?,?,?,?)",(self.now,player_id,len(raw),digest)); self.db.commit()
        packet["packet_meta"]={"chars":len(raw),"hash":digest}
        return packet

    @staticmethod
    def _parse_money(value: Any) -> int | None:
        if value is None or value=="UNKNOWN": return None
        if isinstance(value,int): return value if value>=0 else None
        m=re.fullmatch(r"\s*(\d+)g\s*(\d+)s\s*(\d+)c\s*",str(value))
        if not m: return None
        g,s,c=map(int,m.groups()); return g*10000+s*100+c

    def audit_campaign_snapshot(self, snapshot: dict[str,Any], *, source_label: str="snapshot") -> dict[str,Any]:
        errors=[]; unknowns=[]; warnings=[]
        player=snapshot.get("player") or snapshot.get("maestro")
        if not isinstance(player,dict): errors.append("missing player object"); player={}
        region=player.get("region_id") or player.get("location")
        cash=player.get("cash_copper",player.get("personal_cash"))
        parsed_cash=self._parse_money(cash)
        if region in (None,"UNKNOWN"): unknowns.append("player.region")
        elif self.db.execute("SELECT 1 FROM regions WHERE id=?",(str(region),)).fetchone() is None:
            warnings.append(f"unmapped_region:{region}")
        if parsed_cash is None: unknowns.append("player.cash")
        world_minute=snapshot.get("world_minute")
        if world_minute in (None,"UNKNOWN"): unknowns.append("world_minute")
        elif not isinstance(world_minute,int): errors.append("world_minute must be integer in import contract")
        for idx,a in enumerate(snapshot.get("actors",[])):
            if not isinstance(a,dict): errors.append(f"actors[{idx}] not object"); continue
            for key in ("id","name"):
                if a.get(key) in (None,"UNKNOWN"): unknowns.append(f"actors[{idx}].{key}")
        ready=not errors and not unknowns and not any(x.startswith("unmapped_region") for x in warnings)
        report={"ready":ready,"errors":errors,"unknowns":unknowns,"warnings":warnings,"normalized":{"world_minute":world_minute,"player_region":region,"player_cash_copper":parsed_cash}}
        cur=self.db.execute("INSERT INTO import_runs(world_minute,source_label,source_version,ready,applied,report_json) VALUES(?,?,?,?,0,?)",(self.now,source_label,str(snapshot.get("save_version","UNKNOWN")),int(ready),dumps(report))); self.db.commit(); report["import_run_id"]=int(cur.lastrowid)
        return report

    def apply_campaign_snapshot(self, snapshot: dict[str,Any], *, source_label: str="snapshot") -> dict[str,Any]:
        report=self.audit_campaign_snapshot(snapshot,source_label=source_label)
        if not report["ready"]: return {"applied":False,"report":report}
        player=snapshot.get("player") or snapshot.get("maestro") or {}; n=report["normalized"]
        with self.db:
            self._set_now(int(n["world_minute"]))
            self.db.execute("UPDATE actors SET region_id=?,cash_copper=? WHERE id='player'",(str(n["player_region"]),int(n["player_cash_copper"])))
            for a in snapshot.get("actors",[]):
                aid=str(a["id"]); name=str(a["name"]); region=a.get("region_id")
                if region in (None,"UNKNOWN"): continue
                if self.db.execute("SELECT 1 FROM regions WHERE id=?",(str(region),)).fetchone() is None: continue
                if self.db.execute("SELECT 1 FROM actors WHERE id=?",(aid,)).fetchone():
                    self.db.execute("UPDATE actors SET name=?,region_id=? WHERE id=?",(name,str(region),aid))
                else:
                    self.add_actor(aid,name,str(region),cash=int(a.get("cash_copper",0) or 0),is_player=False)
            self.db.execute("UPDATE import_runs SET applied=1 WHERE id=?",(report["import_run_id"],))
        return {"applied":True,"report":report}
