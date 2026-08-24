import json
import tempfile
import unittest
from pathlib import Path

from v03_engine import dumps
from v100_handoff import runtime_state_hash_v100
from v100_runtime import install_v100_runtime
from v112_receipt import write_receipt
from v112_request_processor import FAST_REQUEST_FORMAT, LEGACY_REQUEST_FORMAT, _decode_request
from v112_seed import seed_world_v112_lab


class V112Tests(unittest.TestCase):
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
            "test:v112_anchor", significance=40, origin_region_id="eurazania",
        )
        w.db.commit()
        w.ensure_character_core_v104("borga")
        w.ensure_character_plan_v104("borga", w.now)
        place = w._place103("player")
        w.ensure_living_scene_v103("player")
        w._visible_set103("borga", "Борга", place)
        w.activate_causal_npc_response_v110()
        w.db.commit()

    def test_activation_is_transport_only(self):
        with seed_world_v112_lab(Path(self.tmp.name) / "a.db") as w:
            self._install(w)
            before = runtime_state_hash_v100(w, 159)
            out = w.activate_runtime_fast_path_reliability_v112()
            after = runtime_state_hash_v100(w, 159)
            self.assertEqual(before, after)
            self.assertTrue(out["transport_only"])
            self.assertEqual(out["time_advanced"], 0)

    def test_fast_nested_payload_no_request_id_required(self):
        pointer = {"journal_seq": 18}
        session = {"last_turn": {"event_key": "turn-17"}}
        req = {
            "format": FAST_REQUEST_FORMAT,
            "schema_version": 1,
            "event_key": "turn-20",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": "turn-17",
            "request": {"raw_text": "Что делаешь?"},
        }
        seq, key, etype, payload, mode = _decode_request(req, pointer, session)
        self.assertEqual(seq, 19)
        self.assertEqual(key, "turn-20")
        self.assertEqual(etype, "player_turn")
        self.assertEqual(payload["raw_text"], "Что делаешь?")
        self.assertEqual(mode, "fast_auto_seq:nested_request")

    def test_fast_top_level_raw_text_compatibility(self):
        pointer = {"journal_seq": 18}
        session = {"last_turn": {"event_key": "turn-17"}}
        req = {
            "format": FAST_REQUEST_FORMAT,
            "schema_version": 1,
            "event_key": "turn-20",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": "turn-17",
            "raw_text": "Что делаешь?",
        }
        seq, _, _, payload, mode = _decode_request(req, pointer, session)
        self.assertEqual(seq, 19)
        self.assertEqual(payload["raw_text"], "Что делаешь?")
        self.assertEqual(mode, "fast_auto_seq:compat_top_level_raw_text")

    def test_conflicting_raw_text_rejected(self):
        pointer = {"journal_seq": 18}
        session = {"last_turn": {"event_key": "turn-17"}}
        req = {
            "format": FAST_REQUEST_FORMAT,
            "schema_version": 1,
            "event_key": "turn-20",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": "turn-17",
            "raw_text": "A",
            "request": {"raw_text": "B"},
        }
        with self.assertRaisesRegex(ValueError, "conflicting"):
            _decode_request(req, pointer, session)

    def test_stale_guard_still_fails_closed(self):
        pointer = {"journal_seq": 18}
        session = {"last_turn": {"event_key": "other"}}
        req = {
            "format": FAST_REQUEST_FORMAT,
            "schema_version": 1,
            "event_key": "turn-20",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": "turn-17",
            "request": {"raw_text": "test"},
        }
        with self.assertRaisesRegex(RuntimeError, "fast_request_stale_gameplay_context"):
            _decode_request(req, pointer, session)

    def test_legacy_request_remains_supported(self):
        pointer = {"journal_seq": 18}
        session = {"last_turn": {"event_key": "turn-17"}}
        req = {
            "format": LEGACY_REQUEST_FORMAT,
            "schema_version": 1,
            "seq": 19,
            "event_key": "legacy-19",
            "event_type": "player_turn",
            "request": {"raw_text": "test"},
        }
        seq, _, _, payload, mode = _decode_request(req, pointer, session)
        self.assertEqual(seq, 19)
        self.assertEqual(payload["raw_text"], "test")
        self.assertEqual(mode, "legacy_explicit_seq:nested_request")

    def test_receipt_is_non_authoritative_transport_record(self):
        root = Path(self.tmp.name)
        req = root / "runtime/requests/q-test.json"
        req.parent.mkdir(parents=True)
        req.write_text(json.dumps({"format":FAST_REQUEST_FORMAT,"event_key":"e"}), encoding="utf-8")
        out = write_receipt(root, req, status="failed", error="schema")
        data = json.loads((root / out["receipt"]).read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "failed")
        self.assertFalse(data["authoritative_gameplay_change"])

    def test_session_exposes_repaired_transport_contract(self):
        with seed_world_v112_lab(Path(self.tmp.name) / "b.db") as w:
            self._install(w)
            entry = w.execute_runtime_event(1, "a112", "runtime_fast_path_reliability_activation", {})["journal"]
            head = runtime_state_hash_v100(w, 159)
            state = w.build_session_state_v112(journal_seq=1, head_state_hash=head, last_event=entry)
            tr = state["transport_runtime"]
            self.assertEqual(state["engine_version"], "1.0.12")
            self.assertFalse(tr["request_id_required"])
            self.assertTrue(tr["request_receipts"])
            self.assertTrue(tr["duplicate_enqueue_forbidden"])


if __name__ == "__main__":
    unittest.main()
