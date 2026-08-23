import argparse
import json
import tempfile
from pathlib import Path

from v04_seed import seed_world_v04


def run(days: int) -> dict:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "probe.db"
        w = seed_world_v04(db)
        try:
            cash0 = int(w.actor("player")["cash_copper"])
            region0 = str(w.actor("player")["region_id"])
            w.remember("player", "probe_trivia", "A forgettable street detail.", salience=18)
            w.advance(days * 1440)

            canon_key = "canon:jura_orc_movement"
            player_knows = w.db.execute(
                "SELECT 1 FROM actor_knowledge WHERE actor_id='player' AND fact_key=?",
                (canon_key,),
            ).fetchone() is not None
            blumund_belief = w.db.execute(
                "SELECT 1 FROM region_beliefs WHERE region_id='blumund' AND fact_key=?",
                (canon_key,),
            ).fetchone() is not None

            ctx = w.build_context()
            return {
                "days": days,
                "world_minute": w.now,
                "player_cash_unchanged": int(w.actor("player")["cash_copper"]) == cash0,
                "player_region_unchanged": str(w.actor("player")["region_id"]) == region0,
                "player_status": str(w.actor("player")["status"]),
                "player_hp": int(w.stats("player")["hp"]),
                "macro_ticks": w.metric("macro_ticks"),
                "faction_actions": w.metric("faction_actions"),
                "packets_delivered": w.metric("packets_delivered"),
                "canon_fact_exists": w.db.execute("SELECT 1 FROM facts WHERE key=?", (canon_key,)).fetchone() is not None,
                "canon_reached_blumund_region": blumund_belief,
                "canon_auto_leaked_to_player": player_knows,
                "seeded_appointment_status": str(w.db.execute("SELECT status FROM appointments ORDER BY id LIMIT 1").fetchone()[0]),
                "important_memory_status": str(w.db.execute(
                    "SELECT status FROM memories WHERE actor_id='player' AND memory_key='departure_contract'"
                ).fetchone()[0]),
                "trivial_memory_status": str(w.db.execute(
                    "SELECT status FROM memories WHERE actor_id='player' AND memory_key='probe_trivia'"
                ).fetchone()[0]),
                "context_chars": len(json.dumps(ctx, ensure_ascii=False)),
                "event_count": int(w.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
                "grain_stocks": {
                    str(r["region_id"]): int(r["supply"])
                    for r in w.db.execute(
                        "SELECT region_id,supply FROM markets WHERE commodity_id='grain' ORDER BY region_id"
                    )
                },
            }
        finally:
            w.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=60)
    args = p.parse_args()
    print(json.dumps(run(args.days), ensure_ascii=False, indent=2))
