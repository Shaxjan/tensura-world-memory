from v105_seed import seed_world_v105_lab, seed_world_v105_migration
from v106_engine import WorldV106


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV106(db_path)


def seed_world_v106_migration(db_path):
    return _upgrade(seed_world_v105_migration(db_path), db_path)


def seed_world_v106_lab(db_path):
    return _upgrade(seed_world_v105_lab(db_path), db_path)
