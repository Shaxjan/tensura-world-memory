import tempfile
import unittest
from pathlib import Path

from v03_engine import dumps
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v107_seed import seed_world_v107_lab
from v108_seed import seed_world_v108_lab
from v108_runtime import BAD_APPROACH_TURNS_V108


class V108Tests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory()
    def tearDown(self): self.tmp.cleanup()

    @staticmethod
    def _install(w, visible=True):
        install_v100_runtime(w,159,{"v":159,"delta":"live_v159","parent":"abc","economy":"ECONOMY_MODEL_v1"},"legacysha")
        w.db.execute("UPDATE actors SET region_id='eurazania',cash_copper=260592 WHERE id='player'")
        w.db.execute("INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
                     ("player","малый боевой/тренировочный двор","test","memory/places.json",w.now))
        w.db.execute("INSERT OR REPLACE INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) VALUES('borga','Борга','eurazania',NULL,'region_only','target_in_current_capital_context',159,'memory/relationships.json','')")
        w.db.execute("INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) VALUES('task:borga','borga','npc_task',?,'ACTIVE','memory/actions.json',159)",
                     (dumps({"person":"Борга","task":"combat rules, admissions, judges, testing and tournament operations","status":"ACTIVE"}),))
        w.db.execute("INSERT OR REPLACE INTO autonomy_runtime(commitment_key,handler,next_due_at,cadence_minutes,tick_count,last_run_at,status,last_outcome_json) VALUES('task:borga','character_task_v105',?,30,1,?,'active','{}')",(w.now+30,w.now))
        w.db.commit(); w.ensure_character_core_v104("borga")
        if visible:
            w._visible_set103("borga","Борга",{"key":"eurazania_small_training_yard","name":"малый боевой/тренировочный двор"}); w.db.commit()
        return int(w.now)

    def test_explicit_visible_approach_is_finite_zero_minute_action(self):
        with seed_world_v108_lab(Path(self.tmp.name)/"a.db") as w:
            t0=self._install(w,True); cash0=int(w.actor("player")["cash_copper"])
            out=w.process_player_turn("approach","Подхожу к Борге.")
            self.assertEqual(out["status"],"executed"); self.assertEqual(out["result"]["outcome"],"approached_visible_named_actor")
            self.assertEqual(out["result"]["approach_minutes"],0); self.assertEqual(w.now,t0); self.assertEqual(int(w.actor("player")["cash_copper"]),cash0)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.turn_key='approach' AND p.status='pending'").fetchone()[0],0)
            self.assertEqual(list((w.character_core_v104("borga") or {}).get("memories") or []),[])

    def test_bare_approach_is_not_auto_bound_to_borga(self):
        with seed_world_v108_lab(Path(self.tmp.name)/"b.db") as w:
            self._install(w,True); out=w.process_player_turn("bare","Подхожу")
            self.assertEqual(out["status"],"scene_pending")
            p=w.db.execute("SELECT p.target_key FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.turn_key='bare' AND p.status='pending'").fetchone()
            self.assertIsNotNone(p); self.assertIsNone(p["target_key"])

    def test_explicit_approach_without_visibility_does_not_invent_success(self):
        with seed_world_v108_lab(Path(self.tmp.name)/"c.db") as w:
            self._install(w,False); out=w.process_player_turn("hidden","Подхожу к Борге.")
            self.assertNotEqual(out.get("status"),"executed")
            self.assertFalse(isinstance(out.get("result"),dict) and out["result"].get("outcome")=="approached_visible_named_actor")

    def test_activation_cancels_only_two_known_stale_pendings_and_preserves_memory(self):
        source_path=Path(self.tmp.name)/"source.db"
        with seed_world_v107_lab(source_path) as old:
            self._install(old,True); old.activate_causal_encounter_memory_v107()
            self.assertEqual(old.process_player_turn(BAD_APPROACH_TURNS_V108[0],"Подхожу к Борге.")["status"],"scene_pending")
            self.assertEqual(old.process_player_turn(BAD_APPROACH_TURNS_V108[1],"Подхожу")["status"],"scene_pending")
            old.process_player_turn("greet","Говорю: «Борга, доброе утро.»")
            memories0=list((old.character_core_v104("borga") or {}).get("memories") or [])
            self.assertEqual(len(memories0),1); snap=export_portable_checkpoint_v100(old,159)
        with seed_world_v108_lab(Path(self.tmp.name)/"repair.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w,snap)["ok"]); t0=w.now
            out=w.activate_visible_local_approach_repair_v108(); self.assertEqual(w.now,t0)
            self.assertEqual(out["repair"]["cancelled_pending_ids"], [3,4])
            for key in BAD_APPROACH_TURNS_V108:
                rows=w.db.execute("SELECT p.status FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id WHERE a.turn_key=? AND p.resolution_kind='local_navigation'",(key,)).fetchall()
                self.assertTrue(rows); self.assertTrue(all(r["status"]!='pending' for r in rows))
            self.assertEqual(list((w.character_core_v104("borga") or {}).get("memories") or []),memories0)

    def test_activation_and_approach_replay_deterministically(self):
        with seed_world_v108_lab(Path(self.tmp.name)/"base.db") as base:
            self._install(base,True); snap=export_portable_checkpoint_v100(base,159)
        with seed_world_v108_lab(Path(self.tmp.name)/"exec.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w,snap)["ok"])
            a=w.execute_runtime_event(1,"a108","visible_local_approach_repair_activation",{})["journal"]
            b=w.execute_runtime_event(2,"b108","player_turn",{"raw_text":"Подхожу к Борге."})["journal"]
            expected=runtime_state_hash_v100(w,159)
        with seed_world_v108_lab(Path(self.tmp.name)/"replay.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w,snap)["ok"]); replay=w.replay_runtime_entries([a,b])
            self.assertTrue(replay["ok"],replay); self.assertEqual(runtime_state_hash_v100(w,159),expected)


if __name__ == "__main__": unittest.main()
