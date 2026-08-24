import tempfile
import unittest
from pathlib import Path

from v102_seed import seed_world_v102_lab


class V102Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_hud_formats_time_location_and_wallet(self):
        db = Path(self.tmp.name) / "a.db"
        with seed_world_v102_lab(db) as w:
            w.db.execute(
                "INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
                ("player", "большой тренировочный двор Борги", "test", "test", w.now),
            )
            w.db.commit()
            hud = w.build_hud_v102()
            self.assertIn("T+", hud["time"]["display"])
            self.assertEqual(hud["location"]["display"], "большой тренировочный двор Борги")
            self.assertTrue(hud["money"]["on_person_display"].endswith("c"))

    def test_project_and_family_money_are_not_personal_elsewhere(self):
        db = Path(self.tmp.name) / "b.db"
        with seed_world_v102_lab(db) as w:
            w.db.execute("DELETE FROM financial_account_state")
            rows = [
                ("lissa_project", "project_fund", 40000, None, "EXACT", "lissa_project", "active", 159, "test", ""),
                ("family_purse", "family_fund", 10000, None, "EXACT", "family", "active", 159, "test", ""),
                ("vern_instrument_float", "entrusted_float", None, 5000, "UNKNOWN", "vern", "pending", 159, "test", ""),
            ]
            w.db.executemany(
                "INSERT INTO financial_account_state(account_id,account_type,balance_copper,known_principal_copper,certainty,holder_key,status,as_of_version,source_path,note) VALUES(?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            w.db.commit()
            elsewhere = w.build_hud_v102()["money"]["elsewhere"]
            self.assertEqual([x["account_id"] for x in elsewhere], ["vern_instrument_float"])
            self.assertEqual(elsewhere[0]["balance_display"], "UNKNOWN")
            self.assertEqual(elsewhere[0]["known_principal_display"], "50s 00c")

    def test_compact_packet_has_hud_and_hides_migration_dump(self):
        db = Path(self.tmp.name) / "c.db"
        with seed_world_v102_lab(db) as w:
            packet = w.build_gm_packet("player")
            self.assertIn("hud", packet)
            self.assertNotIn("migration", packet)
            self.assertEqual(packet["runtime"]["engine"], "1.0.2")
            self.assertIn("hud_required", packet["constraints"])

    def test_session_state_has_mandatory_display_contract(self):
        db = Path(self.tmp.name) / "d.db"
        with seed_world_v102_lab(db) as w:
            state = w.build_session_state_v102(journal_seq=3, head_state_hash="abc", last_event=None)
            self.assertEqual(state["journal_seq"], 3)
            self.assertEqual(len(state["display_contract"]["always_show"]), 4)
            self.assertIn("elsewhere_display", state["hud"]["money"])


if __name__ == "__main__":
    unittest.main()
