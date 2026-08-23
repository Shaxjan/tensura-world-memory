from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v02_engine import SimulationV02
from v02_seed import seed_blumund_v02


def run_probe(days: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "probe.db"
        seed_blumund_v02(db)
        with SimulationV02(db) as sim:
            player_before = dict(sim.actor("char_arlequino"))
            sim.advance(days * 1440)
            player_after = dict(sim.actor("char_arlequino"))
            report = sim.autonomy_report()
            report["days"] = days
            report["player_untouched"] = (
                player_before["location_id"] == player_after["location_id"]
                and player_before["cash_copper"] == player_after["cash_copper"]
            )
            report["completed_goals"] = [
                dict(r) for r in sim.db.execute(
                    "SELECT actor_id,kind,progress,status FROM goals WHERE status='completed' ORDER BY actor_id,id"
                )
            ]
            report["active_goals"] = [
                dict(r) for r in sim.db.execute(
                    "SELECT actor_id,kind,priority,progress,source FROM goals WHERE status='active' ORDER BY actor_id,priority DESC"
                )
            ]
            report["rumor_network"] = [
                dict(r) for r in sim.db.execute(
                    "SELECT actor_id,rumor_id,confidence,source_actor_id,claim_json FROM rumor_beliefs ORDER BY actor_id"
                )
            ]
            return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    print(json.dumps(run_probe(args.days), ensure_ascii=False, indent=2))
