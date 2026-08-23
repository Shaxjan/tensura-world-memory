import copy
import tempfile
import unittest
from pathlib import Path

from v09_runtime import (
    MECHANIC_POLICIES,
    export_portable_checkpoint,
    import_portable_checkpoint,
    install_guarded_mechanics_policy,
)
from v09_seed import seed_world_v09_lab, seed_world_v09_migration


class V09RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_portable_roundtrip_restores_identical_hash_and_critical_state(self):
        db1 = Path(self.tmp.name) / "a.db"
        db2 = Path(self.tmp.name) / "b.db"
        with seed_world_v09_lab(db1) as w:
            w.advance(17)
            before = w.critical_state_snapshot("player")
            snap = export_portable_checkpoint(w, 777)
        with seed_world_v09_lab(db2) as restored:
            result = import_portable_checkpoint(restored, snap)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state_hash"], result["restored_hash"])
            self.assertEqual(before, restored.critical_state_snapshot("player"))

    def test_checkpoint_tampering_fails_closed(self):
        db1 = Path(self.tmp.name) / "c.db"
        db2 = Path(self.tmp.name) / "d.db"
        with seed_world_v09_lab(db1) as w:
            snap = export_portable_checkpoint(w, 1)
        bad = copy.deepcopy(snap)
        bad["world_minute"] += 1
        with seed_world_v09_lab(db2) as restored:
            before = restored.critical_state_snapshot("player")
            result = import_portable_checkpoint(restored, bad)
            self.assertFalse(result["ok"])
            self.assertIn("state_hash_mismatch", result["errors"])
            self.assertEqual(before, restored.critical_state_snapshot("player"))

    def test_raw_campaign_archive_is_not_in_portable_checkpoint(self):
        db = Path(self.tmp.name) / "e.db"
        with seed_world_v09_migration(db) as w:
            w.db.execute(
                "INSERT INTO campaign_archives(source_path,source_version,sha256,byte_count,payload_text,archived_at) "
                "VALUES('x','1','abc',4,'huge',?)", (w.now,)
            )
            w.db.commit()
            snap = export_portable_checkpoint(w, 1)
            self.assertNotIn("campaign_archives", snap["tables"])
            self.assertIn("campaign_metadata", snap["tables"])

    def test_guarded_policy_does_not_invent_numeric_mechanics(self):
        db = Path(self.tmp.name) / "f.db"
        with seed_world_v09_migration(db) as w:
            install_guarded_mechanics_policy(w)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM power_profiles").fetchone()[0], 0)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM actor_skills").fetchone()[0], 0)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM social_bonds").fetchone()[0], 0)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM markets").fetchone()[0], 0)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM routes").fetchone()[0], 0)
            policies = {r["feature"]: (r["mode"], r["authority"]) for r in w.db.execute(
                "SELECT feature,mode,authority FROM mechanic_feature_policy"
            )}
            self.assertEqual(set(policies), set(MECHANIC_POLICIES))
            self.assertTrue(all(v[1] == "NON_CANON_MECHANICAL" for v in policies.values()))

    def test_optional_unknown_mechanics_stay_command_gated(self):
        db = Path(self.tmp.name) / "g.db"
        with seed_world_v09_migration(db) as w:
            install_guarded_mechanics_policy(w)
            caps = {r["command"]: bool(r["enabled"]) for r in w.db.execute(
                "SELECT command,enabled FROM migration_capabilities"
            )}
            for command in ("travel", "buy", "attempt", "strike", "treat", "social", "wait", "attend"):
                self.assertIn(command, caps)
                self.assertFalse(caps[command])

    def test_shadow_blocked_wait_does_not_mutate_critical_state(self):
        db = Path(self.tmp.name) / "h.db"
        with seed_world_v09_migration(db) as w:
            install_guarded_mechanics_policy(w)
            before = w.critical_state_snapshot("player")
            out = w.process_player_turn("shadow", "жду 1 минуту")
            after = w.critical_state_snapshot("player")
            self.assertEqual(out["status"], "blocked_by_migration")
            self.assertFalse(out["accepted"])
            self.assertEqual(before, after)

    def test_runtime_blockers_remain_explicit(self):
        db = Path(self.tmp.name) / "i.db"
        with seed_world_v09_migration(db) as w:
            install_guarded_mechanics_policy(w)
            gates = {r["gate_code"]: r["status"] for r in w.db.execute(
                "SELECT gate_code,status FROM cutover_gate"
            )}
            self.assertEqual(gates["scene_action_bridge_not_implemented"], "active")
            self.assertEqual(gates["autonomy_commitment_execution_not_wired"], "active")
            self.assertEqual(gates["portable_runtime_bridge"], "pending_shadow")


if __name__ == "__main__":
    unittest.main()
