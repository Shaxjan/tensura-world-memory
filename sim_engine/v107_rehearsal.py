from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v106_repository import load_repository_runtime_v106
from v107_seed import seed_world_v107_migration

PROBE_TEXT = "Говорю: «Борга, доброе утро.»"


def rehearse_v107(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    with tempfile.TemporaryDirectory() as td:
        source, pointer, _ = load_repository_runtime_v106(root, Path(td) / "source.db")
        try:
            if pointer.get("engine_version") != "1.0.6":
                raise RuntimeError("v1.0.7 rehearsal requires current v1.0.6 LIVE")
            base_seq = int(pointer["journal_seq"])
            old_head = str(pointer["head_state_hash"])
            t0 = int(source.now)
            cash0 = int(source.actor("player")["cash_copper"])
            region0 = str(source.actor("player")["region_id"])
            core0 = source.character_core_v104("borga") or {}
            memories0 = list(core0.get("memories") or [])
            visible0 = source._borga_visible_to_player_v107("player") if hasattr(source, "_borga_visible_to_player_v107") else any(
                str(row.get("actor") or "") == "borga" for row in source._visible_named103("player")
            )
            if not visible0:
                raise RuntimeError("LIVE rehearsal requires Borga direct visibility from r000009")
            snapshot = export_portable_checkpoint_v100(source, int(pointer["source_live_version"]))
            if snapshot["state_hash"] != old_head:
                raise RuntimeError("LIVE snapshot mismatch")
        finally:
            source.close()

        world = seed_world_v107_migration(Path(td) / "candidate.db")
        try:
            restored = import_portable_checkpoint_v100(world, snapshot)
            if not restored.get("ok") or restored.get("restored_hash") != old_head:
                raise RuntimeError("candidate base import failed")
            activation = world.execute_runtime_event(
                base_seq + 1,
                f"rehearsal-v107-activation-j{base_seq+1:06d}",
                "causal_encounter_memory_activation",
                {"reason": "rehearsal"},
            )["journal"]
            core_after_activation = world.character_core_v104("borga") or {}
            if list(core_after_activation.get("memories") or []) != memories0:
                raise RuntimeError("activation retroactively created Borga memory")
            if int(world.now) != t0 or int(world.actor("player")["cash_copper"]) != cash0 or str(world.actor("player")["region_id"]) != region0:
                raise RuntimeError("activation changed gameplay state")

            relationships_before = dict(core_after_activation.get("relationships") or {})
            interaction = world.execute_runtime_event(
                base_seq + 2,
                f"rehearsal-v107-address-borga-j{base_seq+2:06d}",
                "player_turn",
                {"raw_text": PROBE_TEXT},
            )["journal"]
            result = interaction.get("result") or {}
            if not result.get("accepted"):
                raise RuntimeError("addressed Borga probe was not accepted")
            memory_key = f"v107:character_memory:borga:rehearsal-v107-address-borga-j{base_seq+2:06d}"
            memory = world._get_fact103(memory_key)
            if not memory:
                raise RuntimeError("accepted directly addressed visible Borga interaction created no memory")
            if memory.get("observed_player_text_verbatim") != PROBE_TEXT:
                raise RuntimeError("memory did not preserve observed player text")
            if memory.get("emotional_interpretation") is not None or memory.get("relationship_delta") is not None:
                raise RuntimeError("memory invented emotion or relationship delta")
            core1 = world.character_core_v104("borga") or {}
            refs = list(core1.get("memories") or [])
            if not any(isinstance(row, dict) and row.get("memory_key") == memory_key for row in refs):
                raise RuntimeError("Character Core did not reference encounter memory")
            if dict(core1.get("relationships") or {}) != relationships_before:
                raise RuntimeError("v1.0.7 encounter memory mutated relationships")
            if world.db.execute("SELECT 1 FROM actors WHERE id='borga'").fetchone() is not None:
                raise RuntimeError("v1.0.7 falsely materialized Borga as generic actor")
            final_hash = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
        finally:
            world.close()

        verifier = seed_world_v107_migration(Path(td) / "verify.db")
        try:
            check = import_portable_checkpoint_v100(verifier, snapshot)
            if not check.get("ok") or check.get("restored_hash") != old_head:
                raise RuntimeError("verifier base import failed")
            replay = verifier.replay_runtime_entries([activation, interaction])
            if not replay.get("ok"):
                raise RuntimeError("v1.0.7 rehearsal replay failed:" + str(replay))
            replay_hash = runtime_state_hash_v100(verifier, int(pointer["source_live_version"]))
            if replay_hash != final_hash:
                raise RuntimeError("v1.0.7 rehearsal replay hash mismatch")
        finally:
            verifier.close()

    return {
        "ok": True,
        "source_seq": base_seq,
        "source_head": old_head,
        "world_minute": t0,
        "prior_memories": len(memories0),
        "activation_retroactive_memory": False,
        "probe_text": PROBE_TEXT,
        "direct_address_memory_created": True,
        "relationships_unchanged": True,
        "generic_borga_actor_materialized": False,
        "replay_hash": final_hash,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = rehearse_v107(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
