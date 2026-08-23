from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from seed_blumund import seed_blumund
from sim import Simulation


class SimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        seed_blumund(self.db)
        self.sim = Simulation(self.db)

    def tearDown(self) -> None:
        self.sim.close()
        self.tmp.cleanup()

    def test_economy_transfer_is_exact_and_atomic(self) -> None:
        payer_before = int(self.sim.actor("char_arlequino")["cash_copper"])
        payee_before = int(self.sim.actor("merchant")["cash_copper"])
        payer_after, payee_after = self.sim.transfer(
            "char_arlequino", "merchant", 1234, "test purchase"
        )
        self.assertEqual(payer_after, payer_before - 1234)
        self.assertEqual(payee_after, payee_before + 1234)

        with self.assertRaises(ValueError):
            self.sim.transfer("char_arlequino", "merchant", 999_999_999, "impossible")
        self.assertEqual(int(self.sim.actor("char_arlequino")["cash_copper"]), payer_after)
        self.assertEqual(int(self.sim.actor("merchant")["cash_copper"]), payee_after)

    def test_knowledge_is_not_world_truth(self) -> None:
        self.assertEqual(
            self.sim.known_fact("char_arlequino", "departure.eurazania.destination"),
            "Eurazania",
        )
        self.assertIsNone(
            self.sim.known_fact("merchant", "departure.eurazania.destination")
        )

    def test_travel_uses_graph_time(self) -> None:
        start = self.sim.now
        arrival = self.sim.start_travel("rena", "free_guild", reason="test")
        self.assertGreater(arrival, start)
        self.sim.advance(arrival - start - 1)
        self.assertNotEqual(self.sim.actor("rena")["location_id"], "free_guild")
        self.sim.advance(1)
        self.assertEqual(self.sim.actor("rena")["location_id"], "free_guild")

    def test_player_is_not_autopiloted(self) -> None:
        before = dict(self.sim.actor("char_arlequino"))
        self.sim.advance(6 * 60)
        after = dict(self.sim.actor("char_arlequino"))
        self.assertEqual(before["location_id"], after["location_id"])
        self.assertEqual(before["cash_copper"], after["cash_copper"])

    def test_same_stimulus_can_produce_different_reactions(self) -> None:
        results = {
            self.sim.resolve_reaction(
                actor,
                source_actor_id="char_arlequino",
                tags=["music", "martial", "showmanship"],
                intensity=65,
            ).category
            for actor in ["rena", "lissa", "oren", "merchant", "guard"]
        }
        self.assertGreaterEqual(len(results), 2)

    def test_autonomous_world_generates_hidden_events(self) -> None:
        self.sim.advance(180)
        events = self.sim.recent_events(100, include_hidden=True)
        autonomous = [e for e in events if e["event_type"].startswith("npc_") or e["event_type"].startswith("travel_")]
        self.assertTrue(autonomous)


if __name__ == "__main__":
    unittest.main()
