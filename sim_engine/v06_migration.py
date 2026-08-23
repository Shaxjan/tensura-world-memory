from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from v03_engine import dumps

TIME_RE = re.compile(r"T\+(\d+)\s*~?\s*(\d{1,2}):(\d{2})")
MONEY_RE = re.compile(r"^\s*(\d+)g\s*(\d+)s\s*(\d+)c\s*$", re.IGNORECASE)
DELTA_RE = re.compile(r"live_v(\d+)")

REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "blumund": ("блюмунд", "blumund"),
    "dwargon": ("дваргон", "dwargon"),
    "eurazania": ("эуразан", "eurazania capital", "capital of eurazania"),
    "jura_edge": ("край великого леса джура", "jura edge"),
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_world_time(value: Any) -> int | None:
    if isinstance(value, int) and value >= 0:
        return value
    if not isinstance(value, str):
        return None
    m = TIME_RE.search(value)
    if not m:
        return None
    day, hour, minute = map(int, m.groups())
    if hour > 23 or minute > 59:
        return None
    return day * 1440 + hour * 60 + minute


def parse_money(value: Any) -> int | None:
    if isinstance(value, int):
        return value if value >= 0 else None
    if not isinstance(value, str) or "UNKNOWN" in value.upper():
        return None
    m = MONEY_RE.fullmatch(value)
    if not m:
        return None
    g, s, c = map(int, m.groups())
    if s >= 100 or c >= 100:
        return None
    return g * 10000 + s * 100 + c


def strict_region_from_text(location: Any) -> tuple[str | None, list[str]]:
    if not isinstance(location, str):
        return None, []
    low = location.casefold()
    hits = []
    for region_id, aliases in REGION_ALIASES.items():
        if any(alias in low for alias in aliases):
            hits.append(region_id)
    hits = sorted(set(hits))
    return (hits[0], hits) if len(hits) == 1 else (None, hits)


