from __future__ import annotations

import unittest

from character_agent_contract import (
    DECISION_FORMAT,
    build_agent_context,
    decision_digest,
    public_observable,
    validate_agent_decision,
)


class CharacterAgentContractTests(unittest.TestCase):
    def setUp(self):
        self.turn_key = "test-turn-tease-rena"
        self.utterance_key = f"turn:{self.turn_key}:player_utterance"
        self.context = build_agent_context(
            actor_key="rena",
            source_turn_key=self.turn_key,
            world_minute=189138,
            player_utterance="Подхожу к Рене и с улыбкой дразню её.",
            self_core={
                "format": "TENSURA_CHARACTER_CORE",
                "schema_version": 1,
                "actor_key": "rena",
                "display_name": "Рена",
                "personality": {"status": "authored_from_grounded_profile"},
            },
            causal_fact_keys=[
                "canon:relationship:rena:engaged",
                "canon:music:rena:original_song",
            ],
            observations=[
                {
                    "fact_key": "obs:rena:player-visible-same-scene",
                    "kind": "direct_observation",
                    "subject": "player",
                    "predicate": "visible_in_same_scene",
                }
            ],
            visible_target_keys=["player"],
            current_plan={"kind": "social_presence", "place_key": "eurazania_square"},
            relationship_state={"counterpart_key": "player", "status": "engaged"},
            unresolved_keys=["rena:wedding_preference_exact"],
        )

    def valid_decision(self):
        return {
            "format": DECISION_FORMAT,
            "schema_version": 1,
            "actor_key": "rena",
            "source_turn_key": self.turn_key,
            "decision_kind": "speak_and_act",
            "observable": {
                "speech_act": "tease",
                "surface_text": "Сначала научись дразнить убедительно.",
                "action_kind": "gesture",
                "target_key": "player",
                "clock_minutes": 0,
            },
            "grounding": {
                "fact_refs": [
                    self.utterance_key,
                    "canon:relationship:rena:engaged",
                    "obs:rena:player-visible-same-scene",
                ],
                "asserted_claims": [
                    {
                        "claim": "player addressed Rena in the current scene",
                        "fact_refs": [self.utterance_key, "obs:rena:player-visible-same-scene"],
                    }
                ],
            },
            "private": {
                "emotion_state": "amused",
                "relationship_delta": {"affection": 1, "irritation": 0},
                "memory_proposals": [
                    {
                        "kind": "episodic_interaction",
                        "summary": "Player playfully teased Rena.",
                        "source_fact_refs": [self.utterance_key],
                    }
                ],
                "rationale": "Respond playfully because the interaction is grounded and low-stakes.",
            },
        }

    def test_valid_grounded_social_decision(self):
        result = validate_agent_decision(self.context, self.valid_decision())
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.sanitized["authority"], "AGENT_PROPOSAL_REQUIRES_ENGINE_COMMIT")
        self.assertEqual(result.sanitized["observable"]["speech_act"], "tease")
        self.assertEqual(len(result.decision_digest), 64)

    def test_public_projection_hides_private_state(self):
        result = validate_agent_decision(self.context, self.valid_decision())
        public = public_observable(result)
        self.assertEqual(public["surface_text"], "Сначала научись дразнить убедительно.")
        self.assertNotIn("emotion_state", public)
        self.assertNotIn("relationship_delta", public)
        self.assertNotIn("rationale", public)

    def test_rejects_hallucinated_fact_reference(self):
        decision = self.valid_decision()
        decision["grounding"]["fact_refs"].append("unknown:rena:secret-plan")
        result = validate_agent_decision(self.context, decision)
        self.assertFalse(result.ok)
        self.assertTrue(any("unavailable" in error for error in result.errors))

    def test_rejects_unknown_as_if_known(self):
        decision = self.valid_decision()
        decision["grounding"]["asserted_claims"] = [
            {
                "claim": "Rena wants a huge wedding",
                "fact_refs": ["rena:wedding_preference_exact"],
            }
        ]
        result = validate_agent_decision(self.context, decision)
        self.assertFalse(result.ok)
        self.assertTrue(any("unavailable" in error for error in result.errors))

    def test_rejects_invisible_target(self):
        decision = self.valid_decision()
        decision["observable"]["target_key"] = "borga"
        result = validate_agent_decision(self.context, decision)
        self.assertFalse(result.ok)
        self.assertTrue(any("not currently visible" in error for error in result.errors))

    def test_rejects_direct_world_authority(self):
        decision = self.valid_decision()
        decision["cash_delta"] = 1000000
        result = validate_agent_decision(self.context, decision)
        self.assertFalse(result.ok)
        self.assertTrue(any("forbidden direct authority" in error for error in result.errors))

    def test_rejects_unbounded_relationship_jump(self):
        decision = self.valid_decision()
        decision["private"]["relationship_delta"] = {"affection": 99}
        result = validate_agent_decision(self.context, decision)
        self.assertFalse(result.ok)
        self.assertTrue(any("-2..2" in error for error in result.errors))

    def test_rejects_unbounded_time_skip(self):
        decision = self.valid_decision()
        decision["observable"]["clock_minutes"] = 120
        result = validate_agent_decision(self.context, decision)
        self.assertFalse(result.ok)
        self.assertTrue(any("0..30" in error for error in result.errors))

    def test_digest_is_stable(self):
        result1 = validate_agent_decision(self.context, self.valid_decision())
        result2 = validate_agent_decision(self.context, self.valid_decision())
        self.assertEqual(result1.decision_digest, result2.decision_digest)
        self.assertEqual(result1.decision_digest, decision_digest(result1.sanitized))


if __name__ == "__main__":
    unittest.main()
