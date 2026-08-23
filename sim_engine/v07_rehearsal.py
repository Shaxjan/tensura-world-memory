from __future__ import annotations
import argparse, json, tempfile
from pathlib import Path
from v06_migration import collect_repo_campaign
from v07_baseline import apply_v07_baseline_rehearsal
from v07_seed import seed_world_v07_migration


def run(repo_root: str | Path) -> dict:
    root=Path(repo_root).resolve()
    package=collect_repo_campaign(root)
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"v07_rehearsal.db"
        with seed_world_v07_migration(db) as w:
            report=apply_v07_baseline_rehearsal(w,package,root)
            report["sqlite_player"]={
                "world_minute":w.now,
                "region_id":str(w.actor("player")["region_id"]),
                "cash_copper":int(w.actor("player")["cash_copper"]),
            }
            report["synthetic_market_rows"]=w.db.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
            report["synthetic_route_rows"]=w.db.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
            report["synthetic_commodity_rows"]=w.db.execute("SELECT COUNT(*) FROM commodities").fetchone()[0]
            report["gameplay_enabled"]=sum(int(r["enabled"]) for r in w.db.execute("SELECT enabled FROM migration_capabilities"))
            report["gm_packet_chars"]=w.build_gm_packet("player")["packet_meta"]["chars"]
            report["technical_success"]=not bool(report.get("errors"))
            return report

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--repo-root",default=".."); p.add_argument("--out")
    a=p.parse_args(); result=run(a.repo_root)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.out: Path(a.out).write_text(text,encoding="utf-8")
    print(text)
    raise SystemExit(0 if result.get("technical_success") else 2)
