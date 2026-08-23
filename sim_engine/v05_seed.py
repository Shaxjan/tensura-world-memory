from pathlib import Path

from v04_seed import seed_world_v04
from v05_engine import WorldV05


def seed_world_v05(db_path):
    root=Path(__file__).resolve().parent
    base=seed_world_v04(db_path)
    base.db.executescript((root/'v05_schema.sql').read_text(encoding='utf-8'))
    base.db.commit(); base.close()
    w=WorldV05(db_path)

    # Power profiles are engine-facing balance data, not a claim of final canon values.
    w.set_power_profile('player',threat_rank='D',magicules=1200,physical=28,magic=18,control=24,durability=24,regeneration=0)
    w.set_power_profile('rena',threat_rank='C',magicules=2600,physical=38,magic=12,control=34,durability=32,regeneration=0)
    w.set_power_profile('captain_dalen',threat_rank='C',magicules=1800,physical=34,magic=8,control=30,durability=36,regeneration=0)
    w.set_power_profile('sparring_rival',threat_rank='D',magicules=900,physical=24,magic=5,control=20,durability=22,regeneration=0)
    w.set_power_profile('merchant_borga',threat_rank='E',magicules=250,physical=12,magic=3,control=12,durability=12,regeneration=0)

    for actor, extra in {
        'player': {'medicine':3,'healing_magic':0,'deception':2,'intimidation':2},
        'rena': {'medicine':1,'deception':2,'intimidation':5},
        'captain_dalen': {'medicine':2,'deception':2,'intimidation':5},
        'merchant_borga': {'perception':3,'deception':5,'intimidation':0},
    }.items():
        for skill,bonus in extra.items(): w.set_skill(actor,skill,bonus)

    w.set_bond('rena','player',affinity=62,trust=48,respect=38,fear=0,obligation=5)
    w.set_bond('captain_dalen','player',affinity=5,trust=10,respect=18,fear=0,obligation=0)
    w.set_bond('merchant_borga','player',affinity=8,trust=4,respect=5,fear=0,obligation=0)
    w.relationship_event('rena','player','shared_travel','Chose to continue travelling together.',trust=4,affinity=3,respect=1,salience=82)
    w.add_routine('rena','blumund',9*60,11*60,'training',priority=70)

    # A named-NPC trip that must defer if a higher-priority appointment conflicts.
    w.add_travel_plan('captain_dalen','dwargon',w.now+120,'official inspection',priority=45)
    w.schedule_appointment('captain_dalen','merchant_borga','blumund',w.now+150,grace_minutes=30,purpose='take merchant statement')

    w.event('world_v05_seeded',region='blumund',significance=15,payload={'version':'0.5'})
    w.db.commit(); return w

if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser(); p.add_argument('--db',default='v05_demo.db'); a=p.parse_args()
    with seed_world_v05(a.db) as w: print(json.dumps(w.build_gm_packet(),ensure_ascii=False,indent=2))
