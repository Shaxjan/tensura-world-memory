import tempfile
import unittest
from pathlib import Path

from v03_engine import dumps
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v107_seed import seed_world_v107_lab


class V107Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _install(w, *, visible=True):
        install_v100_runtime(w, 159, {"v":159,"delta":"live_v159","parent":"abc","economy":"ECONOMY_MODEL_v1"}, "legacysha")
        w.db.execute("UPDATE actors SET region_id='eurazania',cash_copper=260592 WHERE id='player'")
        w.db.execute(
            "INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
            ("player", "малый боевой/тренировочный двор", "test", "memory/places.json", w.now),
        )
        w.db.execute(
            "INSERT OR REPLACE INTO actor_position_claims"
            "(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) "
            "VALUES('borga','Борга','eurazania',NULL,'region_only','target_in_current_capital_context',159,'memory/relationships.json','')"
        )
        w.db.execute(
            "INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) "
            "VALUES('task:borga','borga','npc_task',?,'ACTIVE','memory/actions.json',159)",
            (dumps({"person":"Борга","task":"combat rules, admissions, judges, testing and tournament operations","status":"ACTIVE"}),),
        )
        w.db.execute(
            "INSERT OR REPLACE INTO autonomy_runtime"
            "(commitment_key,handler,next_due_at,cadence_minutes,tick_count,last_run_at,status,last_outcome_json) "
            "VALUES('task:borga','character_task_v105',?,30,1,?,'active','{}')",
            (w.now + 30, w.now),
        )
        w.db.commit()
        w.ensure_character_core_v104("borga")
        if visible:
            w._visible_set103("borga", "Борга", {"key":"eurazania_small_training_yard","name":"малый боевой/тренировочный двор"})
            w.db.commit()
        return int(w.now)

    def test_activation_is_zero_time_and_does_not_create_retroactive_memory(self):
        with seed_world_v107_lab(Path(self.tmp.name)/"a.db") as w:
            t0 = self._install(w, visible=True)
            cash0 = int(w.actor("player")["cash_copper"])
            before = list((w.character_core_v104("borga") or {}).get("memories") or [])
            out = w.execute_runtime_event(1, "activate-v107", "causal_encounter_memory_activation", {"reason":"test"})
            after = list((w.character_core_v104("borga") or {}).get("memories") or [])
            self.assertEqual(w.now, t0)
            self.assertEqual(int(w.actor("player")["cash_copper"]), cash0)
            self.assertEqual(after, before)
            self.assertFalse(out["journal"]["result"]["retroactive_memory_created"])
            self.assertIsNone(w.db.execute("SELECT 1 FROM actors WHERE id='borga'").fetchone())

    def test_visible_addressed_speech_creates_fact_memory_and_core_reference(self):
        with seed_world_v107_lab(Path(self.tmp.name)/"b.db") as w:
            self._install(w, visible=True)
            w.activate_causal_encounter_memory_v107()
            relationships0 = dict((w.character_core_v104("borga") or {}).get("relationships") or {})
            raw = "Говорю: «Борга, доброе утро.»"
            result = w.process_player_turn("turn-address-borga", raw)
            self.assertTrue(result["accepted"])
            key = "v107:character_memory:borga:turn-address-borga"
            memory = w._get_fact103(key)
            self.assertIsNotNone(memory)
            self.assertEqual(memory["observed_player_text_verbatim"], raw)
            self.assertIsNone(memory["emotional_interpretation"])
            self.assertIsNone(memory["relationship_delta"])
            self.assertIn("truth of any proposition spoken by the player", memory["does_not_assert"])
            core = w.character_core_v104("borga") or {}
            self.assertTrue(any(row.get("memory_key") == key for row in core.get("memories") or []))
            self.assertEqual(dict(core.get("relationships") or {}), relationships0)
            self.assertIsNone(w.db.execute("SELECT 1 FROM actors WHERE id='borga'").fetchone())

    def test_player_observation_without_address_does_not_create_borga_memory(self):
        with seed_world_v107_lab(Path(self.tmp.name)/"c.db") as w:
            self._install(w, visible=True)
            w.activate_causal_encounter_memory_v107()
            self.assertEqual(list((w.character_core_v104("borga") or {}).get("memories") or []), [])
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM facts WHERE key LIKE 'v107:character_memory:borga:%'").fetchone()[0], 0)

    def test_explicit_borga_address_without_visibility_does_not_create_memory(self):
        with seed_world_v107_lab(Path(self.tmp.name)/"d.db") as w:
            self._install(w, visible=False)
            w.activate_causal_encounter_memory_v107()
            result = w.process_player_turn("turn-not-visible", "Говорю: «Борга, доброе утро.»")
            self.assertTrue(result["accepted"])
            self.assertIsNone(w._get_fact103("v107:character_memory:borga:turn-not-visible"))

    def test_replayed_turn_does_not_duplicate_memory(self):
        with seed_world_v107_lab(Path(self.tmp.name)/"e.db") as w:
            self._install(w, visible=True)
            w.activate_causal_encounter_memory_v107()
            raw = "Говорю: «Борга, доброе утро.»"
            w.process_player_turn("turn-once", raw)
            first = list((w.character_core_v104("borga") or {}).get("memories") or [])
            w.process_player_turn("turn-once", raw)
            second = list((w.character_core_v104("borga") or {}).get("memories") or [])
            self.assertEqual(first, second)
            self.assertEqual(len([row for row in second if row.get("memory_key") == "v107:character_memory:borga:turn-once"]), 1)

    def test_activation_and_addressed_turn_replay_deterministically(self):
        base_path = Path(self.tmp.name)/"base.db"
        with seed_world_v107_lab(base_path) as base:
            self._install(base, visible=True)
            snap = export_portable_checkpoint_v100(base, 159)
        exec_path = Path(self.tmp.name)/"exec.db"
        with seed_world_v107_lab(exec_path) as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            a = w.execute_runtime_event(1, "a-v107", "causal_encounter_memory_activation", {"reason":"test"})["journal"]
            b = w.execute_runtime_event(2, "b-v107", "player_turn", {"raw_text":"Говорю: «Борга, доброе утро.»"})["journal"]
            expected = runtime_state_hash_v100(w, 159)
        replay_path = Path(self.tmp.name)/"replay.db"
        with seed_world_v107_lab(replay_path) as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            replay = w.replay_runtime_entries([a,b])
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(runtime_state_hash_v100(w, 159), expected)


if __name__ == "__main__":
    unittest.main()
