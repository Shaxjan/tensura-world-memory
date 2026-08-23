from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from v03_engine import dumps
from v06_migration import RepoCampaignPackage, apply_repo_campaign_rehearsal

SOURCE_JSON = (
    "memory/money.json",
    "memory/places.json",
    "memory/relationships.json",
    "memory/actions.json",
)
SOURCE_RULES = (
    "rules/NPC_AUTONOMY_MODEL_v1.md",
    "rules/NPC_INDIVIDUALITY_AND_AUTONOMY_RULE.md",
)
ECONOMY_FILES = (
    "ECONOMY_MODEL_v1/01_core.txt",
    "ECONOMY_MODEL_v1/02_money.txt",
    "ECONOMY_MODEL_v1/03_concert_income.txt",
    "ECONOMY_MODEL_v1/04_tips.txt",
    "ECONOMY_MODEL_v1/05_city_profile.txt",
    "ECONOMY_MODEL_v1/06_audience.txt",
    "ECONOMY_MODEL_v1/07_song.txt",
    "ECONOMY_MODEL_v1/08_costs.txt",
    "ECONOMY_MODEL_v1/09_reputation.txt",
    "ECONOMY_MODEL_v1/10_cap.txt",
    "ECONOMY_MODEL_v1/11_dynamics.txt",
    "ECONOMY_MODEL_v1/20_eurazania.txt",
    "ECONOMY_MODEL_v1/21_blumund.txt",
)

NAME_KEYS = {
    "Рена": "rena", "Карион": "carrion", "Борга": "borga", "Мэйра": "meira",
    "Гарет": "gareth", "Верн": "vern", "Лисса": "lissa", "Орен": "oren",
}

FUND_TOKENS = {
    "promo": ("promo", "промо", "publicity", "реклам"),
    "lissa_project": ("lissa", "лисс", "издатель"),
    "oren_project": ("oren", "орен"),
    "vern_instrument_float": ("vern", "верн", "instrument", "инструмент"),
    "meira_obligation": ("meira", "мэйр", "координатор"),
}

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _read(root: Path, rel: str) -> tuple[str, str]:
    text=(root/rel).read_text(encoding="utf-8")
    return text, _sha(text)

def _json(root: Path, rel: str) -> dict[str,Any]:
    return json.loads((root/rel).read_text(encoding="utf-8"))

def parse_loose_money(value: Any) -> int | None:
    if isinstance(value, int):
        return value if value >= 0 else None
    if not isinstance(value, str) or "UNKNOWN" in value.upper():
        return None
    s=value.strip().lower().replace(" ","")
    if s=="0":
        return 0
    m=re.fullmatch(r"(?:(\d+)g)?(?:(\d+)s)?(?:(\d+)c)?", s)
    if not m or not any(x is not None for x in m.groups()):
        return None
    g,silver,c=(int(x or 0) for x in m.groups())
    if silver>=100 or c>=100:
        return None
    return g*10000+silver*100+c

def _version(path: Path) -> int | None:
    m=re.search(r"live_v(\d+)", path.as_posix())
    return int(m.group(1)) if m else None

def scan_late_mentions(root: Path, after_version: int, tokens: tuple[str,...], through_version: int | None) -> list[int]:
    hits=[]
    for p in root.glob("live_v*/delta.json"):
        v=_version(p)
        if v is None or v<=after_version or (through_version is not None and v>through_version):
            continue
        low=p.read_text(encoding="utf-8", errors="replace").casefold()
        if any(t.casefold() in low for t in tokens):
            hits.append(v)
    return sorted(hits)

def _source(world: Any, root: Path, rel: str, kind: str, authority: str) -> tuple[str,str]:
    text, digest=_read(root,rel)
    world.db.execute(
        "INSERT OR REPLACE INTO baseline_sources(source_path,sha256,byte_count,kind,authority,loaded_at) VALUES(?,?,?,?,?,?)",
        (rel,digest,len(text.encode("utf-8")),kind,authority,world.now),
    )
    return text,digest

