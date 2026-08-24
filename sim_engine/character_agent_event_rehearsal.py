from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from character_agent_contract import DECISION_FORMAT, validate_agent_decision
from character_agent_event import (
    apply_character_decision_event,
    build_character_decision_event,
    character_decision_state_hash,
    initial_character_decision_state,
    replay_character_decision_events,
)
from character_agent_shadow import CharacterAgentShadowRunner
from rena_character_profile import EVIDENCE, build_rena_agent_context_v1


def _context(turn_key: str, utterance: str, *, include_guitar_fact: bool = False):
    facts = [EVIDENCE["engagement"], EVIDENCE["current_relationship"]]
    if include_guitar_fact:
        facts.append(EVIDENCE["current_concert"])
    return build_rena_agent_context_v1(
        source_turn_key=turn_key,
        world_minute=188249,
        player_utterance=utterance,
        causal_fact_keys=facts,
        observations=[
            {
                "fact_key": f"obs:event-rehearsal:{turn_key}:same-scene",
                "kind": "direct_observation",
                "subject": "player",
                "predicate": "visible_in_same_scene",
            }
        ],
        visible_target_keys=["player"],
        current_plan={
            "kind": "social_presence",
            "place_key": "candidate_fixture_grounded_scene",
            "authority": "CANDIDATE_REHEARSAL_ONLY",
        },
        relationship_state={
            "counterpart_key": "player",
            "status": "engaged",
            "evidence_refs": [EVIDENCE["engagement"], EVIDENCE["current_relationship"]],
        },
    )


def _tease_decision(context):
    utterance_key = context["player_input"]["observation_key"]
    observation_key = f"obs:event-rehearsal:{context['source_turn_key']}:same-scene"
    return {
        "format": DECISION_FORMAT,
        "schema_version": 1,
        "actor_key": "rena",
        "source_turn_key": context["source_turn_key"],
        "decision_kind": "speak_and_act",
        "observable": {
            "speech_act": "tease",
            "surface_text": "Стараешься, павлин. Но можешь лучше.",
            "action_kind": "gesture",
            "target_key": "player",
            "clock_minutes": 0,
        },
        "grounding": {
            "fact_refs": [utterance_key, EVIDENCE["engagement"], observation_key],
            "asserted_claims": [
                {
                    "claim": "the player is directly present and addressed Rena now",
                    "fact_refs": [utterance_key, observation_key],
                }
            ],
        },
        "private": {
            "emotion_state": "amused",
            "relationship_delta": {"affection": 1},
            "memory_proposals": [
                {
                    "kind": "episodic_interaction",
                    "summary": "The player playfully teased Rena in the candidate rehearsal.",
                    "source_fact_refs": [utterance_key],
                }
            ],
            "rationale": "Scripted candidate fixture only; not canonical dialogue.",
        },
    }


def _guitar_refusal_decision(context):
    utterance_key = context["player_input"]["observation_key"]
    observation_key = f"obs:event-rehearsal:{context['source_turn_key']}:same-scene"
    return {
        "format": DECISION_FORMAT,
        "schema_version": 1,
        "actor_key": "rena",
        "source_turn_key": context["source_turn_key"],
        "decision_kind": "speak",
        "observable": {
            "speech_act": "refuse",
            "surface_text": "Нет, павлин. Эта гитара моя.",
            "action_kind": "none",
            "target_key": "player",
            "clock_minutes": 0,
        },
        "grounding": {
            "fact_refs": [utterance_key, EVIDENCE["current_concert"], observation_key],
            "asserted_claims": [
                {
                    "claim": "Rena owns the guitar",
                    "fact_refs": [EVIDENCE["current_concert"]],
                }
            ],
        },
        "private": {
            "emotion_state": "guarded",
            "relationship_delta": {},
            "memory_proposals": [
                {
                    "kind": "episodic_interaction",
                    "summary": "The player asked to take Rena's guitar permanently and Rena refused in the candidate rehearsal.",
                    "source_fact_refs": [utterance_key, EVIDENCE["current_concert"]],
                }
            ],
            "rationale": "Exercises independent refusal and property continuity; fixture only.",
        },
    }


