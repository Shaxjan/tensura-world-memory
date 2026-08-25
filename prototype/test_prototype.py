from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
SIM_ENGINE = REPO_ROOT / "sim_engine"
for value in (str(HERE), str(SIM_ENGINE)):
    if value not in sys.path:
        sys.path.insert(0, value)

from app import PrototypeSession, _explicit_target  # noqa: E402


class PrototypeTests(unittest.TestCase):
    def setUp(self):
        self.runtime_pointer = REPO_ROOT / "runtime/runtime_state.json"
        self.runtime_session = REPO_ROOT / "runtime/session_state.json"
        self.before_pointer = self.runtime_pointer.read_bytes()
        self.before_session = self.runtime_session.read_bytes()
        self.game = PrototypeSession(REPO_ROOT)

    def tearDown(self):
        self.game.close()
        self.assertEqual(self.runtime_pointer.read_bytes(), self.before_pointer)
        self.assertEqual(self.runtime_session.read_bytes(), self.before_session)

    def test_plain_chat_is_scoped_as_direct_rena_address(self):
        self.assertEqual(_explicit_target("Привет"), "Рена, Привет")
        self.assertEqual(_explicit_target("Рена, привет"), "Рена, привет")
        self.assertEqual(_explicit_target("Спрашиваю Рену: привет"), "Спрашиваю Рену: привет")

    def test_two_turn_playable_dialogue_accumulates_memory_and_replays(self):
        first = self.game.turn("Привет")
        self.assertTrue(first["ok"])
        self.assertTrue(first["replay_ok"])
        self.assertTrue(first["response"])

        second = self.game.turn("Дай мне свою гитару")
        self.assertTrue(second["ok"])
        self.assertTrue(second["replay_ok"])
        self.assertEqual(second["speech_act"], "refuse")
        self.assertIn("гитар", second["response"].casefold())

        state = self.game.state()
        self.assertEqual(state["turn_count"], 2)
        self.assertEqual(state["memory_count"], 2)
        self.assertTrue(state["replay_ok"])
        self.assertFalse(state["private_state_exposed"])

    def test_reset_returns_to_clean_sandbox_without_touching_live(self):
        self.game.turn("Привет")
        self.assertEqual(self.game.state()["turn_count"], 1)
        self.game.reset()
        state = self.game.state()
        self.assertEqual(state["turn_count"], 0)
        self.assertEqual(state["memory_count"], 0)
        self.assertTrue(state["replay_ok"])

    def test_unknown_wedding_detail_is_not_authored_as_fact(self):
        result = self.game.turn("Когда у нас свадьба?")
        self.assertTrue(result["replay_ok"])
        low = result["response"].casefold()
        self.assertNotIn("свадьба будет", low)
        self.assertNotIn("мы поженимся", low)


if __name__ == "__main__":
    unittest.main()
