from pathlib import Path

from v03_seed import seed_world
from v04_engine import DAY, WorldV04


def seed_world_v04(db_path):
    root = Path(__file__).resolve().parent
    base = seed_world(db_path)
    base.db.executescript((root / "v04_schema.sql").read_text(encoding="utf-8"))
    base.db.commit()
    base.close()

    w = WorldV04(db_path)
    w.set_meta("next_memory_decay_at", str(w.now + DAY))

    w.add_actor("rena", "Рена", "blumund", cash=4_000, is_player=False)
    w.add_actor("captain_dalen", "Капитан Дален", "blumund", cash=9_000, is_player=False)
    w.add_actor("sparring_rival", "Тренировочный соперник", "blumund", cash=2_500, is_player=False)
    w.add_actor("merchant_borga", "Торговец Борга", "blumund", cash=32_000, is_player=False)

    w.ensure_profile("player", max_hp=24, armor=2, power=3)
    w.ensure_profile("rena", max_hp=22, armor=3, power=3)
    w.ensure_profile("captain_dalen", max_hp=28, armor=4, power=4)
    w.ensure_profile("sparring_rival", max_hp=18, armor=1, power=2)
    w.ensure_profile("merchant_borga", max_hp=16, armor=0, power=0)

    for actor, skills in {
        "player": {"melee": 4, "athletics": 5, "performance": 6, "stealth": 2, "persuasion": 5},
        "rena": {"melee": 6, "athletics": 4, "perception": 4},
        "captain_dalen": {"melee": 5, "investigation": 6, "perception": 5},
        "sparring_rival": {"melee": 3, "athletics": 2},
        "merchant_borga": {"persuasion": 4, "insight": 3},
    }.items():
        for skill, bonus in skills.items():
            w.set_skill(actor, skill, bonus)

    for region in ("blumund", "dwargon", "eurazania"):
        w.ensure_reputation("player", region)

    w.set_law("blumund", "theft", severity=55, fine_copper=2_500, jail_minutes=120)
    w.set_law("blumund", "assault", severity=70, fine_copper=5_000, jail_minutes=240)
    w.set_law("blumund", "fraud", severity=45, fine_copper=2_000, jail_minutes=60)

    w.schedule_appointment(
        "player", "rena", "blumund", w.now + 180,
        grace_minutes=30, purpose="meet after training"
    )
    w.schedule_canon_event(
        "jura_orc_movement",
        "jura_edge",
        w.now + 360,
        {"kind": "organized_orc_movement", "severity": 72},
        significance=82,
        spread_mode="courier",
    )

    w.remember(
        "player",
        "departure_contract",
        "A signed travel commitment has a fixed departure time.",
        salience=90,
        emotional=15,
    )
    w.event("world_v04_seeded", region="blumund", significance=15, payload={"version": "0.4"})
    w.db.commit()
    return w


if __name__ == "__main__":
    import argparse, json
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="v04_demo.db")
    a = p.parse_args()
    with seed_world_v04(a.db) as w:
        print(json.dumps(w.build_context(), ensure_ascii=False, indent=2))
