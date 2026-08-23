from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from v03_engine import dumps, loads
from v06_migration import RepoCampaignPackage
from v09_runtime import apply_v09_guarded_cutover


CORE_COMBAT = ("атак", "ударя", "бью", "напада", "убива", "режу", "стреля", "attack", "kill")
CORE_MONEY = ("покуп", "плачу", "оплач", "прода", "перевожу деньги", "buy", "pay ", "sell")
CORE_POWER = ("лечу", "исцеля", "колдую", "заклин", "магией", "heal", "cast ", "spell")
LOCAL_MOVE = ("иду", "пойду", "подхожу", "направляюсь", "ухожу", "возвращаюсь", "ищу", "искать", "поднимаюсь", "спускаюсь")
INTERACT = ("целую", "обнимаю", "касаюсь", "беру за руку", "держу за руку", "глажу", "обхватываю")
HANDOFF = ("передаю", "отдаю", "возвращаю", "вручаю", "даю ")
PERFORM = ("пою", "поём", "поем", "исполняю", "сыграю", "играю", "начинаю песню", "perform", "sing ", "play ")
SELF_ACTION = ("киваю", "улыбаюсь", "кланяюсь", "сажусь", "встаю", "смеюсь", "машу рукой")
SOCIAL_REQUEST = ("прошу", "спрашиваю", "предлагаю", "говорю", "отвечаю")
STRONG_SOCIAL = ("убежда", "уговариваю", "запуг", "обманываю", "persuade", "intimidat", "deceiv")


def _stable_int(text: str, modulo: int) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16) % modulo


def _all_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if value is not None else ""


def _quote_fragments(text: str) -> list[str]:
    out = re.findall(r"«([^»]+)»", text)
    out.extend(re.findall(r'"([^"\n]+)"', text))
    seen = []
    for x in out:
        x = x.strip()
        if x and x not in seen:
            seen.append(x)
    return seen


def _claim_mentions(world: Any, text: str) -> list[dict[str, str]]:
    low = text.casefold()
    rows = world.db.execute(
        "SELECT actor_key,display_name FROM actor_position_claims ORDER BY LENGTH(display_name) DESC"
    ).fetchall() if world.db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='actor_position_claims'"
    ).fetchone() else []
    out = []
    for r in rows:
        name = str(r["display_name"])
        key = str(r["actor_key"])
        stems = {name.casefold()}
        if name.endswith("а"):
            stems.add(name[:-1].casefold())
        if any(s and s in low for s in stems):
            out.append({"id": key, "name": name})
    return out


def _regions_mentioned(world: Any, text: str) -> list[str]:
    low = text.casefold()
    out = []
    for r in world.db.execute("SELECT id,name FROM regions ORDER BY LENGTH(name) DESC").fetchall():
        rid, name = str(r["id"]), str(r["name"])
        if rid.casefold() in low or name.casefold() in low:
            out.append(rid)
    return sorted(set(out))


def _latest_payload(package: RepoCampaignPackage) -> dict[str, Any]:
    if package.latest_delta is not None and isinstance(package.latest_delta.data, dict):
        return dict(package.latest_delta.data)
    return {}


def _seed_current_scene_claims(world: Any, package: RepoCampaignPackage) -> None:
    payload = _latest_payload(package)
    src = package.latest_delta.path if package.latest_delta else "live_state.json"
    text = _all_text(payload).casefold()
    location = payload.get("location") if isinstance(payload.get("location"), str) else None
    world.db.execute(
        "INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
        ("player", location, "exact_source_text" if location else "unknown", src, world.now),
    )
    # v159 explicitly says Arlequino takes Rena's guitar with her permission. Seed only when the pointed delta itself says so.
    guitar_claim = (("гитар" in text or "guitar" in text) and ("takes" in text or "бер" in text) and ("permission" in text or "разреш" in text))
    if guitar_claim:
        world.db.execute(
            "INSERT OR REPLACE INTO scene_objects(object_key,display_name,holder_key,state_json,certainty,source_path,updated_at) VALUES(?,?,?,?,?,?,?)",
            ("rena_guitar", "гитара Рены", "player", dumps({"ownership":"Rena","possession":"Arlequino with permission"}),
             "exact_current_delta", src, world.now),
        )

    # Current pointed delta may contain an explicitly authorized autonomous next action. Preserve it as a prospective commitment.
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    rena_next = scene.get("rena_next_action") if isinstance(scene, dict) else None
    if isinstance(rena_next, str) and any(k in rena_next.casefold() for k in ("send", "sending", "отправ")):
        key = f"live:rena_mail_v{int(package.pointer.get('v') or 0)}"
        world.db.execute(
            "INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) VALUES(?,?,?,?,?,?,?)",
            (key, "rena", "mail", dumps({"instruction":rena_next,"source":"pointed_live_delta"}), "ACTIVE", src,
             int(package.pointer.get("v") or 0)),
        )


