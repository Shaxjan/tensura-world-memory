from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from v113_repository import load_repository_runtime_v113_candidate


class V113PreActivationCompatibilityTests(unittest.TestCase):
    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def test_pre_activation_gm_packet_is_still_v112(self):
        with tempfile.TemporaryDirectory() as td:
            world, pointer, _ = load_repository_runtime_v113_candidate(
                self.repo_root, Path(td) / "candidate.db"
            )
            try:
                self.assertIsNone(world.character_agent_state_v113("rena"))
                packet = world.build_gm_packet("player")
                self.assertEqual((packet.get("runtime") or {}).get("engine"), "1.0.12")
                self.assertNotIn("character_agent_v113_candidate", packet.get("constraints") or {})

                world.execute_runtime_event(
                    int(pointer["journal_seq"]) + 1,
                    "test-v113-compat-activation",
                    "character_agent_v113_activation",
                    {"reason": "compat_regression"},
                )
                packet_after = world.build_gm_packet("player")
                self.assertEqual((packet_after.get("runtime") or {}).get("engine"), "1.0.13")
                self.assertIn("character_agent_v113_candidate", packet_after.get("constraints") or {})
            finally:
                world.close()


if __name__ == "__main__":
    unittest.main()
