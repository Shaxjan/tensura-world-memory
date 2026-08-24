from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100
from v101_repository import load_repository_runtime_v101
from v102_seed import seed_world_v102_migration


def activate_v102(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer_path = root / "runtime/runtime_state.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("engine_version") == "1.0.2":
        return {"ok": True, "already_active": True, "journal_seq": pointer["journal_seq"]}
    if pointer.get("engine_version") != "1.0.1" or pointer.get("mode") != "engine_authoritative":
        raise RuntimeError("v1.0.2 activation requires v1.0.1 authoritative runtime")

    seq = int(pointer["journal_seq"])
    with tempfile.TemporaryDirectory() as td:
        world, loaded_pointer, _ = load_repository_runtime_v101(root, Path(td) / "source.db")
        try:
            if loaded_pointer["head_state_hash"] != pointer["head_state_hash"]:
                raise RuntimeError("pointer changed during activation")
            snapshot = export_portable_checkpoint_v100(world, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != pointer["head_state_hash"]:
                raise RuntimeError("compaction checkpoint does not match authoritative head")
            last_event = None
            if seq > 0:
                last_event = json.loads((root / pointer["journal_dir"] / f"j{seq:06d}.json").read_text(encoding="utf-8"))
        finally:
            world.close()

        v102 = seed_world_v102_migration(Path(td) / "verify.db")
        try:
            verified = import_portable_checkpoint_v100(v102, snapshot)
            if not verified.get("ok") or verified.get("restored_hash") != pointer["head_state_hash"]:
                raise RuntimeError("v1.0.2 checkpoint roundtrip failed")
            session_state = v102.build_session_state_v102(
                journal_seq=seq, head_state_hash=pointer["head_state_hash"], last_event=last_event
            )
        finally:
            v102.close()

    checkpoint_rel = f"runtime/checkpoints/v102_base_j{seq:06d}.json"
    checkpoint_path = root / checkpoint_rel
    if checkpoint_path.exists():
        raise RuntimeError("v1.0.2 checkpoint path already exists")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (root / "runtime/session_state.json").write_text(
        json.dumps(session_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pointer["engine_version"] = "1.0.2"
    pointer["base_checkpoint"] = checkpoint_rel
    pointer["base_state_hash"] = pointer["head_state_hash"]
    pointer["journal_base_seq"] = seq
    pointer["session_state"] = "runtime/session_state.json"
    pointer["write_protocol"]["session_fast_path"] = True
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "already_active": False,
        "journal_seq": seq,
        "checkpoint": checkpoint_rel,
        "head_state_hash": pointer["head_state_hash"],
        "session_state": "runtime/session_state.json",
        "hud": session_state["hud"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = activate_v102(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
