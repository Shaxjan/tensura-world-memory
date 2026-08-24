from v110_seed import seed_world_v110_lab, seed_world_v110_migration
from v111_engine import WorldV111


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV111(db_path)


def seed_world_v111_migration(db_path):
    return _upgrade(seed_world_v110_migration(db_path), db_path)


def seed_world_v111_lab(db_path):
    return _upgrade(seed_world_v110_lab(db_path), db_path)
