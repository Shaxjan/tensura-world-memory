from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v06_migration import apply_repo_campaign_rehearsal, collect_repo_campaign
from v06_seed import seed_world_v06_migration


def run_rehearsal(repo_root: Path, db_path: Path) -> dict:
    package = collect_repo_campaign(repo_root)
    with seed_world_v06_migration(db_path) as world:
        report = apply_repo_campaign_rehearsal(world, package)
        player = world.actor("player")
        report["sqlite_player"] = {
            "world_minute": world.now,
            "region_id": str(player["region_id"]),
            "cash_copper": int(player["cash_copper"]),
            "status": str(player["status"]),
        }
        report["checkpoint"] = world.write_checkpoint("player", kind="migration_rehearsal")
        report["gm_packet_chars"] = int(world.build_gm_packet("player")["packet_meta"]["chars"])
        report["checkpoint_verified"] = bool(world.verify_latest_checkpoint("player")["ok"])
    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default="..")
    p.add_argument("--db")
    p.add_argument("--out")
    a = p.parse_args()
    repo = Path(a.repo_root).resolve()
    if a.db:
        db = Path(a.db)
        report = run_rehearsal(repo, db)
    else:
        with tempfile.TemporaryDirectory() as td:
            report = run_rehearsal(repo, Path(td) / "campaign_rehearsal.db")
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.get("rehearsal_ready") and report.get("source_archive_complete") and report.get("checkpoint_verified") else 2


if __name__ == "__main__":
    raise SystemExit(main())
