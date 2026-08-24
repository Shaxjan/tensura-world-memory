import tempfile
import unittest
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v103_seed import seed_world_v103_lab


class V103Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _install(w):
        install_v100_runtime(w, 159, {"v":159,"delta":"live_v159","parent":"abc","economy":"ECONOMY_MODEL_v1"}, "legacysha")
        w.db.execute("UPDATE actors SET region_id='eurazania',cash_copper=260592 WHERE id='player'")
        w.db.execute("INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
                     ("player", "большой тренировочный двор Борги", "test", "memory/places.json", w.now))
        w.db.execute("INSERT OR REPLACE INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) VALUES('borga','Борга','eurazania',NULL,'region_only','target_in_current_capital_context',159,'memory/relationships.json','')")
        w.db.commit()

    def test_observe_materializes_persistent_ambient_scene(self):
        db = Path(self.tmp.name) / "a.db"
        with seed_world_v103_lab(db) as w:
            self._install(w)
            t0 = w.now
            out = w.process_player_turn("observe", "Осматриваюсь.")
            self.assertEqual(out["status"], "executed")
            self.assertEqual(w.now - t0, 1)
            ambient = out["gm_packet"]["scene"]["ambient"]
            self.assertGreaterEqual(len(ambient), 3)
            keys = [x["entity_key"] for x in ambient]
            w.advance(2)
            packet = w.build_gm_packet("player")
            self.assertEqual(keys, [x["entity_key"] for x in packet["scene"]["ambient"]])

    def test_borga_search_is_finite_and_causal(self):
        db = Path(self.tmp.name) / "b.db"
        with seed_world_v103_lab(db) as w:
            self._install(w)
            t0 = w.now
            cash0 = int(w.actor("player")["cash_copper"])
            out = w.process_player_turn("search", "Осматриваюсь. Ищу Боргу.")
            self.assertEqual(out["status"], "executed")
            self.assertIn(out["result"]["outcome"], {"found", "lead", "not_found_no_lead"})
            self.assertEqual(out["result"]["search_minutes"], 6)
            self.assertEqual(w.now - t0, 6)
            self.assertEqual(int(w.actor("player")["cash_copper"]), cash0)
            self.assertGreater(len(out["gm_packet"]["scene"]["ambient"]), 0)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM scene_pending_resolution WHERE status='pending'").fetchone()[0], 0)
            claim = w.db.execute("SELECT precision FROM actor_position_claims WHERE actor_key='borga'").fetchone()
            self.assertEqual(claim[0], "region_only")

    def test_resume_old_pending_completes_same_authorized_search(self):
        db = Path(self.tmp.name) / "c.db"
        with seed_world_v103_lab(db) as w:
            self._install(w)
            raw = "Осматриваюсь. Ищу Боргу. (Гитара у меня)"
            w.db.execute("INSERT INTO gm_turns(turn_key,player_id,raw_text,status,created_at) VALUES('old','player',?,'scene_pending',?)", (raw, w.now))
            action = w.db.execute("INSERT INTO scene_actions(turn_key,world_minute,actor_id,action_kind,raw_text,components_json,resolution_mode,status,effect_json,created_at) VALUES('old',?,'player','local_search_or_move',?,'[]','pending_resolution','pending','{}',?)", (w.now, raw, w.now))
            pending = w.db.execute("INSERT INTO scene_pending_resolution(scene_action_id,resolution_kind,target_key,target_text,state_json,status,created_at) VALUES(?,'local_navigation','borga','Борга','{}','pending',?)", (int(action.lastrowid), w.now))
            w.db.commit()
            t0 = w.now
            event = w.execute_runtime_event(1, "resume-old", "living_scene_resume", {"pending_id": int(pending.lastrowid)})
            self.assertEqual(event["journal"]["result"]["status"], "executed")
            self.assertEqual(w.now - t0, 6)
            self.assertEqual(w.db.execute("SELECT status FROM scene_pending_resolution WHERE id=?", (int(pending.lastrowid),)).fetchone()[0], "resolved")

    def test_living_search_replay_is_deterministic(self):
        base_db = Path(self.tmp.name) / "d.db"
        with seed_world_v103_lab(base_db) as base:
            self._install(base)
            snap = export_portable_checkpoint_v100(base, 159)
        exec_db = Path(self.tmp.name) / "e.db"
        with seed_world_v103_lab(exec_db) as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            event = w.execute_runtime_event(1, "search-replay", "player_turn", {"raw_text": "Ищу Боргу на дворе."})
            entry = event["journal"]
            expected = runtime_state_hash_v100(w, 159)
        replay_db = Path(self.tmp.name) / "f.db"
        with seed_world_v103_lab(replay_db) as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            replay = w.replay_runtime_entries([entry])
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(runtime_state_hash_v100(w, 159), expected)

    def test_session_state_carries_living_scene_and_hud(self):
        db = Path(self.tmp.name) / "g.db"
        with seed_world_v103_lab(db) as w:
            self._install(w)
            event = w.execute_runtime_event(1, "observe-session", "player_turn", {"raw_text":"Осматриваюсь."})
            state = w.build_session_state_v103(journal_seq=1, head_state_hash=event["journal"]["after_hash"], last_event=event["journal"])
            self.assertEqual(state["engine_version"], "1.0.3")
            self.assertEqual(state["hud"]["money"]["on_person_copper"], 260592)
            self.assertGreater(len(state["scene"]["ambient"]), 0)
            self.assertTrue(state["display_contract"]["normal_play_technical_fields_hidden"])


if __name__ == "__main__":
    unittest.main()
