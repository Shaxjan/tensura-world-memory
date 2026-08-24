from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v106_repository import load_repository_runtime_v106
from v107_seed import seed_world_v107_migration


def activate_v107(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer_path = root / "runtime/runtime_state.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("engine_version") == "1.0.7":
        return {"ok": True, "already_active": True, "journal_seq": pointer["journal_seq"], "session_state": pointer.get("session_state")}
    if pointer.get("engine_version") != "1.0.6" or pointer.get("mode") != "engine_authoritative":
        raise RuntimeError("v1.0.7 activation requires v1.0.6 authoritative runtime")

    old_session = json.loads((root / str(pointer.get("session_state") or "runtime/session_state.json")).read_text(encoding="utf-8"))
    if int(old_session.get("journal_seq", -1)) != int(pointer["journal_seq"]):
        raise RuntimeError("session state is stale before v1.0.7 activation")

    base_seq = int(pointer["journal_seq"])
    old_head = str(pointer["head_state_hash"])
    activation_seq = base_seq + 1

    with tempfile.TemporaryDirectory() as td:
        source, loaded_pointer, _ = load_repository_runtime_v106(root, Path(td) / "source.db")
        try:
            if loaded_pointer["head_state_hash"] != old_head or int(loaded_pointer["journal_seq"]) != base_seq:
                raise RuntimeError("pointer changed during v1.0.7 activation")
            source_time = int(source.now)
            source_cash = int(source.actor("player")["cash_copper"])
            source_region = str(source.actor("player")["region_id"])
            source_core = source.character_core_v104("borga") or {}
            source_memories = list(source_core.get("memories") or [])
            borga_actor_before = int(source.db.execute("SELECT COUNT(*) FROM actors WHERE id='borga'").fetchone()[0])
            snapshot = export_portable_checkpoint_v100(source, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != old_head:
                raise RuntimeError("v1.0.7 compact base does not match authoritative head")
        finally:
            source.close()

        world = seed_world_v107_migration(Path(td) / "v107.db")
        try:
            restored = import_portable_checkpoint_v100(world, snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != old_head:
                raise RuntimeError("v1.0.7 base roundtrip failed")
            event_key = f"system-v107-causal-encounter-memory-j{activation_seq:06d}"
            executed = world.execute_runtime_event(
                activation_seq,
                event_key,
                "causal_encounter_memory_activation",
                {
                    "reason": "enable causal named-character encounter memory without inventing reciprocal awareness from prior player observation",
                    "source_engine": "1.0.6",
                    "target_engine": "1.0.7",
                },
            )
            activation_entry = executed["journal"]
            final_hash = str(activation_entry["after_hash"])
            if int(world.now) != source_time:
                raise RuntimeError("v1.0.7 activation changed world time")
            if int(world.actor("player")["cash_copper"]) != source_cash:
                raise RuntimeError("v1.0.7 activation changed player cash")
            if str(world.actor("player")["region_id"]) != source_region:
                raise RuntimeError("v1.0.7 activation changed player region")
            core_after = world.character_core_v104("borga") or {}
            if list(core_after.get("memories") or []) != source_memories:
                raise RuntimeError("v1.0.7 activation created retroactive Borga memory")
            if int(world.db.execute("SELECT COUNT(*) FROM actors WHERE id='borga'").fetchone()[0]) != borga_actor_before:
                raise RuntimeError("v1.0.7 activation falsely materialized Borga as generic actor")
            session_state = world.build_session_state_v107(
                journal_seq=activation_seq,
                head_state_hash=final_hash,
                last_event=activation_entry,
                preserved_last_turn=old_session.get("last_turn"),
            )
        finally:
            world.close()

        verifier = seed_world_v107_migration(Path(td) / "verify.db")
        try:
            check = import_portable_checkpoint_v100(verifier, snapshot)
            if not check.get("ok") or check.get("restored_hash") != old_head:
                raise RuntimeError("v1.0.7 verifier base import failed")
            replay = verifier.replay_runtime_entries([activation_entry])
            if not replay.get("ok"):
                raise RuntimeError("v1.0.7 activation replay failed:" + str(replay))
            if runtime_state_hash_v100(verifier, int(pointer["source_live_version"])) != final_hash:
                raise RuntimeError("v1.0.7 final head mismatch")
        finally:
            verifier.close()

    checkpoint_rel = f"runtime/checkpoints/v107_base_j{base_seq:06d}.json"
    checkpoint_path = root / checkpoint_rel
    journal_path = root / pointer["journal_dir"] / f"j{activation_seq:06d}.json"
    if checkpoint_path.exists() or journal_path.exists():
        raise RuntimeError("v1.0.7 activation output path already exists")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    journal_path.write_text(json.dumps(activation_entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "runtime/session_state.json").write_text(json.dumps(session_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    pointer["engine_version"] = "1.0.7"
    pointer["base_checkpoint"] = checkpoint_rel
    pointer["base_state_hash"] = old_head
    pointer["journal_base_seq"] = base_seq
    pointer["journal_seq"] = activation_seq
    pointer["head_state_hash"] = final_hash
    pointer["last_event"] = str(Path(pointer["journal_dir"]) / f"j{activation_seq:06d}.json")
    pointer["session_state"] = "runtime/session_state.json"
    pointer["write_protocol"]["causal_encounter_memory"] = True
    pointer["system_activation"] = {
        "event": pointer["last_event"],
        "kind": "causal_encounter_memory_v107",
        "world_time_advanced": 0,
        "player_choice": False,
    }
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "already_active": False,
        "base_seq": base_seq,
        "journal_seq": activation_seq,
        "checkpoint": checkpoint_rel,
        "activation_event": pointer["last_event"],
        "head_state_hash": final_hash,
        "hud": session_state["hud"],
        "prior_borga_memories_preserved": len(source_memories),
        "last_gameplay_turn_preserved": session_state.get("last_turn") == old_session.get("last_turn"),
        "generic_borga_actor_materialized": bool(borga_actor_before),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = activate_v107(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
