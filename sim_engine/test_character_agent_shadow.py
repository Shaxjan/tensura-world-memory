from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from character_agent_contract import DECISION_FORMAT
from character_agent_shadow import (
    CharacterAgentShadowRunner,
    ShadowDecisionReplayError,
    ShadowDecisionValidationError,
)
from rena_character_profile import EVIDENCE, build_rena_agent_context_v1


class CharacterAgentShadowTests(unittest.TestCase):
    def build_context(self, turn_key: str = "shadow-rena-tease-001"):
        return build_rena_agent_context_v1(
            source_turn_key=turn_key,
            world_minute=188249,
            player_utterance="Подхожу к Рене и с улыбкой дразню её.",
            causal_fact_keys=[
                EVIDENCE["engagement"],
                EVIDENCE["current_relationship"],
            ],
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

    @staticmethod
    def playful_provider(context):
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
                        "summary": "The player playfully teased Rena in the current scene.",
                        "source_fact_refs": [utterance_key],
                    }
                ],
                "rationale": "Low-stakes playful response is compatible with the grounded profile and current direct interaction.",
            },
        }

    def test_first_call_records_then_duplicate_replays_without_provider(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CharacterAgentShadowRunner(td)
            context = self.build_context()
            calls = {"count": 0}

            def provider(ctx):
                calls["count"] += 1
                return self.playful_provider(ctx)

            first = runner.run(context, provider, provider_id="test-scripted-agent")
            self.assertTrue(first["accepted"])
            self.assertFalse(first["replayed"])
            self.assertTrue(first["provider_called"])
            self.assertEqual(calls["count"], 1)
            self.assertEqual(first["public_observable"]["speech_act"], "tease")
            self.assertNotIn("emotion_state", first["public_observable"])

            def forbidden_provider(_ctx):
                raise AssertionError("provider must never be recalled for committed shadow turn")

            second = runner.run(context, forbidden_provider, provider_id="must-not-run")
            self.assertTrue(second["replayed"])
            self.assertFalse(second["provider_called"])
            self.assertEqual(second["decision_digest"], first["decision_digest"])
            self.assertEqual(second["public_observable"], first["public_observable"])
            self.assertEqual(calls["count"], 1)

    def test_explicit_replay_never_needs_provider(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CharacterAgentShadowRunner(td)
            context = self.build_context("shadow-rena-replay-002")
            first = runner.run(context, self.playful_provider, provider_id="test-scripted-agent")
            replay = runner.replay(context)
            self.assertTrue(replay["replayed"])
            self.assertFalse(replay["provider_called"])
            self.assertEqual(replay["decision_digest"], first["decision_digest"])

    def test_context_change_for_same_turn_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CharacterAgentShadowRunner(td)
            context = self.build_context("shadow-rena-context-003")
            runner.run(context, self.playful_provider, provider_id="test-scripted-agent")
            changed = self.build_context("shadow-rena-context-003")
            changed["player_input"]["utterance"] = "Говорю Рене совсем другую фразу."
            with self.assertRaisesRegex(ShadowDecisionReplayError, "context digest mismatch"):
                runner.replay(changed)

    def test_invalid_provider_output_is_not_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CharacterAgentShadowRunner(td)
            context = self.build_context("shadow-rena-invalid-004")

            def bad_provider(ctx):
                decision = self.playful_provider(ctx)
                decision["grounding"]["fact_refs"].append("unknown:private:fact")
                return decision

            with self.assertRaises(ShadowDecisionValidationError):
                runner.run(context, bad_provider, provider_id="bad-test-agent")
            self.assertFalse(runner.record_path(context).exists())

    def test_tampered_journaled_decision_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CharacterAgentShadowRunner(td)
            context = self.build_context("shadow-rena-tamper-005")
            runner.run(context, self.playful_provider, provider_id="test-scripted-agent")
            path = runner.record_path(context)
            record = json.loads(path.read_text(encoding="utf-8"))
            record["decision"]["observable"]["surface_text"] = "tampered"
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ShadowDecisionReplayError, "decision digest mismatch"):
                runner.replay(context)

    def test_record_does_not_persist_raw_context_or_raw_provider_output(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CharacterAgentShadowRunner(td)
            context = self.build_context("shadow-rena-privacy-006")
            runner.run(context, self.playful_provider, provider_id="test-scripted-agent")
            record = json.loads(runner.record_path(context).read_text(encoding="utf-8"))
            self.assertNotIn("context", record)
            self.assertNotIn("raw_provider_output", record)
            self.assertFalse(record["generation"]["raw_context_persisted"])
            self.assertFalse(record["generation"]["raw_provider_output_persisted"])
            self.assertEqual(record["authority"], "SHADOW_NON_AUTHORITATIVE")


if __name__ == "__main__":
    unittest.main()
