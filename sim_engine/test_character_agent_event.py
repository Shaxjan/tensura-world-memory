from __future__ import annotations

import copy
import unittest

from character_agent_contract import DECISION_FORMAT, validate_agent_decision
from character_agent_event import (
    CharacterDecisionEventError,
    apply_character_decision_event,
    build_character_decision_event,
    character_decision_state_hash,
    initial_character_decision_state,
    replay_character_decision_events,
)
from rena_character_profile import EVIDENCE, build_rena_agent_context_v1


class CharacterAgentEventTests(unittest.TestCase):
    def context(self, turn_key="event-rena-tease-001"):
        return build_rena_agent_context_v1(
            source_turn_key=turn_key,
            world_minute=188249,
            player_utterance="Подхожу к Рене и с улыбкой дразню её.",
            causal_fact_keys=[EVIDENCE["engagement"], EVIDENCE["current_relationship"]],
            observations=[
                {
                    "fact_key": "obs:event:rena-and-player-same-scene",
                    "kind": "direct_observation",
                    "subject": "player",
                    "predicate": "visible_in_same_scene",
                }
            ],
            visible_target_keys=["player"],
            current_plan={"kind": "social_presence", "place_key": "candidate_fixture"},
            relationship_state={
                "counterpart_key": "player",
                "status": "engaged",
                "evidence_refs": [EVIDENCE["engagement"], EVIDENCE["current_relationship"]],
            },
        )

    def decision(self, context):
        utterance_key = context["player_input"]["observation_key"]
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
                "fact_refs": [utterance_key, EVIDENCE["engagement"], "obs:event:rena-and-player-same-scene"],
                "asserted_claims": [
                    {
                        "claim": "the player is directly present and addressed Rena now",
                        "fact_refs": [utterance_key, "obs:event:rena-and-player-same-scene"],
                    }
                ],
            },
            "private": {
                "emotion_state": "amused",
                "relationship_delta": {"affection": 1, "irritation": 0},
                "memory_proposals": [
                    {
                        "kind": "episodic_interaction",
                        "summary": "The player playfully teased Rena.",
                        "source_fact_refs": [utterance_key],
                    }
                ],
                "rationale": "Candidate fixture only.",
            },
        }

    def validated(self, context):
        result = validate_agent_decision(context, self.decision(context))
        self.assertTrue(result.ok, result.errors)
        return result

    def test_event_applies_bounded_private_effects_and_public_observable(self):
        state0 = initial_character_decision_state()
        context = self.context()
        event = build_character_decision_event(
            state0,
            context=context,
            validation=self.validated(context),
            seq=1,
            event_key="candidate-character-event-000001",
        )
        state1 = apply_character_decision_event(state0, event)
        self.assertEqual(state1["last_seq"], 1)
        rena = state1["actors"]["rena"]
        self.assertEqual(rena["relationship_delta_since_agent_activation"]["affection"], 1)
        self.assertEqual(rena["relationship_delta_since_agent_activation"]["irritation"], 0)
        self.assertEqual(rena["last_private_emotion"], "amused")
        self.assertEqual(len(rena["episodic_memories"]), 1)
        public = state1["public_observations"][0]
        self.assertEqual(public["observable"]["speech_act"], "tease")
        self.assertNotIn("emotion_state", public["observable"])
        self.assertNotIn("relationship_delta", public["observable"])

    def test_full_replay_produces_identical_state_hash(self):
        state0 = initial_character_decision_state()
        context = self.context("event-rena-replay-002")
        event = build_character_decision_event(
            state0,
            context=context,
            validation=self.validated(context),
            seq=1,
            event_key="candidate-character-event-000002",
        )
        applied = apply_character_decision_event(state0, event)
        replayed = replay_character_decision_events([event])
        self.assertEqual(character_decision_state_hash(applied), character_decision_state_hash(replayed))
        self.assertEqual(applied, replayed)

    def test_tampered_decision_fails_digest_check(self):
        state0 = initial_character_decision_state()
        context = self.context("event-rena-tamper-003")
        event = build_character_decision_event(
            state0,
            context=context,
            validation=self.validated(context),
            seq=1,
            event_key="candidate-character-event-000003",
        )
        tampered = copy.deepcopy(event)
        tampered["decision"]["observable"]["surface_text"] = "tampered"
        with self.assertRaisesRegex(CharacterDecisionEventError, "digest mismatch"):
            apply_character_decision_event(state0, tampered)

    def test_before_hash_mismatch_fails_closed(self):
        state0 = initial_character_decision_state()
        context = self.context("event-rena-beforehash-004")
        event = build_character_decision_event(
            state0,
            context=context,
            validation=self.validated(context),
            seq=1,
            event_key="candidate-character-event-000004",
        )
        wrong_state = copy.deepcopy(state0)
        wrong_state["public_observations"].append({"unexpected": True})
        with self.assertRaisesRegex(CharacterDecisionEventError, "before-state hash mismatch"):
            apply_character_decision_event(wrong_state, event)

    def test_same_actor_source_turn_cannot_be_committed_twice(self):
        state0 = initial_character_decision_state()
        context = self.context("event-rena-duplicate-005")
        validation = self.validated(context)
        event1 = build_character_decision_event(
            state0,
            context=context,
            validation=validation,
            seq=1,
            event_key="candidate-character-event-000005a",
        )
        state1 = apply_character_decision_event(state0, event1)
        with self.assertRaisesRegex(CharacterDecisionEventError, "already committed"):
            build_character_decision_event(
                state1,
                context=context,
                validation=validation,
                seq=2,
                event_key="candidate-character-event-000005b",
            )

    def test_relationship_accumulator_is_explicitly_delta_since_activation(self):
        state0 = initial_character_decision_state()
        context = self.context("event-rena-delta-006")
        event = build_character_decision_event(
            state0,
            context=context,
            validation=self.validated(context),
            seq=1,
            event_key="candidate-character-event-000006",
        )
        state1 = apply_character_decision_event(state0, event)
        rena = state1["actors"]["rena"]
        self.assertIn("relationship_delta_since_agent_activation", rena)
        self.assertNotIn("absolute_relationship", rena)
        self.assertTrue(
            event["effect_notes"]["relationship_values_are_delta_since_agent_activation_not_absolute_relationship"]
        )


if __name__ == "__main__":
    unittest.main()
