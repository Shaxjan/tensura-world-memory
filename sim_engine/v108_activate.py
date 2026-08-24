from __future__ import annotations

import argparse, json, tempfile
from pathlib import Path
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v107_repository import load_repository_runtime_v107
from v108_seed import seed_world_v108_migration
from v108_runtime import BAD_APPROACH_TURNS_V108


def _pending_for_turn(world, turn_key):
    return [dict(r) for r in world.db.execute(
        "SELECT p.id,p.resolution_kind,p.target_key,p.status FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.turn_key=? ORDER BY p.id",
        (turn_key,),
    ).fetchall()]


def activate_v108(repo_root: str | Path) -> dict:
    root=Path(repo_root).resolve(); pointer_path=root/"runtime/runtime_state.json"; pointer=json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("engine_version") == "1.0.8":
        return {"ok":True,"already_active":True,"journal_seq":pointer["journal_seq"]}
    if pointer.get("engine_version") != "1.0.7" or pointer.get("mode") != "engine_authoritative":
        raise RuntimeError("v1.0.8 activation requires v1.0.7 authoritative runtime")
    old_session=json.loads((root/str(pointer.get("session_state") or "runtime/session_state.json")).read_text(encoding="utf-8"))
    if int(old_session.get("journal_seq",-1)) != int(pointer["journal_seq"]): raise RuntimeError("stale session before v1.0.8 activation")
    base_seq=int(pointer["journal_seq"]); old_head=str(pointer["head_state_hash"]); activation_seq=base_seq+1

    with tempfile.TemporaryDirectory() as td:
        source, loaded, _ = load_repository_runtime_v107(root, Path(td)/"source.db")
        try:
            if loaded["head_state_hash"] != old_head or int(loaded["journal_seq"]) != base_seq: raise RuntimeError("pointer changed during v1.0.8 activation")
            source_time=int(source.now); source_cash=int(source.actor("player")["cash_copper"]); source_region=str(source.actor("player")["region_id"])
            source_core=source.character_core_v104("borga") or {}; source_memories=list(source_core.get("memories") or [])
            before_pending={k:_pending_for_turn(source,k) for k in BAD_APPROACH_TURNS_V108}
            snapshot=export_portable_checkpoint_v100(source,int(pointer["source_live_version"]))
            if snapshot["state_hash"] != old_head: raise RuntimeError("v1.0.8 compact base mismatch")
        finally: source.close()

        world=seed_world_v108_migration(Path(td)/"v108.db")
        try:
            restored=import_portable_checkpoint_v100(world,snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != old_head: raise RuntimeError("v1.0.8 base roundtrip failed")
            event_key=f"system-v108-visible-local-approach-repair-j{activation_seq:06d}"
            executed=world.execute_runtime_event(activation_seq,event_key,"visible_local_approach_repair_activation",{
                "reason":"cancel stale local_navigation pendings created for same-scene approach while Borga was already visible; enable finite explicit visible-NPC approach",
                "source_engine":"1.0.7","target_engine":"1.0.8"})
            entry=executed["journal"]; final_hash=str(entry["after_hash"])
            if int(world.now) != source_time: raise RuntimeError("v1.0.8 activation changed world time")
            if int(world.actor("player")["cash_copper"]) != source_cash: raise RuntimeError("v1.0.8 activation changed player cash")
            if str(world.actor("player")["region_id"]) != source_region: raise RuntimeError("v1.0.8 activation changed player region")
            if list((world.character_core_v104("borga") or {}).get("memories") or []) != source_memories: raise RuntimeError("v1.0.8 activation changed Borga memories")
            after_pending={k:_pending_for_turn(world,k) for k in BAD_APPROACH_TURNS_V108}
            for key, rows in after_pending.items():
                if any(r["resolution_kind"]=="local_navigation" and r["status"]=="pending" for r in rows): raise RuntimeError(f"v1.0.8 left stale approach pending: {key}")
            session=world.build_session_state_v108(journal_seq=activation_seq,head_state_hash=final_hash,last_event=entry,preserved_last_turn=old_session.get("last_turn"))
            if session.get("last_turn") != old_session.get("last_turn"): raise RuntimeError("v1.0.8 activation replaced last gameplay turn")
        finally: world.close()

        verifier=seed_world_v108_migration(Path(td)/"verify.db")
        try:
            check=import_portable_checkpoint_v100(verifier,snapshot)
            if not check.get("ok") or check.get("restored_hash") != old_head: raise RuntimeError("v1.0.8 verifier base import failed")
            replay=verifier.replay_runtime_entries([entry])
            if not replay.get("ok"): raise RuntimeError("v1.0.8 activation replay failed:"+str(replay))
            if runtime_state_hash_v100(verifier,int(pointer["source_live_version"])) != final_hash: raise RuntimeError("v1.0.8 final head mismatch")
        finally: verifier.close()

    checkpoint_rel=f"runtime/checkpoints/v108_base_j{base_seq:06d}.json"; checkpoint_path=root/checkpoint_rel
    journal_path=root/pointer["journal_dir"]/f"j{activation_seq:06d}.json"
    if checkpoint_path.exists() or journal_path.exists(): raise RuntimeError("v1.0.8 activation output exists")
    checkpoint_path.parent.mkdir(parents=True,exist_ok=True); checkpoint_path.write_text(json.dumps(snapshot,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    journal_path.write_text(json.dumps(entry,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (root/"runtime/session_state.json").write_text(json.dumps(session,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    pointer.update({"engine_version":"1.0.8","base_checkpoint":checkpoint_rel,"base_state_hash":old_head,"journal_base_seq":base_seq,
                    "journal_seq":activation_seq,"head_state_hash":final_hash,"last_event":str(Path(pointer["journal_dir"])/f"j{activation_seq:06d}.json"),"session_state":"runtime/session_state.json"})
    pointer["write_protocol"]["visible_local_approach"]=True
    pointer["system_activation"]={"event":pointer["last_event"],"kind":"visible_local_approach_repair_v108","world_time_advanced":0,"player_choice":False}
    pointer_path.write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"ok":True,"already_active":False,"journal_seq":activation_seq,"head_state_hash":final_hash,"checkpoint":checkpoint_rel,
            "pending_before":before_pending,"pending_after":after_pending,"borga_memories_preserved":len(source_memories),"last_gameplay_turn_preserved":True}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",default=".."); ap.add_argument("--out"); args=ap.parse_args(); result=activate_v108(args.repo_root)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out: Path(args.out).write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__ == "__main__": main()
