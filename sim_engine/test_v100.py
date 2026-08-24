import copy
import tempfile
import unittest
from pathlib import Path

from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_repository import build_runtime_pointer, validate_runtime_pointer
from v100_runtime import activate_v100_runtime, install_v100_runtime, resolve_v100_gate
from v100_seed import seed_world_v100_lab


class V100Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _install(w):
        install_v100_runtime(w, 159, {"v": 159, "delta": "live_v159", "parent": "abc", "economy": "ECONOMY_MODEL_v1"}, "legacysha")

    def test_pending_local_navigation_requires_typed_resolution(self):
        db = Path(self.tmp.name) / "a.db"
        with seed_world_v100_lab(db) as w:
            self._install(w)
            before = w.critical_state_snapshot("player")
            action = w.process_player_turn("find", "Иду искать Боргу.")
            self.assertEqual(action["status"], "scene_pending")
            pending = w.db.execute("SELECT id FROM scene_pending_resolution WHERE status='pending'").fetchone()
            self.assertIsNotNone(pending)
            result = w.resolve_scene_pending(int(pending[0]), {"outcome": "not_found", "note": "no result yet"})
            self.assertTrue(result["accepted"])
            self.assertEqual(result["outcome"], "not_found")
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM scene_pending_resolution WHERE status='pending'").fetchone()[0], 0)
            after = w.critical_state_snapshot("player")
            self.assertEqual(before["player"], after["player"])

    def test_handoff_acceptance_changes_only_tracked_holder(self):
        db = Path(self.tmp.name) / "b.db"
        with seed_world_v100_lab(db) as w:
            self._install(w)
            w.db.execute(
                "INSERT INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) "
                "VALUES('rena','Рена',?,'same scene','local','active',159,'test','')",
                (str(w.actor('player')["region_id"]),),
            )
            w.db.execute(
                "INSERT INTO scene_objects(object_key,display_name,holder_key,state_json,certainty,source_path,updated_at) "
                "VALUES('rena_guitar','гитара Рены','player','{}','test','test',?)",
                (w.now,),
            )
            w.db.commit()
            action = w.process_player_turn("give", "Передаю Рене гитару.")
            self.assertEqual(action["status"], "scene_pending")
            pending = w.db.execute("SELECT id FROM scene_pending_resolution WHERE resolution_kind='handoff_acceptance'").fetchone()
            result = w.resolve_scene_pending(int(pending[0]), {"outcome": "accepted", "response_text": "Берёт гитару."})
            self.assertTrue(result["accepted"])
            holder = w.db.execute("SELECT holder_key FROM scene_objects WHERE object_key='rena_guitar'").fetchone()[0]
            self.assertEqual(holder, "rena")

    def test_pending_turn_can_be_narrated_without_resolving_it(self):
        db = Path(self.tmp.name) / "c.db"
        with seed_world_v100_lab(db) as w:
            self._install(w)
            w.process_player_turn("find", "Иду искать Боргу.")
            out = w.record_narration("find", "Арлекино начинает поиски; результат пока не установлен.")
            self.assertTrue(out["recorded"])
            self.assertEqual(out["status"], "scene_pending")
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM scene_pending_resolution WHERE status='pending'").fetchone()[0], 1)

    def test_append_only_journal_replays_to_identical_state_hash(self):
        base_db = Path(self.tmp.name) / "base.db"
        with seed_world_v100_lab(base_db) as base:
            self._install(base)
            snap = export_portable_checkpoint_v100(base, 159)

        a_db = Path(self.tmp.name) / "exec.db"
        with seed_world_v100_lab(a_db) as a:
            self.assertTrue(import_portable_checkpoint_v100(a, snap)["ok"])
            e1 = a.execute_runtime_event(1, "e1", "player_turn", {"raw_text": "Иду искать Боргу."})
            pending = int(a.db.execute("SELECT id FROM scene_pending_resolution WHERE status='pending'").fetchone()[0])
            e2 = a.execute_runtime_event(2, "e2", "scene_resolution", {"pending_id": pending, "payload": {"outcome": "not_found"}})
            e3 = a.execute_runtime_event(3, "e3", "player_turn", {"raw_text": "жду 5 минут"})
            entries = [e1["journal"], e2["journal"], e3["journal"]]
            expected = runtime_state_hash_v100(a, 159)

        b_db = Path(self.tmp.name) / "replay.db"
        with seed_world_v100_lab(b_db) as b:
            self.assertTrue(import_portable_checkpoint_v100(b, snap)["ok"])
            replay = b.replay_runtime_entries(entries)
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(runtime_state_hash_v100(b, 159), expected)

    def test_tampered_journal_fails_closed(self):
        base_db = Path(self.tmp.name) / "d.db"
        with seed_world_v100_lab(base_db) as base:
            self._install(base)
            snap = export_portable_checkpoint_v100(base, 159)
        exec_db = Path(self.tmp.name) / "e.db"
        with seed_world_v100_lab(exec_db) as w:
            import_portable_checkpoint_v100(w, snap)
            entry = w.execute_runtime_event(1, "e1", "player_turn", {"raw_text": "Киваю."})["journal"]
        bad = copy.deepcopy(entry)
        bad["after_hash"] = "0" * 64
        replay_db = Path(self.tmp.name) / "f.db"
        with seed_world_v100_lab(replay_db) as w:
            import_portable_checkpoint_v100(w, snap)
            out = w.replay_runtime_entries([bad])
            self.assertFalse(out["ok"])
            self.assertEqual(out["reason"], "after_hash_mismatch")

    def test_cutover_activation_requires_all_gates_resolved(self):
        db = Path(self.tmp.name) / "g.db"
        with seed_world_v100_lab(db) as w:
            self._install(w)
            with self.assertRaises(RuntimeError):
                activate_v100_runtime(w)
            for code in ("pending_resolution_executor", "append_only_runtime_journal", "legacy_v159_rollback_anchor"):
                resolve_v100_gate(w, code, "test", ["ok"])
            # v0.10 may not have installed its gates in the lab; only active rows matter.
            activate_v100_runtime(w)
            mode = w.db.execute("SELECT mode FROM runtime_cutover WHERE id=1").fetchone()[0]
            self.assertEqual(mode, "engine_authoritative")

    def test_runtime_pointer_has_exact_rollback_anchor(self):
        legacy = {"v": 159, "parent": "abc", "delta": "live_v159", "economy": "ECONOMY_MODEL_v1"}
        p = build_runtime_pointer(source_live_version=159, base_checkpoint="runtime/checkpoints/cutover_v159.json",
                                  base_state_hash="deadbeef", legacy_pointer=legacy, legacy_pointer_blob_sha="sha")
        validate_runtime_pointer(p)
        self.assertEqual(p["legacy_rollback"]["pointer"], legacy)
        self.assertEqual(p["journal_seq"], 0)
        self.assertTrue(p["write_protocol"]["event_file_first"])

    def test_v100_checkpoint_roundtrip_excludes_self_referential_journal(self):
        a_db = Path(self.tmp.name) / "h.db"
        b_db = Path(self.tmp.name) / "i.db"
        with seed_world_v100_lab(a_db) as a:
            self._install(a)
            a.execute_runtime_event(1, "e1", "player_turn", {"raw_text": "Киваю."})
            snap = export_portable_checkpoint_v100(a, 159)
            self.assertNotIn("runtime_journal", snap["tables"])
        with seed_world_v100_lab(b_db) as b:
            result = import_portable_checkpoint_v100(b, snap)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state_hash"], result["restored_hash"])


if __name__ == "__main__":
    unittest.main()
