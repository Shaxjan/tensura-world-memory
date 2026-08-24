from __future__ import annotations

import argparse, json, tempfile
from pathlib import Path
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v108_repository import load_repository_runtime_v108
from v109_seed import seed_world_v109_migration


def activate_v109(repo_root: str | Path) -> dict:
    root=Path(repo_root).resolve(); pointer_path=root/"runtime/runtime_state.json"; pointer=json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("engine_version")=="1.0.9": return {"ok":True,"already_active":True,"journal_seq":pointer["journal_seq"]}
    if pointer.get("engine_version")!="1.0.8" or pointer.get("mode")!="engine_authoritative": raise RuntimeError("v1.0.9 activation requires v1.0.8 authoritative runtime")
    old_session=json.loads((root/str(pointer.get("session_state") or "runtime/session_state.json")).read_text(encoding="utf-8"))
    if int(old_session.get("journal_seq",-1))!=int(pointer["journal_seq"]): raise RuntimeError("stale session before v1.0.9 activation")
    base_seq=int(pointer["journal_seq"]); old_head=str(pointer["head_state_hash"]); activation_seq=base_seq+1
    with tempfile.TemporaryDirectory() as td:
        source,loaded,_=load_repository_runtime_v108(root,Path(td)/"source.db")
        try:
            if loaded["head_state_hash"]!=old_head or int(loaded["journal_seq"])!=base_seq: raise RuntimeError("pointer changed during v1.0.9 activation")
            t0=int(source.now); cash0=int(source.actor("player")["cash_copper"]); region0=str(source.actor("player")["region_id"])
            memories0=list((source.character_core_v104("borga") or {}).get("memories") or [])
            current_pending=[int(r[0]) for r in source.db.execute("SELECT p.id FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.actor_id='player' AND p.status='pending' ORDER BY p.id").fetchall()]
            snapshot=export_portable_checkpoint_v100(source,int(pointer["source_live_version"]))
            if snapshot["state_hash"]!=old_head: raise RuntimeError("v1.0.9 compact base mismatch")
        finally: source.close()
        world=seed_world_v109_migration(Path(td)/"v109.db")
        try:
            restored=import_portable_checkpoint_v100(world,snapshot)
            if not restored.get("ok") or restored.get("restored_hash")!=old_head: raise RuntimeError("v1.0.9 base roundtrip failed")
            event_key=f"system-v109-session-readmodel-repair-j{activation_seq:06d}"
            entry=world.execute_runtime_event(activation_seq,event_key,"session_readmodel_repair_activation",{
                "reason":"project last_turn pending list from current authoritative pending rows; remove repaired stale snapshots",
                "source_engine":"1.0.8","target_engine":"1.0.9"})["journal"]
            final_hash=str(entry["after_hash"])
            if int(world.now)!=t0 or int(world.actor("player")["cash_copper"])!=cash0 or str(world.actor("player")["region_id"])!=region0: raise RuntimeError("v1.0.9 activation changed gameplay state")
            if list((world.character_core_v104("borga") or {}).get("memories") or [])!=memories0: raise RuntimeError("v1.0.9 activation changed Borga memory")
            session=world.build_session_state_v109(journal_seq=activation_seq,head_state_hash=final_hash,last_event=entry,preserved_last_turn=old_session.get("last_turn"))
            if (session.get("last_turn") or {}).get("event_key")!=(old_session.get("last_turn") or {}).get("event_key"): raise RuntimeError("v1.0.9 replaced last gameplay turn")
            session_pending=[int(r["id"]) for r in ((session.get("last_turn") or {}).get("pending_resolutions") or [])]
            if session_pending!=current_pending: raise RuntimeError(f"v1.0.9 last_turn pending projection mismatch: {session_pending} != {current_pending}")
        finally: world.close()
        verifier=seed_world_v109_migration(Path(td)/"verify.db")
        try:
            check=import_portable_checkpoint_v100(verifier,snapshot)
            if not check.get("ok") or check.get("restored_hash")!=old_head: raise RuntimeError("v1.0.9 verifier import failed")
            replay=verifier.replay_runtime_entries([entry])
            if not replay.get("ok"): raise RuntimeError("v1.0.9 replay failed:"+str(replay))
            if runtime_state_hash_v100(verifier,int(pointer["source_live_version"]))!=final_hash: raise RuntimeError("v1.0.9 final hash mismatch")
        finally: verifier.close()
    checkpoint_rel=f"runtime/checkpoints/v109_base_j{base_seq:06d}.json"; checkpoint_path=root/checkpoint_rel; journal_path=root/pointer["journal_dir"]/f"j{activation_seq:06d}.json"
    if checkpoint_path.exists() or journal_path.exists(): raise RuntimeError("v1.0.9 activation output exists")
    checkpoint_path.parent.mkdir(parents=True,exist_ok=True); checkpoint_path.write_text(json.dumps(snapshot,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    journal_path.write_text(json.dumps(entry,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); (root/"runtime/session_state.json").write_text(json.dumps(session,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    pointer.update({"engine_version":"1.0.9","base_checkpoint":checkpoint_rel,"base_state_hash":old_head,"journal_base_seq":base_seq,"journal_seq":activation_seq,"head_state_hash":final_hash,"last_event":str(Path(pointer["journal_dir"])/f"j{activation_seq:06d}.json"),"session_state":"runtime/session_state.json"})
    pointer["write_protocol"]["session_readmodel_authoritative_pending_projection"]=True
    pointer["system_activation"]={"event":pointer["last_event"],"kind":"session_readmodel_repair_v109","world_time_advanced":0,"player_choice":False}
    pointer_path.write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"ok":True,"already_active":False,"journal_seq":activation_seq,"checkpoint":checkpoint_rel,"head_state_hash":final_hash,"current_pending_ids":current_pending,"last_turn_pending_ids":session_pending,"borga_memories_preserved":len(memories0)}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",default=".."); ap.add_argument("--out"); args=ap.parse_args(); result=activate_v109(args.repo_root)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out: Path(args.out).write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__": main()
