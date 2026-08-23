from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from v02_engine import SimulationV02
from v02_seed import seed_blumund_v02


class SimulationV02Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "world.db"
        seed_blumund_v02(self.db)
        self.sim = SimulationV02(self.db)

    def tearDown(self) -> None:
        self.sim.close()
        self.tmp.cleanup()

    def test_economy_is_atomic(self) -> None:
        a0 = int(self.sim.actor("merchant")["cash_copper"])
        b0 = int(self.sim.actor("guard")["cash_copper"])
        a1, b1 = self.sim.transfer("merchant", "guard", 321, "test")
        self.assertEqual(a1, a0 - 321)
        self.assertEqual(b1, b0 + 321)
        with self.assertRaises(ValueError):
            self.sim.transfer("guard", "merchant", 10**9, "impossible")
        self.assertEqual(int(self.sim.actor("merchant")["cash_copper"]), a1)
        self.assertEqual(int(self.sim.actor("guard")["cash_copper"]), b1)

    def test_player_is_never_autonomously_moved(self) -> None:
        before = dict(self.sim.actor("char_arlequino"))
        self.sim.advance(3 * 1440)
        after = dict(self.sim.actor("char_arlequino"))
        self.assertEqual(before["location_id"], after["location_id"])
        self.assertEqual(before["cash_copper"], after["cash_copper"])
        report = self.sim.autonomy_report()
        self.assertEqual(report["player_autonomous_events"], 0)

    def test_needs_accumulate_across_small_ticks(self) -> None:
        hunger0 = int(self.sim.needs("rena")["hunger"])
        fatigue0 = int(self.sim.needs("rena")["fatigue"])
        self.sim.advance(90, tick_minutes=15)
        self.assertGreaterEqual(int(self.sim.needs("rena")["hunger"]), hunger0 + 2)
        self.assertGreaterEqual(int(self.sim.needs("rena")["fatigue"]), fatigue0 + 1)

    def test_needs_override_goal_when_hungry(self) -> None:
        self.sim.db.execute("UPDATE needs SET hunger=95 WHERE actor_id='merchant'")
        self.sim.db.execute("UPDATE actors SET next_action_at=? WHERE id='merchant'", (self.sim.now,))
        self.sim.db.commit()
        food_before = self.sim.resource_qty("market", "food")
        self.sim.advance(15)
        food_after = self.sim.resource_qty("market", "food")
        self.assertLess(food_after, food_before)
        self.assertLess(int(self.sim.needs("merchant")["hunger"]), 95)

    def test_projects_consume_real_resources_and_progress(self) -> None:
        paper0 = self.sim.resource_qty("print_room", "paper")
        wood0 = self.sim.resource_qty("workshop", "wood")
        self.sim.advance(8 * 60)
        self.assertLess(self.sim.resource_qty("print_room", "paper"), paper0)
        self.assertLess(self.sim.resource_qty("workshop", "wood"), wood0)
        lissa = self.sim.db.execute("SELECT MAX(progress) p FROM goals WHERE actor_id='lissa'").fetchone()["p"]
        oren = self.sim.db.execute("SELECT MAX(progress) p FROM goals WHERE actor_id='oren'").fetchone()["p"]
        self.assertGreater(int(lissa), 0)
        self.assertGreater(int(oren), 0)

    def test_rumor_spreads_by_social_contact_not_global_knowledge(self) -> None:
        self.assertIsNone(self.sim.known_fact("merchant", "jura.orc_tracks"))
        self.assertEqual(len(self.sim.rumor_beliefs("merchant")), 0)
        self.sim.advance(4 * 1440)
        total_beliefs = self.sim.db.execute("SELECT COUNT(*) n FROM rumor_beliefs").fetchone()["n"]
        self.assertGreater(int(total_beliefs), 1)
        self.assertIsNone(self.sim.known_fact("merchant", "jura.orc_tracks"))

    def test_npc_initiative_can_create_new_goal(self) -> None:
        rumor = self.sim.rumor_beliefs("courier")[0]
        self.sim.db.execute(
            "INSERT OR REPLACE INTO rumor_beliefs(rumor_id,actor_id,claim_json,confidence,heard_at,source_actor_id) VALUES(?,?,?,?,?,?)",
            (rumor["rumor_id"], "guard", rumor["claim_json"], 70, self.sim.now, "courier"),
        )
        self.sim.db.execute("UPDATE actors SET next_action_at=? WHERE id='guard'", (self.sim.now,))
        self.sim.db.commit()
        self.sim.advance(15)
        self.assertTrue(self.sim._goal_exists("guard", "investigate_rumor"))
        events = self.sim.recent_events(1000)
        self.assertTrue(any(e["event_type"] == "npc_initiative" and e["actor_id"] == "guard" for e in events))

    def test_low_market_stock_causes_merchant_restock_goal(self) -> None:
        self.sim.db.execute("UPDATE location_resources SET qty=3 WHERE location_id='market' AND resource='food'")
        self.sim.db.execute("UPDATE actors SET next_action_at=? WHERE id='merchant'", (self.sim.now,))
        self.sim.db.commit()
        self.sim.advance(15)
        self.assertTrue(self.sim._goal_exists("merchant", "restock_food"))

    def test_plans_are_materialized_from_goals(self) -> None:
        self.sim.advance(60)
        n = self.sim.db.execute("SELECT COUNT(*) n FROM plans").fetchone()["n"]
        steps = self.sim.db.execute("SELECT COUNT(*) n FROM plan_steps").fetchone()["n"]
        self.assertGreater(int(n), 0)
        self.assertGreater(int(steps), 0)

    def test_persistence_is_sqlite_not_text_save(self) -> None:
        self.sim.advance(120)
        now = self.sim.now
        cash = int(self.sim.actor("merchant")["cash_copper"])
        self.sim.close()
        self.sim = SimulationV02(self.db)
        self.assertEqual(self.sim.now, now)
        self.assertEqual(int(self.sim.actor("merchant")["cash_copper"]), cash)

    def test_three_days_without_player_changes_world(self) -> None:
        self.sim.advance(3 * 1440)
        report = self.sim.autonomy_report()
        self.assertGreater(report["npc_initiatives"], 0)
        self.assertGreater(sum(report["event_counts"].values()), 40)
        self.assertEqual(report["player_autonomous_events"], 0)
        self.assertGreater(report["rumor_beliefs"], 1)

    def test_contextual_reactions_have_different_causes(self) -> None:
        results = [
            self.sim.resolve_reaction(
                actor, source_actor_id="char_arlequino",
                tags=["music", "martial", "showmanship"],
                intensity=70, novelty=65, disruption=35, local_norm=10, crowd_sentiment=20,
            )
            for actor in ["rena", "lissa", "oren", "merchant", "guard", "courier"]
        ]
        self.assertGreaterEqual(len({r["category"] for r in results}), 2)
        self.assertGreaterEqual(len({tuple(r["reasons"]) for r in results}), 3)

    def test_reaction_exposes_reasoning_factors_not_prose(self) -> None:
        r = self.sim.resolve_reaction(
            "guard", source_actor_id="char_arlequino", tags=["showmanship"],
            intensity=80, novelty=40, disruption=90, local_norm=-30, crowd_sentiment=-20,
        )
        self.assertIn("dislikes_disruption", r["reasons"])
        self.assertIn("factors", r)
        self.assertIsInstance(r["score"], int)

    def test_seeded_runs_are_reproducible(self) -> None:
        other = Path(self.tmp.name) / "world2.db"
        seed_blumund_v02(other)
        with SimulationV02(other) as sim2:
            self.sim.advance(1440)
            sim2.advance(1440)
            r1 = self.sim.autonomy_report()
            r2 = sim2.autonomy_report()
            self.assertEqual(r1["event_counts"], r2["event_counts"])
            self.assertEqual(r1["resources"], r2["resources"])


if __name__ == "__main__":
    unittest.main()
