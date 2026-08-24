from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v103_repository import load_repository_runtime_v103
from v104_seed import seed_world_v104_migration


def rehearse(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer = json.loads((root / "runtime/runtime_state.json").read_text(encoding="utf-8"))
    if pointer.get("engine_version") != "1.0.3":
        raise RuntimeError("v1.0.4 rehearsal expects current LIVE engine 1.0.3")
    old_session = json.loads((root / "runtime/session_state.json").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as td:
        source, loaded, _ = load_repository_runtime_v103(root, Path(td) / "source.db")
        try:
            source_seq = int(loaded["journal_seq"])
            source_hash = str(loaded["head_state_hash"])
            time0 = int(source.now)
            cash0 = int(source.actor("player")["cash_copper"])
            region0 = str(source.actor("player")["region_id"])
            snapshot = export_portable_checkpoint_v100(source, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != source_hash:
                raise RuntimeError("source compact snapshot mismatch")
        finally:
            source.close()

        world = seed_world_v104_migration(Path(td) / "v104.db")
        try:
            restored = import_portable_checkpoint_v100(world, snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != source_hash:
                raise RuntimeError("v1.0.4 import mismatch")
            seq = source_seq + 1
            event = world.execute_runtime_event(
                seq,
                f"rehearsal-v104-character-core-{seq}",
                "character_core_activation",
                {"reason": "shadow migration rehearsal"},
            )
            entry = event["journal"]
            head = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
            core = world.character_core_v104("borga")
            plan = world.ensure_character_plan_v104("borga")
            presence = world._borga_presence103(world.now)
            session = world.build_session_state_v104(
                journal_seq=seq,
                head_state_hash=head,
                last_event=entry,
                preserved_last_turn=old_session.get("last_turn"),
            )
            time_after = int(world.now)
            cash_after = int(world.actor("player")["cash_copper"])
            region_after = str(world.actor("player")["region_id"])
        finally:
            world.close()

        verifier = seed_world_v104_migration(Path(td) / "verify.db")
        try:
            selfcheck = import_portable_checkpoint_v100(verifier, snapshot)
            if not selfcheck.get("ok"):
                raise RuntimeError("verifier base import failed")
            replay = verifier.replay_runtime_entries([entry])
            replay_hash = runtime_state_hash_v100(verifier, int(pointer["source_live_version"]))
        finally:
            verifier.close()

    report = {
        "source_seq": source_seq,
        "shadow_seq": seq,
        "time_preserved": time_after == time0,
        "cash_preserved": cash_after == cash0,
        "region_preserved": region_after == region0,
        "core_materialized": isinstance(core, dict),
        "personality_status": ((core or {}).get("personality") or {}).get("status"),
        "relationships_empty": ((core or {}).get("relationships") or {}) == {},
        "memories_empty": ((core or {}).get("memories") or []) == [],
        "plan_materialized": isinstance(plan, dict),
        "migration_anchor_used": (plan or {}).get("migration_anchor_used"),
        "presence_certainty": (presence or {}).get("certainty"),
        "session_engine": session.get("engine_version"),
        "last_gameplay_turn_preserved": session.get("last_turn") == old_session.get("last_turn"),
        "journal_after_hash_matches": head == entry["after_hash"],
        "replay_ok": bool(replay.get("ok")) and replay_hash == head,
    }
    report["technical_success"] = all(
        [
            report["time_preserved"],
            report["cash_preserved"],
            report["region_preserved"],
            report["core_materialized"],
            report["personality_status"] == "not_yet_authored",
            report["relationships_empty"],
            report["memories_empty"],
            report["plan_materialized"],
            report["session_engine"] == "1.0.4",
            report["last_gameplay_turn_preserved"],
            report["journal_after_hash_matches"],
            report["replay_ok"],
        ]
    )
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
