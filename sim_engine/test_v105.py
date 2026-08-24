import tempfile
import unittest
from pathlib import Path

from v03_engine import dumps, loads
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v105_seed import seed_world_v105_lab


class V105Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _base_install(w, minute_of_day=480, due_in=5):
        install_v100_runtime(
            w,
            159,
            {"v": 159, "delta": "live_v159", "parent": "abc", "economy": "ECONOMY_MODEL_v1"},
            "legacysha",
        )
        w.db.execute("UPDATE actors SET region_id='eurazania',cash_copper=260592 WHERE id='player'")
        w.db.execute(
            "INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
            ("player", "большой тренировочный двор Борги", "test", "memory/places.json", w.now),
        )
        w.db.execute(
            "INSERT OR REPLACE INTO actor_position_claims"
            "(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) "
            "VALUES('borga','Борга','eurazania',NULL,'region_only','target_in_current_capital_context',159,"
            "'memory/relationships.json','')"
        )
        w.db.commit()
        delta = (int(minute_of_day) - (w.now % 1440)) % 1440
        if delta:
            w.advance(delta)
        state = {
            "person": "Борга",
            "task": "combat rules, admissions, judges, testing and tournament operations",
            "status": "ACTIVE",
        }
        w.db.execute(
            "INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) "
            "VALUES('task:borga','borga','npc_task',?,'ACTIVE','memory/actions.json',159)",
            (dumps(state),),
        )
        w.db.execute(
            "INSERT OR REPLACE INTO autonomy_runtime"
            "(commitment_key,handler,next_due_at,cadence_minutes,tick_count,last_run_at,status,last_outcome_json) "
            "VALUES('task:borga','task_progress',?,30,1,?,'active','{}')",
            (w.now + due_in, w.now - 25),
        )
        w.db.commit()
        return int(w.now)

    def test_activation_wires_existing_scheduler_without_resetting_it(self):
        db = Path(self.tmp.name) / "a.db"
        with seed_world_v105_lab(db) as w:
            t0 = self._base_install(w)
            before = dict(w.db.execute("SELECT * FROM autonomy_runtime WHERE commitment_key='task:borga'").fetchone())
            cash0 = int(w.actor("player")["cash_copper"])
            event = w.execute_runtime_event(1, "activate-v105", "character_autonomy_activation", {"reason": "test"})
            after = dict(w.db.execute("SELECT * FROM autonomy_runtime WHERE commitment_key='task:borga'").fetchone())
            self.assertEqual(w.now, t0)
            self.assertEqual(int(w.actor("player")["cash_copper"]), cash0)
            self.assertEqual(after["handler"], "character_task_v105")
            for field in ("next_due_at", "cadence_minutes", "tick_count", "status"):
                self.assertEqual(after[field], before[field])
            self.assertEqual(event["journal"]["result"]["time_advanced"], 0)
            self.assertFalse(event["journal"]["result"]["player_choice"])

    def test_role_duty_tick_executes_grounded_work_without_completion(self):
        db = Path(self.tmp.name) / "b.db"
        with seed_world_v105_lab(db) as w:
            self._base_install(w, minute_of_day=480, due_in=5)
            cash0 = int(w.actor("player")["cash_copper"])
            w.execute_runtime_event(1, "activate-work-v105", "character_autonomy_activation", {"reason": "test"})
            w.advance(5)
            log = w.db.execute(
                "SELECT * FROM autonomy_execution_log WHERE commitment_key='task:borga' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            outcome = loads(log["outcome_json"], {})
            state = w.character_autonomy_v105("borga")
            commitment = w.db.execute(
                "SELECT status,state_json FROM autonomous_commitments WHERE commitment_key='task:borga'"
            ).fetchone()
            self.assertEqual(outcome["code"], "character_work_progressed")
            self.assertIn(outcome["workstream"], state["grounded_workstreams"])
            self.assertIsNotNone(outcome["place_key"])
            self.assertFalse(outcome["completion_asserted"])
            self.assertEqual(int(log["visible_to_player"]), 0)
            self.assertEqual(int(state["work_ticks"]), 1)
            self.assertEqual(int(state["deferred_ticks"]), 0)
            self.assertEqual(str(commitment["status"]), "ACTIVE")
            self.assertEqual(loads(commitment["state_json"], {})["status"], "ACTIVE")
            self.assertEqual(int(w.actor("player")["cash_copper"]), cash0)

    def test_travel_window_defers_work_and_keeps_exact_place_unknown(self):
        db = Path(self.tmp.name) / "c.db"
        with seed_world_v105_lab(db) as w:
            self._base_install(w, minute_of_day=540, due_in=5)
            w.execute_runtime_event(1, "activate-defer-v105", "character_autonomy_activation", {"reason": "test"})
            w.advance(5)
            log = w.db.execute(
                "SELECT * FROM autonomy_execution_log WHERE commitment_key='task:borga' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            outcome = loads(log["outcome_json"], {})
            state = w.character_autonomy_v105("borga")
            presence = w._borga_presence103(w.now)
            self.assertEqual(outcome["code"], "character_work_deferred")
            self.assertEqual(outcome["plan_block_kind"], "local_travel")
            self.assertIsNone(outcome["place_key"])
            self.assertIsNone(presence["place_key"])
            self.assertEqual(int(state["deferred_ticks"]), 1)
            self.assertEqual(int(state["work_ticks"]), 0)

    def test_other_commitments_stay_on_existing_generic_scheduler(self):
        db = Path(self.tmp.name) / "d.db"
        with seed_world_v105_lab(db) as w:
            self._base_install(w, minute_of_day=480, due_in=5)
            w.db.execute(
                "INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) "
                "VALUES('task:meira','meira','npc_task',?,'ACTIVE','memory/actions.json',159)",
                (dumps({"person":"Мэйра","task":"festival coordination","status":"ACTIVE"}),),
            )
            w.db.execute(
                "INSERT OR REPLACE INTO autonomy_runtime"
                "(commitment_key,handler,next_due_at,cadence_minutes,tick_count,last_run_at,status,last_outcome_json) "
                "VALUES('task:meira','task_progress',?,30,0,NULL,'active','{}')",
                (w.now + 5,),
            )
            w.db.commit()
            w.execute_runtime_event(1, "activate-other-v105", "character_autonomy_activation", {"reason": "test"})
            self.assertEqual(
                w.db.execute("SELECT handler FROM autonomy_runtime WHERE commitment_key='task:meira'").fetchone()[0],
                "task_progress",
            )
            w.advance(5)
            other = w.db.execute(
                "SELECT handler,outcome_code FROM autonomy_execution_log WHERE commitment_key='task:meira' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(other["handler"], "task_progress")
            self.assertEqual(other["outcome_code"], "progressed")

    def test_activation_event_replays_deterministically(self):
        base_db = Path(self.tmp.name) / "e.db"
        with seed_world_v105_lab(base_db) as base:
            self._base_install(base)
            snapshot = export_portable_checkpoint_v100(base, 159)
            t0 = int(base.now)

        exec_db = Path(self.tmp.name) / "f.db"
        with seed_world_v105_lab(exec_db) as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snapshot)["ok"])
            event = w.execute_runtime_event(1, "activate-replay-v105", "character_autonomy_activation", {"reason": "test"})
            entry = event["journal"]
            expected = runtime_state_hash_v100(w, 159)
            self.assertEqual(int(w.now), t0)

        replay_db = Path(self.tmp.name) / "g.db"
        with seed_world_v105_lab(replay_db) as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snapshot)["ok"])
            replay = w.replay_runtime_entries([entry])
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(runtime_state_hash_v100(w, 159), expected)

    def test_session_state_keeps_hud_and_hides_autonomy(self):
        db = Path(self.tmp.name) / "h.db"
        with seed_world_v105_lab(db) as w:
            self._base_install(w)
            event = w.execute_runtime_event(1, "activate-session-v105", "character_autonomy_activation", {"reason": "test"})
            state = w.build_session_state_v105(
                journal_seq=1,
                head_state_hash=event["journal"]["after_hash"],
                last_event=event["journal"],
            )
            self.assertEqual(state["engine_version"], "1.0.5")
            self.assertEqual(state["hud"]["money"]["on_person_copper"], 260592)
            self.assertTrue(state["display_contract"]["normal_play_technical_fields_hidden"])
            self.assertTrue(state["character_runtime"]["shared_scheduler"])
            self.assertTrue(state["character_runtime"]["hidden_autonomy_not_narrator_knowledge"])
            self.assertNotIn("character_autonomy", state["scene"])


if __name__ == "__main__":
    unittest.main()
