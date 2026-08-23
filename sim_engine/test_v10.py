import tempfile
import unittest
from pathlib import Path

from v09_runtime import install_guarded_mechanics_policy
from v10_handoff import export_portable_checkpoint_v10, import_portable_checkpoint_v10
from v10_runtime import install_v10_runtime_bridges
from v10_seed import seed_world_v10_migration


class V10Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
    def tearDown(self): self.tmp.cleanup()

    def db(self,name): return Path(self.tmp.name)/name

    def _claim_borga(self,w):
        w.db.execute(
            "INSERT OR REPLACE INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) VALUES(?,?,?,?,?,?,?,?,?)",
            ("borga","Борга","eurazania",None,"region_only","current_region",159,"test","")
        ); w.db.commit()

    def _commitment(self,w,key="task:borga",kind="npc_task",owner="borga"):
        w.db.execute(
            "INSERT OR REPLACE INTO autonomous_commitments(commitment_key,owner_key,kind,state_json,status,source_path,as_of_version) VALUES(?,?,?,?,?,?,?)",
            (key,owner,kind,'{"task":"work"}',"ACTIVE","test",159)
        ); w.db.commit()

    def test_dialogue_is_recorded_without_world_mutation(self):
        with seed_world_v10_migration(self.db("a.db")) as w:
            install_v10_runtime_bridges(w)
            before=(w.actor("player")["region_id"],w.actor("player")["cash_copper"],w.now)
            out=w.process_player_turn("speak","Говорю вслух: «Доброе утро.»")
            after=(w.actor("player")["region_id"],w.actor("player")["cash_copper"],w.now)
            self.assertTrue(out["accepted"]); self.assertEqual(out["status"],"executed"); self.assertEqual(before,after)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM scene_pending_resolution").fetchone()[0],0)

    def test_current_style_local_search_is_pending_not_teleport(self):
        with seed_world_v10_migration(self.db("b.db")) as w:
            self._claim_borga(w); install_v10_runtime_bridges(w)
            region=str(w.actor("player")["region_id"]); cash=int(w.actor("player")["cash_copper"])
            out=w.process_player_turn("find-borga","Иду искать Боргу.")
            self.assertTrue(out["accepted"]); self.assertEqual(out["status"],"scene_pending")
            self.assertEqual(str(w.actor("player")["region_id"]),region); self.assertEqual(int(w.actor("player")["cash_copper"]),cash)
            p=w.db.execute("SELECT resolution_kind,target_key,status FROM scene_pending_resolution").fetchone()
            self.assertEqual(p["resolution_kind"],"local_navigation"); self.assertEqual(p["target_key"],"borga"); self.assertEqual(p["status"],"pending")

    def test_interaction_attempt_never_invents_npc_response(self):
        with seed_world_v10_migration(self.db("c.db")) as w:
            w.db.execute("INSERT OR REPLACE INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) VALUES('rena','Рена','eurazania',NULL,'region_only','current',159,'test','')")
            w.db.commit(); install_v10_runtime_bridges(w)
            out=w.process_player_turn("hug","Обнимаю Рену.")
            self.assertEqual(out["status"],"scene_pending")
            self.assertEqual(w.db.execute("SELECT resolution_kind FROM scene_pending_resolution").fetchone()[0],"npc_or_world_response")

    def test_money_action_cannot_bypass_economy(self):
        with seed_world_v10_migration(self.db("d.db")) as w:
            install_v10_runtime_bridges(w)
            before=int(w.actor("player")["cash_copper"])
            out=w.process_player_turn("pay","Плачу Борге 1g.")
            self.assertFalse(out["accepted"]); self.assertEqual(out["status"],"blocked_by_guardrail")
            self.assertEqual(int(w.actor("player")["cash_copper"]),before)
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM scene_actions").fetchone()[0],0)

    def test_combat_never_falls_through_generic_scene_bridge(self):
        with seed_world_v10_migration(self.db("e.db")) as w:
            self._claim_borga(w); install_guarded_mechanics_policy(w); install_v10_runtime_bridges(w)
            out=w.process_player_turn("hit","Бью Боргу.")
            self.assertFalse(out["accepted"])
            self.assertNotIn(out["status"],{"executed","scene_pending"})
            self.assertEqual(w.db.execute("SELECT COUNT(*) FROM scene_actions").fetchone()[0],0)

    def test_handoff_is_offer_until_recipient_response(self):
        with seed_world_v10_migration(self.db("f.db")) as w:
            w.db.execute("INSERT OR REPLACE INTO actor_position_claims(actor_key,display_name,region_id,location_text,precision,status,as_of_version,source_path,note) VALUES('rena','Рена','eurazania',NULL,'region_only','current',159,'test','')")
            w.db.execute("INSERT INTO scene_objects(object_key,display_name,holder_key,state_json,certainty,source_path,updated_at) VALUES('rena_guitar','гитара Рены','player','{}','exact','test',?)",(w.now,))
            w.db.commit(); install_v10_runtime_bridges(w)
            out=w.process_player_turn("return-guitar","Возвращаю Рене гитару.")
            self.assertEqual(out["status"],"scene_pending")
            self.assertEqual(w.db.execute("SELECT holder_key FROM scene_objects WHERE object_key='rena_guitar'").fetchone()[0],"player")

    def test_wait_advances_one_clock_and_runs_commitments(self):
        with seed_world_v10_migration(self.db("g.db")) as w:
            self._commitment(w); install_guarded_mechanics_policy(w); install_v10_runtime_bridges(w)
            before=w.now; region=str(w.actor("player")["region_id"]); cash=int(w.actor("player")["cash_copper"])
            out=w.process_player_turn("wait15","жду 15 минут")
            self.assertTrue(out["accepted"]); self.assertEqual(out["status"],"executed"); self.assertEqual(w.now,before+15)
            self.assertGreater(w.db.execute("SELECT COUNT(*) FROM autonomy_execution_log").fetchone()[0],0)
            self.assertEqual(str(w.actor("player")["region_id"]),region); self.assertEqual(int(w.actor("player")["cash_copper"]),cash)

    def test_mail_unknown_route_records_causal_block_not_fake_arrival(self):
        with seed_world_v10_migration(self.db("h.db")) as w:
            self._commitment(w,"mail:1","mail",None); install_guarded_mechanics_policy(w); install_v10_runtime_bridges(w)
            w.advance(15)
            row=w.db.execute("SELECT outcome_code,outcome_json FROM autonomy_execution_log WHERE commitment_key='mail:1' ORDER BY id DESC LIMIT 1").fetchone()
            self.assertEqual(row["outcome_code"],"causally_blocked"); self.assertIn("route_or_dispatch_price_unknown",row["outcome_json"])

    def test_v10_portable_roundtrip_contains_scene_and_autonomy_state(self):
        with seed_world_v10_migration(self.db("i1.db")) as w:
            self._commitment(w); install_guarded_mechanics_policy(w); install_v10_runtime_bridges(w)
            w.process_player_turn("scene","Говорю: «Проверка.»")
            snap=export_portable_checkpoint_v10(w,159); before=w.critical_state_snapshot("player")
        with seed_world_v10_migration(self.db("i2.db")) as r:
            result=import_portable_checkpoint_v10(r,snap)
            self.assertTrue(result["ok"],result); self.assertEqual(result["state_hash"],result["restored_hash"])
            self.assertEqual(before,r.critical_state_snapshot("player"))

    def test_install_resolves_two_v09_runtime_gates_but_leaves_shadow(self):
        with seed_world_v10_migration(self.db("j.db")) as w:
            install_guarded_mechanics_policy(w); install_v10_runtime_bridges(w)
            gates={r["gate_code"]:r["status"] for r in w.db.execute("SELECT gate_code,status FROM cutover_gate")}
            self.assertEqual(gates["scene_action_bridge_not_implemented"],"resolved")
            self.assertEqual(gates["autonomy_commitment_execution_not_wired"],"resolved")
            self.assertEqual(gates["shadow_scene_verification"],"pending_shadow")
            self.assertTrue(bool(w.db.execute("SELECT enabled FROM migration_capabilities WHERE command='wait'").fetchone()[0]))


if __name__=="__main__": unittest.main()
