from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from v03_engine import dumps, loads
from v06_migration import RepoCampaignPackage
from v08_money import apply_v08_money_reconciliation


PORTABLE_FORMAT = "TENSURA_ENGINE_RUNTIME"
PORTABLE_SCHEMA_VERSION = 9
PORTABLE_EXCLUDE = {
    "campaign_archives",          # reproducible from repository source files; too large for ordinary handoff
    "portable_checkpoint_audit", # audit of transport itself must not make the transported hash self-referential
}

MECHANIC_POLICIES = {
    "player_power": {
        "mode": "guarded_unknown",
        "command": "strike",
        "reason": "No authoritative Arlequino power profile exists in migrated history; do not invent a threat rank or combat stats.",
    },
    "player_skills": {
        "mode": "guarded_unknown",
        "command": "attempt",
        "reason": "No authoritative numeric skill profile exists; missing skills are not equivalent to bonus=0.",
    },
    "relationship_mechanics": {
        "mode": "qualitative_until_prospective_event",
        "command": "social",
        "reason": "Imported relationship history remains qualitative. Numeric bonds may begin prospectively, never as retrospective canon.",
    },
    "markets": {
        "mode": "observation_first",
        "command": "buy",
        "reason": "Economy rules are authoritative but current stock/prices are not. Create rows only from observed transactions or explicit prospective calibration.",
    },
    "routes": {
        "mode": "observation_first",
        "command": "travel",
        "reason": "Lab route durations are non-authoritative. Inter-region travel remains gated until an observed or explicitly calibrated route exists.",
    },
}

CUTOVER_BLOCKERS = {
    "scene_action_bridge_not_implemented": (
        "runtime",
        "The current deterministic parser covers a narrow command set and cannot yet represent ordinary live-scene actions/dialogue/state changes without bypassing engine authority.",
    ),
    "autonomy_commitment_execution_not_wired": (
        "runtime",
        "Imported autonomous commitments are preserved but are not yet connected to a prospective scheduler/resolution API. Enabling time advance now could freeze important off-screen work.",
    ),
}

OLD_CALIBRATION_BLOCKERS = {
    "player_power_profile_not_authoritatively_mapped",
    "player_skill_profile_not_authoritatively_mapped",
    "relationship_history_not_numerically_normalized",
    "live_market_baseline_not_imported",
    "live_route_time_model_not_imported",
    "player_power_calibration_pending",
    "player_skill_calibration_pending",
    "relationship_mechanics_unrated",
    "market_calibration_pending",
    "route_calibration_pending",
}


def _encode_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__sqlite_blob_b64__": base64.b64encode(value).decode("ascii")}
    return value


def _decode_value(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"__sqlite_blob_b64__"}:
        return base64.b64decode(value["__sqlite_blob_b64__"])
    return value


def _portable_tables(world: Any) -> list[str]:
    rows = world.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(r[0]) for r in rows if str(r[0]) not in PORTABLE_EXCLUDE]


def _table_rows(world: Any, table: str) -> list[dict[str, Any]]:
    quoted = '"' + table.replace('"', '""') + '"'
    cols = [str(r[1]) for r in world.db.execute(f"PRAGMA table_info({quoted})").fetchall()]
    rows = world.db.execute(f"SELECT * FROM {quoted} ORDER BY rowid").fetchall()
    return [{c: _encode_value(row[c]) for c in cols} for row in rows]


def _canonical_body(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": snapshot["format"],
        "schema_version": snapshot["schema_version"],
        "engine_version": snapshot["engine_version"],
        "source_live_version": snapshot["source_live_version"],
        "world_minute": snapshot["world_minute"],
        "tables": snapshot["tables"],
    }


