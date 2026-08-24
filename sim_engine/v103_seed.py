from v102_seed import seed_world_v102_lab, seed_world_v102_migration
from v103_engine import WorldV103


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV103(db_path)


def seed_world_v103_migration(db_path):
    return _upgrade(seed_world_v102_migration(db_path), db_path)


def seed_world_v103_lab(db_path):
    return _upgrade(seed_world_v102_lab(db_path), db_path)
