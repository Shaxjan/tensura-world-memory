from __future__ import annotations

import argparse, json, tempfile
from pathlib import Path
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v108_repository import load_repository_runtime_v108
from v109_seed import seed_world_v109_migration


def _changed_tables(before: dict, after: dict) -> list[str]:
    bt, at = before.get("tables") or {}, after.get("tables") or {}
    return [k for k in sorted(set(bt) | set(at)) if bt.get(k) != at.get(k)]


def rehearse_v109(repo_root: str | Path) -> dict:
    root=Path(repo_root).resolve(); old_session=json.loads((root/"runtime/session_state.json").read_text(encoding="utf-8"))
    stale_ids=[int(r["id"]) for r in ((old_session.get("last_turn") or {}).get("pending_resolutions") or [])]
    if stale_ids != [3,4]: raise RuntimeError(f"v1.0.9 LIVE rehearsal expected stale last_turn pending [3,4], got {stale_ids}")
    if list((old_session.get("scene") or {}).get("pending_resolutions") or []): raise RuntimeError("current LIVE scene unexpectedly has active pending")
    with tempfile.TemporaryDirectory() as td:
        source,pointer,_=load_repository_runtime_v108(root,Path(td)/"source.db")
        try:
            if pointer.get("engine_version")!="1.0.8": raise RuntimeError("v1.0.9 rehearsal requires v1.0.8 LIVE")
            base_seq=int(pointer["journal_seq"]); old_head=str(pointer["head_state_hash"]); t0=int(source.now); cash0=int(source.actor("player")["cash_copper"]); region0=str(source.actor("player")["region_id"])
            memories0=list((source.character_core_v104("borga") or {}).get("memories") or [])
            current_pending=[int(r[0]) for r in source.db.execute("SELECT p.id FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.actor_id='player' AND p.status='pending' ORDER BY p.id").fetchall()]
            if current_pending: raise RuntimeError(f"v1.0.9 expected no current authoritative pending, got {current_pending}")
            snapshot=export_portable_checkpoint_v100(source,int(pointer["source_live_version"]))
            if snapshot["state_hash"]!=old_head: raise RuntimeError("LIVE snapshot mismatch")
        finally: source.close()
        world=seed_world_v109_migration(Path(td)/"candidate.db")
        try:
            restored=import_portable_checkpoint_v100(world,snapshot)
            if not restored.get("ok") or restored.get("restored_hash")!=old_head: raise RuntimeError("candidate import failed")
            entry=world.execute_runtime_event(base_seq+1,f"rehearsal-v109-activation-j{base_seq+1:06d}","session_readmodel_repair_activation",{"reason":"rehearsal"})["journal"]
            event_hash=runtime_state_hash_v100(world,int(pointer["source_live_version"]))
            if event_hash != entry["after_hash"]: raise RuntimeError("v1.0.9 event hash mismatch before session build")
            if int(world.now)!=t0 or int(world.actor("player")["cash_copper"])!=cash0 or str(world.actor("player")["region_id"])!=region0: raise RuntimeError("v1.0.9 activation changed gameplay state")
            if list((world.character_core_v104("borga") or {}).get("memories") or [])!=memories0: raise RuntimeError("v1.0.9 activation changed Borga memories")
            state_before=export_portable_checkpoint_v100(world,int(pointer["source_live_version"]))
            state=world.build_session_state_v109(journal_seq=base_seq+1,head_state_hash=entry["after_hash"],last_event=entry,preserved_last_turn=old_session.get("last_turn"))
            state_after=export_portable_checkpoint_v100(world,int(pointer["source_live_version"]))
            changed=_changed_tables(state_before,state_after)
            if changed: raise RuntimeError("session builder mutated authoritative tables: "+",".join(changed))
            if runtime_state_hash_v100(world,int(pointer["source_live_version"])) != event_hash: raise RuntimeError("session builder changed authoritative hash without exported table diff")
            if (state.get("last_turn") or {}).get("event_key")!=(old_session.get("last_turn") or {}).get("event_key"): raise RuntimeError("last gameplay turn replaced")
            if list((state.get("last_turn") or {}).get("pending_resolutions") or []): raise RuntimeError("stale last_turn pending survived v1.0.9")
            if list((state.get("scene") or {}).get("pending_resolutions") or []): raise RuntimeError("current scene pending not empty after v1.0.9")
            if (state.get("last_turn") or {}).get("narration_contract",{}).get("player_text_verbatim") != (old_session.get("last_turn") or {}).get("narration_contract",{}).get("player_text_verbatim"): raise RuntimeError("greeting text changed")
            final_hash=event_hash
        finally: world.close()
        verifier=seed_world_v109_migration(Path(td)/"verify.db")
        try:
            check=import_portable_checkpoint_v100(verifier,snapshot)
            if not check.get("ok") or check.get("restored_hash")!=old_head: raise RuntimeError("verifier import failed")
            replay=verifier.replay_runtime_entries([entry])
            if not replay.get("ok"): raise RuntimeError("v1.0.9 rehearsal replay failed:"+str(replay))
            if runtime_state_hash_v100(verifier,int(pointer["source_live_version"]))!=final_hash: raise RuntimeError("v1.0.9 replay hash mismatch")
        finally: verifier.close()
    return {"ok":True,"source_seq":base_seq,"source_head":old_head,"world_minute":t0,"stale_last_turn_pending_ids":stale_ids,"authoritative_pending_ids":current_pending,"sanitized_last_turn_pending_ids":[],"borga_memories_preserved":len(memories0),"last_gameplay_turn_preserved":True,"session_builder_pure":True,"replay_hash":final_hash}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",default=".."); ap.add_argument("--out"); args=ap.parse_args(); result=rehearse_v109(args.repo_root)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out: Path(args.out).write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__": main()
