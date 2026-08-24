from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from v100_handoff import import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_seed import seed_world_v100_migration

POINTER_FORMAT = "TENSURA_RUNTIME_POINTER"
POINTER_SCHEMA_VERSION = 1


def journal_filename(seq: int) -> str:
    return f"j{int(seq):06d}.json"


def build_runtime_pointer(*, source_live_version: int, base_checkpoint: str, base_state_hash: str,
                          legacy_pointer: dict[str, Any], legacy_pointer_blob_sha: str,
                          mode: str = "prepared", journal_base_seq: int = 0,
                          journal_seq: int = 0, head_state_hash: str | None = None) -> dict[str, Any]:
    if mode not in {"prepared", "engine_authoritative", "rollback"}:
        raise ValueError("invalid runtime pointer mode")
    return {
        "format": POINTER_FORMAT,
        "schema_version": POINTER_SCHEMA_VERSION,
        "engine_version": "1.0",
        "mode": mode,
        "source_live_version": int(source_live_version),
        "base_checkpoint": str(base_checkpoint),
        "base_state_hash": str(base_state_hash),
        "journal_dir": "runtime/journal",
        "journal_base_seq": int(journal_base_seq),
        "journal_seq": int(journal_seq),
        "head_state_hash": str(head_state_hash or base_state_hash),
        "legacy_rollback": {
            "path": "live_state.json",
            "version": int(legacy_pointer.get("v") or source_live_version),
            "delta": legacy_pointer.get("delta"),
            "pointer": legacy_pointer,
            "blob_sha": str(legacy_pointer_blob_sha),
        },
        "write_protocol": {
            "event_file_first": True,
            "pointer_second": True,
            "immutable_journal": True,
            "checkpoint_every": 25,
        },
    }


def validate_runtime_pointer(pointer: dict[str, Any]) -> None:
    if pointer.get("format") != POINTER_FORMAT:
        raise ValueError("bad runtime pointer format")
    if pointer.get("schema_version") != POINTER_SCHEMA_VERSION:
        raise ValueError("unsupported runtime pointer schema")
    if pointer.get("engine_version") != "1.0":
        raise ValueError("runtime engine version mismatch")
    for key in ("base_checkpoint", "base_state_hash", "journal_dir", "head_state_hash"):
        if not isinstance(pointer.get(key), str) or not pointer[key]:
            raise ValueError(f"runtime pointer missing {key}")
    base = pointer.get("journal_base_seq")
    head = pointer.get("journal_seq")
    if not isinstance(base, int) or not isinstance(head, int) or base < 0 or head < base:
        raise ValueError("invalid journal sequence range")


def load_repository_runtime(repo_root: str | Path, db_path: str | Path):
    root = Path(repo_root).resolve()
    pointer = json.loads((root / "runtime/runtime_state.json").read_text(encoding="utf-8"))
    validate_runtime_pointer(pointer)
    checkpoint = json.loads((root / pointer["base_checkpoint"]).read_text(encoding="utf-8"))
    world = seed_world_v100_migration(db_path)
    imported = import_portable_checkpoint_v100(world, checkpoint)
    if not imported.get("ok"):
        world.close()
        raise RuntimeError("runtime checkpoint import failed:" + ",".join(imported.get("errors", [])))
    if imported.get("state_hash") != pointer["base_state_hash"]:
        world.close()
        raise RuntimeError("runtime base hash mismatch")

    entries = []
    for seq in range(int(pointer["journal_base_seq"]) + 1, int(pointer["journal_seq"]) + 1):
        path = root / pointer["journal_dir"] / journal_filename(seq)
        if not path.exists():
            world.close()
            raise RuntimeError(f"runtime journal gap:{seq}")
        entries.append(json.loads(path.read_text(encoding="utf-8")))
    replay = world.replay_runtime_entries(entries)
    if not replay.get("ok"):
        world.close()
        raise RuntimeError("runtime journal replay failed:" + str(replay))
    head = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
    if head != pointer["head_state_hash"]:
        world.close()
        raise RuntimeError("runtime head hash mismatch")
    return world, pointer, {"checkpoint": imported, "replay": replay, "head_hash": head}
