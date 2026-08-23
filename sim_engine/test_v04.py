import json
import tempfile
import unittest
from pathlib import Path

from v04_seed import seed_world_v04


class V04Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "w.db"
        self.w = seed_world_v04(self.db)

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def test_unknown_state_mutation_command_is_rejected(self):
        before = int(self.w.actor("player")["cash_copper"])
        r = self.w.submit_player_command("player", "set_cash", {"cash_copper": 999999})
        self.assertFalse(r["accepted"])
        self.assertEqual(int(self.w.actor("player")["cash_copper"]), before)
        log = self.w.db.execute("SELECT * FROM action_log ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(log["accepted"], 0)

    def test_command_firewall_rejects_extra_state_fields(self):
        cash0 = int(self.w.actor("player")["cash_copper"])
        region0 = str(self.w.actor("player")["region_id"])
        r = self.w.submit_player_command(
            "player", "travel", {"destination": "dwargon", "cash_copper": 0}
        )
        self.assertFalse(r["accepted"])
        self.assertEqual(int(self.w.actor("player")["cash_copper"]), cash0)
        self.assertEqual(str(self.w.actor("player")["region_id"]), region0)
        self.assertEqual(str(self.w.actor("player")["status"]), "idle")

    def test_travel_is_validated_and_delayed(self):
        start = self.w.now
        r = self.w.submit_player_command("player", "travel", {"destination": "dwargon"})
        self.assertTrue(r["accepted"])
        due = int(r["result"]["due_at"])
        self.assertEqual(str(self.w.actor("player")["region_id"]), "blumund")
        self.w.advance(due - start - 1)
        self.assertEqual(str(self.w.actor("player")["region_id"]), "blumund")
        self.w.advance(1)
        self.assertEqual(str(self.w.actor("player")["region_id"]), "dwargon")

    def test_invalid_travel_does_not_mutate(self):
        before = dict(self.w.actor("player"))
        r = self.w.submit_player_command("player", "travel", {"destination": "moon"})
        self.assertFalse(r["accepted"])
        after = dict(self.w.actor("player"))
        self.assertEqual(before["region_id"], after["region_id"])
        self.assertEqual(before["cash_copper"], after["cash_copper"])

    def test_buy_command_is_atomic(self):
        cash0 = int(self.w.actor("player")["cash_copper"])
        r = self.w.submit_player_command("player", "buy", {"commodity": "grain", "qty": 2})
        self.assertTrue(r["accepted"])
        self.assertLess(int(self.w.actor("player")["cash_copper"]), cash0)
        cash1 = int(self.w.actor("player")["cash_copper"])
        bad = self.w.submit_player_command("player", "buy", {"commodity": "grain", "qty": 999999})
        self.assertFalse(bad["accepted"])
        self.assertEqual(int(self.w.actor("player")["cash_copper"]), cash1)

    def test_seeded_skill_checks_are_auditable_and_deterministic(self):
        other = Path(self.tmp.name) / "w2.db"
        w2 = seed_world_v04(other)
        try:
            a = self.w.submit_player_command("player", "attempt", {"skill": "performance", "difficulty": "hard"})
            b = w2.submit_player_command("player", "attempt", {"skill": "performance", "difficulty": "hard"})
            self.assertEqual(a, b)
            row = self.w.db.execute("SELECT * FROM checks ORDER BY id DESC LIMIT 1").fetchone()
            self.assertEqual(int(row["total"]), int(a["result"]["total"]))
        finally:
            w2.close()

    def test_remote_attack_rejected(self):
        self.w.db.execute("UPDATE actors SET region_id='jura_edge' WHERE id='sparring_rival'")
        self.w.db.commit()
        hp = int(self.w.stats("sparring_rival")["hp"])
        r = self.w.submit_player_command("player", "attack", {"target": "sparring_rival"})
        self.assertFalse(r["accepted"])
        self.assertEqual(int(self.w.stats("sparring_rival")["hp"]), hp)

    def test_combat_can_create_injury_and_death(self):
        self.w.set_skill("player", "melee", 30)
        self.w.db.execute("UPDATE actor_stats SET hp=1,max_hp=18 WHERE actor_id='sparring_rival'")
        self.w.db.commit()
        r = self.w.submit_player_command("player", "attack", {"target": "sparring_rival"})
        self.assertTrue(r["accepted"])
        self.assertTrue(r["result"]["target_dead"])
        self.assertEqual(int(self.w.stats("sparring_rival")["alive"]), 0)
        death = self.w.db.execute("SELECT COUNT(*) FROM events WHERE event_type='actor_death'").fetchone()[0]
        self.assertEqual(death, 1)

    def test_witnessed_crime_creates_delayed_legal_consequence(self):
        rep0 = self.w.reputation("player", "blumund")["authority"]
        c = self.w.record_crime("player", "theft", witnessed=True)
        self.assertTrue(c["witnessed"])
        self.assertLess(self.w.reputation("player", "blumund")["authority"], rep0)
        case = self.w.db.execute("SELECT * FROM legal_cases WHERE crime_id=?", (c["crime_id"],)).fetchone()
        self.assertEqual(case["status"], "pending")
        self.w.advance(int(case["due_at"]) - self.w.now)
        case2 = self.w.db.execute("SELECT * FROM legal_cases WHERE id=?", (case["id"],)).fetchone()
        self.assertEqual(case2["status"], "summons_issued")
        crime = self.w.db.execute("SELECT status FROM crimes WHERE id=?", (c["crime_id"],)).fetchone()
        self.assertEqual(crime["status"], "wanted")

    def test_unwitnessed_crime_does_not_instantly_create_case(self):
        c = self.w.record_crime("player", "theft", witnessed=False)
        case = self.w.db.execute("SELECT 1 FROM legal_cases WHERE crime_id=?", (c["crime_id"],)).fetchone()
        self.assertIsNone(case)

    def test_player_appointment_never_auto_attends_and_can_be_explicitly_met(self):
        appt = self.w.db.execute(
            "SELECT * FROM appointments WHERE actor_id='player' ORDER BY id LIMIT 1"
        ).fetchone()
        self.w.advance(int(appt["due_at"]) - self.w.now + 10)
        status = self.w.db.execute("SELECT status FROM appointments WHERE id=?", (appt["id"],)).fetchone()[0]
        self.assertEqual(status, "waiting")
        result = self.w.submit_player_command("player", "attend", {"appointment_id": int(appt["id"])})
        self.assertTrue(result["accepted"])
        status = self.w.db.execute("SELECT status FROM appointments WHERE id=?", (appt["id"],)).fetchone()[0]
        self.assertEqual(status, "met")

    def test_player_appointment_long_jump_becomes_missed_not_met(self):
        appt_id = self.w.schedule_appointment(
            "player", "captain_dalen", "blumund", self.w.now + 60,
            grace_minutes=20, purpose="briefing"
        )
        self.w.advance(100)
        status = self.w.db.execute("SELECT status FROM appointments WHERE id=?", (appt_id,)).fetchone()[0]
        self.assertEqual(status, "missed")

    def test_appointment_can_be_missed(self):
        appt_id = self.w.schedule_appointment(
            "player", "captain_dalen", "dwargon", self.w.now + 60,
            grace_minutes=20, purpose="formal hearing"
        )
        self.w.advance(100)
        status = self.w.db.execute("SELECT status FROM appointments WHERE id=?", (appt_id,)).fetchone()[0]
        self.assertEqual(status, "missed")

    def test_memory_salience_forgets_trivial_but_preserves_important(self):
        self.w.remember("player", "smalltalk", "A trivial tavern greeting.", salience=20, emotional=0)
        self.w.remember("player", "life_event", "A life-changing promise.", salience=95, emotional=80)
        self.w.advance(20 * 1440)
        trivial = self.w.db.execute(
            "SELECT status,salience FROM memories WHERE actor_id='player' AND memory_key='smalltalk'"
        ).fetchone()
        important = self.w.db.execute(
            "SELECT status,salience FROM memories WHERE actor_id='player' AND memory_key='life_event'"
        ).fetchone()
        self.assertEqual(trivial["status"], "forgotten")
        self.assertEqual(important["status"], "active")
        self.assertGreaterEqual(int(important["salience"]), 80)

    def test_canon_event_does_not_leak_into_actor_knowledge(self):
        ce = self.w.db.execute("SELECT * FROM canon_events WHERE event_key='jura_orc_movement'").fetchone()
        self.w.advance(int(ce["due_at"]) - self.w.now)
        fact_key = "canon:jura_orc_movement"
        self.assertIsNotNone(self.w.db.execute("SELECT 1 FROM facts WHERE key=?", (fact_key,)).fetchone())
        self.assertIsNone(self.w.db.execute(
            "SELECT 1 FROM actor_knowledge WHERE actor_id='player' AND fact_key=?", (fact_key,)
        ).fetchone())
        self.w.advance(400)
        self.assertTrue(self.w.observe_local_fact("player", fact_key))
        self.assertIsNotNone(self.w.db.execute(
            "SELECT 1 FROM actor_knowledge WHERE actor_id='player' AND fact_key=?", (fact_key,)
        ).fetchone())

    def test_context_is_small_and_contains_only_player_relevant_v04_state(self):
        self.w.remember("player", "important", "Remember this.", salience=90)
        ctx = self.w.build_context()
        raw = json.dumps(ctx, ensure_ascii=False)
        self.assertLess(len(raw), 8000)
        self.assertIn("hp", ctx["player"])
        self.assertIn("reputation", ctx)
        self.assertTrue(any(m["key"] == "important" for m in ctx["memories"]))
        self.assertNotIn("canon:jura_orc_movement", [x["key"] for x in ctx["known_facts"]])

    def test_v03_macro_world_keeps_running_under_v04(self):
        cash0 = int(self.w.actor("player")["cash_copper"])
        region0 = str(self.w.actor("player")["region_id"])
        self.w.db.execute("UPDATE appointments SET status='cancelled' WHERE actor_id='player'")
        self.w.advance(30 * 1440)
        self.assertEqual(int(self.w.actor("player")["cash_copper"]), cash0)
        self.assertEqual(str(self.w.actor("player")["region_id"]), region0)
        self.assertGreater(self.w.metric("macro_ticks"), 0)
        self.assertGreater(self.w.metric("faction_actions"), 0)
        grain = self.w.db.execute("SELECT supply FROM markets WHERE region_id='blumund' AND commodity_id='grain'").fetchone()[0]
        self.assertGreaterEqual(int(grain), 0)


if __name__ == "__main__":
    unittest.main()
