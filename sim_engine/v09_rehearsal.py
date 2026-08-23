import argparse
import json
import tempfile
from pathlib import Path

from v06_migration import collect_repo_campaign
from v09_runtime import (
    apply_v09_guarded_cutover,
    export_portable_checkpoint,
    import_portable_checkpoint,
    mark_portable_bridge_verified,
)
from v09_seed import seed_world_v09_migration


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default="..")
    p.add_argument("--out")
    p.add_argument("--checkpoint-out")
    a = p.parse_args()
    repo = Path(a.repo_root).resolve()
    package = collect_repo_campaign(repo)

    with tempfile.TemporaryDirectory() as td:
        db1 = Path(td) / "source.db"
        with seed_world_v09_migration(db1) as w:
            report = apply_v09_guarded_cutover(w, package, repo)
            if report.get("errors"):
                text = json.dumps(report, ensure_ascii=False, indent=2)
                print(text)
                if a.out: Path(a.out).write_text(text, encoding="utf-8")
                return
            snapshot = export_portable_checkpoint(w, int(package.pointer["v"]))
            source_critical = w.critical_state_snapshot("player")
            source_hash = snapshot["state_hash"]

        db2 = Path(td) / "restored.db"
        with seed_world_v09_migration(db2) as restored:
            roundtrip = import_portable_checkpoint(restored, snapshot)
            restored_critical = restored.critical_state_snapshot("player") if roundtrip.get("ok") else None
            hash_equal = bool(roundtrip.get("ok") and roundtrip.get("restored_hash") == source_hash)
            critical_equal = restored_critical == source_critical
            if hash_equal and critical_equal:
                mark_portable_bridge_verified(restored, source_hash)

            before = restored.critical_state_snapshot("player") if roundtrip.get("ok") else None
            shadow = restored.process_player_turn("v09-shadow-wait", "жду 1 минуту") if roundtrip.get("ok") else None
            after = restored.critical_state_snapshot("player") if roundtrip.get("ok") else None
            shadow_guardrail_ok = bool(
                shadow
                and shadow.get("status") == "blocked_by_migration"
                and not shadow.get("accepted")
                and before == after
            )
            packet = restored.build_gm_packet("player") if roundtrip.get("ok") else {}
            active_gates = [
                str(r[0]) for r in restored.db.execute(
                    "SELECT gate_code FROM cutover_gate WHERE status!='resolved' ORDER BY gate_code"
                ).fetchall()
            ] if roundtrip.get("ok") else ["portable_runtime_bridge"]

            report.update({
                "portable_checkpoint": {
                    "state_hash": source_hash,
                    "table_count": snapshot["transport_meta"]["table_count"],
                    "row_count": snapshot["transport_meta"]["row_count"],
                    "byte_count": snapshot["transport_meta"]["byte_count"],
                    "roundtrip_ok": bool(roundtrip.get("ok")),
                    "hash_equal": hash_equal,
                    "critical_state_equal": critical_equal,
                    "excluded_tables": snapshot["transport_meta"]["excluded_tables"],
                },
                "shadow_turn": {
                    "status": shadow.get("status") if shadow else None,
                    "accepted": shadow.get("accepted") if shadow else None,
                    "state_unchanged": before == after if before is not None else False,
                    "guardrail_ok": shadow_guardrail_ok,
                },
                "cutover_blockers": active_gates,
                "live_cutover_ready": not active_gates and hash_equal and critical_equal and shadow_guardrail_ok,
                "gm_packet_chars": packet.get("packet_meta", {}).get("chars"),
                "synthetic_market_rows": restored.db.execute("SELECT COUNT(*) FROM markets").fetchone()[0],
                "synthetic_route_rows": restored.db.execute("SELECT COUNT(*) FROM routes").fetchone()[0],
                "synthetic_commodity_rows": restored.db.execute("SELECT COUNT(*) FROM commodities").fetchone()[0],
                "technical_success": bool(hash_equal and critical_equal and shadow_guardrail_ok),
            })

        if a.checkpoint_out:
            Path(a.checkpoint_out).write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        text = json.dumps(report, ensure_ascii=False, indent=2)
        print(text)
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
