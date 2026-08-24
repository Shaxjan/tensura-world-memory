from v112_seed import seed_world_v112_lab, seed_world_v112_migration
from v113_engine import WorldV113


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV113(db_path)


def seed_world_v113_migration(db_path):
    return _upgrade(seed_world_v112_migration(db_path), db_path)


def seed_world_v113_lab(db_path):
    return _upgrade(seed_world_v112_lab(db_path), db_path)
