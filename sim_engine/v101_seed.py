from v100_seed import seed_world_v100_lab, seed_world_v100_migration
from v101_engine import WorldV101


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV101(db_path)


def seed_world_v101_migration(db_path):
    return _upgrade(seed_world_v100_migration(db_path), db_path)


def seed_world_v101_lab(db_path):
    return _upgrade(seed_world_v100_lab(db_path), db_path)