def _baseline(world: Any, kind: str, key: str, value: Any, rel: str, sha: str,
              authority: str, status: str, version: int | None=None) -> None:
    world.db.execute(
        "INSERT OR REPLACE INTO source_baselines(kind,baseline_key,value_json,source_path,source_sha,authority,status,as_of_version) VALUES(?,?,?,?,?,?,?,?)",
        (kind,key,dumps(value),rel,sha,authority,status,version),
    )

def _set_resolution(world: Any, code: str, classification: str, status: str, resolution: str,
                    evidence: list[str], replacement: str | None=None) -> None:
    world.db.execute(
        "INSERT OR REPLACE INTO blocker_resolution(blocker_code,classification,status,resolution,evidence_json,replacement_blocker) VALUES(?,?,?,?,?,?)",
        (code,classification,status,resolution,dumps(evidence),replacement),
    )

def _import_money(world: Any, root: Path, pointer_v: int) -> dict[str,Any]:
    rel="memory/money.json"; data=_json(root,rel); _,sha=_source(world,root,rel,"money_audit","SAVED_CANON_AUDIT")
    audit_v=int(data.get("current_saved_canon",{}).get("live_pointer_version") or 0)
    sf=data.get("separate_funds_last_explicit_record",{})
    accounts={
        "promo": sf.get("promo_remaining",{}).get("amount"),
        "lissa_project": sf.get("lissa_project_fund",{}).get("amount"),
        "oren_project": sf.get("oren_project_fund",{}).get("amount"),
        "vern_instrument_float": data.get("paid_and_held_money",{}).get("vern",{}).get("instrument_float_held"),
        "meira_obligation": data.get("paid_and_held_money",{}).get("meira",{}).get("remaining_obligation"),
    }
    rows={}
    for aid,value in accounts.items():
        copper=parse_loose_money(value)
        mentions=scan_late_mentions(root,audit_v,FUND_TOKENS[aid],pointer_v)
        certainty="exact_as_of_audit_no_current_claim" if copper is not None else "unknown"
        if mentions:
            certainty="stale_after_later_mentions"
        world.db.execute(
            "INSERT OR REPLACE INTO fund_account_audit(account_id,balance_copper,certainty,exact_as_of_version,later_mentions_json,source_path,note) VALUES(?,?,?,?,?,?,?)",
            (aid,copper,certainty,audit_v,dumps(mentions),rel,
             "Historical amount is preserved; later mention never implies an unrecorded debit/credit."),
        )
        rows[aid]={"balance_copper":copper,"certainty":certainty,"later_mentions":mentions}
    _baseline(world,"money","audit",data,rel,sha,"SAVED_CANON_AUDIT","imported",audit_v)
    return {"audit_version":audit_v,"accounts":rows}

def _import_relationships(world: Any, root: Path, pointer_v: int) -> int:
    rel="memory/relationships.json"; data=_json(root,rel); _,sha=_source(world,root,rel,"relationships","SAVED_CANON")
    n=0
    for item in data.get("relationships",[]):
        name=str(item.get("entity","UNKNOWN")); actor=NAME_KEYS.get(name,name.casefold())
        world.db.execute(
            "INSERT OR REPLACE INTO relationship_evidence(actor_key,target_key,evidence_key,summary_json,source_path,authority,as_of_version) VALUES(?,?,?,?,?,?,?)",
            (actor,"player","saved_relationship",dumps(item),rel,str(item.get("status","SAVED_CANON")),pointer_v),
        ); n+=1
        _baseline(world,"relationship",actor,item,rel,sha,str(item.get("status","SAVED_CANON")),"qualitative",pointer_v)
    return n

