import tempfile
import unittest
from pathlib import Path

from v03_engine import dumps
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v106_seed import seed_world_v106_lab

BAD_KEY = "chat-20260824-go-small-training-yard-r000006"
RAW = "Илу в малый тренировочный лагерь."


class V106Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _install(w):
        install_v100_runtime(w, 159, {"v":159,"delta":"live_v159","parent":"abc","economy":"ECONOMY_MODEL_v1"}, "legacysha")
        w.db.execute("UPDATE actors SET region_id='eurazania',cash_copper=260592 WHERE id='player'")
        w.db.execute(
            "INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
            ("player", "большой тренировочный двор Борги", "test", "memory/places.json", w.now),
        )
        for key, name in (("borga","Борга"),("rena","Рена")):
            w.db.execute(
                "INSERT OR REPLACE INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) VALUES(?,?,?,?,?,?,?,?,?)",
                (key,name,"eurazania",None,"region_only","known_region_exact_place_unknown",159,"test",""),
            )
        fact_key = "v103:player_observation:test-small-yard-lead"
        lead = {"outcome":"lead","lead":{"destination_key":"eurazania_small_training_yard","destination_text":"малый боевой/тренировочный двор"}}
        w.db.execute("INSERT OR REPLACE INTO facts(key,value_json,created_at,source) VALUES(?,?,?,?)", (fact_key,dumps(lead),w.now,"test"))
        w.db.execute("INSERT OR REPLACE INTO knowledge(actor_id,fact_key,learned_at,source,confidence) VALUES(?,?,?,?,?)", ("player",fact_key,w.now,"test",90))
        w.db.commit()

    @staticmethod
    def _insert_bad_turn(w):
        w.db.execute("INSERT INTO gm_turns(turn_key,player_id,raw_text,status,created_at) VALUES(?,?,?,?,?)", (BAD_KEY,"player",RAW,"scene_pending",w.now))
        cur = w.db.execute(
            "INSERT INTO scene_actions(turn_key,world_minute,actor_id,action_kind,raw_text,components_json,resolution_mode,status,effect_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (BAD_KEY,w.now,"player","generic_player_action_attempt",RAW,"[]","pending_resolution","pending","{}",w.now),
        )
        w.db.execute(
            "INSERT INTO scene_pending_resolution(scene_action_id,resolution_kind,target_key,target_text,state_json,status,created_at) VALUES(?,?,?,?,?,'pending',?)",
            (int(cur.lastrowid),"world_resolution_required","rena","Рена","{}",w.now),
        )
        w.db.commit()

    def test_training_word_does_not_mention_rena(self):
        with seed_world_v106_lab(Path(self.tmp.name)/"a.db") as w:
            self._install(w)
            self.assertEqual(w._safe_named_mentions_v106(RAW), [])
            self.assertEqual(w._safe_named_mentions_v106("Иду к Рене."), [{"id":"rena","name":"Рена"}])

    def test_typo_and_known_lead_resolve_small_yard(self):
        with seed_world_v106_lab(Path(self.tmp.name)/"b.db") as w:
            self._install(w)
            destination = w._match_known_local_place_v101("player", RAW)
            self.assertEqual(destination["key"], "eurazania_small_training_yard")
            t0 = int(w.now)
            cash0 = int(w.actor("player")["cash_copper"])
            out = w.process_player_turn("retry-v106", RAW)
            self.assertEqual(out["status"], "executed")
            self.assertEqual(out["result"]["destination_key"], "eurazania_small_training_yard")
            self.assertEqual(int(w.now)-t0, 12)
            self.assertEqual(int(w.actor("player")["cash_copper"]), cash0)

    def test_generic_fallback_cannot_attach_unmentioned_rena(self):
        with seed_world_v106_lab(Path(self.tmp.name)/"c.db") as w:
            self._install(w)
            proposal = w.propose_scene_action("player", "Смотрю на тренировочный инвентарь.")
            self.assertEqual(proposal["status"], "ready")
            self.assertTrue(proposal["pending"])
            self.assertTrue(all(p.get("target_key") != "rena" for p in proposal["pending"]))

    def test_activation_cancels_false_pending_without_time_or_money_change(self):
        with seed_world_v106_lab(Path(self.tmp.name)/"d.db") as w:
            self._install(w); self._insert_bad_turn(w)
            t0, cash0 = int(w.now), int(w.actor("player")["cash_copper"])
            event = w.execute_runtime_event(1,"activate-v106","intent_grounding_repair_activation",{"reason":"test"})
            row = w.db.execute("SELECT status,target_key FROM scene_pending_resolution ORDER BY id DESC LIMIT 1").fetchone()
            self.assertEqual(row["status"], "cancelled_parser_false_positive")
            self.assertEqual(row["target_key"], "rena")
            self.assertEqual(int(w.now), t0)
            self.assertEqual(int(w.actor("player")["cash_copper"]), cash0)
            self.assertEqual(event["journal"]["result"]["repair"]["status"], "repaired")

    def test_activation_replays(self):
        base_path = Path(self.tmp.name)/"e.db"
        with seed_world_v106_lab(base_path) as base:
            self._install(base); self._insert_bad_turn(base)
            snapshot = export_portable_checkpoint_v100(base,159)
        with seed_world_v106_lab(Path(self.tmp.name)/"f.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w,snapshot)["ok"])
            entry = w.execute_runtime_event(1,"activate-replay-v106","intent_grounding_repair_activation",{"reason":"test"})["journal"]
            expected = runtime_state_hash_v100(w,159)
        with seed_world_v106_lab(Path(self.tmp.name)/"g.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w,snapshot)["ok"])
            replay = w.replay_runtime_entries([entry])
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(runtime_state_hash_v100(w,159), expected)


if __name__ == "__main__":
    unittest.main()
