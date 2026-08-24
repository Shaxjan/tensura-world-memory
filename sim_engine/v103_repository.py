from __future__ import annotations

import json
from pathlib import Path

from v100_handoff import import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_repository import POINTER_FORMAT, POINTER_SCHEMA_VERSION, journal_filename
from v103_seed import seed_world_v103_migration


def validate_runtime_pointer_v103(pointer: dict) -> None:
    if pointer.get("format") != POINTER_FORMAT:
        raise ValueError("bad runtime pointer format")
    if pointer.get("schema_version") != POINTER_SCHEMA_VERSION:
        raise ValueError("unsupported runtime pointer schema")
    if pointer.get("engine_version") != "1.0.3":
        raise ValueError("runtime engine version mismatch")
    if pointer.get("mode") != "engine_authoritative":
        raise ValueError("runtime is not authoritative")
    for key in ("base_checkpoint", "base_state_hash", "journal_dir", "head_state_hash"):
        if not isinstance(pointer.get(key), str) or not pointer[key]:
            raise ValueError(f"runtime pointer missing {key}")
    base, head = pointer.get("journal_base_seq"), pointer.get("journal_seq")
    if not isinstance(base, int) or not isinstance(head, int) or base < 0 or head < base:
        raise ValueError("invalid journal sequence range")


def load_repository_runtime_v103(repo_root: str | Path, db_path: str | Path):
    root = Path(repo_root).resolve()
    pointer = json.loads((root / "runtime/runtime_state.json").read_text(encoding="utf-8"))
    validate_runtime_pointer_v103(pointer)
    checkpoint = json.loads((root / pointer["base_checkpoint"]).read_text(encoding="utf-8"))
    world = seed_world_v103_migration(db_path)
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
