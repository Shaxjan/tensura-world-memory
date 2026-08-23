import json, tempfile, unittest
from pathlib import Path
from v03_seed import seed_world


class V03Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'w.db'
        self.w=seed_world(self.db)

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def test_player_not_autopiloted(self):
        b=dict(self.w.actor('player'))
        self.w.advance(7*1440)
        a=dict(self.w.actor('player'))
        self.assertEqual(b['region_id'],a['region_id'])
        self.assertEqual(b['cash_copper'],a['cash_copper'])

    def test_factions_act_without_player(self):
        self.w.advance(1440)
        self.assertGreater(self.w.metric('faction_actions'),0)
        self.assertGreater(self.w.db.execute("SELECT COUNT(*) FROM events WHERE event_type='faction_action'").fetchone()[0],0)

    def test_information_has_real_delay(self):
        self.w.create_fact('test.alert',{'severity':80},'eurazania',80,mode='courier')
        self.assertIsNone(self.w.db.execute("SELECT 1 FROM region_beliefs WHERE region_id='blumund' AND fact_key='test.alert'").fetchone())
        self.w.advance(700)
        self.assertIsNone(self.w.db.execute("SELECT 1 FROM region_beliefs WHERE region_id='blumund' AND fact_key='test.alert'").fetchone())
        self.w.advance(200)
        self.assertIsNotNone(self.w.db.execute("SELECT 1 FROM region_beliefs WHERE region_id='blumund' AND fact_key='test.alert'").fetchone())

    def test_market_price_responds_to_scarcity(self):
        p0=self.w.price('blumund','grain')
        self.w.db.execute("UPDATE markets SET supply=40,demand=500 WHERE region_id='blumund' AND commodity_id='grain'")
        for _ in range(3):
            self.w._reprice('blumund','grain')
        self.assertGreater(self.w.price('blumund','grain'),p0)

    def test_purchase_is_atomic(self):
        before=int(self.w.actor('player')['cash_copper'])
        supply=self.w.db.execute("SELECT supply FROM markets WHERE region_id='blumund' AND commodity_id='grain'").fetchone()[0]
        with self.assertRaises(ValueError):
            self.w.buy_from_market('player','grain',999999)
        self.assertEqual(int(self.w.actor('player')['cash_copper']),before)
        self.assertEqual(self.w.db.execute("SELECT supply FROM markets WHERE region_id='blumund' AND commodity_id='grain'").fetchone()[0],supply)

    def test_trade_caravan_moves_real_stock(self):
        self.w.advance(4*1440)
        self.assertGreater(self.w.metric('caravans_completed'),0)

    def test_lod_is_relative_to_player(self):
        self.assertEqual(self.w.detail_level('blumund'),'full')
        self.assertEqual(self.w.detail_level('dwargon'),'active')
        self.assertEqual(self.w.detail_level('eurazania'),'macro')

    def test_macro_sim_not_per_person(self):
        pop=self.w.db.execute("SELECT SUM(population) FROM regions").fetchone()[0]
        self.w.advance(30*1440)
        events=self.w.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.assertGreater(pop,100000)
        self.assertLess(events,5000)
        self.assertEqual(self.w.metric('macro_ticks'),120)

    def test_30_day_essential_supply_does_not_systemically_collapse(self):
        self.w.advance(30*1440)
        rows=self.w.db.execute("SELECT region_id,supply,target_supply FROM markets WHERE commodity_id='grain' ORDER BY region_id").fetchall()
        self.assertTrue(all(int(r['supply'])>0 for r in rows))
        self.assertTrue(all(self.w.price(str(r['region_id']),'grain')>0 for r in rows))

    def test_context_is_small_and_local(self):
        self.w.event('remote_secret',region='eurazania',significance=100,payload={'secret':'must_not_leak'})
        self.w.event('local_notice',region='blumund',significance=80,payload={'notice':'visible'})
        text=json.dumps(self.w.build_context(),ensure_ascii=False)
        self.assertLess(len(text),8000)
        self.assertIn('local_notice',text)
        self.assertNotIn('must_not_leak',text)

    def test_context_uses_actor_knowledge_not_global_truth(self):
        self.w.create_fact('hidden.remote',{'x':1},'eurazania',90)
        ctx=self.w.build_context()
        self.assertFalse(any(x['key']=='hidden.remote' for x in ctx['known_facts']))
        self.w.db.execute("INSERT INTO actor_knowledge VALUES('player','hidden.remote',100,?,'direct')",(self.w.now,))
        ctx=self.w.build_context()
        self.assertTrue(any(x['key']=='hidden.remote' for x in ctx['known_facts']))

    def test_security_faction_reacts_to_received_threat(self):
        sec0=self.w.db.execute("SELECT security FROM regions WHERE id='blumund'").fetchone()[0]
        self.w.create_fact('threat.west',{'severity':90},'jura_edge',90,mode='courier')
        self.w.advance(1000)
        sec1=self.w.db.execute("SELECT security FROM regions WHERE id='blumund'").fetchone()[0]
        self.assertGreaterEqual(sec1,sec0)
        actions=self.w.db.execute("SELECT payload_json FROM events WHERE faction_id='blumund_guard' AND event_type='faction_action'").fetchall()
        self.assertTrue(any('security_spend' in r['payload_json'] for r in actions))

    def test_seeded_replay_deterministic(self):
        other=Path(self.tmp.name)/'w2.db'
        w2=seed_world(other)
        try:
            self.w.create_fact('x',{'v':2},'jura_edge',70)
            w2.create_fact('x',{'v':2},'jura_edge',70)
            self.w.advance(5*1440)
            w2.advance(5*1440)
            def snap(w):
                return (
                    [tuple(r) for r in w.db.execute("SELECT region_id,commodity_id,supply,demand,price_copper FROM markets ORDER BY 1,2")],
                    [tuple(r) for r in w.db.execute("SELECT id,treasury_copper,next_action_at FROM factions ORDER BY id")],
                    w.metric('faction_actions'),w.metric('packets_delivered'),w.metric('caravans_completed')
                )
            self.assertEqual(snap(self.w),snap(w2))
        finally:
            w2.close()


if __name__=='__main__':
    unittest.main()
