from __future__ import annotations

import json
from pathlib import Path

from v100_handoff import import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_repository import journal_filename
from v112_repository import validate_runtime_pointer_v112
from v113_seed import seed_world_v113_migration


def load_repository_runtime_v113_candidate(repo_root: str | Path, db_path: str | Path):
    """Load current v1.0.12 authoritative repository state into a v1.0.13 candidate DB.

    No pointer/runtime files are changed. The candidate uses the same production
    schema, imports the current base checkpoint, replays the current immutable
    journal, and must reproduce the exact v1.0.12 head hash before any v1.0.13
    candidate event is allowed.
    """
    root = Path(repo_root).resolve()
    pointer = json.loads((root / "runtime/runtime_state.json").read_text(encoding="utf-8"))
    validate_runtime_pointer_v112(pointer)
    checkpoint = json.loads((root / pointer["base_checkpoint"]).read_text(encoding="utf-8"))
    world = seed_world_v113_migration(db_path)
    imported = import_portable_checkpoint_v100(world, checkpoint)
    if not imported.get("ok"):
        world.close()
        raise RuntimeError("v1.0.13 candidate checkpoint import failed:" + ",".join(imported.get("errors", [])))
    if imported.get("state_hash") != pointer["base_state_hash"]:
        world.close()
        raise RuntimeError("v1.0.13 candidate base hash mismatch")

    entries = []
    for seq in range(int(pointer["journal_base_seq"]) + 1, int(pointer["journal_seq"]) + 1):
        path = root / pointer["journal_dir"] / journal_filename(seq)
        if not path.exists():
            world.close()
            raise RuntimeError(f"v1.0.13 candidate source journal gap:{seq}")
        entries.append(json.loads(path.read_text(encoding="utf-8")))
    replay = world.replay_runtime_entries(entries)
    if not replay.get("ok"):
        world.close()
        raise RuntimeError("v1.0.13 candidate source journal replay failed:" + str(replay))
    head = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
    if head != pointer["head_state_hash"]:
        world.close()
        raise RuntimeError("v1.0.13 candidate pre-activation head hash mismatch")
    return world, pointer, {"checkpoint": imported, "replay": replay, "head_hash": head}