def _handler_for(kind: str) -> tuple[str, int]:
    k = kind.casefold()
    if k == "npc_task":
        return "task_progress", 30
    if k in {"festival", "tournament"}:
        return "project_progress", 60
    if k == "mail":
        return "mail_guarded", 30
    return "opaque_guarded", 60


def install_v10_runtime_bridges(world: Any, package: RepoCampaignPackage | None = None) -> None:
    with world.db:
        if package is not None:
            _seed_current_scene_claims(world, package)
        for r in world.db.execute(
            "SELECT commitment_key,kind FROM autonomous_commitments ORDER BY commitment_key"
        ).fetchall():
            key, kind = str(r["commitment_key"]), str(r["kind"])
            handler, cadence = _handler_for(kind)
            offset = 1 + _stable_int(key, min(15, cadence))
            world.db.execute(
                "INSERT OR IGNORE INTO autonomy_runtime(commitment_key,handler,next_due_at,cadence_minutes,tick_count,status,last_outcome_json) "
                "VALUES(?,?,?,?,0,'active','{}')",
                (key, handler, world.now + offset, cadence),
            )
        # Time advance is now safe: imported commitments have an executable or explicit guarded handler.
        world.db.execute(
            "INSERT OR REPLACE INTO migration_capabilities(command,enabled,reason) VALUES('wait',1,?)",
            ("v10_autonomy_scheduler_wired",),
        )
        world.db.execute(
            "INSERT OR REPLACE INTO migration_capabilities(command,enabled,reason) VALUES('scene',1,?)",
            ("v10_structured_scene_action_bridge",),
        )
        for code, detail in {
            "scene_action_bridge_not_implemented":"Structured ordinary-scene actions are persisted as event-only or pending-resolution transitions; narrator cannot silently mutate outcomes.",
            "autonomy_commitment_execution_not_wired":"Every imported commitment is wired to a prospective handler; unsupported semantics produce explicit causal blocking rather than frozen invisible work.",
        }.items():
            world.db.execute(
                "UPDATE cutover_gate SET status='resolved',detail=?,evidence_json=?,updated_at=? WHERE gate_code=?",
                (detail, dumps(["engine:v10"]), world.now, code),
            )
        world.db.execute(
            "INSERT OR REPLACE INTO cutover_gate(gate_code,status,classification,detail,evidence_json,updated_at) VALUES(?,?,?,?,?,?)",
            ("shadow_scene_verification", "pending_shadow", "runtime",
             "Current LIVE continuation must pass scene bridge + autonomous-time shadow rehearsal without authoritative cutover.", "[]", world.now),
        )
        world.db.execute(
            "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
            ("runtime_mode", '"v10_shadow_rehearsal"', "engine:v10"),
        )


def mark_v10_shadow_verified(world: Any, evidence: list[Any]) -> None:
    with world.db:
        world.db.execute(
            "UPDATE cutover_gate SET status='resolved',detail=?,evidence_json=?,updated_at=? WHERE gate_code='shadow_scene_verification'",
            ("Current LIVE continuation accepted by scene bridge and autonomous scheduler progressed under shadow runtime.", dumps(evidence), world.now),
        )