def _position(world: Any, actor: str, name: str, region: str | None, location: str | None,
              precision: str, status: str, version: int, source: str, note: str="") -> None:
    world.db.execute(
        "INSERT OR REPLACE INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) VALUES(?,?,?,?,?,?,?,?,?)",
        (actor,name,region,location,precision,status,version,source,note),
    )

def _import_positions(world: Any, root: Path, package: RepoCampaignPackage) -> dict[str,int]:
    rel="memory/places.json"; _json(root,rel); _source(world,root,rel,"places","SAVED_CANON_AUDIT")
    v=int(package.pointer.get("v") or 0)
    _position(world,"rena","Рена","eurazania",None,"region_only","known_region_exact_place_unknown",v,package.snapshot["source"]["latest_delta"] or rel,
              "Current scene keeps Rena in Eurazania; exact instantaneous place after breakfast is not asserted.")
    _position(world,"borga","Борга","eurazania",None,"region_only","target_in_current_capital_context",v,package.snapshot["source"]["latest_delta"] or rel,
              "Arlequino is going to find him; exact instantaneous location is explicitly unestablished.")
    _position(world,"carrion","Карион","eurazania","дворец Кариона","named_place","institutional_home",v,rel)
    _position(world,"meira","Мэйра","eurazania",None,"region_only","active_festival_coordinator",v,"memory/actions.json")
    _position(world,"gareth","Гарет","eurazania",None,"region_only","active_capital_survey",v,"memory/actions.json")
    _position(world,"vern","Верн",None,None,"unknown","active_trip_progress_unknown",v,"memory/actions.json")
    _position(world,"lissa","Лисса","blumund",None,"region_only","project_contact",v,"memory/relationships.json")
    _position(world,"oren","Орен","blumund",None,"region_only","project_contact",v,"memory/relationships.json")
    return {"claims":8,"unknown_exact":sum(1 for _ in world.db.execute("SELECT 1 FROM actor_position_claims WHERE precision IN ('region_only','unknown')"))}

def _import_autonomy(world: Any, root: Path, pointer_v: int) -> int:
    rel="memory/actions.json"; data=_json(root,rel); _,sha=_source(world,root,rel,"actions","SAVED_CANON")
    n=0
    for item in data.get("active_people_tasks",[]):
        owner=NAME_KEYS.get(str(item.get("person")),str(item.get("person","unknown")).casefold())
        key=f"task:{owner}"
        world.db.execute(
            "INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) VALUES(?,?,?,?,?,?,?)",
            (key,owner,"npc_task",dumps(item),str(item.get("status","ACTIVE")),rel,pointer_v),
        ); n+=1
    for i,item in enumerate(data.get("mail",[]),1):
        world.db.execute(
            "INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) VALUES(?,?,?,?,?,?,?)",
            (f"mail:{i}",None,"mail",dumps(item),str(item.get("last_known_status","UNKNOWN")),rel,pointer_v),
        ); n+=1
    for key in ("festival","tournament"):
        if key in data:
            world.db.execute(
                "INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) VALUES(?,?,?,?,?,?,?)",
                (key,None,key,dumps(data[key]),str(data[key].get("status","SAVED_CANON")),rel,pointer_v),
            ); n+=1
    _baseline(world,"autonomy","actions",data,rel,sha,"SAVED_CANON","prospective_epoch_ready",pointer_v)
    for rule in SOURCE_RULES:
        text,digest=_source(world,root,rule,"autonomy_rule","HARD_RULE")
        _baseline(world,"autonomy_rule",Path(rule).stem,text,rule,digest,"HARD_RULE","active",pointer_v)
    return n

