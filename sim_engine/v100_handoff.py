from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from v09_runtime import PORTABLE_EXCLUDE

PORTABLE_FORMAT = "TENSURA_ENGINE_RUNTIME"
PORTABLE_SCHEMA_VERSION = 100
ENGINE_VERSION = "1.0"
PORTABLE_EXCLUDE_V100 = set(PORTABLE_EXCLUDE) | {"runtime_journal"}


def _enc(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__sqlite_blob_b64__": base64.b64encode(value).decode("ascii")}
    return value


def _dec(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"__sqlite_blob_b64__"}:
        return base64.b64decode(value["__sqlite_blob_b64__"])
    return value


def _tables(world: Any) -> list[str]:
    rows = world.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(r[0]) for r in rows if str(r[0]) not in PORTABLE_EXCLUDE_V100]


def _rows(world: Any, table: str) -> list[dict[str, Any]]:
    q = '"' + table.replace('"', '""') + '"'
    cols = [str(r[1]) for r in world.db.execute(f"PRAGMA table_info({q})").fetchall()]
    rows = world.db.execute(f"SELECT * FROM {q} ORDER BY rowid").fetchall()
    return [{c: _enc(row[c]) for c in cols} for row in rows]


def _body(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {k: snapshot[k] for k in (
        "format", "schema_version", "engine_version", "source_live_version", "world_minute", "tables"
    )}


def _hash(body: dict[str, Any]) -> str:
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def runtime_state_hash_v100(world: Any, source_live_version: int) -> str:
    body = {
        "format": PORTABLE_FORMAT,
        "schema_version": PORTABLE_SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "source_live_version": int(source_live_version),
        "world_minute": int(world.now),
        "tables": {name: _rows(world, name) for name in _tables(world)},
    }
    return _hash(body)


def export_portable_checkpoint_v100(world: Any, source_live_version: int) -> dict[str, Any]:
    tables = {name: _rows(world, name) for name in _tables(world)}
    snap = {
        "format": PORTABLE_FORMAT,
        "schema_version": PORTABLE_SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "source_live_version": int(source_live_version),
        "world_minute": int(world.now),
        "tables": tables,
    }
    snap["state_hash"] = _hash(_body(snap))
    raw = json.dumps(snap, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    count = sum(len(v) for v in tables.values())
    world.db.execute(
        "INSERT INTO portable_checkpoint_audit(world_minute,source_version,direction,state_hash,table_count,row_count,byte_count,ok,note) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (world.now, int(source_live_version), "export-v100", snap["state_hash"], len(tables), count,
         len(raw.encode("utf-8")), 1, "v1.0 portable runtime export"),
    )
    world.db.commit()
    snap["transport_meta"] = {
        "table_count": len(tables),
        "row_count": count,
        "byte_count": len(raw.encode("utf-8")),
        "excluded_tables": sorted(PORTABLE_EXCLUDE_V100),
    }
    return snap


def import_portable_checkpoint_v100(world: Any, snapshot: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if snapshot.get("format") != PORTABLE_FORMAT:
        errors.append("bad_format")
    if snapshot.get("schema_version") != PORTABLE_SCHEMA_VERSION:
        errors.append("unsupported_schema_version")
    if snapshot.get("engine_version") != ENGINE_VERSION:
        errors.append("engine_version_mismatch")
    expected = str(snapshot.get("state_hash", ""))
    actual = _hash(_body(snapshot)) if not errors else ""
    if expected != actual:
        errors.append("state_hash_mismatch")
    tables = snapshot.get("tables")
    if not isinstance(tables, dict):
        errors.append("tables_not_object")
        tables = {}

    existing = set(_tables(world))
    unknown = sorted(set(tables) - existing)
    if unknown:
        errors.append("unknown_tables:" + ",".join(unknown))
    if errors:
        return {"ok": False, "errors": errors, "expected_hash": expected, "actual_hash": actual}

    world.db.commit()
    world.db.execute("PRAGMA foreign_keys=OFF")
    try:
        for table in existing:
            q = '"' + table.replace('"', '""') + '"'
            world.db.execute(f"DELETE FROM {q}")
        for table in sorted(tables):
            q = '"' + table.replace('"', '""') + '"'
            for row in tables[table]:
                if not isinstance(row, dict):
                    raise ValueError(f"invalid row in {table}")
                cols = list(row)
                if not cols:
                    continue
                col_sql = ",".join('"' + c.replace('"', '""') + '"' for c in cols)
                marks = ",".join("?" for _ in cols)
                world.db.execute(
                    f"INSERT INTO {q}({col_sql}) VALUES({marks})",
                    [_dec(row[c]) for c in cols],
                )
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
    world.db.commit()
    restored_hash = runtime_state_hash_v100(world, int(snapshot["source_live_version"]))
    ok = restored_hash == expected
    world.db.execute(
        "INSERT INTO portable_checkpoint_audit(world_minute,source_version,direction,state_hash,table_count,row_count,byte_count,ok,note) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (world.now, int(snapshot["source_live_version"]), "import-v100", expected,
         int(snapshot.get("transport_meta", {}).get("table_count", len(tables))),
         int(snapshot.get("transport_meta", {}).get("row_count", sum(len(v) for v in tables.values()))),
         int(snapshot.get("transport_meta", {}).get("byte_count", 0)), int(ok),
         "v1.0 roundtrip verified" if ok else "v1.0 roundtrip mismatch"),
    )
    world.db.commit()
    return {
        "ok": ok,
        "errors": [] if ok else ["roundtrip_hash_mismatch"],
        "state_hash": expected,
        "restored_hash": restored_hash,
    }
