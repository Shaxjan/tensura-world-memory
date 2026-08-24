from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from character_agent_contract import DECISION_FORMAT
from character_agent_shadow import CharacterAgentShadowRunner
from v100_handoff import runtime_state_hash_v100
from v113_repository import load_repository_runtime_v113_candidate
from v113_runtime import RENA_RESPONSE_PREFIX_V113

TEST_UTTERANCE = "Подхожу к Рене и с улыбкой дразню её."
TEST_TURN_KEY = "rehearsal-v113-rena-tease"
TEST_OBSERVATION_KEY = "candidate:v113:direct-observation:rena-player-same-scene"
TEST_SURFACE = "Стараешься, павлин. Но можешь лучше."


def _scripted_provider(context):
    utterance_key = context["player_input"]["observation_key"]
    return {
        "format": DECISION_FORMAT,
        "schema_version": 1,
        "actor_key": "rena",
        "source_turn_key": context["source_turn_key"],
        "decision_kind": "speak_and_act",
        "observable": {
            "speech_act": "tease",
            "surface_text": TEST_SURFACE,
            "action_kind": "gesture",
            "target_key": "player",
            "clock_minutes": 0,
        },
        "grounding": {
            "fact_refs": [utterance_key, TEST_OBSERVATION_KEY],
            "asserted_claims": [
                {
                    "claim": "the player is directly present and addressed Rena now",
                    "fact_refs": [utterance_key, TEST_OBSERVATION_KEY],
                }
            ],
        },
        "private": {
            "emotion_state": "amused",
            "relationship_delta": {"affection": 1},
            "memory_proposals": [
                {
                    "kind": "episodic_interaction",
                    "summary": "The player playfully teased Rena in the v1.0.13 candidate rehearsal.",
                    "source_fact_refs": [utterance_key],
                }
            ],
            "rationale": "Scripted candidate fixture only; not canonical dialogue.",
        },
    }


