from pathlib import Path

from v03_seed import seed_world
from v05_seed import seed_world_v05
from v06_engine import WorldV06


def seed_world_v06_lab(db_path):
    root = Path(__file__).resolve().parent
    base = seed_world_v05(db_path)
    base.db.executescript((root / "v06_schema.sql").read_text(encoding="utf-8"))
    base.db.commit(); base.close()
    return WorldV06(db_path)


def seed_world_v06_migration(db_path):
    """Regional identifiers/schema only: no lab world state becomes campaign truth."""
    root = Path(__file__).resolve().parent
    base = seed_world(db_path)
    base.db.executescript((root / "v04_schema.sql").read_text(encoding="utf-8"))
    base.db.executescript((root / "v05_schema.sql").read_text(encoding="utf-8"))
    base.db.executescript((root / "v06_schema.sql").read_text(encoding="utf-8"))

    # v0.3 provides compatible region identifiers/schema, but its economy, routes,
    # factions, population pressure and events are laboratory data. Purge them so
    # the rehearsal cannot present synthetic values as migrated campaign truth.
    base.db.execute("DELETE FROM events")
    base.db.execute("DELETE FROM caravans")
    base.db.execute("DELETE FROM info_packets")
    base.db.execute("DELETE FROM faction_goals")
    base.db.execute("DELETE FROM factions")
    base.db.execute("DELETE FROM population_groups")
    base.db.execute("DELETE FROM markets")
    base.db.execute("DELETE FROM routes")
    base.db.execute(
        "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
        ("runtime_mode", '"migration_rehearsal"', "engine:v06_seed"),
    )
    base.db.commit(); base.close()
    return WorldV06(db_path)
