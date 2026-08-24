from v111_seed import seed_world_v111_lab, seed_world_v111_migration
from v112_engine import WorldV112


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV112(db_path)


def seed_world_v112_migration(db_path):
    return _upgrade(seed_world_v111_migration(db_path), db_path)


def seed_world_v112_lab(db_path):
    return _upgrade(seed_world_v111_lab(db_path), db_path)
