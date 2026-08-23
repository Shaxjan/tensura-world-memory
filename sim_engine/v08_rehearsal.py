import argparse
import json
import tempfile
from pathlib import Path

from v06_migration import collect_repo_campaign
from v08_money import apply_v08_money_reconciliation
from v08_seed import seed_world_v08_migration


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default="..")
    p.add_argument("--out")
    a = p.parse_args()
    repo = Path(a.repo_root).resolve()
    package = collect_repo_campaign(repo)
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v08.db"
        with seed_world_v08_migration(db) as w:
            report = apply_v08_money_reconciliation(w, package, repo)
            report["sqlite_player"] = {
                "world_minute": w.now,
                "region_id": str(w.actor("player")["region_id"]),
                "cash_copper": int(w.actor("player")["cash_copper"]),
            }
            report["gameplay_enabled"] = sum(
                int(r["enabled"]) for r in w.db.execute("SELECT enabled FROM migration_capabilities")
            )
            report["technical_success"] = not report["errors"]
            text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
