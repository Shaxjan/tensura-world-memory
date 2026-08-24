from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v105_repository import load_repository_runtime_v105
from v106_seed import seed_world_v106_migration

BAD_KEY = "chat-20260824-go-small-training-yard-r000006"


def rehearse(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer = json.loads((root / "runtime/runtime_state.json").read_text(encoding="utf-8"))
    if pointer.get("engine_version") != "1.0.5":
        raise RuntimeError("v1.0.6 rehearsal expects current LIVE engine 1.0.5")
    old_session = json.loads((root / "runtime/session_state.json").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as td:
        source, loaded, _ = load_repository_runtime_v105(root, Path(td) / "source.db")
        try:
            source_seq = int(loaded["journal_seq"])
            source_hash = str(loaded["head_state_hash"])
            time0 = int(source.now)
            cash0 = int(source.actor("player")["cash_copper"])
            turn = source.db.execute("SELECT raw_text FROM gm_turns WHERE turn_key=?", (BAD_KEY,)).fetchone()
            if turn is None:
                raise RuntimeError("real r000006 turn is absent")
            raw = str(turn["raw_text"])
            bad_rows = source.db.execute(
                "SELECT p.status,p.target_key FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.turn_key=?",
                (BAD_KEY,),
            ).fetchall()
            false_rena_present = any(str(r["target_key"] or "") == "rena" and str(r["status"]) == "pending" for r in bad_rows)
            if not false_rena_present:
                raise RuntimeError("rehearsal no longer sees the live false-Rena defect")
            snapshot = export_portable_checkpoint_v100(source, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != source_hash:
                raise RuntimeError("source compact snapshot mismatch")
        finally:
            source.close()

        world = seed_world_v106_migration(Path(td) / "v106.db")
        try:
            restored = import_portable_checkpoint_v100(world, snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != source_hash:
                raise RuntimeError("v1.0.6 import mismatch")
            seq = source_seq + 1
            event = world.execute_runtime_event(seq, f"rehearsal-v106-repair-{seq}", "intent_grounding_repair_activation", {"reason":"shadow repair"})
            entry = event["journal"]
            activation_head = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
            repair = event.get("result", {}).get("repair", {})
            pending_after = world.db.execute(
                "SELECT p.status,p.target_key FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.turn_key=?",
                (BAD_KEY,),
            ).fetchall()
            false_rena_after = any(str(r["target_key"] or "") == "rena" and str(r["status"]) == "pending" for r in pending_after)
            session = world.build_session_state_v106(
                journal_seq=seq,
                head_state_hash=activation_head,
                last_event=entry,
                preserved_last_turn=old_session.get("last_turn"),
            )
            destination = world._match_known_local_place_v101("player", raw)
            retry_start = int(world.now)
            retry = world.process_player_turn("rehearsal-v106-retry-r000006", raw)
            retry_end = int(world.now)
            retry_pending = ((retry.get("proposal") or {}).get("pending") or []) if isinstance(retry, dict) else []
        finally:
            world.close()

        verifier = seed_world_v106_migration(Path(td) / "verify.db")
        try:
            check = import_portable_checkpoint_v100(verifier, snapshot)
            if not check.get("ok"):
                raise RuntimeError("verifier base import failed")
            replay = verifier.replay_runtime_entries([entry])
            replay_hash = runtime_state_hash_v100(verifier, int(pointer["source_live_version"]))
        finally:
            verifier.close()

    report = {
        "source_seq": source_seq,
        "shadow_seq": seq,
        "false_rena_present_before": false_rena_present,
        "repair_status": repair.get("status"),
        "false_rena_pending_after": false_rena_after,
        "activation_zero_time": int(entry["world_minute"]) == time0,
        "cash_preserved": session["hud"]["money"]["on_person_copper"] == cash0,
        "session_engine": session.get("engine_version"),
        "last_turn_status": (session.get("last_turn") or {}).get("status"),
        "matched_destination": (destination or {}).get("key"),
        "retry_status": retry.get("status"),
        "retry_destination": (retry.get("result") or {}).get("destination_key"),
        "retry_minutes": retry_end - retry_start,
        "retry_has_rena_target": any(p.get("target_key") == "rena" for p in retry_pending),
        "activation_hash_matches": activation_head == entry["after_hash"],
        "replay_ok": bool(replay.get("ok")) and replay_hash == activation_head,
    }
    report["technical_success"] = all([
        report["false_rena_present_before"],
        report["repair_status"] == "repaired",
        not report["false_rena_pending_after"],
        report["activation_zero_time"],
        report["cash_preserved"],
        report["session_engine"] == "1.0.6",
        report["last_turn_status"] == "superseded_parser_repair",
        report["matched_destination"] == "eurazania_small_training_yard",
        report["retry_status"] == "executed",
        report["retry_destination"] == "eurazania_small_training_yard",
        report["retry_minutes"] == 12,
        not report["retry_has_rena_target"],
        report["activation_hash_matches"],
        report["replay_ok"],
    ])
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    report = rehearse(args.repo_root)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    if not report["technical_success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
