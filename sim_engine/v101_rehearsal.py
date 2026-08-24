from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import runtime_state_hash_v100
from v101_repository import load_repository_runtime_v101


def run(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    with tempfile.TemporaryDirectory() as td:
        world, pointer, meta = load_repository_runtime_v101(root, Path(td) / "shadow.db")
        try:
            before = {
                "time": int(world.now),
                "cash": int(world.actor("player")["cash_copper"]),
                "region": str(world.actor("player")["region_id"]),
            }
            seq = int(pointer["journal_seq"]) + 1
            event = world.execute_runtime_event(seq, "v101-shadow-local-travel", "player_turn", {"raw_text": "Иду к тренировочному двору."})
            after = {
                "time": int(world.now),
                "cash": int(world.actor("player")["cash_copper"]),
                "region": str(world.actor("player")["region_id"]),
            }
            result = event["result"]
            pending = int(world.db.execute(
                "SELECT COUNT(*) FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id "
                "WHERE a.turn_key='v101-shadow-local-travel' AND p.status IN ('pending','deferred')"
            ).fetchone()[0])
            journal = event["journal"]
            return {
                "source_seq": int(pointer["journal_seq"]),
                "shadow_seq": seq,
                "status": result.get("status"),
                "travel_result": result.get("result"),
                "time_delta": after["time"] - before["time"],
                "cash_preserved": after["cash"] == before["cash"],
                "region_preserved": after["region"] == before["region"],
                "pending_for_turn": pending,
                "journal_after_hash_matches": journal["after_hash"] == runtime_state_hash_v100(world, int(pointer["source_live_version"])),
                "technical_success": result.get("status") == "executed" and pending == 0 and after["time"] > before["time"] and after["cash"] == before["cash"],
            }
        finally:
            world.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    a = ap.parse_args()
    result = run(a.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    if not result["technical_success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
