from v107_seed import seed_world_v107_lab, seed_world_v107_migration
from v108_engine import WorldV108


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV108(db_path)


def seed_world_v108_migration(db_path):
    return _upgrade(seed_world_v107_migration(db_path), db_path)


def seed_world_v108_lab(db_path):
    return _upgrade(seed_world_v107_lab(db_path), db_path)