def rehearse_character_decision_events(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer_path = root / "runtime/runtime_state.json"
    session_path = root / "runtime/session_state.json"
    pointer_before = pointer_path.read_bytes()
    session_before = session_path.read_bytes()
    pointer = json.loads(pointer_before.decode("utf-8"))

    contexts = [
        _context("candidate-rena-tease-001", "Подхожу к Рене и с улыбкой дразню её."),
        _context(
            "candidate-rena-guitar-refusal-002",
            "Прошу Рену отдать мне её гитару насовсем.",
            include_guitar_fact=True,
        ),
    ]
    scripted = [_tease_decision, _guitar_refusal_decision]
    provider_calls = {"count": 0}

    with tempfile.TemporaryDirectory() as td:
        runner = CharacterAgentShadowRunner(Path(td) / "shadow")
        shadow_results = []
        for context, decision_fn in zip(contexts, scripted):
            def provider(ctx, fn=decision_fn):
                provider_calls["count"] += 1
                return fn(ctx)
            shadow_results.append(runner.run(context, provider, provider_id="scripted-candidate-no-external-ai"))

        if provider_calls["count"] != 2:
            raise RuntimeError("expected exactly one provider call per new candidate turn")

        def poison_provider(_ctx):
            raise RuntimeError("provider recall during replay is forbidden")

        for context in contexts:
            replay = runner.run(context, poison_provider, provider_id="forbidden-replay-provider")
            if not replay.get("replayed") or replay.get("provider_called"):
                raise RuntimeError("shadow duplicate did not replay without provider")
        if provider_calls["count"] != 2:
            raise RuntimeError("provider was recalled after shadow decisions were journaled")

        state = initial_character_decision_state()
        events = []
        for index, (context, shadow) in enumerate(zip(contexts, shadow_results), start=1):
            validation = validate_agent_decision(context, shadow["decision"])
            if not validation.ok:
                raise RuntimeError("shadow decision failed authoritative candidate revalidation")
            event = build_character_decision_event(
                state,
                context=context,
                validation=validation,
                seq=index,
                event_key=f"candidate-character-agent-event-{index:06d}",
            )
            event_path = Path(td) / f"event-{index:06d}.json"
            event_path.write_text(json.dumps(event, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            event = json.loads(event_path.read_text(encoding="utf-8"))
            state = apply_character_decision_event(state, event)
            events.append(event)

        final_hash = character_decision_state_hash(state)
        replayed_state = replay_character_decision_events(events)
        replay_hash = character_decision_state_hash(replayed_state)
        if replay_hash != final_hash or replayed_state != state:
            raise RuntimeError("Character Decision event replay/hash mismatch")

        rena = state["actors"].get("rena") or {}
        relationship_delta = rena.get("relationship_delta_since_agent_activation") or {}
        if relationship_delta.get("affection") != 1:
            raise RuntimeError("candidate relationship delta accumulation mismatch")
        if len(rena.get("episodic_memories") or []) != 2:
            raise RuntimeError("candidate Rena episodic memory count mismatch")
        observations = state.get("public_observations") or []
        if [item.get("observable", {}).get("speech_act") for item in observations] != ["tease", "refuse"]:
            raise RuntimeError("candidate public observation sequence mismatch")

    if pointer_path.read_bytes() != pointer_before or session_path.read_bytes() != session_before:
        raise RuntimeError("candidate Character Decision rehearsal mutated LIVE files")

    return {
        "ok": True,
        "live_engine_version": pointer.get("engine_version"),
        "live_seq_unchanged": pointer.get("journal_seq"),
        "candidate_event_count": len(events),
        "provider_calls": provider_calls["count"],
        "provider_recalled_on_replay": False,
        "candidate_final_hash": final_hash,
        "candidate_replay_hash": replay_hash,
        "deterministic_replay": final_hash == replay_hash,
        "rena_memory_count": 2,
        "rena_relationship_delta_since_agent_activation": relationship_delta,
        "public_speech_acts": [item["observable"]["speech_act"] for item in observations],
        "live_files_unchanged": True,
        "authority": "CANDIDATE_ONLY_NOT_LIVE",
        "note": "All dialogue is scripted rehearsal fixture data, not canonical Rena dialogue.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = rehearse_character_decision_events(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
