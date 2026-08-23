import argparse,json,tempfile
from pathlib import Path
from v05_seed import seed_world_v05

p=argparse.ArgumentParser(); p.add_argument('--days',type=int,default=30); a=p.parse_args()
with tempfile.TemporaryDirectory() as td:
    db=Path(td)/'probe.db'; w=seed_world_v05(db)
    before={'region':str(w.actor('player')['region_id']),'cash':int(w.actor('player')['cash_copper']),'hp':int(w.stats('player')['hp'])}
    w.record_crime('player','theft',witnessed=False)
    w.advance(a.days*1440)
    after={'region':str(w.actor('player')['region_id']),'cash':int(w.actor('player')['cash_copper']),'hp':int(w.stats('player')['hp'])}
    packet=w.build_gm_packet()
    out={
      'days':a.days,'player_unchanged':before==after,'before':before,'after':after,
      'macro_ticks':w.metric('macro_ticks'),'faction_actions':w.metric('faction_actions'),
      'gm_packet_chars':packet['packet_meta']['chars'],
      'active_conditions':w.db.execute("SELECT COUNT(*) FROM conditions WHERE status='active'").fetchone()[0],
      'evidence_active':w.db.execute("SELECT COUNT(*) FROM evidence_items WHERE status='active'").fetchone()[0],
      'intent_rows':w.db.execute("SELECT COUNT(*) FROM intent_proposals").fetchone()[0],
      'deferred_named_plans':w.db.execute("SELECT COUNT(*) FROM npc_travel_plans WHERE status='deferred'").fetchone()[0],
    }
    print(json.dumps(out,ensure_ascii=False,indent=2)); w.close()
