from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v110_repository import load_repository_runtime_v110
from v111_seed import seed_world_v111_migration


def activate_v111(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer_path = root / "runtime/runtime_state.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("engine_version") == "1.0.11":
        return {"ok": True, "already_active": True, "journal_seq": pointer["journal_seq"]}
    if pointer.get("engine_version") != "1.0.10" or pointer.get("mode") != "engine_authoritative":
        raise RuntimeError("v1.0.11 activation requires v1.0.10 authoritative runtime")

    session_path = root / str(pointer.get("session_state") or "runtime/session_state.json")
    old_session = json.loads(session_path.read_text(encoding="utf-8"))
    if int(old_session.get("journal_seq", -1)) != int(pointer["journal_seq"]):
        raise RuntimeError("stale session before v1.0.11 activation")
    if str(old_session.get("head_state_hash") or "") != str(pointer.get("head_state_hash") or ""):
        raise RuntimeError("session/pointer head mismatch before v1.0.11 activation")

    base_seq = int(pointer["journal_seq"])
    old_head = str(pointer["head_state_hash"])
    activation_seq = base_seq + 1

    with tempfile.TemporaryDirectory() as td:
        source, loaded, _ = load_repository_runtime_v110(root, Path(td) / "source.db")
        try:
            if loaded["head_state_hash"] != old_head or int(loaded["journal_seq"]) != base_seq:
                raise RuntimeError("pointer changed during v1.0.11 activation")
            t0 = int(source.now)
            cash0 = int(source.actor("player")["cash_copper"])
            region0 = str(source.actor("player")["region_id"])
            place0 = source._place103("player")
            core0 = source.character_core_v104("borga") or {}
            memories0 = list(core0.get("memories") or [])
            relationships0 = dict(core0.get("relationships") or {})
            personality0 = dict(core0.get("personality") or {})
            response_count0 = int(source.db.execute(
                "SELECT COUNT(*) FROM facts WHERE key LIKE 'v110:player_observed_response:borga:%'"
            ).fetchone()[0])
            snapshot = export_portable_checkpoint_v100(source, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != old_head:
                raise RuntimeError("v1.0.11 compact base mismatch")
        finally:
            source.close()

        world = seed_world_v111_migration(Path(td) / "v111.db")
        try:
            restored = import_portable_checkpoint_v100(world, snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != old_head:
                raise RuntimeError("v1.0.11 base roundtrip failed")
            event_key = f"system-v111-runtime-fast-path-j{activation_seq:06d}"
            entry = world.execute_runtime_event(
                activation_seq,
                event_key,
                "runtime_fast_path_activation",
                {
                    "reason": "enable auto-sequenced guarded turn queue and reduced-round-trip gameplay transport",
                    "source_engine": "1.0.10",
                    "target_engine": "1.0.11",
                },
            )["journal"]
            final_hash = str(entry["after_hash"])
            if final_hash != old_head:
                raise RuntimeError("v1.0.11 transport activation changed authoritative state hash")
            if int(world.now) != t0 or int(world.actor("player")["cash_copper"]) != cash0 or str(world.actor("player")["region_id"]) != region0:
                raise RuntimeError("v1.0.11 activation changed gameplay state")
            if world._place103("player") != place0:
                raise RuntimeError("v1.0.11 activation changed player place")
            core1 = world.character_core_v104("borga") or {}
            if list(core1.get("memories") or []) != memories0:
                raise RuntimeError("v1.0.11 activation changed Borga memories")
            if dict(core1.get("relationships") or {}) != relationships0:
                raise RuntimeError("v1.0.11 activation changed Borga relationships")
            if dict(core1.get("personality") or {}) != personality0:
                raise RuntimeError("v1.0.11 activation changed Borga personality")
            response_count1 = int(world.db.execute(
                "SELECT COUNT(*) FROM facts WHERE key LIKE 'v110:player_observed_response:borga:%'"
            ).fetchone()[0])
            if response_count1 != response_count0:
                raise RuntimeError("v1.0.11 activation changed NPC responses")
            session = world.build_session_state_v111(
                journal_seq=activation_seq,
                head_state_hash=final_hash,
                last_event=entry,
                preserved_last_turn=old_session.get("last_turn"),
            )
            if (session.get("last_turn") or {}).get("event_key") != (old_session.get("last_turn") or {}).get("event_key"):
                raise RuntimeError("v1.0.11 activation replaced last gameplay turn")
        finally:
            world.close()

        verifier = seed_world_v111_migration(Path(td) / "verify.db")
        try:
            check = import_portable_checkpoint_v100(verifier, snapshot)
            if not check.get("ok") or check.get("restored_hash") != old_head:
                raise RuntimeError("v1.0.11 verifier import failed")
            replay = verifier.replay_runtime_entries([entry])
            if not replay.get("ok"):
                raise RuntimeError("v1.0.11 activation replay failed:" + str(replay))
            if runtime_state_hash_v100(verifier, int(pointer["source_live_version"])) != final_hash:
                raise RuntimeError("v1.0.11 final hash mismatch")
        finally:
            verifier.close()

    checkpoint_rel = f"runtime/checkpoints/v111_base_j{base_seq:06d}.json"
    checkpoint_path = root / checkpoint_rel
    journal_path = root / pointer["journal_dir"] / f"j{activation_seq:06d}.json"
    if checkpoint_path.exists() or journal_path.exists():
        raise RuntimeError("v1.0.11 activation output exists")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    journal_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    pointer.update({
        "engine_version": "1.0.11",
        "base_checkpoint": checkpoint_rel,
        "base_state_hash": old_head,
        "journal_base_seq": base_seq,
        "journal_seq": activation_seq,
        "head_state_hash": final_hash,
        "last_event": str(Path(pointer["journal_dir"]) / f"j{activation_seq:06d}.json"),
        "session_state": "runtime/session_state.json",
    })
    pointer.setdefault("write_protocol", {})["runtime_fast_path"] = True
    pointer["write_protocol"]["fast_request_auto_sequence"] = True
    pointer["write_protocol"]["fast_request_last_turn_guard"] = True
    pointer["system_activation"] = {
        "event": pointer["last_event"],
        "kind": "runtime_fast_path_v111",
        "world_time_advanced": 0,
        "player_choice": False,
    }
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "already_active": False,
        "journal_seq": activation_seq,
        "checkpoint": checkpoint_rel,
        "head_state_hash": final_hash,
        "gameplay_hash_unchanged": final_hash == old_head,
        "last_gameplay_turn_preserved": (session.get("last_turn") or {}).get("event_key"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = activate_v111(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
