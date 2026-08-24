from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from character_agent_engine_routing import (
    VISIBLE_RENA_KEY,
    build_engine_owned_rena_context_v113,
    install_candidate_reciprocal_fixture,
    reciprocal_key,
)
from v113_repository import load_repository_runtime_v113_candidate


class CharacterAgentEngineRoutingTests(unittest.TestCase):
    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def load_activated(self, td: str):
        world, pointer, _ = load_repository_runtime_v113_candidate(
            self.repo_root, Path(td) / "candidate.db"
        )
        world.execute_runtime_event(
            int(pointer["journal_seq"]) + 1,
            "test-routing-v113-activation",
            "character_agent_v113_activation",
            {"reason": "routing_test"},
        )
        return world, pointer

    def put_visibility_only(self, world):
        place = world._place103("player")
        self.assertIsNotNone(place)
        world._put_fact103(
            VISIBLE_RENA_KEY,
            {
                "actor_key": "rena",
                "name": "Рена",
                "place_key": place["key"],
                "place_text": place["name"],
                "observed_at": int(world.now),
                "valid_until": int(world.now) + 20,
                "authority": "CANDIDATE_REHEARSAL_FIXTURE",
                "historical_claim": False,
            },
            "candidate:test_visibility_only",
            significance=5,
        )
        world.db.commit()

    def test_current_live_state_does_not_make_rena_eligible(self):
        with tempfile.TemporaryDirectory() as td:
            world, _ = self.load_activated(td)
            try:
                routed = build_engine_owned_rena_context_v113(
                    world,
                    source_turn_key="routing-current-live-001",
                    raw_text="Обращаюсь к Рене: привет.",
                )
                self.assertFalse(routed.eligible)
                self.assertEqual(routed.reason, "rena_not_directly_visible")
            finally:
                world.close()

    def test_player_visibility_alone_does_not_create_reciprocal_awareness(self):
        with tempfile.TemporaryDirectory() as td:
            world, _ = self.load_activated(td)
            try:
                self.put_visibility_only(world)
                routed = build_engine_owned_rena_context_v113(
                    world,
                    source_turn_key="routing-one-way-002",
                    raw_text="Обращаюсь к Рене: привет.",
                    allow_candidate_fixture=True,
                )
                self.assertFalse(routed.eligible)
                self.assertEqual(routed.reason, "rena_has_no_causal_awareness_of_this_turn")
            finally:
                world.close()

    def test_candidate_fixture_is_rejected_by_production_default(self):
        with tempfile.TemporaryDirectory() as td:
            world, _ = self.load_activated(td)
            try:
                turn = "routing-fixture-default-003"
                raw = "Обращаюсь к Рене: привет."
                install_candidate_reciprocal_fixture(world, source_turn_key=turn, raw_text=raw)
                routed = build_engine_owned_rena_context_v113(
                    world, source_turn_key=turn, raw_text=raw
                )
                self.assertFalse(routed.eligible)
                self.assertEqual(routed.reason, "rena_has_no_causal_awareness_of_this_turn")
            finally:
                world.close()

    def test_engine_owned_fixture_context_requires_explicit_rena_address(self):
        with tempfile.TemporaryDirectory() as td:
            world, _ = self.load_activated(td)
            try:
                turn = "routing-address-004"
                raw = "Говорю вслух: привет."
                install_candidate_reciprocal_fixture(world, source_turn_key=turn, raw_text=raw)
                routed = build_engine_owned_rena_context_v113(
                    world,
                    source_turn_key=turn,
                    raw_text=raw,
                    allow_candidate_fixture=True,
                )
                self.assertFalse(routed.eligible)
                self.assertEqual(routed.reason, "rena_not_explicitly_addressed")
            finally:
                world.close()

    def test_engine_owned_context_exposes_only_rena_actor_knowledge(self):
        with tempfile.TemporaryDirectory() as td:
            world, _ = self.load_activated(td)
            try:
                turn = "routing-knowledge-005"
                raw = "Спрашиваю Рену: что ты знаешь?"
                install_candidate_reciprocal_fixture(world, source_turn_key=turn, raw_text=raw)

                world._put_fact103(
                    "test:rena:known-direct",
                    {"kind": "test_fact", "text": "known directly by Rena"},
                    "candidate:test",
                    significance=5,
                )
                world._put_fact103(
                    "test:rena:uncertain",
                    {"kind": "test_fact", "text": "uncertain belief"},
                    "candidate:test",
                    significance=5,
                )
                world._put_fact103(
                    "test:other:private",
                    {"kind": "test_fact", "text": "belongs to another actor"},
                    "candidate:test",
                    significance=5,
                )
                world.db.execute(
                    "INSERT OR REPLACE INTO actor_knowledge(actor_id,fact_key,confidence,learned_at,source) VALUES(?,?,?,?,?)",
                    ("rena", "test:rena:known-direct", 100, int(world.now), "candidate:test_direct"),
                )
                world.db.execute(
                    "INSERT OR REPLACE INTO actor_knowledge(actor_id,fact_key,confidence,learned_at,source) VALUES(?,?,?,?,?)",
                    ("rena", "test:rena:uncertain", 70, int(world.now), "candidate:test_uncertain"),
                )
                world.db.execute(
                    "INSERT OR REPLACE INTO actor_knowledge(actor_id,fact_key,confidence,learned_at,source) VALUES(?,?,?,?,?)",
                    ("borga", "test:other:private", 100, int(world.now), "candidate:test_other"),
                )
                world.db.commit()

                routed = build_engine_owned_rena_context_v113(
                    world,
                    source_turn_key=turn,
                    raw_text=raw,
                    allow_candidate_fixture=True,
                )
                self.assertTrue(routed.eligible, routed.reason)
                context = routed.context
                self.assertIsNotNone(context)
                knowledge = context["knowledge"]
                keys = knowledge["causal_fact_keys"]
                self.assertIn("test:rena:known-direct", keys)
                self.assertNotIn("test:rena:uncertain", keys)
                self.assertNotIn("test:other:private", keys)
                records = {row["fact_key"]: row for row in knowledge["causal_facts"]}
                self.assertEqual(records["test:rena:known-direct"]["value"]["text"], "known directly by Rena")
                self.assertEqual(knowledge["minimum_confidence_exposed"], 100)
                self.assertTrue(context["routing"]["engine_owned"])
                self.assertTrue(context["routing"]["player_visibility_does_not_imply_reciprocal_awareness"])
                self.assertNotIn("world_state", context)
                self.assertNotIn("other_character_private_state", context)
            finally:
                world.close()

    def test_reciprocal_fact_must_match_exact_turn_text_and_minute(self):
        with tempfile.TemporaryDirectory() as td:
            world, _ = self.load_activated(td)
            try:
                turn = "routing-exactness-006"
                raw = "Обращаюсь к Рене: доброе утро."
                install_candidate_reciprocal_fixture(world, source_turn_key=turn, raw_text=raw)
                mismatch = build_engine_owned_rena_context_v113(
                    world,
                    source_turn_key=turn,
                    raw_text="Обращаюсь к Рене: другая фраза.",
                    allow_candidate_fixture=True,
                )
                self.assertFalse(mismatch.eligible)
                self.assertEqual(mismatch.reason, "rena_has_no_causal_awareness_of_this_turn")

                fact = world._get_fact103(reciprocal_key(turn))
                fact["world_minute"] = int(world.now) - 1
                world._put_fact103(
                    reciprocal_key(turn), fact, "candidate:test_stale_awareness", significance=5
                )
                world.db.commit()
                stale = build_engine_owned_rena_context_v113(
                    world,
                    source_turn_key=turn,
                    raw_text=raw,
                    allow_candidate_fixture=True,
                )
                self.assertFalse(stale.eligible)
                self.assertEqual(stale.reason, "rena_has_no_causal_awareness_of_this_turn")
            finally:
                world.close()


if __name__ == "__main__":
    unittest.main()
