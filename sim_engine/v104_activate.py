from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v103_repository import load_repository_runtime_v103
from v104_seed import seed_world_v104_migration


def activate_v104(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer_path = root / "runtime/runtime_state.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("engine_version") == "1.0.4":
        return {
            "ok": True,
            "already_active": True,
            "journal_seq": pointer["journal_seq"],
            "session_state": pointer.get("session_state"),
        }
    if pointer.get("engine_version") != "1.0.3" or pointer.get("mode") != "engine_authoritative":
        raise RuntimeError("v1.0.4 activation requires v1.0.3 authoritative runtime")

    old_session_path = root / str(pointer.get("session_state") or "runtime/session_state.json")
    old_session = json.loads(old_session_path.read_text(encoding="utf-8"))
    if int(old_session.get("journal_seq", -1)) != int(pointer["journal_seq"]):
        raise RuntimeError("session state is stale before v1.0.4 activation")

    base_seq = int(pointer["journal_seq"])
    old_head = str(pointer["head_state_hash"])
    activation_seq = base_seq + 1
    activation_entry = None
    final_hash = None
    session_state = None

    with tempfile.TemporaryDirectory() as td:
        source, loaded_pointer, _ = load_repository_runtime_v103(root, Path(td) / "source.db")
        try:
            if loaded_pointer["head_state_hash"] != old_head or int(loaded_pointer["journal_seq"]) != base_seq:
                raise RuntimeError("pointer changed during v1.0.4 activation")
            source_time = int(source.now)
            source_cash = int(source.actor("player")["cash_copper"])
            source_region = str(source.actor("player")["region_id"])
            snapshot = export_portable_checkpoint_v100(source, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != old_head:
                raise RuntimeError("v1.0.4 compact base does not match authoritative head")
        finally:
            source.close()

        world = seed_world_v104_migration(Path(td) / "v104.db")
        try:
            restored = import_portable_checkpoint_v100(world, snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != old_head:
                raise RuntimeError("v1.0.4 base roundtrip failed")
            event_key = f"system-v104-character-core-j{activation_seq:06d}"
            executed = world.execute_runtime_event(
                activation_seq,
                event_key,
                "character_core_activation",
                {
                    "reason": "activate persistent Character Core without choosing a player action",
                    "source_engine": "1.0.3",
                    "target_engine": "1.0.4",
                },
            )
            activation_entry = executed["journal"]
            final_hash = str(activation_entry["after_hash"])
            if int(world.now) != source_time:
                raise RuntimeError("v1.0.4 activation changed world time")
            if int(world.actor("player")["cash_copper"]) != source_cash:
                raise RuntimeError("v1.0.4 activation changed player cash")
            if str(world.actor("player")["region_id"]) != source_region:
                raise RuntimeError("v1.0.4 activation changed player region")
            session_state = world.build_session_state_v104(
                journal_seq=activation_seq,
                head_state_hash=final_hash,
                last_event=activation_entry,
                preserved_last_turn=old_session.get("last_turn"),
            )
        finally:
            world.close()

        verifier = seed_world_v104_migration(Path(td) / "verify.db")
        try:
            check = import_portable_checkpoint_v100(verifier, snapshot)
            if not check.get("ok") or check.get("restored_hash") != old_head:
                raise RuntimeError("v1.0.4 verifier base import failed")
            replay = verifier.replay_runtime_entries([activation_entry])
            if not replay.get("ok"):
                raise RuntimeError("v1.0.4 activation replay failed:" + str(replay))
            if runtime_state_hash_v100(verifier, int(pointer["source_live_version"])) != final_hash:
                raise RuntimeError("v1.0.4 final head mismatch")
        finally:
            verifier.close()

    checkpoint_rel = f"runtime/checkpoints/v104_base_j{base_seq:06d}.json"
    checkpoint_path = root / checkpoint_rel
    if checkpoint_path.exists():
        raise RuntimeError("v1.0.4 compact checkpoint path already exists")
    journal_path = root / pointer["journal_dir"] / f"j{activation_seq:06d}.json"
    if journal_path.exists():
        raise RuntimeError("v1.0.4 activation journal path already exists")

    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    journal_path.write_text(
        json.dumps(activation_entry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "runtime/session_state.json").write_text(
        json.dumps(session_state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    pointer["engine_version"] = "1.0.4"
    pointer["base_checkpoint"] = checkpoint_rel
    pointer["base_state_hash"] = old_head
    pointer["journal_base_seq"] = base_seq
    pointer["journal_seq"] = activation_seq
    pointer["head_state_hash"] = final_hash
    pointer["last_event"] = str(Path(pointer["journal_dir"]) / f"j{activation_seq:06d}.json")
    pointer["session_state"] = "runtime/session_state.json"
    pointer["write_protocol"]["character_core"] = True
    pointer["system_activation"] = {
        "event": pointer["last_event"],
        "kind": "character_core_v104",
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
        "last_gameplay_turn_preserved": session_state.get("last_turn") == old_session.get("last_turn"),
        "character_runtime": session_state.get("character_runtime"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = activate_v104(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
