from v03_engine import WorldV03, DAY


def seed_world(db_path):
    from pathlib import Path
    root=Path(__file__).resolve().parent
    w=WorldV03.create(db_path,root/'v03_schema.sql',seed=303117,start_minute=117*DAY+8*60)
    for row in [
        ('blumund','Блюмунд','city',18000,62,55),
        ('dwargon','Дваргон','city',85000,88,82),
        ('eurazania','Столица Эуразании','city',52000,72,68),
        ('jura_edge','Край Великого леса Джура','region',9000,35,28)
    ]:
        w.add_region(*row)
    w.connect('blumund','dwargon',720,180,12)
    w.connect('blumund','jura_edge',540,100,35)
    w.connect('jura_edge','eurazania',780,90,42)
    w.connect('dwargon','jura_edge',900,150,25)

    w.add_actor('player','Маэстро Арлекино','blumund',cash=216641,is_player=True)

    for c in [
        ('grain','Зерно',18,1),
        ('paper','Бумага',55,0),
        ('iron','Железо',90,0)
    ]:
        w.add_commodity(*c)

    markets={
      'blumund': {
        'grain':(700,900,240,620,600),
        'paper':(120,220,80,70,75),
        'iron':(90,180,55,35,50)
      },
      'dwargon': {
        'grain':(1300,1500,300,1200,880),
        'paper':(500,500,90,250,210),
        'iron':(1400,900,180,1050,650)
      },
      'eurazania': {
        'grain':(300,1100,420,720,720),
        'paper':(90,260,100,45,80),
        'iron':(120,300,95,55,100)
      },
      'jura_edge': {
        'grain':(120,420,180,380,310),
        'paper':(20,80,30,5,15),
        'iron':(30,100,40,10,30)
      },
    }
    for r,cs in markets.items():
        for cid,(s,t,d,pd,cd) in cs.items():
            w.set_market(r,cid,supply=s,target=t,demand=d,production=pd,consumption=cd)

    w.add_faction('blumund_guard','Блюмундская стража','guard','blumund',90000,{'security':90})
    w.add_faction('merchant_league','Торговая лига','merchant','blumund',450000,{'profit':90,'risk_tolerance':45})
    w.add_faction('dwargon_trade','Дваргонские торговые дома','merchant','dwargon',1200000,{'profit':85,'risk_tolerance':35})
    w.add_faction_goal('blumund_guard','secure_home','blumund',80)
    w.add_faction_goal('merchant_league','trade_profit','blumund',75)
    w.add_faction_goal('dwargon_trade','trade_profit','dwargon',70)

    for r,pop in [
        ('blumund',18000),('dwargon',85000),('eurazania',52000),('jura_edge',9000)
    ]:
        w.db.execute(
            "INSERT INTO population_groups(region_id,role,count,wealth,unrest,last_macro_at) VALUES(?,?,?,?,?,?)",
            (r,'commoners',round(pop*.72),50,8,w.now)
        )
        w.db.execute(
            "INSERT INTO population_groups(region_id,role,count,wealth,unrest,last_macro_at) VALUES(?,?,?,?,?,?)",
            (r,'workers',round(pop*.20),55,6,w.now)
        )
        w.db.execute(
            "INSERT INTO population_groups(region_id,role,count,wealth,unrest,last_macro_at) VALUES(?,?,?,?,?,?)",
            (r,'elite',pop-round(pop*.92),82,2,w.now)
        )

    w.event('world_seeded',region='blumund',significance=10,payload={'version':'0.3'})
    w.db.commit()
    return w


if __name__=='__main__':
    import argparse, json
    p=argparse.ArgumentParser()
    p.add_argument('--db',default='v03_demo.db')
    a=p.parse_args()
    with seed_world(a.db) as w:
        print(json.dumps(w.build_context(), ensure_ascii=False, indent=2))
