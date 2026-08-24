from v109_seed import seed_world_v109_lab, seed_world_v109_migration
from v110_engine import WorldV110


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV110(db_path)


def seed_world_v110_migration(db_path):
    return _upgrade(seed_world_v109_migration(db_path), db_path)


def seed_world_v110_lab(db_path):
    return _upgrade(seed_world_v109_lab(db_path), db_path)
