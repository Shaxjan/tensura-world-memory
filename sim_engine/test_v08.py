import json
import tempfile
import unittest
from pathlib import Path

from v06_migration import collect_repo_campaign
from v08_money import apply_v08_money_reconciliation
from v08_seed import seed_world_v08_migration


class V08MoneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        (self.root / "memory").mkdir(parents=True)
        (self.root / "rules").mkdir()
        (self.root / "ECONOMY_MODEL_v1").mkdir()
        self._write_sources()
        self._write_campaign(9)
        self._write_reconciliation(9)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_sources(self):
        (self.root / "memory/money.json").write_text(json.dumps({
            "current_saved_canon": {"live_pointer_version": 7},
            "separate_funds_last_explicit_record": {
                "promo_remaining": {"amount": "27s36c"},
                "lissa_project_fund": {"amount": "4g"},
                "oren_project_fund": {"amount": "4g"}},
            "paid_and_held_money": {
                "vern": {"instrument_float_held": "50s"},
                "meira": {"remaining_obligation": "1g"}},
        }, ensure_ascii=False), encoding="utf-8")
        (self.root / "memory/places.json").write_text("{}", encoding="utf-8")
        (self.root / "memory/relationships.json").write_text(json.dumps({
            "relationships": [{"entity": "Рена", "status": "SAVED_CANON", "relationship": "помолвлены"}]
        }, ensure_ascii=False), encoding="utf-8")
        (self.root / "memory/actions.json").write_text(json.dumps({
            "active_people_tasks": [{"person": "Борга", "task": "турнир", "status": "ACTIVE"}],
            "mail": [], "festival": {"status": "SAVED_CANON"}, "tournament": {"status": "SAVED_CANON"}
        }, ensure_ascii=False), encoding="utf-8")
        for rel in ("NPC_AUTONOMY_MODEL_v1.md", "NPC_INDIVIDUALITY_AND_AUTONOMY_RULE.md"):
            (self.root / "rules" / rel).write_text("HARD RULE autonomy", encoding="utf-8")
        for rel in ("01_core.txt","02_money.txt","03_concert_income.txt","04_tips.txt","05_city_profile.txt","06_audience.txt","07_song.txt","08_costs.txt","09_reputation.txt","10_cap.txt","11_dynamics.txt","20_eurazania.txt","21_blumund.txt"):
            (self.root / "ECONOMY_MODEL_v1" / rel).write_text("rule", encoding="utf-8")

    def _write_delta(self, version, payload):
        d = self.root / f"live_v{version}"
        d.mkdir(exist_ok=True)
        (d / "delta.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _write_campaign(self, version):
        (self.root / "world_save.json").write_text(json.dumps({"save_version": 3}), encoding="utf-8")
        self._write_delta(8, {
            "v": 8, "time": "T+131 ~07:30", "location": "Eurazania capital",
            "cash_before": "28g05s93c", "cash_after": "26g05s92c",
            "economy": {"allocation": [{"amount": "1g"}, {"amount": "1g"}, {"amount": "1c"}]},
            "note": "promo Lissa Oren Vern Meira publicity instrument coordinator"})
        current = {
            "v": version, "time": "T+131 ~07:42", "location": "Eurazania capital; leaving lodging",
            "personal_cash": "26g05s92c", "scene": {"family": {"current_balance": "0"}},
            "hard_rules_reaffirmed": ["UNKNOWN stays UNKNOWN"]}
        if version > 9:
            current["note"] = "Lissa project fund mentioned after reconciliation"
        self._write_delta(version, current)
        (self.root / "live_state.json").write_text(json.dumps({
            "v": version, "parent": "x", "delta": f"live_v{version}", "economy": "ECONOMY_MODEL_v1"
        }), encoding="utf-8")

    def _write_reconciliation(self, through):
        audit = {
            "audit_version": 8,
            "reconciled_through_live_version": through,
            "reviewed_mentions": {
                "promo": [8], "lissa_project": [8], "oren_project": [8],
                "vern_instrument_float": [8], "meira_obligation": [8]},
            "accounts": {
                "promo": {"account_type":"separate_fund","balance":"27s36c","known_principal":None,"certainty":"EXACT_CURRENT","holder":"project","status":"available","source_path":"memory/money.json"},
                "lissa_project": {"account_type":"project_fund","balance":"4g","known_principal":None,"certainty":"EXACT_CURRENT","holder":"lissa_project","status":"separate","source_path":"memory/money.json"},
                "oren_project": {"account_type":"project_fund","balance":"4g","known_principal":None,"certainty":"EXACT_CURRENT","holder":"oren_project","status":"separate","source_path":"memory/money.json"},
                "vern_instrument_float": {"account_type":"entrusted_float","balance":"UNKNOWN","known_principal":"50s","certainty":"AUTHORITATIVE_UNKNOWN_CURRENT_BALANCE","holder":"vern","status":"settlement_pending","source_path":"memory/money.json"},
                "meira_obligation": {"account_type":"payable","balance":"1g","known_principal":None,"certainty":"EXACT_OUTSTANDING","holder":"obligation","status":"payable","source_path":"memory/money.json"},
                "family_purse": {"account_type":"family_fund","balance":"0","known_principal":None,"certainty":"EXACT_CURRENT","holder":"family","status":"created_not_funded","source_path":"live_v9/delta.json"},
                "lissa_outreach_enclosure": {"account_type":"earmarked_enclosure","balance":"1g","known_principal":None,"certainty":"EXACT_ALLOCATED","holder":"rena","status":"not_delivered","source_path":"live_v8/delta.json"},
                "dwargon_outreach_enclosure": {"account_type":"earmarked_enclosure","balance":"1g","known_principal":None,"certainty":"EXACT_ALLOCATED","holder":"rena","status":"not_delivered","source_path":"live_v8/delta.json"},
                "queen_enclosure": {"account_type":"earmarked_enclosure","balance":"1c","known_principal":None,"certainty":"EXACT_ALLOCATED","holder":"rena","status":"not_delivered","source_path":"live_v8/delta.json"}},
            "evidence": [
                {"account":"promo","versions":[8],"classification":"reviewed_no_effect"},
                {"account":"lissa_project","versions":[8],"classification":"reviewed_no_effect"},
                {"account":"oren_project","versions":[8],"classification":"reviewed_no_effect"},
                {"account":"vern_instrument_float","versions":[8],"classification":"unknown_balance"},
                {"account":"meira_obligation","versions":[8],"classification":"no_payment"}],
            "verified_anchors": [
                {"path":"memory/money.json","must_contain":["27s36c","50s"]},
                {"path":"live_v8/delta.json","must_contain":["cash_before","promo","Lissa"]}],
            "conservation_check": {
                "path": "live_v8/delta.json", "expected_cash_before": "28g05s93c",
                "expected_cash_after": "26g05s92c", "expected_allocated": "2g00s01c"}}
        (self.root / "memory/money_reconciliation_v159.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    def _run(self):
        package = collect_repo_campaign(self.root)
        db = Path(self.tmp.name) / "v08.db"
        w = seed_world_v08_migration(db)
        report = apply_v08_money_reconciliation(w, package, self.root)
        return w, report

    def test_money_integrity_blocker_is_resolved(self):
        w, r = self._run()
        try:
            self.assertTrue(r["baseline_ready"])
            self.assertEqual(r["historical_integrity_blockers"], [])
            self.assertIn("player_power_calibration_pending", r["feature_calibration_pending"])
            self.assertFalse(r["live_cutover_ready"])
        finally: w.close()

    def test_vern_principal_is_known_but_current_balance_is_unknown(self):
        w, r = self._run()
        try:
            row = w.db.execute("SELECT balance_copper,known_principal_copper,certainty FROM financial_account_state WHERE account_id='vern_instrument_float'").fetchone()
            self.assertIsNone(row["balance_copper"])
            self.assertEqual(int(row["known_principal_copper"]), 5000)
            self.assertIn("UNKNOWN", row["certainty"])
        finally: w.close()

    def test_lissa_project_and_new_enclosure_are_distinct(self):
        w, r = self._run()
        try:
            project = w.db.execute("SELECT balance_copper FROM financial_account_state WHERE account_id='lissa_project'").fetchone()[0]
            enclosure = w.db.execute("SELECT balance_copper FROM financial_account_state WHERE account_id='lissa_outreach_enclosure'").fetchone()[0]
            self.assertEqual(int(project), 40000)
            self.assertEqual(int(enclosure), 10000)
        finally: w.close()

    def test_allocation_conservation_is_exact(self):
        w, r = self._run()
        try:
            c = r["conservation"]
            self.assertTrue(c["ok"])
            self.assertEqual(c["cash_before_copper"] - c["cash_after_copper"], 20001)
            self.assertEqual(c["allocated_copper"], 20001)
        finally: w.close()

    def test_future_relevant_mention_makes_reconciliation_stale(self):
        self._write_campaign(10)
        w, r = self._run()
        try:
            self.assertFalse(r["baseline_ready"])
            self.assertIn("money_reconciliation_stale_after_checkpoint", r["historical_integrity_blockers"])
            self.assertIn("lissa_project", r["stale_after_reconciliation"])
        finally: w.close()

    def test_missing_anchor_fails_closed(self):
        audit = json.loads((self.root / "memory/money_reconciliation_v159.json").read_text())
        audit["verified_anchors"].append({"path":"live_v8/delta.json","must_contain":["DOES_NOT_EXIST"]})
        (self.root / "memory/money_reconciliation_v159.json").write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
        w, r = self._run()
        try:
            self.assertFalse(r["baseline_ready"])
            self.assertTrue(any("evidence_anchor_missing" in e for e in r["errors"]))
        finally: w.close()


if __name__ == "__main__": unittest.main()