class V10RuntimeMixin:
    def _next_v10_due(self, target: int) -> int:
        row = self.db.execute(
            "SELECT MIN(next_due_at) FROM autonomy_runtime WHERE status='active' AND next_due_at>? AND next_due_at<=?",
            (self.now, target),
        ).fetchone()
        return min(target, int(row[0])) if row and row[0] is not None else target

    def _run_commitment(self, row: Any) -> dict[str, Any]:
        key = str(row["commitment_key"])
        owner = str(row["owner_key"]) if row["owner_key"] is not None else None
        handler = str(row["handler"])
        state = loads(row["state_json"], {})
        tick = int(row["tick_count"]) + 1
        visible = 0
        if handler == "task_progress":
            outcome = {"code":"progressed","tick":tick,"effect":"owner works on preserved task; no invented completion"}
        elif handler == "project_progress":
            outcome = {"code":"progressed","tick":tick,"effect":"project receives prospective work tick; no invented milestone/completion"}
        elif handler == "mail_guarded":
            low = _all_text(state).casefold()
            if any(x in low for x in ("arrived", "delivered", "доставлен", "получен")):
                outcome = {"code":"already_settled","tick":tick,"effect":"no duplicate delivery"}
            else:
                outcome = {"code":"causally_blocked","tick":tick,"reason":"route_or_dispatch_price_unknown",
                           "initiative":"seek dispatch method/quote; do not invent payment or arrival"}
        else:
            outcome = {"code":"guarded_no_semantics","tick":tick,"reason":"handler semantics unavailable; commitment remains explicit and scheduled"}
        self.db.execute(
            "INSERT INTO autonomy_execution_log(world_minute,commitment_key,owner_key,handler,outcome_code,outcome_json,visible_to_player) VALUES(?,?,?,?,?,?,?)",
            (self.now, key, owner, handler, outcome["code"], dumps(outcome), visible),
        )
        self.db.execute(
            "UPDATE autonomy_runtime SET tick_count=?,last_run_at=?,next_due_at=?,last_outcome_json=? WHERE commitment_key=?",
            (tick, self.now, self.now + int(row["cadence_minutes"]), dumps(outcome), key),
        )
        return outcome

    def _process_v10_due(self) -> int:
        ran = 0
        while True:
            rows = self.db.execute(
                "SELECT ar.*,ac.owner_key,ac.kind,ac.state_json FROM autonomy_runtime ar "
                "JOIN autonomous_commitments ac USING(commitment_key) "
                "WHERE ar.status='active' AND ar.next_due_at<=? ORDER BY ar.next_due_at,ar.commitment_key LIMIT 100",
                (self.now,),
            ).fetchall()
            if not rows:
                break
            for row in rows:
                self._run_commitment(row); ran += 1
            if ran > 5000:
                raise RuntimeError("autonomy catch-up guard exceeded")
        return ran

    def advance(self, minutes: int) -> None:
        if minutes < 0:
            raise ValueError("time backwards")
        target = self.now + int(minutes)
        self._process_v10_due()
        while self.now < target:
            nxt = self._next_v10_due(target)
            super().advance(nxt - self.now)
            self._process_v10_due()
        self.db.commit()

    def propose_scene_action(self, player_id: str, raw_text: str) -> dict[str, Any]:
        text = str(raw_text).strip()
        low = text.casefold()
        if not text:
            return {"status":"needs_clarification","reason":"empty_action","components":[]}
        # Never let the generic scene bridge bypass mechanics that can change bodies, money, magic or cross-region state.
        if any(x in low for x in ("жду", "подожду", "wait")):
            return {"status":"core_or_blocked","reason":"wait_uses_authoritative_clock","components":[]}
        if any(x in low for x in CORE_COMBAT):
            return {"status":"core_or_blocked","reason":"combat_requires_guarded_engine","components":[]}
        if any(x in low for x in CORE_MONEY):
            return {"status":"blocked","reason":"money_mutation_requires_explicit_engine_transaction","components":[]}
        if any(x in low for x in CORE_POWER):
            return {"status":"blocked","reason":"power_or_treatment_mechanics_guarded_unknown","components":[]}
        if any(x in low for x in STRONG_SOCIAL):
            return {"status":"core_or_blocked","reason":"contested_social_requires_guarded_engine","components":[]}

        regions = _regions_mentioned(self, text)
        moving = any(x in low for x in LOCAL_MOVE)
        if moving and regions:
            return {"status":"core_or_blocked","reason":"inter_region_travel_requires_route_engine","components":[]}

        claims = _claim_mentions(self, text)
        components: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        quotes = _quote_fragments(text)
        if quotes or any(x in low for x in SOCIAL_REQUEST):
            components.append({"kind":"speech_or_request","quotes":quotes,"grounding":"verbatim_raw_text"})
            if any(x in low for x in ("прошу", "предлагаю", "спрашиваю")) and claims:
                pending.append({"kind":"npc_response","target_key":claims[0]["id"],"target_text":claims[0]["name"]})
        if any(x in low for x in PERFORM):
            components.append({"kind":"performance","grounding":"verbatim_raw_text","economy":"no_auto_income"})
        if moving:
            target = claims[0] if len(claims) == 1 else None
            kind = "local_search_or_move"
            components.append({"kind":kind,"target":target,"grounding":"verbatim_raw_text"})
            pending.append({"kind":"local_navigation","target_key":target["id"] if target else None,
                            "target_text":target["name"] if target else text})
        if any(x in low for x in INTERACT):
            target = claims[0] if len(claims) == 1 else None
            components.append({"kind":"interaction_attempt","target":target,"grounding":"verbatim_raw_text"})
            pending.append({"kind":"npc_or_world_response","target_key":target["id"] if target else None,
                            "target_text":target["name"] if target else None})
        if any(x in low for x in HANDOFF):
            obj = None
            if "гитар" in low:
                row = self.db.execute("SELECT object_key,display_name,holder_key FROM scene_objects WHERE object_key='rena_guitar'").fetchone()
                if row is not None:
                    obj = {"key":str(row["object_key"]),"name":str(row["display_name"]),"holder":row["holder_key"]}
            target = claims[0] if len(claims) == 1 else None
            components.append({"kind":"handoff_offer","object":obj,"target":target,"grounding":"verbatim_raw_text"})
            if obj is None:
                return {"status":"needs_clarification","reason":"object_not_authoritatively_tracked","components":components}
            if str(obj.get("holder")) != player_id:
                return {"status":"blocked","reason":"player_not_current_holder","components":components}
            pending.append({"kind":"handoff_acceptance","target_key":target["id"] if target else None,
                            "target_text":target["name"] if target else None})
        if any(x in low for x in SELF_ACTION):
            components.append({"kind":"self_action","grounding":"verbatim_raw_text"})

        if not components:
            # Generic non-high-risk action is preserved as an attempt, never silently promoted to a successful world mutation.
            components.append({"kind":"generic_player_action_attempt","grounding":"verbatim_raw_text"})
            pending.append({"kind":"world_resolution_required","target_key":claims[0]["id"] if len(claims)==1 else None,
                            "target_text":claims[0]["name"] if len(claims)==1 else None})

        mode = "pending_resolution" if pending else "event_only"
        return {"status":"ready","action_kind":"compound" if len(components)>1 else components[0]["kind"],
                "components":components,"pending":pending,"resolution_mode":mode}

    def _scene_turn(self, turn_key: str, raw_text: str, proposal: dict[str, Any], player_id: str) -> dict[str, Any]:
        old = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if old is not None:
            return self._load_turn_public(old, replayed=True)
        cur = self.db.execute(
            "INSERT INTO gm_turns(turn_key,player_id,raw_text,status,created_at) VALUES(?,?,?,?,?)",
            (turn_key, player_id, str(raw_text), "received", self.now),
        )
        turn_id = int(cur.lastrowid)
        action_cur = self.db.execute(
            "INSERT INTO scene_actions(turn_key,world_minute,actor_id,action_kind,raw_text,components_json,resolution_mode,status,effect_json,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (turn_key, self.now, player_id, proposal["action_kind"], str(raw_text), dumps(proposal["components"]),
             proposal["resolution_mode"], "pending" if proposal["pending"] else "recorded", "{}", self.now),
        )
        action_id = int(action_cur.lastrowid)
        for p in proposal["pending"]:
            self.db.execute(
                "INSERT INTO scene_pending_resolution(scene_action_id,resolution_kind,target_key,target_text,state_json,status,created_at) VALUES(?,?,?,?,?,'pending',?)",
                (action_id, p["kind"], p.get("target_key"), p.get("target_text"), dumps(p), self.now),
            )
        self.db.commit()
        packet = self.build_gm_packet(player_id)
        checkpoint = self.write_checkpoint(player_id, turn_id=turn_id, kind="scene_player_turn")
        status = "scene_pending" if proposal["pending"] else "executed"
        contract = {
            "state_authority":"engine_scene_record_and_checkpoint_only",
            "player_text_verbatim":str(raw_text),
            "must_preserve":["verbatim player action","pending outcomes remain pending","money/time/region from GM packet","UNKNOWN values"],
            "may_add":["sensory description already supported by perceivable state","neutral acknowledgement of player speech/performance"],
            "forbidden":["resolve pending NPC/world response in narration","invent movement success","invent consent","invent income/expense","new hidden state mutation"],
        }
        public = {"status":status,"accepted":True,"turn_key":turn_key,"scene_action_id":action_id,
                  "proposal":proposal,"gm_packet":packet,"narration_contract":contract,"checkpoint":checkpoint}
        self.db.execute(
            "UPDATE gm_turns SET status=?,proposal_json=?,validation_json=?,engine_result_json=?,gm_packet_json=?,narration_contract_json=?,checkpoint_hash=?,public_result_json=?,completed_at=? WHERE id=?",
            (status,dumps(proposal),dumps({"valid":True,"reason":"v10_scene_grounded"}),
             dumps({"scene_action_id":action_id,"resolution_mode":proposal["resolution_mode"]}),dumps(packet),dumps(contract),
             checkpoint["state_hash"],dumps(public),self.now,turn_id),
        )
        self.db.commit()
        return public

    def process_player_turn(self, turn_key: str, raw_text: str, *, player_id: str="player", external_intent: dict[str, Any] | None=None):
        old = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if old is not None:
            return self._load_turn_public(old, replayed=True)
        scene = self.propose_scene_action(player_id, raw_text)
        if scene["status"] == "ready":
            if external_intent is not None:
                return {"status":"needs_clarification","accepted":False,"reason":"external_intent_not_used_for_scene_bridge","proposal":scene,"turn_key":turn_key}
            return self._scene_turn(turn_key, raw_text, scene, player_id)
        if scene["status"] == "blocked":
            return {"status":"blocked_by_guardrail","accepted":False,"reason":scene["reason"],"proposal":scene,"turn_key":turn_key}
        return super().process_player_turn(turn_key, raw_text, player_id=player_id, external_intent=external_intent)

    def critical_state_snapshot(self, player_id: str="player") -> dict[str, Any]:
        snap = super().critical_state_snapshot(player_id)
        snap["scene"] = {
            "actions": [tuple(r) for r in self.db.execute(
                "SELECT id,action_kind,status,resolution_mode FROM scene_actions WHERE actor_id=? ORDER BY id DESC LIMIT 8", (player_id,)
            ).fetchall()],
            "pending": [tuple(r) for r in self.db.execute(
                "SELECT p.id,p.resolution_kind,p.target_key,p.status FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.actor_id=? ORDER BY p.id DESC LIMIT 8", (player_id,)
            ).fetchall()],
            "objects": [tuple(r) for r in self.db.execute(
                "SELECT object_key,holder_key,certainty FROM scene_objects ORDER BY object_key"
            ).fetchall()],
        }
        snap["autonomy_runtime"] = [tuple(r) for r in self.db.execute(
            "SELECT commitment_key,tick_count,last_run_at,status,last_outcome_json FROM autonomy_runtime ORDER BY commitment_key"
        ).fetchall()]
        return snap

    def build_gm_packet(self, player_id: str="player"):
        packet = super().build_gm_packet(player_id)
        recent = [
            {"id":int(r["id"]),"kind":str(r["action_kind"]),"raw":str(r["raw_text"]),"status":str(r["status"]),"resolution":str(r["resolution_mode"])}
            for r in self.db.execute(
                "SELECT id,action_kind,raw_text,status,resolution_mode FROM scene_actions WHERE actor_id=? ORDER BY id DESC LIMIT 4", (player_id,)
            ).fetchall()
        ]
        pending = [
            {"id":int(r["id"]),"kind":str(r["resolution_kind"]),"target":r["target_text"],"status":str(r["status"])}
            for r in self.db.execute(
                "SELECT p.id,p.resolution_kind,p.target_text,p.status FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id "
                "WHERE a.actor_id=? AND p.status='pending' ORDER BY p.id LIMIT 8", (player_id,)
            ).fetchall()
        ]
        packet["scene_bridge"] = {"recent_player_actions":recent,"pending_resolutions":pending}
        packet["migration"]["autonomy_runtime"] = {
            "active":self.db.execute("SELECT COUNT(*) FROM autonomy_runtime WHERE status='active'").fetchone()[0],
            "executions":self.db.execute("SELECT COUNT(*) FROM autonomy_execution_log").fetchone()[0],
        }
        packet["constraints"]["pending_resolution"] = (
            "A pending scene resolution is authoritative uncertainty. Narrator may describe the attempt but may not decide its success, NPC consent/response, navigation result, payment, or reward."
        )
        raw = dumps(packet)
        if len(raw) > 8000:
            packet["scene_bridge"]["recent_player_actions"] = packet["scene_bridge"]["recent_player_actions"][:2]
            packet["scene_bridge"]["pending_resolutions"] = packet["scene_bridge"]["pending_resolutions"][:4]
        return packet


def apply_v10_shadow_cutover(world: Any, package: RepoCampaignPackage, repo_root: str | Path) -> dict[str, Any]:
    report = apply_v09_guarded_cutover(world, package, repo_root)
    if report.get("errors") or not report.get("baseline_ready"):
        return {"source_version":package.pointer.get("v"),"baseline_ready":False,"live_cutover_ready":False,
                "errors":["v09_baseline_not_ready", *report.get("errors",[])]}
    install_v10_runtime_bridges(world, package)
    active = [str(r[0]) for r in world.db.execute(
        "SELECT gate_code FROM cutover_gate WHERE status!='resolved' ORDER BY gate_code"
    ).fetchall()]
    return {"source_version":int(package.pointer.get("v") or 0),"baseline_ready":True,
            "cutover_blockers":active,"live_cutover_ready":False,"errors":[]}
