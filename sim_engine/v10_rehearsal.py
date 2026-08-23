import argparse
import json
import tempfile
from pathlib import Path

from v06_migration import collect_repo_campaign
from v09_runtime import mark_portable_bridge_verified
from v10_handoff import export_portable_checkpoint_v10, import_portable_checkpoint_v10
from v10_runtime import apply_v10_shadow_cutover, mark_v10_shadow_verified
from v10_seed import seed_world_v10_migration


def run(repo_root: str | Path) -> dict:
    repo=Path(repo_root).resolve(); package=collect_repo_campaign(repo)
    with tempfile.TemporaryDirectory() as td:
        db1=Path(td)/"source.db"
        with seed_world_v10_migration(db1) as w:
            report=apply_v10_shadow_cutover(w,package,repo)
            if report.get("errors"):
                report["technical_success"]=False; return report
            snap=export_portable_checkpoint_v10(w,int(package.pointer["v"]))
            source_hash=snap["state_hash"]
            source_core={"time":w.now,"region":str(w.actor("player")["region_id"]),"cash":int(w.actor("player")["cash_copper"])}

        db2=Path(td)/"shadow.db"
        with seed_world_v10_migration(db2) as shadow:
            rt=import_portable_checkpoint_v10(shadow,snap)
            hash_equal=bool(rt.get("ok") and rt.get("restored_hash")==source_hash)
            restored_core={"time":shadow.now,"region":str(shadow.actor("player")["region_id"]),"cash":int(shadow.actor("player")["cash_copper"])} if rt.get("ok") else None
            core_equal=restored_core==source_core
            if hash_equal and core_equal:
                mark_portable_bridge_verified(shadow,source_hash)

            before_search={"time":shadow.now,"region":str(shadow.actor("player")["region_id"]),"cash":int(shadow.actor("player")["cash_copper"])}
            search=shadow.process_player_turn("v10-shadow-find-borga","Иду искать Боргу.") if rt.get("ok") else None
            after_search={"time":shadow.now,"region":str(shadow.actor("player")["region_id"]),"cash":int(shadow.actor("player")["cash_copper"])} if rt.get("ok") else None
            search_ok=bool(search and search.get("accepted") and search.get("status")=="scene_pending" and before_search==after_search)
            pending_nav=shadow.db.execute("SELECT COUNT(*) FROM scene_pending_resolution WHERE resolution_kind='local_navigation' AND status='pending'").fetchone()[0] if rt.get("ok") else 0

            exec_before=shadow.db.execute("SELECT COUNT(*) FROM autonomy_execution_log").fetchone()[0] if rt.get("ok") else 0
            wait=shadow.process_player_turn("v10-shadow-wait","жду 15 минут") if rt.get("ok") else None
            exec_after=shadow.db.execute("SELECT COUNT(*) FROM autonomy_execution_log").fetchone()[0] if rt.get("ok") else 0
            autonomy_ok=bool(wait and wait.get("accepted") and wait.get("status")=="executed" and exec_after>exec_before)
            player_safe=bool(rt.get("ok") and str(shadow.actor("player")["region_id"])==source_core["region"] and int(shadow.actor("player")["cash_copper"])==source_core["cash"])

            shadow_ok=bool(hash_equal and core_equal and search_ok and pending_nav>0 and autonomy_ok and player_safe)
            if shadow_ok:
                mark_v10_shadow_verified(shadow,["local_search_pending_no_teleport",f"autonomy_executions:+{exec_after-exec_before}","player_cash_region_preserved"])
            active=[str(r[0]) for r in shadow.db.execute("SELECT gate_code FROM cutover_gate WHERE status!='resolved' ORDER BY gate_code").fetchall()]
            packet=shadow.build_gm_packet("player") if rt.get("ok") else {}
            report.update({
                "portable_checkpoint":{"schema_version":snap["schema_version"],"engine_version":snap["engine_version"],"state_hash":source_hash,
                                       "byte_count":snap["transport_meta"]["byte_count"],"roundtrip_ok":bool(rt.get("ok")),"hash_equal":hash_equal,"critical_core_equal":core_equal},
                "shadow_scene":{"action":"Иду искать Боргу.","status":search.get("status") if search else None,"accepted":search.get("accepted") if search else None,
                                "core_state_unchanged":before_search==after_search,"pending_navigation":int(pending_nav)},
                "shadow_autonomy":{"wait_status":wait.get("status") if wait else None,"wait_accepted":wait.get("accepted") if wait else None,
                                   "execution_delta":int(exec_after-exec_before),"player_cash_region_preserved":player_safe},
                "cutover_blockers":active,
                "live_cutover_ready":bool(shadow_ok and not active),
                "gm_packet_chars":packet.get("packet_meta",{}).get("chars"),
                "technical_success":shadow_ok,
            })
            return report


if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--repo-root",default=".."); p.add_argument("--out")
    a=p.parse_args(); result=run(a.repo_root); text=json.dumps(result,ensure_ascii=False,indent=2); print(text)
    if a.out: Path(a.out).write_text(text,encoding="utf-8")
    raise SystemExit(0 if result.get("technical_success") else 2)
