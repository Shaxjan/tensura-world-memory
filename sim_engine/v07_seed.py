from pathlib import Path
from v06_seed import seed_world_v06_migration, seed_world_v06_lab
from v07_engine import WorldV07


def seed_world_v07_migration(db_path):
    root=Path(__file__).resolve().parent
    base=seed_world_v06_migration(db_path)
    base.db.executescript((root/"v07_schema.sql").read_text(encoding="utf-8"))
    # Commodity prices/catalog in v0.3 were laboratory data too. Do not leak them.
    base.db.execute("DELETE FROM actor_inventory")
    base.db.execute("DELETE FROM commodities")
    base.db.commit(); base.close()
    return WorldV07(db_path)


def seed_world_v07_lab(db_path):
    root=Path(__file__).resolve().parent
    base=seed_world_v06_lab(db_path)
    base.db.executescript((root/"v07_schema.sql").read_text(encoding="utf-8"))
    base.db.commit(); base.close()
    return WorldV07(db_path)
