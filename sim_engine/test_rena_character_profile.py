from __future__ import annotations

import unittest

from rena_character_profile import (
    build_rena_agent_context_v1,
    rena_profile_v1,
    validate_rena_profile_v1,
)


class RenaCharacterProfileTests(unittest.TestCase):
    def test_profile_is_grounded_and_valid(self):
        profile = rena_profile_v1()
        self.assertEqual(validate_rena_profile_v1(profile), [])
        self.assertEqual(profile["actor_key"], "rena")
        self.assertEqual(profile["relationship_with_player"]["status"], "engaged")

    def test_stable_traits_are_evidence_backed(self):
        profile = rena_profile_v1()
        traits = profile["personality"]["traits"]
        values = {item["value"] for item in traits}
        self.assertEqual(values, {"practical", "direct", "independent", "proud"})
        for item in traits:
            self.assertTrue(item["evidence_refs"])

    def test_jealousy_is_capability_not_default(self):
        profile = rena_profile_v1()
        tendencies = {item["value"]: item for item in profile["personality"]["conditional_tendencies"]}
        self.assertIn("can_express_jealousy_or_anger", tendencies)
        self.assertIn("never automatic", tendencies["can_express_jealousy_or_anger"]["rule"])
        self.assertIn("do not make jealousy automatic", profile["personality"]["anti_flattening_rules"])

    def test_wedding_preference_remains_unknown(self):
        profile = rena_profile_v1()
        self.assertEqual(profile["known_unknowns"]["exact_wedding_preference"], "UNKNOWN")
        self.assertIn("exact wedding preference", profile["does_not_assert"])

    def test_engagement_does_not_mean_obedience(self):
        profile = rena_profile_v1()
        policy = profile["agent_policy"]
        self.assertTrue(policy["may_disagree_with_player"])
        self.assertTrue(policy["may_refuse_player"])
        self.assertTrue(policy["may_continue_own_goals_without_player"])
        self.assertTrue(policy["relationship_is_context_not_obedience"])

    def test_build_agent_context_preserves_private_boundary(self):
        context = build_rena_agent_context_v1(
            source_turn_key="shadow-rena-tease-001",
            world_minute=189138,
            player_utterance="Рена, ты опять решила сделать всё сама?",
            causal_fact_keys=["fact:rena:engaged", "fact:rena:current-scene"],
            observations=[
                {
                    "fact_key": "obs:rena:player-visible",
                    "kind": "direct_observation",
                    "subject": "player",
                    "predicate": "visible_in_same_scene",
                }
            ],
            visible_target_keys=["player"],
            current_plan={"kind": "current_activity", "status": "active"},
        )
        self.assertEqual(context["actor_key"], "rena")
        self.assertEqual(context["self"]["character_core"]["personality"]["status"], "grounded_from_preserved_authoritative_saves")
        self.assertNotIn("world_state", context)
        self.assertIn("rena:exact_wedding_preference", context["knowledge"]["unresolved_keys"])

    def test_profile_does_not_claim_current_mood(self):
        profile = rena_profile_v1()
        self.assertEqual(profile["known_unknowns"]["current_exact_mood"], "UNKNOWN until caused/observed in scene")
        trait_values = {item["value"] for item in profile["personality"]["traits"]}
        self.assertNotIn("amused", trait_values)
        self.assertNotIn("angry", trait_values)

    def test_missing_evidence_fails_closed(self):
        profile = rena_profile_v1()
        profile["personality"]["traits"][0]["evidence_refs"] = []
        errors = validate_rena_profile_v1(profile)
        self.assertTrue(any("has no evidence_refs" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