def _hash_body(body: dict[str, Any]) -> str:
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def export_portable_checkpoint(world: Any, source_live_version: int) -> dict[str, Any]:
    tables = {name: _table_rows(world, name) for name in _portable_tables(world)}
    snapshot = {
        "format": PORTABLE_FORMAT,
        "schema_version": PORTABLE_SCHEMA_VERSION,
        "engine_version": "0.9",
        "source_live_version": int(source_live_version),
        "world_minute": int(world.now),
        "tables": tables,
    }
    snapshot["state_hash"] = _hash_body(_canonical_body(snapshot))
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    row_count = sum(len(v) for v in tables.values())
    world.db.execute(
        "INSERT INTO portable_checkpoint_audit(world_minute,source_version,direction,state_hash,table_count,row_count,byte_count,ok,note) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (world.now, int(source_live_version), "export", snapshot["state_hash"], len(tables), row_count,
         len(raw.encode("utf-8")), 1, "portable runtime export"),
    )
    world.db.commit()
    snapshot["transport_meta"] = {
        "table_count": len(tables),
        "row_count": row_count,
        "byte_count": len(raw.encode("utf-8")),
        "excluded_tables": sorted(PORTABLE_EXCLUDE),
    }
    return snapshot


def import_portable_checkpoint(world: Any, snapshot: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if snapshot.get("format") != PORTABLE_FORMAT:
        errors.append("bad_format")
    if snapshot.get("schema_version") != PORTABLE_SCHEMA_VERSION:
        errors.append("unsupported_schema_version")
    if snapshot.get("engine_version") != "0.9":
        errors.append("engine_version_mismatch")
    expected = str(snapshot.get("state_hash", ""))
    actual = _hash_body(_canonical_body(snapshot)) if not errors else ""
    if expected != actual:
        errors.append("state_hash_mismatch")
    tables = snapshot.get("tables")
    if not isinstance(tables, dict):
        errors.append("tables_not_object")
        tables = {}

    existing = set(_portable_tables(world))
    unknown = sorted(set(tables) - existing)
    if unknown:
        errors.append("unknown_tables:" + ",".join(unknown))
    if errors:
        return {"ok": False, "errors": errors, "expected_hash": expected, "actual_hash": actual}

    world.db.commit()
    world.db.execute("PRAGMA foreign_keys=OFF")
    try:
        for table in existing:
            quoted = '"' + table.replace('"', '""') + '"'
            world.db.execute(f"DELETE FROM {quoted}")
        for table in sorted(tables):
            quoted = '"' + table.replace('"', '""') + '"'
            for row in tables[table]:
                if not isinstance(row, dict):
                    raise ValueError(f"invalid row in {table}")
                cols = list(row)
                if not cols:
                    continue
                col_sql = ",".join('"' + c.replace('"', '""') + '"' for c in cols)
                q = ",".join("?" for _ in cols)
                vals = [_decode_value(row[c]) for c in cols]
                world.db.execute(f"INSERT INTO {quoted}({col_sql}) VALUES({q})", vals)
        world.db.commit()
    except Exception:
        world.db.rollback()
        world.db.execute("PRAGMA foreign_keys=ON")
        raise
    world.db.execute("PRAGMA foreign_keys=ON")
    fk = [tuple(r) for r in world.db.execute("PRAGMA foreign_key_check").fetchall()]
    if fk:
        return {"ok": False, "errors": ["foreign_key_check_failed"], "foreign_key_errors": fk}

    world._set_now(int(snapshot["world_minute"]))
    # _set_now may rewrite the same clock value in meta; this must remain hash-stable.
    world.db.commit()
    restored = export_portable_checkpoint(world, int(snapshot["source_live_version"]))
    ok = restored["state_hash"] == expected
    world.db.execute(
        "INSERT INTO portable_checkpoint_audit(world_minute,source_version,direction,state_hash,table_count,row_count,byte_count,ok,note) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (world.now, int(snapshot["source_live_version"]), "import", expected,
         int(snapshot.get("transport_meta", {}).get("table_count", len(tables))),
         int(snapshot.get("transport_meta", {}).get("row_count", sum(len(v) for v in tables.values()))),
         int(snapshot.get("transport_meta", {}).get("byte_count", 0)), int(ok),
         "roundtrip hash verified" if ok else "roundtrip hash mismatch"),
    )
    world.db.commit()
    return {"ok": ok, "errors": [] if ok else ["roundtrip_hash_mismatch"], "state_hash": expected,
            "restored_hash": restored["state_hash"]}


