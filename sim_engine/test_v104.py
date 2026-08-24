import tempfile
import unittest
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v104_seed import seed_world_v104_lab


class V104Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _install(w):
        install_v100_runtime(
            w,
            159,
            {"v": 159, "delta": "live_v159", "parent": "abc", "economy": "ECONOMY_MODEL_v1"},
            "legacysha",
        )
        w.db.execute("UPDATE actors SET region_id='eurazania',cash_copper=260592 WHERE id='player'")
        w.db.execute(
            "INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) "
            "VALUES(?,?,?,?,?)",
            ("player", "большой тренировочный двор Борги", "test", "memory/places.json", w.now),
        )
        w.db.execute(
            "INSERT OR REPLACE INTO actor_position_claims"
            "(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) "
            "VALUES('borga','Борга','eurazania',NULL,'region_only','target_in_current_capital_context',159,"
            "'memory/relationships.json','')"
        )
        w.db.commit()

    @staticmethod
    def _anchor_small_yard(w):
        slot = (int(w.now) // 60) * 60
        w._put_fact103(
            f"v103:named_presence:borga:{slot}",
            {
                "actor_key": "borga",
                "display_name": "Борга",
                "slot_start": slot,
                "slot_end": slot + 60,
                "region_id": "eurazania",
                "place_key": "eurazania_small_training_yard",
                "place_text": "малый боевой/тренировочный двор",
                "certainty": "prospective_hidden_schedule_exact",
                "authority": "NON_CANON_MECHANICAL_PROSPECTIVE",
                "historical_claim": False,
            },
            "test:v103_anchor",
            significance=45,
            origin_region_id="eurazania",
        )
        w.db.commit()

    def test_character_core_persists_without_invented_personality(self):
        db = Path(self.tmp.name) / "a.db"
        with seed_world_v104_lab(db) as w:
            self._install(w)
            core1 = w.ensure_character_core_v104("borga")
            core2 = w.ensure_character_core_v104("borga")
            self.assertEqual(core1, core2)
            self.assertEqual(core1["personality"]["status"], "not_yet_authored")
            self.assertEqual(core1["personality"]["traits"], [])
            self.assertEqual(core1["relationships"], {})
            self.assertEqual(core1["memories"], [])

    def test_current_day_plan_uses_existing_v103_presence_as_migration_anchor(self):
        db = Path(self.tmp.name) / "b.db"
        with seed_world_v104_lab(db) as w:
            self._install(w)
            delta = (480 - (w.now % 1440)) % 1440
            if delta:
                w.advance(delta)
            self._anchor_small_yard(w)
            core = w.ensure_character_core_v104("borga")
            plan = w.ensure_character_plan_v104("borga")
            self.assertEqual(plan["migration_anchor_used"], "eurazania_small_training_yard")
            self.assertEqual(plan["blocks"][0]["place_key"], "eurazania_small_training_yard")
            self.assertEqual((core["planning"]["migration_anchor"] or {})["place_key"], "eurazania_small_training_yard")
            presence = w._borga_presence103(w.now)
            self.assertEqual(presence["place_key"], "eurazania_small_training_yard")

    def test_transition_window_keeps_exact_position_unknown(self):
        db = Path(self.tmp.name) / "c.db"
        with seed_world_v104_lab(db) as w:
            self._install(w)
            delta = (545 - (w.now % 1440)) % 1440
            if delta:
                w.advance(delta)
            presence = w._borga_presence103(w.now)
            self.assertIsNone(presence["place_key"])
            self.assertEqual(presence["plan_block_kind"], "local_travel")
            self.assertEqual(presence["certainty"], "prospective_hidden_region_only")

    def test_borga_search_uses_character_plan_and_preserves_cash(self):
        db = Path(self.tmp.name) / "d.db"
        with seed_world_v104_lab(db) as w:
            self._install(w)
            delta = (480 - (w.now % 1440)) % 1440
            if delta:
                w.advance(delta)
            self._anchor_small_yard(w)
            cash0 = int(w.actor("player")["cash_copper"])
            out = w.process_player_turn("search-v104", "Осматриваюсь. Ищу Боргу.")
            self.assertEqual(out["status"], "executed")
            self.assertEqual(out["result"]["outcome"], "lead")
            self.assertEqual(out["result"]["lead"]["destination_key"], "eurazania_small_training_yard")
            self.assertEqual(out["result"]["search_minutes"], 6)
            self.assertEqual(int(w.actor("player")["cash_copper"]), cash0)

    def test_activation_event_is_replayable_and_zero_time(self):
        base_db = Path(self.tmp.name) / "e.db"
        with seed_world_v104_lab(base_db) as base:
            self._install(base)
            delta = (480 - (base.now % 1440)) % 1440
            if delta:
                base.advance(delta)
            self._anchor_small_yard(base)
            snapshot = export_portable_checkpoint_v100(base, 159)
            t0 = int(base.now)

        exec_db = Path(self.tmp.name) / "f.db"
        with seed_world_v104_lab(exec_db) as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snapshot)["ok"])
            event = w.execute_runtime_event(
                1,
                "activate-v104",
                "character_core_activation",
                {"reason": "test"},
            )
            entry = event["journal"]
            expected = runtime_state_hash_v100(w, 159)
            self.assertEqual(int(w.now), t0)
            self.assertTrue(w.character_core_v104("borga"))

        replay_db = Path(self.tmp.name) / "g.db"
        with seed_world_v104_lab(replay_db) as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snapshot)["ok"])
            replay = w.replay_runtime_entries([entry])
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(runtime_state_hash_v100(w, 159), expected)

    def test_session_state_keeps_hud_contract(self):
        db = Path(self.tmp.name) / "h.db"
        with seed_world_v104_lab(db) as w:
            self._install(w)
            event = w.execute_runtime_event(
                1,
                "activate-session-v104",
                "character_core_activation",
                {"reason": "test"},
            )
            state = w.build_session_state_v104(
                journal_seq=1,
                head_state_hash=event["journal"]["after_hash"],
                last_event=event["journal"],
            )
            self.assertEqual(state["engine_version"], "1.0.4")
            self.assertEqual(state["hud"]["money"]["on_person_copper"], 260592)
            self.assertTrue(state["display_contract"]["normal_play_technical_fields_hidden"])
            self.assertTrue(state["character_runtime"]["hidden_plans_not_narrator_knowledge"])


if __name__ == "__main__":
    unittest.main()
