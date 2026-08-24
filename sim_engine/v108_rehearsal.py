from __future__ import annotations

import argparse, json, tempfile
from pathlib import Path
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v107_repository import load_repository_runtime_v107
from v108_seed import seed_world_v108_migration
from v108_runtime import BAD_APPROACH_TURNS_V108

PROBE_TEXT="Подхожу к Борге."


def _pending(world,key):
    return [dict(r) for r in world.db.execute(
        "SELECT p.id,p.resolution_kind,p.target_key,p.status FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.turn_key=? ORDER BY p.id",(key,)).fetchall()]


def rehearse_v108(repo_root: str | Path) -> dict:
    root=Path(repo_root).resolve()
    with tempfile.TemporaryDirectory() as td:
        source,pointer,_=load_repository_runtime_v107(root,Path(td)/"source.db")
        try:
            if pointer.get("engine_version")!="1.0.7": raise RuntimeError("v1.0.8 rehearsal requires v1.0.7 LIVE")
            base_seq=int(pointer["journal_seq"]); old_head=str(pointer["head_state_hash"]); t0=int(source.now)
            cash0=int(source.actor("player")["cash_copper"]); region0=str(source.actor("player")["region_id"])
            memories0=list((source.character_core_v104("borga") or {}).get("memories") or [])
            if not memories0: raise RuntimeError("LIVE rehearsal expected causal Borga greeting memory before v1.0.8")
            if not any(str(x.get("actor") or "")=="borga" and x.get("status")=="visible" for x in source._visible_named103("player")):
                raise RuntimeError("LIVE rehearsal requires Borga direct visibility")
            before={k:_pending(source,k) for k in BAD_APPROACH_TURNS_V108}
            stale=[r["id"] for rows in before.values() for r in rows if r["resolution_kind"]=="local_navigation" and r["status"]=="pending"]
            if len(stale)!=2: raise RuntimeError("LIVE rehearsal expected exactly two stale approach pendings")
            snapshot=export_portable_checkpoint_v100(source,int(pointer["source_live_version"]))
            if snapshot["state_hash"]!=old_head: raise RuntimeError("LIVE snapshot mismatch")
        finally: source.close()

        world=seed_world_v108_migration(Path(td)/"candidate.db")
        try:
            restored=import_portable_checkpoint_v100(world,snapshot)
            if not restored.get("ok") or restored.get("restored_hash")!=old_head: raise RuntimeError("candidate import failed")
            activation=world.execute_runtime_event(base_seq+1,f"rehearsal-v108-activation-j{base_seq+1:06d}","visible_local_approach_repair_activation",{"reason":"rehearsal"})["journal"]
            if int(world.now)!=t0 or int(world.actor("player")["cash_copper"])!=cash0 or str(world.actor("player")["region_id"])!=region0:
                raise RuntimeError("activation changed gameplay state")
            if list((world.character_core_v104("borga") or {}).get("memories") or [])!=memories0: raise RuntimeError("activation changed Borga memory")
            after={k:_pending(world,k) for k in BAD_APPROACH_TURNS_V108}
            if any(r["resolution_kind"]=="local_navigation" and r["status"]=="pending" for rows in after.values() for r in rows):
                raise RuntimeError("activation left stale local_navigation pending")
            approach=world.execute_runtime_event(base_seq+2,f"rehearsal-v108-approach-borga-j{base_seq+2:06d}","player_turn",{"raw_text":PROBE_TEXT})["journal"]
            result=approach.get("result") or {}; effect=result.get("result") or {}
            if result.get("status")!="executed" or effect.get("outcome")!="approached_visible_named_actor": raise RuntimeError("visible Borga approach did not resolve")
            if effect.get("approach_minutes")!=0 or int(world.now)!=t0: raise RuntimeError("same-scene approach advanced minute clock")
            if list((world.character_core_v104("borga") or {}).get("memories") or [])!=memories0: raise RuntimeError("movement alone created Borga memory")
            probe_pending=world.db.execute("SELECT COUNT(*) FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.turn_key=? AND p.status='pending'",(f"rehearsal-v108-approach-borga-j{base_seq+2:06d}",)).fetchone()[0]
            if probe_pending: raise RuntimeError("resolved visible approach created pending")
            final_hash=runtime_state_hash_v100(world,int(pointer["source_live_version"]))
        finally: world.close()

        verifier=seed_world_v108_migration(Path(td)/"verify.db")
        try:
            check=import_portable_checkpoint_v100(verifier,snapshot)
            if not check.get("ok") or check.get("restored_hash")!=old_head: raise RuntimeError("verifier import failed")
            replay=verifier.replay_runtime_entries([activation,approach])
            if not replay.get("ok"): raise RuntimeError("v1.0.8 rehearsal replay failed:"+str(replay))
            if runtime_state_hash_v100(verifier,int(pointer["source_live_version"]))!=final_hash: raise RuntimeError("v1.0.8 replay hash mismatch")
        finally: verifier.close()
    return {"ok":True,"source_seq":base_seq,"source_head":old_head,"world_minute":t0,"stale_pending_ids":stale,
            "stale_pending_repaired":True,"borga_memories_preserved":len(memories0),"probe_text":PROBE_TEXT,
            "visible_approach_executed":True,"approach_minutes":0,"movement_created_memory":False,"replay_hash":final_hash}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",default=".."); ap.add_argument("--out"); args=ap.parse_args(); result=rehearse_v108(args.repo_root)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out: Path(args.out).write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__": main()