def _import_economy_policy(world: Any, root: Path, pointer_v: int) -> int:
    count=0
    for rel in ECONOMY_FILES:
        p=root/rel
        if not p.exists():
            continue
        text,digest=_source(world,root,rel,"economy_rule","ECONOMY_MODEL_v1")
        _baseline(world,"economy_rule",Path(rel).stem,text,rel,digest,"ECONOMY_MODEL_v1","active",pointer_v); count+=1
    policy={
        "epoch_world_minute": world.now,
        "historical_claim": False,
        "rule": "No market price/stock or route duration exists merely because the lab seed had one.",
        "market": "instantiate only from an explicit price observation, transaction, or separately calibrated deterministic generator",
        "routes": "instantiate only from an explicit saved duration, observed trip, or separately calibrated geography model",
    }
    for system in ("market","routes"):
        world.db.execute(
            "INSERT OR REPLACE INTO cutover_worldgen_policy(system_key,mode,seed_namespace,policy_json,authority,status) VALUES(?,?,?,?,?,?)",
            (system,"prospective_only",f"v07:{system}:{pointer_v}",dumps(policy),"NON_CANON_MECHANICAL_POLICY","awaiting_calibration"),
        )
    return count

def _mechanical_placeholders(world: Any) -> None:
    for system in ("power","skills","relationship_mechanics"):
        world.db.execute(
            "INSERT OR REPLACE INTO mechanical_calibrations(system_key,actor_key,value_json,authority,status,created_at) VALUES(?,?,?,?,?,?)",
            (system,"player","{}","NON_CANON_MECHANICAL","unrated",world.now),
        )

