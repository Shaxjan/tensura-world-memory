from v104_seed import seed_world_v104_lab, seed_world_v104_migration
from v105_engine import WorldV105


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV105(db_path)


def seed_world_v105_migration(db_path):
    return _upgrade(seed_world_v104_migration(db_path), db_path)


def seed_world_v105_lab(db_path):
    return _upgrade(seed_world_v104_lab(db_path), db_path)
