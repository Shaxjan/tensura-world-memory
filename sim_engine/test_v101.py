import json
import tempfile
import unittest
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, runtime_state_hash_v100
from v100_repository import build_runtime_pointer
from v100_runtime import install_v100_runtime
from v101_request_processor import process_request
from v101_seed import seed_world_v101_lab


class V101Tests(unittest.TestCase):
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
            ("player", "Eurazania capital; Arlequino leaves lodging heading to Borga", "exact_source_text", "live_v159/delta.json", w.now),
        )
        w.db.commit()

    def test_known_training_yard_finishes_in_one_turn(self):
        db = Path(self.tmp.name) / "a.db"
        with seed_world_v101_lab(db) as w:
            self._install(w)
            t0, cash0 = w.now, int(w.actor("player")["cash_copper"])
            out = w.process_player_turn("go-yard", "Иду к тренировочному двору.")
            self.assertEqual(out["status"], "executed")
            self.assertEqual(out["result"]["destination_text"], "большой тренировочный двор Борги")
            self.assertEqual(out["result"]["travel_minutes"], 12)
            self.assertEqual(w.now - t0, 12)
            self.assertEqual(int(w.actor("player")["cash_copper"]), cash0)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM scene_pending_resolution").fetchone()[0], 0)

    def test_repeated_same_destination_does_not_advance_again(self):
        db = Path(self.tmp.name) / "b.db"
        with seed_world_v101_lab(db) as w:
            self._install(w)
            w.process_player_turn("first", "Иду к тренировочному двору.")
            t1 = w.now
            out = w.process_player_turn("second", "Иду к большому тренировочному двору.")
            self.assertEqual(out["result"]["outcome"], "already_at_destination")
            self.assertEqual(w.now, t1)

    def test_unknown_local_destination_remains_guarded(self):
        db = Path(self.tmp.name) / "c.db"
        with seed_world_v101_lab(db) as w:
            self._install(w)
            out = w.process_player_turn("unknown", "Иду к синей башне.")
            self.assertEqual(out["status"], "scene_pending")

    def test_journal_replay_of_local_travel_is_deterministic(self):
        base_db = Path(self.tmp.name) / "d.db"
        with seed_world_v101_lab(base_db) as base:
            self._install(base)
            snap = export_portable_checkpoint_v100(base, 159)
        exec_db = Path(self.tmp.name) / "e.db"
        with seed_world_v101_lab(exec_db) as w:
            from v100_handoff import import_portable_checkpoint_v100
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            event = w.execute_runtime_event(1, "e1", "player_turn", {"raw_text":"Иду к тренировочному двору."})
            expected = runtime_state_hash_v100(w, 159)
            entry = event["journal"]
        replay_db = Path(self.tmp.name) / "f.db"
        with seed_world_v101_lab(replay_db) as w:
            from v100_handoff import import_portable_checkpoint_v100
            self.assertTrue(import_portable_checkpoint_v100(w, snap)["ok"])
            replay = w.replay_runtime_entries([entry])
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(runtime_state_hash_v100(w,159), expected)

    def test_request_processor_writes_journal_and_pointer(self):
        root = Path(self.tmp.name) / "repo"
        (root / "runtime/checkpoints").mkdir(parents=True)
        (root / "runtime/requests").mkdir(parents=True)
        base_db = Path(self.tmp.name) / "g.db"
        with seed_world_v101_lab(base_db) as base:
            self._install(base)
            snap = export_portable_checkpoint_v100(base, 159)
        cp = root / "runtime/checkpoints/cutover_v159.json"
        cp.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
        pointer = build_runtime_pointer(
            source_live_version=159, base_checkpoint="runtime/checkpoints/cutover_v159.json",
            base_state_hash=snap["state_hash"], legacy_pointer={"v":159,"delta":"live_v159"},
            legacy_pointer_blob_sha="legacy", mode="engine_authoritative",
        )
        (root / "runtime/runtime_state.json").write_text(json.dumps(pointer), encoding="utf-8")
        req = {
            "format":"TENSURA_TURN_REQUEST","schema_version":1,"seq":1,"event_key":"live-000001",
            "event_type":"player_turn","request":{"raw_text":"Иду к тренировочному двору."}
        }
        rp = root / "runtime/requests/r000001.json"
        rp.write_text(json.dumps(req,ensure_ascii=False),encoding="utf-8")
        out = process_request(root, rp)
        self.assertTrue(out["ok"])
        self.assertTrue((root / "runtime/journal/j000001.json").exists())
        newp = json.loads((root / "runtime/runtime_state.json").read_text(encoding="utf-8"))
        self.assertEqual(newp["journal_seq"],1)
        self.assertEqual(newp["engine_version"],"1.0.1")
        self.assertEqual(newp["head_state_hash"],out["after_hash"])


if __name__ == "__main__":
    unittest.main()
