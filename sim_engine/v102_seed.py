from v101_seed import seed_world_v101_lab, seed_world_v101_migration
from v102_engine import WorldV102


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV102(db_path)


def seed_world_v102_migration(db_path):
    return _upgrade(seed_world_v101_migration(db_path), db_path)


def seed_world_v102_lab(db_path):
    return _upgrade(seed_world_v101_lab(db_path), db_path)