def install_guarded_mechanics_policy(world: Any) -> None:
    with world.db:
        # The five v0.7/v0.8 calibration items are resolved by an explicit safe policy,
        # not by fabricating numeric values.
        for code in OLD_CALIBRATION_BLOCKERS:
            world.db.execute(
                "INSERT OR REPLACE INTO migration_blockers(code,detail,status) VALUES(?,?,?)",
                (code, "resolved by guarded prospective mechanics policy", "resolved"),
            )
        for feature, spec in MECHANIC_POLICIES.items():
            world.db.execute(
                "INSERT OR REPLACE INTO mechanic_feature_policy(feature,mode,authority,status,command,reason,activated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (feature, spec["mode"], "NON_CANON_MECHANICAL", "guarded_deferred", spec["command"], spec["reason"], world.now),
            )
        # Keep unsupported command families hard-disabled. A disabled optional feature is safer than a guessed model.
        command_reasons = {
            "travel": "route observation/calibration required",
            "buy": "market observation/calibration required",
            "attempt": "relevant player skill requires explicit prospective calibration",
            "strike": "player combat profile requires explicit prospective calibration",
            "treat": "relevant treatment skill/power requires explicit prospective calibration",
            "social": "numeric relationship/skill mechanics are not initialized retrospectively",
            "wait": "autonomous commitment execution is not wired yet",
            "attend": "live appointments are not normalized into executable runtime appointments",
        }
        for command, reason in command_reasons.items():
            world.db.execute(
                "INSERT OR REPLACE INTO migration_capabilities(command,enabled,reason) VALUES(?,?,?)",
                (command, 0, "v09_guarded:" + reason),
            )
        for code, (klass, detail) in CUTOVER_BLOCKERS.items():
            world.db.execute(
                "INSERT OR REPLACE INTO cutover_gate(gate_code,status,classification,detail,evidence_json,updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (code, "active", klass, detail, "[]", world.now),
            )
        world.db.execute(
            "INSERT OR REPLACE INTO cutover_gate(gate_code,status,classification,detail,evidence_json,updated_at) "
            "VALUES(?,?,?,?,?,?)",
            ("portable_runtime_bridge", "pending_shadow", "runtime",
             "Portable SQLite-to-JSON handoff exists but must pass roundtrip against current LIVE state.", "[]", world.now),
        )
        world.db.execute(
            "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
            ("runtime_mode", '"v09_guarded_shadow_rehearsal"', "engine:v09"),
        )


def mark_portable_bridge_verified(world: Any, state_hash: str) -> None:
    with world.db:
        world.db.execute(
            "UPDATE cutover_gate SET status='resolved',detail=?,evidence_json=?,updated_at=? WHERE gate_code='portable_runtime_bridge'",
            ("Portable checkpoint exported and restored with identical canonical state hash.", dumps([state_hash]), world.now),
        )


def apply_v09_guarded_cutover(world: Any, package: RepoCampaignPackage, repo_root: str | Path) -> dict[str, Any]:
    v08 = apply_v08_money_reconciliation(world, package, repo_root)
    if not v08.get("baseline_ready") or v08.get("errors"):
        return {
            "source_version": package.pointer.get("v"),
            "baseline_ready": False,
            "live_cutover_ready": False,
            "errors": ["v08_baseline_not_ready", *v08.get("errors", [])],
        }
    install_guarded_mechanics_policy(world)
    active = [str(r[0]) for r in world.db.execute(
        "SELECT gate_code FROM cutover_gate WHERE status!='resolved' ORDER BY gate_code"
    ).fetchall()]
    return {
        "source_version": int(package.pointer.get("v") or 0),
        "baseline_ready": True,
        "historical_integrity_blockers": [],
        "feature_calibration_pending": [],
        "deferred_mechanics": sorted(MECHANIC_POLICIES),
        "cutover_blockers": active,
        "live_cutover_ready": False,
        "errors": [],
    }
