import tempfile
import unittest
from pathlib import Path

from v03_engine import dumps
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v111_request_processor import FAST_REQUEST_FORMAT, _decode_request
from v111_seed import seed_world_v111_lab


class V111Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

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
            "test:v111_anchor", significance=40, origin_region_id="eurazania",
        )
        w.db.commit()
        w.ensure_character_core_v104("borga")
        w.ensure_character_plan_v104("borga", w.now)
        place = w._place103("player")
        w.ensure_living_scene_v103("player")
        w._visible_set103("borga", "Борга", place)
        w.activate_causal_npc_response_v110()
        w.db.commit()
        return int(w.now)

    def test_transport_activation_is_zero_state_change(self):
        with seed_world_v111_lab(Path(self.tmp.name) / "a.db") as w:
            t0 = self._install(w)
            before = runtime_state_hash_v100(w, 159)
            core0 = w.character_core_v104("borga") or {}
            response0 = int(w.db.execute("SELECT COUNT(*) FROM facts WHERE key LIKE 'v110:player_observed_response:borga:%'").fetchone()[0])
            out = w.activate_runtime_fast_path_v111()
            after = runtime_state_hash_v100(w, 159)
            self.assertEqual(before, after)
            self.assertEqual(w.now, t0)
            self.assertTrue(out["transport_only"])
            self.assertEqual(int(w.db.execute("SELECT COUNT(*) FROM facts WHERE key LIKE 'v110:player_observed_response:borga:%'").fetchone()[0]), response0)
            self.assertEqual(w.character_core_v104("borga"), core0)

    def test_fast_request_allocates_next_seq_without_client_seq(self):
        pointer = {"journal_seq": 17}
        session = {"last_turn": {"event_key": "turn-17"}}
        req = {
            "format": FAST_REQUEST_FORMAT,
            "schema_version": 1,
            "request_id": "q1",
            "event_key": "turn-18",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": "turn-17",
            "request": {"raw_text": "test"},
        }
        seq, key, etype, payload, mode = _decode_request(req, pointer, session)
        self.assertEqual(seq, 18)
        self.assertEqual(key, "turn-18")
        self.assertEqual(etype, "player_turn")
        self.assertEqual(payload["raw_text"], "test")
        self.assertEqual(mode, "fast_auto_seq")

    def test_fast_request_fails_closed_on_stale_gameplay_context(self):
        pointer = {"journal_seq": 17}
        session = {"last_turn": {"event_key": "turn-17-other"}}
        req = {
            "format": FAST_REQUEST_FORMAT,
            "schema_version": 1,
            "request_id": "q2",
            "event_key": "turn-18",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": "turn-17",
            "request": {"raw_text": "test"},
        }
        with self.assertRaisesRegex(RuntimeError, "fast_request_stale_gameplay_context"):
            _decode_request(req, pointer, session)

    def test_fast_request_rejects_client_preallocated_seq(self):
        pointer = {"journal_seq": 17}
        session = {"last_turn": {"event_key": "turn-17"}}
        req = {
            "format": FAST_REQUEST_FORMAT,
            "schema_version": 1,
            "request_id": "q3",
            "seq": 18,
            "event_key": "turn-18",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": "turn-17",
            "request": {"raw_text": "test"},
        }
        with self.assertRaisesRegex(ValueError, "must not pre-allocate"):
            _decode_request(req, pointer, session)

    def test_v110_gameplay_semantics_survive_v111(self):
        with seed_world_v111_lab(Path(self.tmp.name) / "b.db") as w:
            t0 = self._install(w)
            public = w.process_player_turn("fast-greeting", "Обращаюсь к Борге: «Доброе утро».")
            result = public.get("result") or {}
            response = result.get("npc_response") or {}
            self.assertEqual(result.get("outcome"), "npc_response_resolved")
            self.assertEqual(response.get("surface_text"), "Доброе утро.")
            self.assertEqual(w.now, t0)
            self.assertIsNone(response.get("relationship_delta"))
            self.assertIsNone(response.get("emotion"))

    def test_session_state_exposes_fast_transport_metadata_read_only(self):
        with seed_world_v111_lab(Path(self.tmp.name) / "c.db") as w:
            self._install(w)
            entry = w.execute_runtime_event(1, "activation-111", "runtime_fast_path_activation", {})["journal"]
            before = runtime_state_hash_v100(w, 159)
            state = w.build_session_state_v111(journal_seq=1, head_state_hash=before, last_event=entry)
            after = runtime_state_hash_v100(w, 159)
            self.assertEqual(before, after)
            self.assertEqual(state["engine_version"], "1.0.11")
            self.assertFalse(state["transport_runtime"]["normal_preflight_pointer_read_required"])
            self.assertEqual(state["transport_runtime"]["optimistic_guard"], "expected_last_gameplay_turn_key")

    def test_activation_replays_deterministically(self):
        with seed_world_v111_lab(Path(self.tmp.name) / "base.db") as base:
            self._install(base)
            snap = export_portable_checkpoint_v100(base, 159)
        with seed_world_v111_lab(Path(self.tmp.name) / "exec.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            event = w.execute_runtime_event(1, "a111", "runtime_fast_path_activation", {})["journal"]
            expected = runtime_state_hash_v100(w, 159)
        with seed_world_v111_lab(Path(self.tmp.name) / "replay.db") as w:
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            replay = w.replay_runtime_entries([event])
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(runtime_state_hash_v100(w, 159), expected)


if __name__ == "__main__":
    unittest.main()
