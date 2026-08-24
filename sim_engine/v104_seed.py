from v103_seed import seed_world_v103_lab, seed_world_v103_migration
from v104_engine import WorldV104


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV104(db_path)


def seed_world_v104_migration(db_path):
    return _upgrade(seed_world_v103_migration(db_path), db_path)


def seed_world_v104_lab(db_path):
    return _upgrade(seed_world_v103_lab(db_path), db_path)
