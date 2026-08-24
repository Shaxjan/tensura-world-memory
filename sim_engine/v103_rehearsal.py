from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v102_repository import load_repository_runtime_v102
from v103_seed import seed_world_v103_migration


def rehearse(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer = json.loads((root / "runtime/runtime_state.json").read_text(encoding="utf-8"))
    if pointer.get("engine_version") != "1.0.2":
        raise RuntimeError("v1.0.3 rehearsal expects current LIVE engine 1.0.2")
    with tempfile.TemporaryDirectory() as td:
        source, loaded, _ = load_repository_runtime_v102(root, Path(td) / "source.db")
        try:
            source_seq = int(loaded["journal_seq"])
            source_hash = str(loaded["head_state_hash"])
            t0 = int(source.now)
            cash0 = int(source.actor("player")["cash_copper"])
            region0 = str(source.actor("player")["region_id"])
            pending = source.db.execute("SELECT p.id,a.turn_key FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE p.status IN ('pending','deferred') AND p.resolution_kind='local_navigation' AND p.target_key='borga' ORDER BY p.id DESC LIMIT 1").fetchone()
            if pending is None:
                raise RuntimeError("current LIVE no longer has the Borga pending search expected by v1.0.3 rehearsal")
            pending_id = int(pending["id"])
            pending_turn = str(pending["turn_key"])
            snapshot = export_portable_checkpoint_v100(source, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != source_hash:
                raise RuntimeError("source compact snapshot mismatch")
        finally:
            source.close()
        world = seed_world_v103_migration(Path(td) / "v103.db")
        try:
            restored = import_portable_checkpoint_v100(world, snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != source_hash:
                raise RuntimeError("v1.0.3 import mismatch")
            seq = source_seq + 1
            event = world.execute_runtime_event(seq, f"rehearsal-v103-resume-{seq}", "living_scene_resume",
                                                {"pending_id": pending_id, "source_turn_key": pending_turn})
            entry = event["journal"]
            result = entry["result"]
            packet = result["gm_packet"]
            head = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
            pending_after = world.db.execute("SELECT COUNT(*) FROM scene_pending_resolution WHERE status IN ('pending','deferred') AND target_key='borga'").fetchone()[0]
            cash_after = int(world.actor("player")["cash_copper"])
            region_after = str(world.actor("player")["region_id"])
            ambient = list(packet["scene"].get("ambient") or [])
            outcome = (result.get("result") or {}).get("outcome")
            session = world.build_session_state_v103(journal_seq=seq, head_state_hash=head, last_event=entry)
        finally:
            world.close()
        verifier = seed_world_v103_migration(Path(td) / "verify.db")
        try:
            selfcheck = import_portable_checkpoint_v100(verifier, snapshot)
            if not selfcheck.get("ok"):
                raise RuntimeError("verifier base import failed")
            replay = verifier.replay_runtime_entries([entry])
            replay_hash = runtime_state_hash_v100(verifier, int(pointer["source_live_version"]))
        finally:
            verifier.close()
    report = {
        "source_seq": source_seq, "shadow_seq": seq, "source_time": t0,
        "shadow_time": int(entry["world_minute"]), "time_delta": int(entry["world_minute"]) - t0,
        "outcome": outcome, "ambient_entities": len(ambient),
        "ambient_preview": [{"descriptor": x.get("descriptor"), "activity": x.get("activity"), "group_size": x.get("group_size")} for x in ambient[:5]],
        "named_observations": packet["scene"].get("named_observations"),
        "pending_borga_after": int(pending_after), "cash_preserved": cash_after == cash0,
        "region_preserved": region_after == region0, "hud": session["hud"],
        "session_engine": session["engine_version"], "journal_after_hash_matches": head == entry["after_hash"],
        "replay_ok": bool(replay.get("ok")) and replay_hash == head,
    }
    report["technical_success"] = (report["time_delta"] == 6 and report["outcome"] in {"found","lead","not_found_no_lead"}
        and report["ambient_entities"] >= 3 and report["pending_borga_after"] == 0 and report["cash_preserved"]
        and report["region_preserved"] and report["session_engine"] == "1.0.3"
        and report["journal_after_hash_matches"] and report["replay_ok"])
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
