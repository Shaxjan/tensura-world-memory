from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from v06_seed import seed_world_v06_lab


def run(turns: int = 100) -> dict:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v06.db"
        with seed_world_v06_lab(db) as w:
            start = dict(w.actor("player"))
            timings = []
            for i in range(turns):
                t0 = time.perf_counter()
                r = w.process_player_turn(f"wait-{i}", "жду 1 минуту")
                timings.append((time.perf_counter() - t0) * 1000)
                if not r.get("accepted"):
                    raise RuntimeError(r)
            before_replay = w.now
            replay = w.process_player_turn("wait-0", "жду 1 минуту")
            after = dict(w.actor("player"))
            packet = w.build_gm_packet()
            checkpoints = w.db.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
            return {
                "turns": turns,
                "checkpoints": int(checkpoints),
                "world_minutes_advanced": w.now - (117 * 1440 + 8 * 60),
                "duplicate_replayed": bool(replay.get("replayed")),
                "duplicate_did_not_advance_time": w.now == before_replay,
                "player_region_unchanged": str(start["region_id"]) == str(after["region_id"]),
                "player_cash_unchanged": int(start["cash_copper"]) == int(after["cash_copper"]),
                "checkpoint_verified": bool(w.verify_latest_checkpoint()["ok"]),
                "gm_packet_chars": int(packet["packet_meta"]["chars"]),
                "checkpoint_ms": {
                    "median": round(statistics.median(timings), 3),
                    "p95": round(sorted(timings)[max(0, int(len(timings) * .95) - 1)], 3),
                    "max": round(max(timings), 3),
                },
            }


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--turns", type=int, default=100); a = p.parse_args()
    result = run(a.turns)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    ok = (result["checkpoints"] == a.turns and result["duplicate_replayed"] and
          result["duplicate_did_not_advance_time"] and result["checkpoint_verified"] and
          result["gm_packet_chars"] < 8000)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
