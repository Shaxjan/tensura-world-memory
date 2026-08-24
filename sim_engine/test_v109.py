import tempfile
import unittest
from pathlib import Path

from v03_engine import dumps
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v109_seed import seed_world_v109_lab


class V109Tests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory()
    def tearDown(self): self.tmp.cleanup()

    @staticmethod
    def _install(w):
        install_v100_runtime(w,159,{"v":159,"delta":"live_v159","parent":"abc","economy":"ECONOMY_MODEL_v1"},"legacysha")
        w.db.execute("UPDATE actors SET region_id='eurazania',cash_copper=260592 WHERE id='player'")
        w.db.execute("INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",("player","малый боевой/тренировочный двор","test","memory/places.json",w.now))
        w.db.execute("INSERT OR REPLACE INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) VALUES('borga','Борга','eurazania',NULL,'region_only','target_in_current_capital_context',159,'memory/relationships.json','')")
        w.db.execute("INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) VALUES('task:borga','borga','npc_task',?,'ACTIVE','memory/actions.json',159)",(dumps({"person":"Борга","task":"combat rules","status":"ACTIVE"}),))
        w.db.execute("INSERT OR REPLACE INTO autonomy_runtime(commitment_key,handler,next_due_at,cadence_minutes,tick_count,last_run_at,status,last_outcome_json) VALUES('task:borga','character_task_v105',?,30,1,?,'active','{}')",(w.now+30,w.now))
        w.db.commit(); w.ensure_character_core_v104("borga"); return int(w.now)

    @staticmethod
    def _make_pending(w, turn_key, target_text, status="pending"):
        w.db.execute("INSERT INTO gm_turns(turn_key,player_id,raw_text,status,created_at) VALUES(?,?,?,?,?)",(turn_key,"player",target_text,"scene_pending",w.now))
        a=w.db.execute("INSERT INTO scene_actions(turn_key,world_minute,actor_id,action_kind,raw_text,components_json,resolution_mode,status,effect_json,created_at) VALUES(?,?,?,?,?,'[]','pending_resolution','pending','{}',?)",(turn_key,w.now,"player","local_search_or_move",target_text,w.now))
        p=w.db.execute("INSERT INTO scene_pending_resolution(scene_action_id,resolution_kind,target_key,target_text,state_json,status,created_at) VALUES(?,?,?,?,?,?,?)",(int(a.lastrowid),"local_navigation",None,target_text,"{}",status,w.now))
        w.db.commit(); return int(p.lastrowid)

    def test_sanitizer_removes_repaired_pending_but_keeps_current_pending(self):
        with seed_world_v109_lab(Path(self.tmp.name)/"a.db") as w:
            self._install(w)
            cancelled=self._make_pending(w,"old","old","cancelled_visible_approach_parser_repair")
            active=self._make_pending(w,"active","active","pending")
            last={"event_key":"greet","pending_resolutions":[{"id":cancelled,"kind":"local_navigation","target":"old","status":"pending"},{"id":active,"kind":"local_navigation","target":"active","status":"pending"}],"narration_contract":{"must_preserve":["verbatim player action","pending outcomes remain pending"]}}
            out=w._sanitize_last_turn_v109(last)
            self.assertEqual([r["id"] for r in out["pending_resolutions"]],[active])
            self.assertNotIn("pending outcomes remain pending",out["narration_contract"]["must_preserve"])
            self.assertIn("historical repaired pending are not current pending",out["narration_contract"]["must_preserve"])

    def test_activation_is_zero_time_and_does_not_change_gameplay_state(self):
        with seed_world_v109_lab(Path(self.tmp.name)/"b.db") as w:
            t0=self._install(w); cash0=int(w.actor("player")["cash_copper"]); core0=w.character_core_v104("borga") or {}
            out=w.execute_runtime_event(1,"activate109","session_readmodel_repair_activation",{})
            self.assertEqual(w.now,t0); self.assertEqual(int(w.actor("player")["cash_copper"]),cash0)
            self.assertEqual((w.character_core_v104("borga") or {}).get("memories"),core0.get("memories"))
            self.assertFalse(out["journal"]["result"]["db_gameplay_mutation"])

    def test_session_builder_projects_authoritative_pending(self):
        with seed_world_v109_lab(Path(self.tmp.name)/"c.db") as w:
            self._install(w); stale=self._make_pending(w,"old","old","cancelled_visible_approach_parser_repair")
            preserved={"seq":9,"event_key":"greet","pending_resolutions":[{"id":stale,"kind":"local_navigation","target":"old","status":"pending"}],"narration_contract":{"must_preserve":["pending outcomes remain pending"]}}
            state=w.build_session_state_v109(journal_seq=1,head_state_hash="hash",preserved_last_turn=preserved)
            self.assertEqual(state["last_turn"]["event_key"],"greet"); self.assertEqual(state["last_turn"]["pending_resolutions"],[])
            self.assertEqual(state["readmodel_runtime"]["pending_source"],"authoritative_scene_pending_resolution_status_pending")

    def test_activation_replay_deterministically(self):
        with seed_world_v109_lab(Path(self.tmp.name)/"base.db") as base:
            self._install(base); snap=export_portable_checkpoint_v100(base,159)
        with seed_world_v109_lab(Path(self.tmp.name)/"exec.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w,snap)["ok"]); entry=w.execute_runtime_event(1,"a109","session_readmodel_repair_activation",{})["journal"]; expected=runtime_state_hash_v100(w,159)
        with seed_world_v109_lab(Path(self.tmp.name)/"replay.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w,snap)["ok"]); replay=w.replay_runtime_entries([entry]); self.assertTrue(replay["ok"],replay); self.assertEqual(runtime_state_hash_v100(w,159),expected)


if __name__=="__main__": unittest.main()