def rehearse_v113(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer_path = root / "runtime/runtime_state.json"
    session_path = root / "runtime/session_state.json"
    pointer_before = pointer_path.read_bytes()
    session_before = session_path.read_bytes()
    source_session = json.loads(session_before.decode("utf-8"))

    with tempfile.TemporaryDirectory() as td:
        world, pointer, loaded = load_repository_runtime_v113_candidate(root, Path(td) / "candidate.db")
        try:
            base_seq = int(pointer["journal_seq"])
            source_hash = str(pointer["head_state_hash"])
            if loaded["head_hash"] != source_hash:
                raise RuntimeError("v1.0.13 candidate did not reproduce LIVE head before activation")
            if world.character_core_v113("rena") is not None or world.character_agent_state_v113("rena") is not None:
                raise RuntimeError("v1.0.13 candidate Rena state existed before activation")

            t0 = int(world.now)
            cash0 = int(world.actor("player")["cash_copper"])
            region0 = str(world.actor("player")["region_id"])
            before_activation_hash = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
            if before_activation_hash != source_hash:
                raise RuntimeError("v1.0.13 candidate pre-activation runtime hash mismatch")

            activation_out = world.execute_runtime_event(
                base_seq + 1,
                f"rehearsal-v113-activation-j{base_seq + 1:06d}",
                "character_agent_v113_activation",
                {"reason": "playable_alpha_candidate_rehearsal"},
            )
            activation = activation_out["journal"]
            activation_result = activation.get("result") or {}
            if not activation_result.get("accepted") or activation_result.get("retroactive_response_created"):
                raise RuntimeError("v1.0.13 candidate activation safety invariant failed")
            if int(world.now) != t0 or int(world.actor("player")["cash_copper"]) != cash0 or str(world.actor("player")["region_id"]) != region0:
                raise RuntimeError("v1.0.13 candidate activation changed player gameplay state")
            state0 = world.character_agent_state_v113("rena") or {}
            if list(state0.get("episodic_memories") or []):
                raise RuntimeError("v1.0.13 candidate activation created retroactive Rena memory")
            if any(int(v) != 0 for v in (state0.get("relationship_delta_since_activation") or {}).values()):
                raise RuntimeError("v1.0.13 candidate activation created relationship delta")
            if state0.get("last_private_emotion") is not None:
                raise RuntimeError("v1.0.13 candidate activation inferred current Rena emotion")

            session_hash_before = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
            activation_session = world.build_session_state_v113(
                journal_seq=base_seq + 1,
                head_state_hash=activation["after_hash"],
                last_event=activation,
                preserved_last_turn=source_session.get("last_turn"),
            )
            if runtime_state_hash_v100(world, int(pointer["source_live_version"])) != session_hash_before:
                raise RuntimeError("v1.0.13 session builder mutated candidate authoritative state")
            if activation_session.get("last_turn") != source_session.get("last_turn"):
                raise RuntimeError("v1.0.13 activation replaced the last real gameplay turn")

            context = world.build_rena_agent_context_v113(
                source_turn_key=TEST_TURN_KEY,
                player_utterance=TEST_UTTERANCE,
                causal_fact_keys=[],
                observations=[
                    {
                        "fact_key": TEST_OBSERVATION_KEY,
                        "kind": "candidate_rehearsal_direct_observation",
                        "subject": "player",
                        "predicate": "visible_in_same_scene",
                    }
                ],
                visible_target_keys=["player"],
                current_plan={
                    "kind": "candidate_rehearsal_fixture",
                    "authority": "CANDIDATE_REHEARSAL_ONLY",
                    "exact_live_location_asserted": False,
                },
            )

            provider_calls = {"count": 0}

            def provider(ctx):
                provider_calls["count"] += 1
                return _scripted_provider(ctx)

            shadow = CharacterAgentShadowRunner(Path(td) / "shadow")
            generated = shadow.run(context, provider, provider_id="scripted-v113-rehearsal-no-external-ai")
            if provider_calls["count"] != 1 or generated.get("replayed") or not generated.get("provider_called"):
                raise RuntimeError("v1.0.13 candidate did not generate exactly one new shadow decision")

            def poison_provider(_ctx):
                raise RuntimeError("provider recall during replay is forbidden")

            duplicate = shadow.run(context, poison_provider, provider_id="forbidden-replay-provider")
            if not duplicate.get("replayed") or duplicate.get("provider_called") or provider_calls["count"] != 1:
                raise RuntimeError("v1.0.13 shadow replay recalled provider")

            decision_out = world.execute_runtime_event(
                base_seq + 2,
                f"rehearsal-v113-decision-j{base_seq + 2:06d}",
                "character_agent_decision_v113",
                {
                    "mode": "candidate_rehearsal_fixture",
                    "context": context,
                    "decision": generated["decision"],
                },
            )
            decision_event = decision_out["journal"]
            result = decision_event.get("result") or {}
            response = result.get("npc_response") or {}
            if result.get("outcome") != "character_agent_response_committed":
                raise RuntimeError("v1.0.13 candidate decision did not commit")
            if response.get("actor_key") != "rena" or response.get("surface_text") != TEST_SURFACE:
                raise RuntimeError("v1.0.13 candidate committed wrong public Rena response")
            if response.get("private_state_exposed") is not False or result.get("private_state_exposed") is not False:
                raise RuntimeError("v1.0.13 candidate leaked private Character Agent state")
            if int(world.now) != t0 or int(world.actor("player")["cash_copper"]) != cash0 or str(world.actor("player")["region_id"]) != region0:
                raise RuntimeError("v1.0.13 zero-time candidate response changed unrelated player gameplay state")

            state1 = world.character_agent_state_v113("rena") or {}
            delta = state1.get("relationship_delta_since_activation") or {}
            if int(delta.get("affection", 0)) != 1:
                raise RuntimeError("v1.0.13 candidate relationship delta mismatch")
            if len(list(state1.get("episodic_memories") or [])) != 1:
                raise RuntimeError("v1.0.13 candidate episodic memory mismatch")
            if state1.get("last_private_emotion") != "amused":
                raise RuntimeError("v1.0.13 candidate private continuity state mismatch")
            response_key = RENA_RESPONSE_PREFIX_V113 + TEST_TURN_KEY
            known = world.db.execute(
                "SELECT confidence,source FROM actor_knowledge WHERE actor_id='player' AND fact_key=?",
                (response_key,),
            ).fetchone()
            if known is None or int(known["confidence"]) != 100:
                raise RuntimeError("v1.0.13 direct candidate response was not recorded as player knowledge")

            final_hash = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
            if final_hash != decision_event["after_hash"]:
                raise RuntimeError("v1.0.13 candidate final hash mismatch")

            session_hash_before = final_hash
            candidate_session = world.build_session_state_v113(
                journal_seq=base_seq + 2,
                head_state_hash=final_hash,
                last_event=decision_event,
                preserved_last_turn=source_session.get("last_turn"),
            )
            if runtime_state_hash_v100(world, int(pointer["source_live_version"])) != session_hash_before:
                raise RuntimeError("v1.0.13 candidate session projection mutated state")
            if candidate_session.get("last_turn") != source_session.get("last_turn"):
                raise RuntimeError("candidate rehearsal event replaced the last real gameplay turn")
            if (candidate_session.get("character_agent_runtime") or {}).get("production_gameplay_routing_enabled") is not False:
                raise RuntimeError("v1.0.13 candidate accidentally enabled production gameplay routing")
        finally:
            world.close()

        verifier, verify_pointer, _ = load_repository_runtime_v113_candidate(root, Path(td) / "verify.db")
        try:
            if verify_pointer["head_state_hash"] != source_hash:
                raise RuntimeError("v1.0.13 verifier did not start from current LIVE head")
            replay = verifier.replay_runtime_entries([activation, decision_event])
            if not replay.get("ok"):
                raise RuntimeError("v1.0.13 candidate full engine replay failed:" + str(replay))
            replay_hash = runtime_state_hash_v100(verifier, int(pointer["source_live_version"]))
            if replay_hash != final_hash:
                raise RuntimeError("v1.0.13 candidate replay hash mismatch")
            replay_state = verifier.character_agent_state_v113("rena") or {}
            if replay_state != state1:
                raise RuntimeError("v1.0.13 candidate replayed private character state differs")
        finally:
            verifier.close()

    if pointer_path.read_bytes() != pointer_before or session_path.read_bytes() != session_before:
        raise RuntimeError("v1.0.13 candidate rehearsal mutated repository LIVE files")

    return {
        "ok": True,
        "source_engine_version": "1.0.12",
        "candidate_engine_version": "1.0.13",
        "source_seq": base_seq,
        "candidate_activation_seq": base_seq + 1,
        "candidate_decision_seq": base_seq + 2,
        "world_minute_unchanged": t0,
        "player_cash_unchanged": cash0,
        "player_region_unchanged": region0,
        "last_real_gameplay_turn_preserved": True,
        "retroactive_response_created": False,
        "retroactive_memory_created": False,
        "relationship_delta_on_activation": 0,
        "provider_calls": provider_calls["count"],
        "provider_recalled_on_shadow_replay": False,
        "candidate_response_surface_fixture": TEST_SURFACE,
        "candidate_memory_count": 1,
        "candidate_affection_delta_since_activation": 1,
        "private_state_exposed": False,
        "candidate_final_hash": final_hash,
        "candidate_replay_hash": replay_hash,
        "deterministic_full_engine_replay": final_hash == replay_hash,
        "production_gameplay_routing_enabled": False,
        "live_files_unchanged": True,
        "note": "Rena response text is scripted rehearsal fixture data, not canonical dialogue.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = rehearse_v113(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
