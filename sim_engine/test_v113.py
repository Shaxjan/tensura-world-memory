from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v100_handoff import runtime_state_hash_v100
from v113_repository import load_repository_runtime_v113_candidate


class V113CandidateTests(unittest.TestCase):
    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def load(self, td: str):
        return load_repository_runtime_v113_candidate(self.repo_root, Path(td) / "candidate.db")

    def test_candidate_load_reproduces_current_v112_head_exactly(self):
        with tempfile.TemporaryDirectory() as td:
            world, pointer, loaded = self.load(td)
            try:
                self.assertEqual(pointer["engine_version"], "1.0.12")
                self.assertEqual(loaded["head_hash"], pointer["head_state_hash"])
                self.assertEqual(
                    runtime_state_hash_v100(world, int(pointer["source_live_version"])),
                    pointer["head_state_hash"],
                )
                self.assertIsNone(world.character_core_v113("rena"))
                self.assertIsNone(world.character_agent_state_v113("rena"))
            finally:
                world.close()

    def test_activation_is_prospective_and_zero_time(self):
        with tempfile.TemporaryDirectory() as td:
            world, pointer, _ = self.load(td)
            try:
                seq = int(pointer["journal_seq"]) + 1
                t0 = int(world.now)
                cash0 = int(world.actor("player")["cash_copper"])
                region0 = str(world.actor("player")["region_id"])
                out = world.execute_runtime_event(
                    seq,
                    "test-v113-activation",
                    "character_agent_v113_activation",
                    {"reason": "unit_test"},
                )
                result = out["result"]
                self.assertEqual(int(world.now), t0)
                self.assertEqual(int(world.actor("player")["cash_copper"]), cash0)
                self.assertEqual(str(world.actor("player")["region_id"]), region0)
                self.assertFalse(result["retroactive_response_created"])
                self.assertFalse(result["retroactive_memory_created"])
                self.assertFalse(result["current_emotion_inferred"])
                state = world.character_agent_state_v113("rena")
                self.assertEqual(state["episodic_memories"], [])
                self.assertIsNone(state["last_private_emotion"])
                self.assertTrue(all(int(v) == 0 for v in state["relationship_delta_since_activation"].values()))
            finally:
                world.close()

    def test_production_gameplay_route_is_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            world, pointer, _ = self.load(td)
            try:
                world.execute_runtime_event(
                    int(pointer["journal_seq"]) + 1,
                    "test-v113-activation-route",
                    "character_agent_v113_activation",
                    {"reason": "unit_test"},
                )
                with self.assertRaisesRegex(ValueError, "production gameplay routing is not enabled"):
                    world.commit_character_agent_decision_v113({"mode": "production"})
            finally:
                world.close()

    def test_candidate_context_rejects_non_engine_character_core(self):
        with tempfile.TemporaryDirectory() as td:
            world, pointer, _ = self.load(td)
            try:
                world.execute_runtime_event(
                    int(pointer["journal_seq"]) + 1,
                    "test-v113-activation-core",
                    "character_agent_v113_activation",
                    {"reason": "unit_test"},
                )
                context = world.build_rena_agent_context_v113(
                    source_turn_key="test-v113-context-core",
                    player_utterance="Тест.",
                    causal_fact_keys=[],
                    observations=[
                        {
                            "fact_key": "test:v113:obs",
                            "kind": "candidate_rehearsal_direct_observation",
                            "subject": "player",
                            "predicate": "visible_in_same_scene",
                        }
                    ],
                    visible_target_keys=["player"],
                    current_plan={"kind": "candidate_rehearsal_fixture"},
                )
                context["self"]["character_core"]["personality"]["traits"].append(
                    {"value": "invented_trait", "evidence_refs": ["none"]}
                )
                with self.assertRaisesRegex(ValueError, "not the engine-owned Rena core"):
                    world._validate_rehearsal_context_v113(context)
            finally:
                world.close()

    def test_activation_session_preserves_last_real_gameplay_turn(self):
        source_session = json.loads((self.repo_root / "runtime/session_state.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            world, pointer, _ = self.load(td)
            try:
                seq = int(pointer["journal_seq"]) + 1
                out = world.execute_runtime_event(
                    seq,
                    "test-v113-activation-session",
                    "character_agent_v113_activation",
                    {"reason": "unit_test"},
                )
                event = out["journal"]
                before = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
                session = world.build_session_state_v113(
                    journal_seq=seq,
                    head_state_hash=event["after_hash"],
                    last_event=event,
                    preserved_last_turn=source_session.get("last_turn"),
                )
                after = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
                self.assertEqual(before, after)
                self.assertEqual(session.get("last_turn"), source_session.get("last_turn"))
                self.assertFalse(session["character_agent_runtime"]["production_gameplay_routing_enabled"])
            finally:
                world.close()


if __name__ == "__main__":
    unittest.main()