def apply_v07_baseline_rehearsal(world: Any, package: RepoCampaignPackage, repo_root: str | Path) -> dict[str,Any]:
    root=Path(repo_root).resolve()
    report=apply_repo_campaign_rehearsal(world,package)
    if not report.get("rehearsal_ready"):
        return {"v06":report,"baseline_ready":False,"live_cutover_ready":False,"errors":["v06_rehearsal_not_ready"]}

    required=[*SOURCE_JSON,*SOURCE_RULES]
    missing=[rel for rel in required if not (root/rel).exists()]
    if missing:
        return {"v06":report,"baseline_ready":False,"live_cutover_ready":False,"errors":[f"missing_source:{x}" for x in missing]}

    pointer_v=int(package.pointer.get("v") or 0)
    with world.db:
        money=_import_money(world,root,pointer_v)
        relationships=_import_relationships(world,root,pointer_v)
        positions=_import_positions(world,root,package)
        commitments=_import_autonomy(world,root,pointer_v)
        economy_rules=_import_economy_policy(world,root,pointer_v)
        _mechanical_placeholders(world)

        resolutions={
            "named_npc_exact_locations_not_normalized":
                ("historical_integrity","resolved","UNKNOWN/region-only position claims are first-class state, so exact coordinates are not fabricated.",["memory/places.json","memory/actions.json"],None),
            "relationship_history_not_numerically_normalized":
                ("historical_integrity","resolved","Qualitative relationship evidence is imported verbatim; old history is not assigned retrospective scores.",["memory/relationships.json"],"relationship_mechanics_unrated"),
            "autonomous_world_baseline_not_imported":
                ("historical_integrity","resolved","Active tasks, mail, festival/tournament commitments and hard autonomy rules establish the prospective cutover epoch.",["memory/actions.json",*SOURCE_RULES],None),
            "malformed_historical_deltas_not_semantically_normalized":
                ("historical_integrity","resolved_with_degradation","Raw historical bytes/hashes remain preserved; malformed old deltas are not required to invent a current state.",["campaign_archives"],"historical_semantics_degraded"),
            "live_market_baseline_not_imported":
                ("feature","deferred_safe","Historical market values do not exist. Lab values stay purged; prospective initialization policy is recorded.",["ECONOMY_MODEL_v1"],"market_calibration_pending"),
            "live_route_time_model_not_imported":
                ("feature","deferred_safe","Historical route durations do not exist. Lab routes stay purged; prospective initialization policy is recorded.",["cutover_worldgen_policy"],"route_calibration_pending"),
            "player_power_profile_not_authoritatively_mapped":
                ("feature","deferred_safe","No retrospective power numbers are invented.",["mechanical_calibrations"],"player_power_calibration_pending"),
            "player_skill_profile_not_authoritatively_mapped":
                ("feature","deferred_safe","No retrospective skill numbers are invented.",["mechanical_calibrations"],"player_skill_calibration_pending"),
        }
        for code,(cl,st,res,ev,repl) in resolutions.items():
            _set_resolution(world,code,cl,st,res,list(ev),repl)
            world.db.execute("UPDATE migration_blockers SET status=? WHERE code=?",("resolved" if st.startswith("resolved") else "deferred",code))

        fund_uncertain=[k for k,v in money["accounts"].items() if v["certainty"]!="exact_as_of_audit_no_current_claim"]
        if fund_uncertain:
            _set_resolution(world,"separate_project_funds_not_fully_normalized","historical_integrity","partial",
                            "Exact historical balances are preserved but later mentions prevent pretending every account stayed unchanged.",
                            ["memory/money.json"],"project_fund_reconciliation_pending")
            world.db.execute("UPDATE migration_blockers SET status='partial' WHERE code='separate_project_funds_not_fully_normalized'")
        else:
            _set_resolution(world,"separate_project_funds_not_fully_normalized","historical_integrity","resolved",
                            "All separate balances carry forward without later account mentions.",["memory/money.json"])
            world.db.execute("UPDATE migration_blockers SET status='resolved' WHERE code='separate_project_funds_not_fully_normalized'")

        replacements=[
            ("relationship_mechanics_unrated","feature","active"),
            ("market_calibration_pending","feature","active"),
            ("route_calibration_pending","feature","active"),
            ("player_power_calibration_pending","feature","active"),
            ("player_skill_calibration_pending","feature","active"),
        ]
        if fund_uncertain:
            replacements.append(("project_fund_reconciliation_pending","historical_integrity","active"))
        if package.report.get("malformed_historical_delta_versions"):
            replacements.append(("historical_semantics_degraded","accepted_degradation","active"))
        for code,classification,status in replacements:
            world.db.execute(
                "INSERT OR REPLACE INTO migration_blockers(code,detail,status) VALUES(?,?,?)",
                (code,classification.replace("_"," "),status),
            )

        world.db.execute("UPDATE migration_capabilities SET enabled=0,reason='v07_cutover_gate_not_complete'")
        world.db.execute(
            "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
            ("runtime_mode",'"v07_baseline_rehearsal"',"engine:v07"),
        )

    active_integrity=[str(r["code"]) for r in world.db.execute(
        "SELECT code FROM migration_blockers WHERE status IN ('active','partial') AND code IN ('project_fund_reconciliation_pending') ORDER BY code"
    )]
    feature_pending=[str(r["code"]) for r in world.db.execute(
        "SELECT code FROM migration_blockers WHERE status='active' AND code IN "
        "('relationship_mechanics_unrated','market_calibration_pending','route_calibration_pending','player_power_calibration_pending','player_skill_calibration_pending') ORDER BY code"
    )]
    degraded=[str(r["code"]) for r in world.db.execute(
        "SELECT code FROM migration_blockers WHERE status='active' AND code='historical_semantics_degraded'"
    )]
    result={
        "source_version":pointer_v,
        "baseline_ready":not active_integrity,
        "live_cutover_ready":False,
        "historical_integrity_blockers":active_integrity,
        "feature_calibration_pending":feature_pending,
        "accepted_degradation":degraded,
        "funds":money,
        "relationship_evidence_count":relationships,
        "position_claims":positions,
        "autonomous_commitment_count":commitments,
        "economy_rule_count":economy_rules,
        "source_baseline_count":world.db.execute("SELECT COUNT(*) FROM source_baselines").fetchone()[0],
    }
    world.db.execute(
        "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
        ("v07_report",dumps(result),"engine:v07"),
    )
    world.db.commit()
    return result
