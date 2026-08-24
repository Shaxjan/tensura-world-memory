import tempfile
import unittest
from pathlib import Path

from v03_engine import dumps
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v110_seed import seed_world_v110_lab


class V110Tests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmp.cleanup()

    @staticmethod
    def _install(w):
        w._set_now(189138)
        install_v100_runtime(w, 159, {"v":159,"delta":"live_v159","parent":"abc","economy":"ECONOMY_MODEL_v1"}, "legacysha")
        w.db.execute("UPDATE actors SET region_id='eurazania',cash_copper=260592 WHERE id='player'")
        w.db.execute(
            "INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
            ("player","малый боевой/тренировочный двор","test","memory/places.json",w.now),
        )
        w.db.execute(
            "INSERT OR REPLACE INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) VALUES('borga','Борга','eurazania',NULL,'region_only','target_in_current_capital_context',159,'memory/relationships.json','')"
        )
        w.db.execute(
            "INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) VALUES('task:borga','borga','npc_task',?,'ACTIVE','memory/actions.json',159)",
            (dumps({"person":"Борга","task":"combat rules, admissions, judges, testing and tournament operations","status":"ACTIVE"}),),
        )
        w.db.execute(
            "INSERT OR REPLACE INTO autonomy_runtime(commitment_key,handler,next_due_at,cadence_minutes,tick_count,last_run_at,status,last_outcome_json) VALUES('task:borga','character_task_v105',?,30,1,?,'active','{}')",
            (w.now + 30, w.now - 4),
        )
        slot = (w.now // 60) * 60
        w._put_fact103(
            f"v103:named_presence:borga:{slot}",
            {"actor_key":"borga","display_name":"Борга","slot_start":slot,"slot_end":slot+60,"region_id":"eurazania","place_key":"eurazania_small_training_yard","place_text":"малый боевой/тренировочный двор","certainty":"test_anchor","authority":"NON_CANON_MECHANICAL_PROSPECTIVE","historical_claim":False},
            "test:v110_anchor", significance=40, origin_region_id="eurazania",
        )
        w.db.commit()
        w.ensure_character_core_v104("borga")
        w.ensure_character_plan_v104("borga", w.now)
        place = w._place103("player")
        w.ensure_living_scene_v103("player")
        w._visible_set103("borga", "Борга", place)
        w.db.commit()
        return int(w.now)

    def test_activation_does_not_retroactively_answer_existing_greeting(self):
        with seed_world_v110_lab(Path(self.tmp.name) / "a.db") as w:
            t0 = self._install(w)
            old = w.process_player_turn("old-greeting", "Обращаюсь к Борге: «Доброе утро».")
            self.assertTrue(old["accepted"])
            self.assertIsNotNone(w._get_fact103("v107:character_memory:borga:old-greeting"))
            self.assertIsNone(w._get_fact103("v110:player_observed_response:borga:old-greeting"))
            core0 = w.character_core_v104("borga") or {}
            memories0 = list(core0.get("memories") or []); rel0 = dict(core0.get("relationships") or {}); personality0 = dict(core0.get("personality") or {})
            out = w.activate_causal_npc_response_v110()
            self.assertFalse(out["retroactive_response_created"])
            self.assertEqual(w.now, t0)
            self.assertIsNone(w._get_fact103("v110:player_observed_response:borga:old-greeting"))
            core1 = w.character_core_v104("borga") or {}
            self.assertEqual(core1.get("memories"), memories0)
            self.assertEqual(core1.get("relationships"), rel0)
            self.assertEqual(core1.get("personality"), personality0)

    def test_new_simple_visible_greeting_gets_minimal_authoritative_response(self):
        with seed_world_v110_lab(Path(self.tmp.name) / "b.db") as w:
            t0 = self._install(w); w.activate_causal_npc_response_v110()
            rel0 = dict((w.character_core_v104("borga") or {}).get("relationships") or {})
            memories0 = len(list((w.character_core_v104("borga") or {}).get("memories") or []))
            public = w.process_player_turn("new-greeting", "Обращаюсь к Борге: «Доброе утро».")
            result = public.get("result") or {}; response = result.get("npc_response") or {}
            self.assertEqual(result.get("outcome"), "npc_response_resolved")
            self.assertEqual(response.get("actor_key"), "borga")
            self.assertEqual(response.get("speech_act"), "return_greeting")
            self.assertEqual(response.get("surface_text"), "Доброе утро.")
            self.assertEqual(response.get("clock_minutes"), 0)
            self.assertIsNone(response.get("emotion")); self.assertIsNone(response.get("relationship_delta")); self.assertIsNone(response.get("conversation_commitment"))
            self.assertNotIn("plan_block_kind", response); self.assertNotIn("decision_basis", response)
            self.assertEqual(w.now, t0)
            core = w.character_core_v104("borga") or {}
            self.assertEqual(len(list(core.get("memories") or [])), memories0 + 1)
            self.assertEqual(dict(core.get("relationships") or {}), rel0)
            key = response["response_key"]
            known = w.db.execute("SELECT confidence,source FROM actor_knowledge WHERE actor_id='player' AND fact_key=?", (key,)).fetchone()
            self.assertIsNotNone(known); self.assertEqual(int(known["confidence"]), 100)
            pending = w.db.execute("SELECT COUNT(*) FROM scene_pending_resolution WHERE status='pending'").fetchone()[0]
            self.assertEqual(int(pending), 0)

    def test_contentful_greeting_is_not_auto_answered(self):
        with seed_world_v110_lab(Path(self.tmp.name) / "c.db") as w:
            self._install(w); w.activate_causal_npc_response_v110()
            public = w.process_player_turn("question-greeting", "Обращаюсь к Борге: «Доброе утро. Как дела?»")
            self.assertNotEqual(((public.get("result") or {}).get("outcome")), "npc_response_resolved")
            self.assertIsNone(w._get_fact103("v110:player_observed_response:borga:question-greeting"))
            self.assertIsNotNone(w._get_fact103("v107:character_memory:borga:question-greeting"))

    def test_activation_and_greeting_replay_deterministically(self):
        with seed_world_v110_lab(Path(self.tmp.name) / "base.db") as base:
            self._install(base); snap = export_portable_checkpoint_v100(base, 159)
        with seed_world_v110_lab(Path(self.tmp.name) / "exec.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            a = w.execute_runtime_event(1, "a110", "causal_npc_response_activation", {})["journal"]
            g = w.execute_runtime_event(2, "g110", "player_turn", {"raw_text":"Обращаюсь к Борге: «Доброе утро»."})["journal"]
            expected = runtime_state_hash_v100(w, 159)
            self.assertEqual(((g.get("result") or {}).get("result") or {}).get("outcome"), "npc_response_resolved")
        with seed_world_v110_lab(Path(self.tmp.name) / "replay.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            replay = w.replay_runtime_entries([a, g])
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(runtime_state_hash_v100(w, 159), expected)

    def test_session_state_exposes_response_but_read_path_stays_pure(self):
        with seed_world_v110_lab(Path(self.tmp.name) / "d.db") as w:
            self._install(w); w.activate_causal_npc_response_v110()
            entry = w.execute_runtime_event(2, "session-greeting", "player_turn", {"raw_text":"Обращаюсь к Борге: «Доброе утро»."})["journal"]
            before = runtime_state_hash_v100(w, 159)
            state = w.build_session_state_v110(journal_seq=2, head_state_hash=before, last_event=entry)
            after = runtime_state_hash_v100(w, 159)
            self.assertEqual(before, after)
            self.assertEqual(((state.get("last_turn") or {}).get("action_result") or {}).get("outcome"), "npc_response_resolved")
            self.assertEqual(state["response_runtime"]["supported_response"], "simple_direct_greeting")


if __name__ == "__main__": unittest.main()