def collect_unknown_paths(value: Any, prefix: str = "$") -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            out.extend(collect_unknown_paths(v, f"{prefix}.{k}"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out.extend(collect_unknown_paths(v, f"{prefix}[{i}]"))
    elif isinstance(value, str) and "UNKNOWN" in value.upper():
        out.append(prefix)
    return out


def _version_from_path(path: Path) -> int | None:
    for part in path.parts:
        m = DELTA_RE.fullmatch(part)
        if m:
            return int(m.group(1))
    return None


@dataclass
class SourceDocument:
    path: str
    text: str
    data: Any
    version: int | None
    parse_error: str | None = None

    @property
    def sha256(self) -> str:
        return sha256_text(self.text)


@dataclass
class RepoCampaignPackage:
    repo_root: Path
    pointer: dict[str, Any]
    pointer_doc: SourceDocument
    base_doc: SourceDocument | None
    deltas: list[SourceDocument]
    latest_delta: SourceDocument | None
    report: dict[str, Any]
    snapshot: dict[str, Any]

    @property
    def source_documents(self) -> list[SourceDocument]:
        docs = [self.pointer_doc]
        if self.base_doc is not None:
            docs.append(self.base_doc)
        docs.extend(self.deltas)
        return docs


def _read_json_doc(root: Path, rel: str, version: int | None = None, *, tolerate_parse: bool = False) -> SourceDocument:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        return SourceDocument(rel, text, data, version, None)
    except Exception as exc:
        if not tolerate_parse:
            raise
        return SourceDocument(rel, text, None, version, str(exc))


def collect_repo_campaign(repo_root: str | Path) -> RepoCampaignPackage:
    root = Path(repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []

    pointer_doc = _read_json_doc(root, "live_state.json")
    if not isinstance(pointer_doc.data, dict):
        raise ValueError("live_state.json must be a JSON object")
    pointer = dict(pointer_doc.data)
    pointer_v = pointer.get("v")
    if not isinstance(pointer_v, int):
        errors.append("live_state.v must be integer")
        pointer_v = None

    base_doc = None
    base_path = root / "world_save.json"
    if base_path.exists():
        try:
            base_doc = _read_json_doc(root, "world_save.json")
        except Exception as exc:
            errors.append(f"world_save parse failed:{exc}")

    deltas: list[SourceDocument] = []
    seen_versions: set[int] = set()
    duplicate_versions: list[int] = []
    malformed_delta_versions: list[int] = []
    for path in sorted(root.glob("live_v*/delta.json"), key=lambda p: (_version_from_path(p) or -1, str(p))):
        v = _version_from_path(path)
        if v is None:
            continue
        rel = path.relative_to(root).as_posix()
        doc = _read_json_doc(root, rel, v, tolerate_parse=True)
        if doc.parse_error:
            malformed_delta_versions.append(v)
            warnings.append(f"malformed historical delta archived raw:{rel}:{doc.parse_error}")
        if v in seen_versions:
            duplicate_versions.append(v)
        seen_versions.add(v)
        if isinstance(doc.data, dict) and isinstance(doc.data.get("v"), int) and doc.data["v"] != v:
            errors.append(f"delta version mismatch:{rel}:{doc.data['v']}!={v}")
        deltas.append(doc)
    if duplicate_versions:
        errors.append("duplicate delta versions:" + ",".join(map(str, sorted(set(duplicate_versions)))))

    expected_delta = pointer.get("delta")
    expected_rel = f"{expected_delta}/delta.json" if isinstance(expected_delta, str) else None
    latest_delta = None
    if expected_rel:
        latest_delta = next((d for d in deltas if d.path == expected_rel), None)
        if latest_delta is None:
            errors.append(f"pointer delta missing:{expected_rel}")
    else:
        errors.append("live_state.delta missing")

    max_v = max((d.version or -1 for d in deltas), default=-1)
    if pointer_v is not None and max_v > pointer_v:
        warnings.append(f"unpointed_future_delta:max={max_v}:pointer={pointer_v}")
    if latest_delta is not None and pointer_v is not None and latest_delta.version != pointer_v:
        errors.append(f"pointer version mismatch:{pointer_v}!={latest_delta.version}")
    if latest_delta is not None and latest_delta.parse_error:
        errors.append(f"pointed delta is malformed:{latest_delta.path}:{latest_delta.parse_error}")

    def latest_top_value(key: str) -> tuple[Any, str | None]:
        for doc in reversed(deltas):
            if doc.version is not None and pointer_v is not None and doc.version > pointer_v:
                continue
            if isinstance(doc.data, dict) and key in doc.data:
                return doc.data[key], doc.path
        return None, None

    time_text, time_source = latest_top_value("time")
    location_text, location_source = latest_top_value("location")
    cash_text, cash_source = latest_top_value("personal_cash")
    world_minute = parse_world_time(time_text)
    player_cash = parse_money(cash_text)
    region_id, region_hits = strict_region_from_text(location_text)

    if world_minute is None:
        blockers.append("current_world_time_not_exact")
    if player_cash is None:
        blockers.append("current_personal_cash_not_exact")
    if region_id is None:
        blockers.append("current_region_not_unambiguous")
        if region_hits:
            warnings.append("location_mentions_multiple_regions:" + ",".join(region_hits))

    current_scene, scene_source = latest_top_value("scene")
    rules, rules_source = latest_top_value("hard_rules_reaffirmed")
    if current_scene is None:
        warnings.append("latest scene not found in deltas")
    if rules is None:
        warnings.append("latest hard rules not found in deltas")

    unknowns = collect_unknown_paths(latest_delta.data if latest_delta else {})
    semantic_blockers = [
        "player_power_profile_not_authoritatively_mapped",
        "player_skill_profile_not_authoritatively_mapped",
        "named_npc_exact_locations_not_normalized",
        "relationship_history_not_numerically_normalized",
        "separate_project_funds_not_fully_normalized",
        "live_market_baseline_not_imported",
        "live_route_time_model_not_imported",
        "autonomous_world_baseline_not_imported",
    ]
    if malformed_delta_versions:
        semantic_blockers.append("malformed_historical_deltas_not_semantically_normalized")

    base_version = None
    if base_doc and isinstance(base_doc.data, dict):
        bv = base_doc.data.get("save_version")
        if isinstance(bv, int):
            base_version = bv
            if pointer_v is not None and bv > pointer_v:
                errors.append(f"archive base newer than live pointer:{bv}>{pointer_v}")

    source_paths = [pointer_doc.path] + ([base_doc.path] if base_doc else []) + [d.path for d in deltas]
    source_hash = hashlib.sha256("\n".join(
        f"{doc.path}:{doc.sha256}" for doc in ([pointer_doc] + ([base_doc] if base_doc else []) + deltas)
    ).encode("utf-8")).hexdigest()

    rehearsal_ready = not errors and not blockers and latest_delta is not None
    snapshot = {
        "save_version": pointer_v,
        "world_minute": world_minute,
        "player": {
            "region_id": region_id,
            "personal_cash": cash_text,
            "cash_copper": player_cash,
            "location_text": location_text,
            "status": "scene_pending",
        },
        "source": {
            "live_state": pointer_doc.path,
            "latest_delta": latest_delta.path if latest_delta else None,
            "time_source": time_source,
            "location_source": location_source,
            "cash_source": cash_source,
            "scene_source": scene_source,
            "rules_source": rules_source,
        },
        "current_scene": current_scene,
        "hard_rules_reaffirmed": rules,
        "preserved_unknown_paths": unknowns,
    }
    report = {
        "rehearsal_ready": rehearsal_ready,
        "live_cutover_ready": False,
        "source_version": pointer_v,
        "base_version": base_version,
        "source_document_count": len(source_paths),
        "delta_count": len(deltas),
        "source_hash": source_hash,
        "errors": errors,
        "warnings": warnings,
        "core_blockers": blockers,
        "semantic_blockers": semantic_blockers,
        "preserved_unknown_paths": unknowns,
        "malformed_historical_delta_versions": sorted(malformed_delta_versions),
        "normalized_current": {
            "world_time_text": time_text,
            "world_minute": world_minute,
            "location_text": location_text,
            "region_id": region_id,
            "personal_cash_text": cash_text,
            "personal_cash_copper": player_cash,
        },
        "source_paths": source_paths,
    }
    return RepoCampaignPackage(root, pointer, pointer_doc, base_doc, deltas, latest_delta, report, snapshot)


def _audit_field(world: Any, field_key: str, status: str, source_path: str | None,
                 value: Any, target: str | None, note: str | None = None) -> None:
    world.db.execute(
        "INSERT INTO migration_field_audit(field_key,status,source_path,source_value_json,engine_target,note) VALUES(?,?,?,?,?,?)",
        (field_key, status, source_path, dumps(value), target, note),
    )


def apply_repo_campaign_rehearsal(world: Any, package: RepoCampaignPackage) -> dict[str, Any]:
    report = json.loads(json.dumps(package.report, ensure_ascii=False))
    if not report["rehearsal_ready"]:
        cur = world.db.execute(
            "INSERT INTO migration_rehearsal_runs(world_minute,source_version,rehearsal_ready,live_cutover_ready,report_json) VALUES(?,?,?,?,?)",
            (world.now, package.pointer.get("v"), 0, 0, dumps(report)),
        )
        world.db.commit()
        report["migration_run_id"] = int(cur.lastrowid)
        return report

    snap = package.snapshot
    player = snap["player"]
    with world.db:
        world._set_now(int(snap["world_minute"]))
        world.db.execute(
            "UPDATE actors SET region_id=?,cash_copper=?,status=? WHERE id='player'",
            (str(player["region_id"]), int(player["cash_copper"]), str(player["status"])),
        )

        for doc in package.source_documents:
            world.db.execute(
                "INSERT INTO campaign_archives(source_path,source_version,sha256,byte_count,payload_text,archived_at) VALUES(?,?,?,?,?,?)",
                (doc.path, str(doc.version) if doc.version is not None else None, doc.sha256,
                 len(doc.text.encode("utf-8")), doc.text, world.now),
            )

        metadata = {
            "source_save_version": (snap["save_version"], "live_state.json"),
            "current_location_text": (player["location_text"], snap["source"]["location_source"] or "UNKNOWN"),
            "current_scene": (snap.get("current_scene"), snap["source"].get("scene_source") or "UNKNOWN"),
            "hard_rules_reaffirmed": (snap.get("hard_rules_reaffirmed"), snap["source"].get("rules_source") or "UNKNOWN"),
            "preserved_unknown_paths": (snap.get("preserved_unknown_paths", []), snap["source"]["latest_delta"] or "UNKNOWN"),
            "source_hash": (report["source_hash"], "derived:all_sources"),
        }
        for key, (value, source) in metadata.items():
            world.db.execute(
                "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
                (key, dumps(value), source),
            )

        _audit_field(world, "save_version", "mapped_exact", "live_state.json", snap["save_version"], "campaign_metadata.source_save_version")
        _audit_field(world, "world_time", "mapped_exact", snap["source"]["time_source"], snap["world_minute"], "meta.world_minute")
        _audit_field(world, "player.location_text", "archived_exact", snap["source"]["location_source"], player["location_text"], "campaign_metadata.current_location_text")
        _audit_field(world, "player.region", "mapped_exact", snap["source"]["location_source"], player["region_id"], "actors.region_id", "Mapped only because one explicit region alias occurs in current location text.")
        _audit_field(world, "player.personal_cash", "mapped_exact", snap["source"]["cash_source"], player["cash_copper"], "actors.cash_copper")
        _audit_field(world, "current_scene", "archived_exact", snap["source"].get("scene_source"), snap.get("current_scene"), "campaign_metadata.current_scene")
        _audit_field(world, "unknowns", "preserved_unknown", snap["source"].get("latest_delta"), snap.get("preserved_unknown_paths", []), "campaign_archives")

        for code in report["semantic_blockers"]:
            world.db.execute(
                "INSERT OR REPLACE INTO migration_blockers(code,detail,status) VALUES(?,?, 'active')",
                (code, code.replace("_", " ")),
            )

        enabled = {
            "travel": (0, "live route times/topology are not authoritatively migrated"),
            "buy": (0, "live market stock/prices are not authoritatively migrated"),
            "wait": (0, "autonomous world baseline is not authoritatively migrated"),
            "attempt": (0, "player skill profile not authoritatively migrated"),
            "strike": (0, "player power/skill profile not authoritatively migrated"),
            "treat": (0, "player treatment skills/power not authoritatively migrated"),
            "social": (0, "relationship/skill values not authoritatively migrated"),
            "attend": (0, "live appointments not yet normalized into engine appointments"),
        }
        for command, (flag, reason) in enabled.items():
            world.db.execute(
                "INSERT OR REPLACE INTO migration_capabilities(command,enabled,reason) VALUES(?,?,?)",
                (command, flag, reason),
            )

        latest = package.latest_delta.data if package.latest_delta and isinstance(package.latest_delta.data, dict) else {}
        fam = latest.get("family_budget")
        scene = latest.get("scene") if isinstance(latest.get("scene"), dict) else {}
        decision = scene.get("rena_family_budget_decision") if isinstance(scene, dict) and isinstance(scene.get("rena_family_budget_decision"), dict) else {}
        current_balance = decision.get("current_balance")
        if isinstance(fam, str) and fam.strip().startswith("0") and isinstance(current_balance, str) and current_balance.strip().startswith("0"):
            world.db.execute(
                "INSERT OR REPLACE INTO fund_accounts(id,label,balance_copper,certainty,source_path,note) VALUES(?,?,?,?,?,?)",
                ("family_purse", "Family purse", 0, "exact_zero", package.latest_delta.path,
                 "Only the explicit current zero is normalized; future contribution framework remains archived as authored."),
            )
            _audit_field(world, "family_budget.current_balance", "mapped_exact", package.latest_delta.path, 0, "fund_accounts.family_purse")

        archive_count = world.db.execute("SELECT COUNT(*) FROM campaign_archives").fetchone()[0]
        report["archived_document_count"] = int(archive_count)
        report["source_archive_complete"] = int(archive_count) == len(package.source_documents)
        report["live_cutover_ready"] = False
        cur = world.db.execute(
            "INSERT INTO migration_rehearsal_runs(world_minute,source_version,rehearsal_ready,live_cutover_ready,report_json) VALUES(?,?,?,?,?)",
            (world.now, snap["save_version"], int(report["rehearsal_ready"] and report["source_archive_complete"]), 0, dumps(report)),
        )
        report["migration_run_id"] = int(cur.lastrowid)
    return report
