import json
import tempfile
import unittest
from pathlib import Path

from v06_migration import apply_repo_campaign_rehearsal, collect_repo_campaign, parse_money, parse_world_time, strict_region_from_text
from v06_seed import seed_world_v06_lab, seed_world_v06_migration


class V06LoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "lab.db"
        self.w = seed_world_v06_lab(self.db)

    def tearDown(self):
        self.w.close(); self.tmp.cleanup()

    def test_grounded_turn_executes_and_checkpoints(self):
        cash0 = int(self.w.actor("player")["cash_copper"])
        r = self.w.process_player_turn("t1", "покупаю 2 Зерно")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["status"], "executed")
        self.assertLess(int(self.w.actor("player")["cash_copper"]), cash0)
        self.assertEqual(self.w.db.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0], 1)

    def test_turn_key_is_idempotent_across_reopen(self):
        r1 = self.w.process_player_turn("same", "жду 1 минуту")
        t = self.w.now
        self.w.close()
        self.w = type(self.w)(self.db)
        r2 = self.w.process_player_turn("same", "жду 1 минуту")
        self.assertTrue(r2["replayed"])
        self.assertEqual(self.w.now, t)
        self.assertEqual(r1["checkpoint"]["state_hash"], r2["checkpoint"]["state_hash"])

    def test_missing_destination_does_not_execute(self):
        before = self.w.critical_state_snapshot()
        r = self.w.process_player_turn("clarify", "иду")
        self.assertFalse(r["accepted"])
        self.assertEqual(r["status"], "needs_clarification")
        self.assertEqual(before, self.w.critical_state_snapshot())

    def test_external_intent_cannot_invent_destination(self):
        r = self.w.process_player_turn(
            "hostile", "иду", external_intent={"command": "travel", "params": {"destination": "dwargon"}}
        )
        self.assertFalse(r["accepted"])
        self.assertEqual(r["validation"]["valid"], False)
        self.assertEqual(str(self.w.actor("player")["region_id"]), "blumund")

    def test_external_intent_exact_match_is_allowed(self):
        r = self.w.process_player_turn(
            "exact", "иду в Дваргон", external_intent={"command": "travel", "params": {"destination": "dwargon"}}
        )
        self.assertTrue(r["accepted"])
        self.assertEqual(str(self.w.actor("player")["status"]), "traveling")

    def test_narration_cannot_be_recorded_after_external_state_change(self):
        self.w.process_player_turn("n1", "жду 1 минуту")
        self.w.db.execute("UPDATE actors SET cash_copper=cash_copper+1 WHERE id='player'")
        self.w.db.commit()
        with self.assertRaises(RuntimeError):
            self.w.record_narration("n1", "text")

    def test_narration_records_without_state_mutation(self):
        self.w.process_player_turn("n2", "жду 1 минуту")
        before = self.w.critical_state_snapshot()
        out = self.w.record_narration("n2", "Описание результата.")
        self.assertTrue(out["recorded"])
        self.assertEqual(before, self.w.critical_state_snapshot())

    def test_checkpoint_detects_external_mutation(self):
        self.w.process_player_turn("c1", "жду 1 минуту")
        self.assertTrue(self.w.verify_latest_checkpoint()["ok"])
        self.w.db.execute("UPDATE actors SET cash_copper=cash_copper+1 WHERE id='player'")
        self.w.db.commit()
        self.assertFalse(self.w.verify_latest_checkpoint()["ok"])

    def test_gm_packet_has_authority_contract_and_guardrail(self):
        r = self.w.process_player_turn("g1", "жду 1 минуту")
        packet = r["gm_packet"]
        self.assertLess(packet["packet_meta"]["chars"], 8000)
        self.assertIn("state_authority", packet["constraints"])
        self.assertIn("forbidden", r["narration_contract"])


