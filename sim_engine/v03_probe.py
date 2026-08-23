import argparse, json, tempfile
from pathlib import Path
from v03_seed import seed_world


def run(days=30):
    with tempfile.TemporaryDirectory() as td:
        with seed_world(Path(td)/'probe.db') as w:
            before=dict(w.actor('player'))
            w.create_fact(
                'regional.threat',
                {'severity':82,'kind':'organized movement'},
                'jura_edge',
                85,
                mode='rumor'
            )
            w.advance(days*1440)
            after=dict(w.actor('player'))
            markets=[dict(r) for r in w.db.execute(
                "SELECT region_id,commodity_id,supply,demand,price_copper FROM markets ORDER BY 1,2"
            )]
            ctx=w.build_context()
            return {
                'days':days,
                'player_unchanged':before['region_id']==after['region_id'] and before['cash_copper']==after['cash_copper'],
                'metrics':{r['key']:r['value'] for r in w.db.execute('SELECT * FROM metrics')},
                'events':w.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],
                'population':w.db.execute('SELECT SUM(population) FROM regions').fetchone()[0],
                'markets':markets,
                'context_chars':len(json.dumps(ctx,ensure_ascii=False))
            }


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--days',type=int,default=30)
    a=p.parse_args()
    print(json.dumps(run(a.days),ensure_ascii=False,indent=2))
