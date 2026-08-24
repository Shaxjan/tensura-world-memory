from __future__ import annotations

import argparse, json, tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v109_repository import load_repository_runtime_v109
from v110_seed import seed_world_v110_migration

TEST_GREETING = "Обращаюсь к Борге: «Доброе утро»."
OLD_GREETING_TURN = "chat-20260824-greet-borga-r000013"


def rehearse_v110(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    old_session = json.loads((root / "runtime/session_state.json").read_text(encoding="utf-8"))
    if (old_session.get("last_turn") or {}).get("event_key") != OLD_GREETING_TURN:
        raise RuntimeError("v1.0.10 rehearsal requires the preserved r000013 greeting as current last gameplay turn")
    if list((old_session.get("scene") or {}).get("pending_resolutions") or []):
        raise RuntimeError("v1.0.10 rehearsal requires no current scene pending")

    with tempfile.TemporaryDirectory() as td:
        source, pointer, _ = load_repository_runtime_v109(root, Path(td) / "source.db")
        try:
            if pointer.get("engine_version") != "1.0.9": raise RuntimeError("v1.0.10 rehearsal requires v1.0.9 LIVE")
            base_seq = int(pointer["journal_seq"]); old_head = str(pointer["head_state_hash"])
            t0 = int(source.now); cash0 = int(source.actor("player")["cash_copper"]); region0 = str(source.actor("player")["region_id"])
            core0 = source.character_core_v104("borga") or {}
            memories0 = list(core0.get("memories") or []); relationships0 = dict(core0.get("relationships") or {}); personality0 = dict(core0.get("personality") or {})
            if source._get_fact103(f"v107:character_memory:borga:{OLD_GREETING_TURN}") is None:
                raise RuntimeError("v1.0.10 rehearsal requires the existing causal memory of r000013")
            if source._get_fact103(f"v110:player_observed_response:borga:{OLD_GREETING_TURN}") is not None:
                raise RuntimeError("r000013 already has a response before v1.0.10")
            if not source._borga_visible_to_player_v107("player"):
                raise RuntimeError("v1.0.10 rehearsal requires Borga directly visible")
            place = source._place103("player") or {}
            presence = source._borga_presence103(source.now) or {}
            if place.get("key") != "eurazania_small_training_yard" or presence.get("place_key") != place.get("key"):
                raise RuntimeError("v1.0.10 rehearsal requires Borga grounded at the current small training yard")
            snapshot = export_portable_checkpoint_v100(source, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != old_head: raise RuntimeError("v1.0.10 LIVE snapshot mismatch")
        finally:
            source.close()

        world = seed_world_v110_migration(Path(td) / "candidate.db")
        try:
            restored = import_portable_checkpoint_v100(world, snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != old_head: raise RuntimeError("v1.0.10 candidate import failed")
            activation = world.execute_runtime_event(
                base_seq + 1,
                f"rehearsal-v110-activation-j{base_seq + 1:06d}",
                "causal_npc_response_activation",
                {"reason": "rehearsal"},
            )["journal"]
            if int(world.now) != t0 or int(world.actor("player")["cash_copper"]) != cash0 or str(world.actor("player")["region_id"]) != region0:
                raise RuntimeError("v1.0.10 activation changed gameplay state")
            if world._get_fact103(f"v110:player_observed_response:borga:{OLD_GREETING_TURN}") is not None:
                raise RuntimeError("v1.0.10 activation retroactively answered r000013")
            activation_session = world.build_session_state_v110(
                journal_seq=base_seq + 1,
                head_state_hash=activation["after_hash"],
                last_event=activation,
                preserved_last_turn=old_session.get("last_turn"),
            )
            if (activation_session.get("last_turn") or {}).get("event_key") != OLD_GREETING_TURN:
                raise RuntimeError("v1.0.10 activation replaced last gameplay turn")
            if ((activation_session.get("last_turn") or {}).get("action_result") or {}).get("outcome") == "npc_response_resolved":
                raise RuntimeError("v1.0.10 activation projected a retroactive response")

            greeting_key = "rehearsal-v110-greet-borga"
            greeting = world.execute_runtime_event(
                base_seq + 2,
                greeting_key,
                "player_turn",
                {"raw_text": TEST_GREETING},
            )["journal"]
            public = greeting.get("result") or {}
            result = public.get("result") or {}
            response = result.get("npc_response") or {}
            if result.get("outcome") != "npc_response_resolved":
                raise RuntimeError("v1.0.10 did not resolve the new greeting")
            if response.get("actor_key") != "borga" or response.get("speech_act") != "return_greeting":
                raise RuntimeError("v1.0.10 returned the wrong NPC response semantics")
            if response.get("surface_text") != "Доброе утро." or int(response.get("clock_minutes", -1)) != 0:
                raise RuntimeError("v1.0.10 greeting surface/clock mismatch")
            if response.get("emotion") is not None or response.get("relationship_delta") is not None or response.get("conversation_commitment") is not None:
                raise RuntimeError("v1.0.10 invented social state")
            if int(world.now) != t0:
                raise RuntimeError("v1.0.10 simple greeting advanced the minute clock")
            core1 = world.character_core_v104("borga") or {}
            if len(list(core1.get("memories") or [])) != len(memories0) + 1:
                raise RuntimeError("v1.0.10 new addressed greeting did not add exactly one causal memory")
            if dict(core1.get("relationships") or {}) != relationships0:
                raise RuntimeError("v1.0.10 greeting changed relationships")
            if dict(core1.get("personality") or {}) != personality0:
                raise RuntimeError("v1.0.10 greeting changed personality")
            pending = world.db.execute(
                "SELECT COUNT(*) FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.actor_id='player' AND p.status='pending'"
            ).fetchone()[0]
            if int(pending) != 0: raise RuntimeError("v1.0.10 simple greeting left a pending resolution")
            response_key = str(response.get("response_key") or "")
            known = world.db.execute("SELECT confidence,source FROM actor_knowledge WHERE actor_id='player' AND fact_key=?", (response_key,)).fetchone()
            if known is None or int(known["confidence"]) != 100:
                raise RuntimeError("v1.0.10 direct response was not recorded as player knowledge")

            final_hash = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
            if final_hash != greeting["after_hash"]: raise RuntimeError("v1.0.10 greeting hash mismatch")
            before_session_hash = final_hash
            session = world.build_session_state_v110(journal_seq=base_seq + 2, head_state_hash=final_hash, last_event=greeting)
            if runtime_state_hash_v100(world, int(pointer["source_live_version"])) != before_session_hash:
                raise RuntimeError("v1.0.10 session builder mutated authoritative state")
            last_result = (session.get("last_turn") or {}).get("action_result") or {}
            if last_result.get("outcome") != "npc_response_resolved":
                raise RuntimeError("v1.0.10 session did not expose the authoritative response outcome")
        finally:
            world.close()

        verifier = seed_world_v110_migration(Path(td) / "verify.db")
        try:
            check = import_portable_checkpoint_v100(verifier, snapshot)
            if not check.get("ok") or check.get("restored_hash") != old_head: raise RuntimeError("v1.0.10 verifier import failed")
            replay = verifier.replay_runtime_entries([activation, greeting])
            if not replay.get("ok"): raise RuntimeError("v1.0.10 replay failed:" + str(replay))
            if runtime_state_hash_v100(verifier, int(pointer["source_live_version"])) != final_hash:
                raise RuntimeError("v1.0.10 replay hash mismatch")
        finally:
            verifier.close()

    return {
        "ok": True,
        "source_seq": base_seq,
        "source_head": old_head,
        "world_minute": t0,
        "old_greeting_response_preserved_unresolved": True,
        "new_greeting_response": "Доброе утро.",
        "new_greeting_clock_minutes": 0,
        "memory_delta": 1,
        "relationship_delta": 0,
        "personality_delta": 0,
        "pending_after": 0,
        "session_builder_pure": True,
        "replay_hash": final_hash,
    }


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--repo-root", default=".."); ap.add_argument("--out"); args = ap.parse_args()
    result = rehearse_v110(args.repo_root); text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out: Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__": main()
