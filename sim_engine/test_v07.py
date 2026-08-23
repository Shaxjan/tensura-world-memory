import json, tempfile, unittest
from pathlib import Path
from v06_migration import collect_repo_campaign
from v07_baseline import apply_v07_baseline_rehearsal, parse_loose_money
from v07_seed import seed_world_v07_migration

class V07Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)/"repo"; self.root.mkdir()
        (self.root/"memory").mkdir(); (self.root/"rules").mkdir(); (self.root/"ECONOMY_MODEL_v1").mkdir()
        self._write_sources()
    def tearDown(self): self.tmp.cleanup()

    def _write_sources(self):
        (self.root/"memory/money.json").write_text(json.dumps({
            "current_saved_canon":{"live_pointer_version":7},
            "separate_funds_last_explicit_record":{
                "promo_remaining":{"amount":"27s36c"},"oren_project_fund":{"amount":"4g"},"lissa_project_fund":{"amount":"4g"}},
            "paid_and_held_money":{"vern":{"instrument_float_held":"50s"},"meira":{"remaining_obligation":"1g"}}
        },ensure_ascii=False),encoding="utf-8")
        (self.root/"memory/places.json").write_text("{}",encoding="utf-8")
        (self.root/"memory/relationships.json").write_text(json.dumps({"relationships":[
            {"entity":"Рена","status":"SAVED_CANON","relationship":"помолвлены"},
            {"entity":"Борга","status":"SAVED_CANON","relationship":"профессиональный контакт"}]},ensure_ascii=False),encoding="utf-8")
        (self.root/"memory/actions.json").write_text(json.dumps({
            "active_people_tasks":[{"person":"Борга","task":"турнир","status":"ACTIVE"}],
            "mail":[{"recipient":"Lissa","last_known_status":"accepted"}],
            "festival":{"status":"SAVED_CANON"},"tournament":{"status":"SAVED_CANON"}},ensure_ascii=False),encoding="utf-8")
        for rel in ("NPC_AUTONOMY_MODEL_v1.md","NPC_INDIVIDUALITY_AND_AUTONOMY_RULE.md"):
            (self.root/"rules"/rel).write_text("HARD RULE autonomy",encoding="utf-8")
        for rel in ("01_core.txt","02_money.txt","03_concert_income.txt","04_tips.txt","05_city_profile.txt","06_audience.txt","07_song.txt","08_costs.txt","09_reputation.txt","10_cap.txt","11_dynamics.txt","20_eurazania.txt","21_blumund.txt"):
            (self.root/"ECONOMY_MODEL_v1"/rel).write_text("rule",encoding="utf-8")

    def _write_campaign(self,version=9,late_text=None):
        (self.root/"live_state.json").write_text(json.dumps({"v":version,"parent":"x","delta":f"live_v{version}","economy":"ECONOMY_MODEL_v1"}),encoding="utf-8")
        (self.root/"world_save.json").write_text(json.dumps({"save_version":3}),encoding="utf-8")
        d=self.root/f"live_v{version}"; d.mkdir(exist_ok=True)
        payload={"v":version,"time":"T+131 ~07:42","location":"Eurazania capital; leaving lodging","personal_cash":"26g05s92c",
                 "scene":{"rena_family_budget_decision":{"current_balance":"0","rena_personal_cash":"UNKNOWN"}},
                 "hard_rules_reaffirmed":["UNKNOWN stays UNKNOWN"]}
        if late_text: payload["note"]=late_text
        (d/"delta.json").write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")

    def test_loose_money(self):
        self.assertEqual(parse_loose_money("4g"),40000); self.assertEqual(parse_loose_money("50s"),5000)
        self.assertEqual(parse_loose_money("27s36c"),2736); self.assertIsNone(parse_loose_money("UNKNOWN"))

    def test_v07_imports_qualitative_not_numeric_relationship(self):
        self._write_campaign()
        p=collect_repo_campaign(self.root); db=Path(self.tmp.name)/"a.db"
        with seed_world_v07_migration(db) as w:
            r=apply_v07_baseline_rehearsal(w,p,self.root)
            self.assertEqual(r["relationship_evidence_count"],2)
            self.assertEqual(w.db.execute("SELECT status FROM mechanical_calibrations WHERE system_key='relationship_mechanics'").fetchone()[0],"unrated")
            self.assertIsNone(w.db.execute("SELECT 1 FROM social_bonds WHERE actor_id='rena'").fetchone())

    def test_lab_markets_routes_and_commodities_never_leak(self):
        self._write_campaign()
        p=collect_repo_campaign(self.root); db=Path(self.tmp.name)/"b.db"
        with seed_world_v07_migration(db) as w:
            apply_v07_baseline_rehearsal(w,p,self.root)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM markets").fetchone()[0],0)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM routes").fetchone()[0],0)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM commodities").fetchone()[0],0)

    def test_unknown_position_is_structured_not_invented(self):
        self._write_campaign()
        p=collect_repo_campaign(self.root); db=Path(self.tmp.name)/"c.db"
        with seed_world_v07_migration(db) as w:
            apply_v07_baseline_rehearsal(w,p,self.root)
            vern=w.db.execute("SELECT region_id,precision,status FROM actor_position_claims WHERE actor_key='vern'").fetchone()
            self.assertIsNone(vern["region_id"]); self.assertEqual(vern["precision"],"unknown")

    def test_late_money_mention_blocks_carry_forward(self):
        self._write_campaign(version=9,late_text="Лисса: project fund discussed")
        p=collect_repo_campaign(self.root); db=Path(self.tmp.name)/"d.db"
        with seed_world_v07_migration(db) as w:
            r=apply_v07_baseline_rehearsal(w,p,self.root)
            row=w.db.execute("SELECT certainty FROM fund_account_audit WHERE account_id='lissa_project'").fetchone()
            self.assertEqual(row["certainty"],"stale_after_later_mentions")
            self.assertIn("project_fund_reconciliation_pending",r["historical_integrity_blockers"])

    def test_rehearsal_keeps_all_gameplay_locked(self):
        self._write_campaign()
        p=collect_repo_campaign(self.root); db=Path(self.tmp.name)/"e.db"
        with seed_world_v07_migration(db) as w:
            r=apply_v07_baseline_rehearsal(w,p,self.root)
            self.assertFalse(r["live_cutover_ready"])
            self.assertTrue(all(not bool(x["enabled"]) for x in w.db.execute("SELECT enabled FROM migration_capabilities")))
            self.assertIn("player_power_calibration_pending",r["feature_calibration_pending"])

    def test_malformed_history_is_degradation_not_fake_repair(self):
        self._write_campaign(version=9)
        d=self.root/"live_v8"; d.mkdir(); (d/"delta.json").write_text('{"v":8,"broken"',encoding="utf-8")
        p=collect_repo_campaign(self.root); db=Path(self.tmp.name)/"f.db"
        with seed_world_v07_migration(db) as w:
            r=apply_v07_baseline_rehearsal(w,p,self.root)
            self.assertIn("historical_semantics_degraded",r["accepted_degradation"])
            raw=w.db.execute("SELECT payload_text FROM campaign_archives WHERE source_path='live_v8/delta.json'").fetchone()[0]
            self.assertEqual(raw,'{"v":8,"broken"')

if __name__=="__main__": unittest.main()
