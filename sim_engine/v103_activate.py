from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v102_repository import load_repository_runtime_v102
from v103_seed import seed_world_v103_migration


def _latest_borga_pending(world):
    return world.db.execute(
        "SELECT p.id,a.turn_key FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id "
        "WHERE p.status IN ('pending','deferred') AND p.resolution_kind='local_navigation' "
        "AND p.target_key='borga' ORDER BY p.id DESC LIMIT 1").fetchone()


def activate_v103(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer_path = root / "runtime/runtime_state.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("engine_version") == "1.0.3":
        return {"ok": True, "already_active": True, "journal_seq": pointer["journal_seq"],
                "session_state": pointer.get("session_state")}
    if pointer.get("engine_version") != "1.0.2" or pointer.get("mode") != "engine_authoritative":
        raise RuntimeError("v1.0.3 activation requires v1.0.2 authoritative runtime")
    base_seq = int(pointer["journal_seq"])
    old_head = str(pointer["head_state_hash"])
    system_entry = None
    final_hash, final_seq, session_state = old_head, base_seq, None
    with tempfile.TemporaryDirectory() as td:
        source, loaded_pointer, _ = load_repository_runtime_v102(root, Path(td) / "source.db")
        try:
            if loaded_pointer["head_state_hash"] != old_head or int(loaded_pointer["journal_seq"]) != base_seq:
                raise RuntimeError("pointer changed during v1.0.3 activation")
            snapshot = export_portable_checkpoint_v100(source, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != old_head:
                raise RuntimeError("v1.0.3 compact base does not match authoritative head")
            pending = _latest_borga_pending(source)
            pending_id = int(pending["id"]) if pending is not None else None
            pending_turn_key = str(pending["turn_key"]) if pending is not None else None
        finally:
            source.close()
        world = seed_world_v103_migration(Path(td) / "v103.db")
        try:
            restored = import_portable_checkpoint_v100(world, snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != old_head:
                raise RuntimeError("v1.0.3 base roundtrip failed")
            if pending_id is not None:
                final_seq = base_seq + 1
                event_key = f"system-v103-resume-{pending_turn_key}-j{final_seq:06d}"
                executed = world.execute_runtime_event(
                    final_seq, event_key, "living_scene_resume",
                    {"pending_id": pending_id, "source_turn_key": pending_turn_key,
                     "reason": "resume already-authorized pre-upgrade local search; not a new player choice"})
                system_entry = executed["journal"]
                final_hash = str(system_entry["after_hash"])
            else:
                final_hash = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
            session_state = world.build_session_state_v103(
                journal_seq=final_seq, head_state_hash=final_hash, last_event=system_entry)
        finally:
            world.close()
        verifier = seed_world_v103_migration(Path(td) / "verify.db")
        try:
            check = import_portable_checkpoint_v100(verifier, snapshot)
            if not check.get("ok") or check.get("restored_hash") != old_head:
                raise RuntimeError("v1.0.3 verifier base import failed")
            if system_entry is not None:
                replay = verifier.replay_runtime_entries([system_entry])
                if not replay.get("ok"):
                    raise RuntimeError("v1.0.3 system resume replay failed:" + str(replay))
            if runtime_state_hash_v100(verifier, int(pointer["source_live_version"])) != final_hash:
                raise RuntimeError("v1.0.3 final head mismatch")
        finally:
            verifier.close()
    checkpoint_rel = f"runtime/checkpoints/v103_base_j{base_seq:06d}.json"
    checkpoint_path = root / checkpoint_rel
    if checkpoint_path.exists():
        raise RuntimeError("v1.0.3 compact checkpoint path already exists")
    journal_path = None
    if system_entry is not None:
        journal_path = root / pointer["journal_dir"] / f"j{final_seq:06d}.json"
        if journal_path.exists():
            raise RuntimeError("v1.0.3 resume journal path already exists")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    if system_entry is not None:
        journal_path.write_text(json.dumps(system_entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "runtime/session_state.json").write_text(
        json.dumps(session_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pointer["engine_version"] = "1.0.3"
    pointer["base_checkpoint"] = checkpoint_rel
    pointer["base_state_hash"] = old_head
    pointer["journal_base_seq"] = base_seq
    pointer["journal_seq"] = final_seq
    pointer["head_state_hash"] = final_hash
    pointer["session_state"] = "runtime/session_state.json"
    pointer["write_protocol"]["living_scene"] = True
    if system_entry is not None:
        pointer["last_event"] = str(Path(pointer["journal_dir"]) / f"j{final_seq:06d}.json")
        pointer["system_resume"] = {"event": pointer["last_event"], "source_pending_turn": pending_turn_key,
                                    "reason": "completed already-authorized local search under v1.0.3"}
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "already_active": False, "base_seq": base_seq, "journal_seq": final_seq,
            "checkpoint": checkpoint_rel, "system_resume": system_entry is not None,
            "system_event": pointer.get("last_event") if system_entry is not None else None,
            "head_state_hash": final_hash, "hud": session_state["hud"],
            "scene": session_state.get("scene"), "last_turn": session_state.get("last_turn")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = activate_v103(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