class V06MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"; self.root.mkdir()

    def tearDown(self): self.tmp.cleanup()

    def write_repo(self, *, version=7, location="Eurazania capital; street", cash="26g05s92c", time="T+131 ~07:42", extra=None):
        (self.root / "live_state.json").write_text(json.dumps({"v": version, "parent": "abc", "delta": f"live_v{version}", "economy": "ECONOMY_MODEL_v1"}), encoding="utf-8")
        (self.root / "world_save.json").write_text(json.dumps({"save_version": 3, "archive": True}), encoding="utf-8")
        d = self.root / f"live_v{version}"; d.mkdir()
        payload = {"v": version, "time": time, "location": location, "personal_cash": cash,
                   "scene": {"x": "y"}, "hard_rules_reaffirmed": ["UNKNOWN stays UNKNOWN"]}
        if extra: payload.update(extra)
        (d / "delta.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_time_money_and_region_parsers(self):
        self.assertEqual(parse_world_time("T+131 ~07:42"), 131*1440+7*60+42)
        self.assertEqual(parse_money("26g05s92c"), 260592)
        self.assertEqual(strict_region_from_text("Eurazania capital; street")[0], "eurazania")

    def test_ambiguous_region_is_not_guessed(self):
        region, hits = strict_region_from_text("Leaving Blumund for Dwargon")
        self.assertIsNone(region); self.assertEqual(set(hits), {"blumund", "dwargon"})

    def test_repo_package_exact_core_is_rehearsal_ready(self):
        self.write_repo(extra={"unknown_field": "UNKNOWN"})
        p = collect_repo_campaign(self.root)
        self.assertTrue(p.report["rehearsal_ready"])
        self.assertFalse(p.report["live_cutover_ready"])
        self.assertEqual(p.snapshot["player"]["cash_copper"], 260592)
        self.assertIn("$.unknown_field", p.report["preserved_unknown_paths"])

    def test_bad_cash_blocks_rehearsal(self):
        self.write_repo(cash="UNKNOWN")
        p = collect_repo_campaign(self.root)
        self.assertFalse(p.report["rehearsal_ready"])
        self.assertIn("current_personal_cash_not_exact", p.report["core_blockers"])

    def test_ambiguous_current_location_blocks_rehearsal(self):
        self.write_repo(location="between Blumund and Dwargon")
        p = collect_repo_campaign(self.root)
        self.assertFalse(p.report["rehearsal_ready"])
        self.assertIn("current_region_not_unambiguous", p.report["core_blockers"])

    def test_pointer_must_resolve_exact_delta(self):
        self.write_repo()
        data = json.loads((self.root / "live_state.json").read_text())
        data["delta"] = "live_v999"
        (self.root / "live_state.json").write_text(json.dumps(data), encoding="utf-8")
        p = collect_repo_campaign(self.root)
        self.assertFalse(p.report["rehearsal_ready"])
        self.assertTrue(any("pointer delta missing" in x for x in p.report["errors"]))

    def test_apply_archives_every_source_and_maps_only_exact_core(self):
        self.write_repo(extra={"family_budget": "0 currently", "scene": {"rena_family_budget_decision": {"current_balance": "0; no transfer", "rena_personal_cash": "UNKNOWN"}}})
        p = collect_repo_campaign(self.root)
        db = Path(self.tmp.name) / "migration.db"
        with seed_world_v06_migration(db) as w:
            report = apply_repo_campaign_rehearsal(w, p)
            self.assertTrue(report["source_archive_complete"])
            self.assertEqual(str(w.actor("player")["region_id"]), "eurazania")
            self.assertEqual(int(w.actor("player")["cash_copper"]), 260592)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM campaign_archives").fetchone()[0], len(p.source_documents))
            fam = w.db.execute("SELECT balance_copper FROM fund_accounts WHERE id='family_purse'").fetchone()
            self.assertEqual(int(fam[0]), 0)

    def test_migration_disables_unmapped_combat_and_social_checks(self):
        self.write_repo()
        p = collect_repo_campaign(self.root)
        db = Path(self.tmp.name) / "migration2.db"
        with seed_world_v06_migration(db) as w:
            apply_repo_campaign_rehearsal(w, p)
            caps = {r["command"]: bool(r["enabled"]) for r in w.db.execute("SELECT command,enabled FROM migration_capabilities")}
            self.assertTrue(caps["travel"]); self.assertTrue(caps["buy"]); self.assertTrue(caps["wait"])
            self.assertFalse(caps["strike"]); self.assertFalse(caps["attempt"]); self.assertFalse(caps["social"])

    def test_migrated_unknowns_are_archived_not_normalized(self):
        self.write_repo(extra={"rena": {"cash": "UNKNOWN"}})
        p = collect_repo_campaign(self.root)
        db = Path(self.tmp.name) / "migration3.db"
        with seed_world_v06_migration(db) as w:
            apply_repo_campaign_rehearsal(w, p)
            raw = w.db.execute("SELECT payload_text FROM campaign_archives WHERE source_path=?", (p.latest_delta.path,)).fetchone()[0]
            self.assertIn("UNKNOWN", raw)
            self.assertIsNone(w.db.execute("SELECT 1 FROM actors WHERE id='rena'").fetchone())


if __name__ == "__main__": unittest.main()
