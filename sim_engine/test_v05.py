import json
import tempfile
import unittest
from pathlib import Path

from v05_seed import seed_world_v05


class V05Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/'w.db'; self.w=seed_world_v05(self.db)
    def tearDown(self): self.w.close(); self.tmp.cleanup()

    def test_grounded_travel_text(self):
        p=self.w.propose_text_intent('player','Иду в Дваргон')
        self.assertEqual(p['status'],'ready'); self.assertEqual(p['command'],'travel'); self.assertEqual(p['params']['destination'],'dwargon')

    def test_missing_destination_requires_clarification(self):
        p=self.w.propose_text_intent('player','Я ухожу из города')
        self.assertEqual(p['status'],'needs_clarification'); self.assertIn('destination',p['missing'])

    def test_external_llm_cannot_invent_destination(self):
        v=self.w.validate_external_intent('player','Я ухожу из города','travel',{'destination':'dwargon'})
        self.assertFalse(v['valid'])

    def test_attack_without_lethality_requires_clarification(self):
        p=self.w.propose_text_intent('player','Атакую Тренировочный соперник')
        self.assertEqual(p['status'],'needs_clarification'); self.assertIn('mode',p['missing'])

    def test_explicit_nonlethal_attack_is_grounded(self):
        p=self.w.propose_text_intent('player','Атакую Тренировочный соперник не убивая')
        self.assertEqual(p['status'],'ready'); self.assertEqual(p['params']['mode'],'nonlethal')

    def test_grounded_social_has_engine_derived_dc(self):
        r=self.w.submit_text_intent('player','Пытаюсь убедить Рена помочь мне')
        self.assertIn('proposal',r); self.assertEqual(r['proposal']['command'],'social')
        if r['accepted']:
            self.assertIn('target_decision',r['engine']['result'])

    def test_old_attack_command_is_disabled(self):
        r=self.w.submit_player_command('player','attack',{'target':'sparring_rival'})
        self.assertFalse(r['accepted']); self.assertIn('explicit_mode',r['reason'])

    def test_nonlethal_attack_cannot_kill(self):
        self.w.set_skill('player','melee',30)
        self.w.db.execute("UPDATE actor_stats SET hp=1,max_hp=18 WHERE actor_id='sparring_rival'"); self.w.db.commit()
        r=self.w.submit_player_command('player','strike',{'target':'sparring_rival','mode':'nonlethal'})
        self.assertTrue(r['accepted']); self.assertNotEqual(r['result']['target_state'],'dead')
        self.assertEqual(int(self.w.stats('sparring_rival')['alive']),1)

    def test_lethal_zero_hp_can_incapacitate_before_death(self):
        self.w.set_skill('player','melee',30)
        self.w.db.execute("UPDATE actor_stats SET hp=2,max_hp=50 WHERE actor_id='sparring_rival'"); self.w.db.commit()
        r=self.w.submit_player_command('player','strike',{'target':'sparring_rival','mode':'lethal'})
        self.assertTrue(r['accepted'])
        self.assertIn(r['result']['target_state'],{'hurt','wounded','incapacitated','dead','unhurt'})
        if r['result']['target_state']=='incapacitated': self.assertEqual(int(self.w.stats('sparring_rival')['alive']),1)

    def test_treatment_can_restore_hp_without_resurrecting_dead(self):
        self.w.db.execute("UPDATE actor_stats SET hp=4,max_hp=24 WHERE actor_id='player'"); self.w.db.commit()
        before=int(self.w.stats('player')['hp'])
        r=self.w.submit_player_command('player','treat',{'target':'player','method':'first_aid'})
        self.assertTrue(r['accepted'])
        self.assertGreaterEqual(int(self.w.stats('player')['hp']),before)

    def test_rank_gap_can_make_attack_ineffective(self):
        self.w.set_power_profile('sparring_rival',threat_rank='S',magicules=99999,physical=100,magic=80,control=90,durability=100,regeneration=0)
        self.w.set_skill('player','melee',0)
        seen=False
        for _ in range(5):
            r=self.w.resolve_tensura_attack('player','sparring_rival',mode='lethal')
            if r['ineffective']: seen=True; break
        self.assertTrue(seen)

    def test_crime_uses_named_witnesses(self):
        r=self.w.record_crime('player','theft',witnessed=True)
        self.assertTrue(r['witnesses'])
        rows=self.w.db.execute("SELECT witness_id FROM crime_witnesses WHERE crime_id=?",(r['crime_id'],)).fetchall()
        self.assertEqual(sorted(r['witnesses']),sorted(str(x['witness_id']) for x in rows))

    def test_unobserved_crime_has_no_testimony(self):
        r=self.w.record_crime('player','theft',witnessed=False)
        self.assertFalse(r['witnesses'])
        self.assertEqual(self.w.db.execute("SELECT COUNT(*) FROM testimonies WHERE crime_id=?",(r['crime_id'],)).fetchone()[0],0)

    def test_unobserved_crime_does_not_instantly_create_legal_case(self):
        r=self.w.record_crime('player','theft',witnessed=False)
        case=self.w.db.execute("SELECT 1 FROM legal_cases WHERE crime_id=?",(r['crime_id'],)).fetchone()
        self.assertIsNone(case)

    def test_evidence_decays(self):
        r=self.w.record_crime('player','theft',witnessed=False)
        s0=int(self.w.db.execute("SELECT strength FROM evidence_items WHERE crime_id=?",(r['crime_id'],)).fetchone()[0])
        self.w.advance(3*1440)
        s1=int(self.w.db.execute("SELECT strength FROM evidence_items WHERE crime_id=?",(r['crime_id'],)).fetchone()[0])
        self.assertLess(s1,s0)

    def test_relationship_memory_changes_decision(self):
        b=self.w.decision_score('rena','player','help')['score']
        self.w.relationship_event('rena','player','betrayal','Player broke a serious promise.',affinity=-35,trust=-55,respect=-20,salience=95)
        a=self.w.decision_score('rena','player','help')['score']
        self.assertLess(a,b)
        self.assertTrue(any('memory:' in x for x in self.w.decision_score('rena','player','help')['reasons']))

    def test_named_routine_changes_npc_activity_not_player(self):
        self.w.advance(60)
        self.assertEqual(str(self.w.actor('rena')['status']),'routine:training')
        self.assertEqual(str(self.w.actor('player')['status']),'idle')

    def test_named_travel_plan_defers_for_appointment(self):
        self.w.advance(121)
        row=self.w.db.execute("SELECT status,resolution FROM npc_travel_plans WHERE actor_id='captain_dalen' ORDER BY id LIMIT 1").fetchone()
        self.assertEqual(row['status'],'deferred'); self.assertIn('appointment:',row['resolution'])

    def test_player_never_gets_npc_travel_plan_autopilot(self):
        pid=self.w.add_travel_plan('player','dwargon',self.w.now+1,'bad scheduler test')
        loc=str(self.w.actor('player')['region_id']); self.w.advance(2)
        self.assertEqual(str(self.w.actor('player')['region_id']),loc)
        self.assertEqual(self.w.db.execute("SELECT status FROM npc_travel_plans WHERE id=?",(pid,)).fetchone()[0],'invalid')

    def test_gm_packet_is_small_and_does_not_expose_remote_secret(self):
        self.w.create_fact('remote.secret.v05',{'secret':'DO_NOT_SHOW'},'eurazania',95)
        packet=self.w.build_gm_packet(); text=json.dumps(packet,ensure_ascii=False)
        self.assertLess(packet['packet_meta']['chars'],8000); self.assertNotIn('DO_NOT_SHOW',text)

    def test_import_refuses_unknown_required_fields(self):
        snap={'save_version':1,'world_minute':'UNKNOWN','player':{'region_id':'blumund','personal_cash':'21g 66s 41c'}}
        r=self.w.apply_campaign_snapshot(snap,source_label='test')
        self.assertFalse(r['applied']); self.assertIn('world_minute',r['report']['unknowns'])

    def test_import_never_guesses_unmapped_region(self):
        snap={'save_version':1,'world_minute':123,'player':{'region_id':'mystery_city','personal_cash':'21g 66s 41c'}}
        r=self.w.apply_campaign_snapshot(snap,source_label='test')
        self.assertFalse(r['applied']); self.assertTrue(any(x.startswith('unmapped_region') for x in r['report']['warnings']))

    def test_import_explicit_snapshot_applies_exact_cash_and_time(self):
        snap={'save_version':1,'world_minute':200000,'player':{'region_id':'blumund','personal_cash':'21g 66s 41c'},'actors':[]}
        r=self.w.apply_campaign_snapshot(snap,source_label='test')
        self.assertTrue(r['applied']); self.assertEqual(self.w.now,200000); self.assertEqual(int(self.w.actor('player')['cash_copper']),216641)

    def test_30_days_no_player_autopilot(self):
        before=(str(self.w.actor('player')['region_id']),int(self.w.actor('player')['cash_copper']))
        self.w.advance(30*1440)
        after=(str(self.w.actor('player')['region_id']),int(self.w.actor('player')['cash_copper']))
        self.assertEqual(before,after)


if __name__=='__main__': unittest.main()
