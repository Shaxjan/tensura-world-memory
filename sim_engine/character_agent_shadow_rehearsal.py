from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from character_agent_contract import DECISION_FORMAT
from character_agent_shadow import CharacterAgentShadowRunner
from rena_character_profile import EVIDENCE, build_rena_agent_context_v1


def _scripted_shadow_provider(context):
    turn_key = context["source_turn_key"]
    utterance_key = context["player_input"]["observation_key"]
    return {
        "format": DECISION_FORMAT,
        "schema_version": 1,
        "actor_key": "rena",
        "source_turn_key": turn_key,
        "decision_kind": "speak_and_act",
        "observable": {
            "speech_act": "tease",
            "surface_text": "Стараешься, павлин. Но можешь лучше.",
            "action_kind": "gesture",
            "target_key": "player",
            "clock_minutes": 0,
        },
        "grounding": {
            "fact_refs": [
                utterance_key,
                EVIDENCE["engagement"],
                "obs:shadow:rena-and-player-same-scene",
            ],
            "asserted_claims": [
                {
                    "claim": "the player is directly present and addressed Rena now",
                    "fact_refs": [utterance_key, "obs:shadow:rena-and-player-same-scene"],
                }
            ],
        },
        "private": {
            "emotion_state": "amused",
            "relationship_delta": {"affection": 1},
            "memory_proposals": [
                {
                    "kind": "episodic_interaction",
                    "summary": "The player playfully teased Rena in the shadow scene.",
                    "source_fact_refs": [utterance_key],
                }
            ],
            "rationale": "Scripted rehearsal output exercises the contract; it is not LIVE dialogue.",
        },
    }


def rehearse_rena_shadow(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer_path = root / "runtime/runtime_state.json"
    session_path = root / "runtime/session_state.json"
    pointer_before = pointer_path.read_bytes()
    session_before = session_path.read_bytes()
    pointer = json.loads(pointer_before.decode("utf-8"))

    context = build_rena_agent_context_v1(
        source_turn_key="rehearsal-shadow-rena-tease-v1",
        world_minute=188249,
        player_utterance="Подхожу к Рене и с улыбкой дразню её.",
        causal_fact_keys=[EVIDENCE["engagement"], EVIDENCE["current_relationship"]],
        observations=[
            {
                "fact_key": "obs:shadow:rena-and-player-same-scene",
                "kind": "direct_observation",
                "subject": "player",
                "predicate": "visible_in_same_scene",
            }
        ],
        visible_target_keys=["player"],
        current_plan={
            "kind": "social_presence",
            "place_key": "shadow_fixture_grounded_scene",
            "authority": "SHADOW_FIXTURE_ONLY",
        },
        relationship_state={
            "counterpart_key": "player",
            "status": "engaged",
            "evidence_refs": [EVIDENCE["engagement"], EVIDENCE["current_relationship"]],
        },
    )

    calls = {"count": 0}

    def provider(ctx):
        calls["count"] += 1
        return _scripted_shadow_provider(ctx)

    with tempfile.TemporaryDirectory() as td:
        runner = CharacterAgentShadowRunner(Path(td) / "shadow-journal")
        first = runner.run(context, provider, provider_id="scripted-rehearsal-no-external-ai")
        if not first.get("accepted") or first.get("replayed") or not first.get("provider_called"):
            raise RuntimeError("first shadow decision was not generated and recorded exactly once")
        if calls["count"] != 1:
            raise RuntimeError("shadow provider call count mismatch after first pass")

        def poison_provider(_ctx):
            raise RuntimeError("provider recall during replay is forbidden")

        second = runner.run(context, poison_provider, provider_id="forbidden-replay-provider")
        if not second.get("accepted") or not second.get("replayed") or second.get("provider_called"):
            raise RuntimeError("duplicate shadow turn did not replay journaled decision")
        if first.get("decision_digest") != second.get("decision_digest"):
            raise RuntimeError("replay changed Character Agent decision digest")
        if first.get("public_observable") != second.get("public_observable"):
            raise RuntimeError("replay changed public observable")
        if calls["count"] != 1:
            raise RuntimeError("provider was recalled during replay")

        record_path = Path(first["record_path"])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if "context" in record or "raw_provider_output" in record:
            raise RuntimeError("shadow journal persisted forbidden raw material")
        if record.get("authority") != "SHADOW_NON_AUTHORITATIVE":
            raise RuntimeError("shadow decision accidentally gained authoritative status")

    if pointer_path.read_bytes() != pointer_before or session_path.read_bytes() != session_before:
        raise RuntimeError("shadow rehearsal mutated authoritative LIVE files")

    return {
        "ok": True,
        "live_engine_version": pointer.get("engine_version"),
        "live_seq_unchanged": pointer.get("journal_seq"),
        "provider_calls": calls["count"],
        "first_pass_replayed": first["replayed"],
        "second_pass_replayed": second["replayed"],
        "decision_digest_stable": first["decision_digest"] == second["decision_digest"],
        "public_observable_stable": first["public_observable"] == second["public_observable"],
        "raw_context_persisted": False,
        "raw_provider_output_persisted": False,
        "live_files_unchanged": True,
        "authority": "SHADOW_NON_AUTHORITATIVE",
        "note": "Scripted provider only; this rehearsal does not claim the generated line is canonical Rena dialogue.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = rehearse_rena_shadow(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
