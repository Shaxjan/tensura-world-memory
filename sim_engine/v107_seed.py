from v106_seed import seed_world_v106_lab, seed_world_v106_migration
from v107_engine import WorldV107


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV107(db_path)


def seed_world_v107_migration(db_path):
    return _upgrade(seed_world_v106_migration(db_path), db_path)


def seed_world_v107_lab(db_path):
    return _upgrade(seed_world_v106_lab(db_path), db_path)
