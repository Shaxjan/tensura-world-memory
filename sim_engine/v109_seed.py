from v108_seed import seed_world_v108_lab, seed_world_v108_migration
from v109_engine import WorldV109


def _upgrade(base, db_path):
    base.db.commit()
    base.close()
    return WorldV109(db_path)


def seed_world_v109_migration(db_path):
    return _upgrade(seed_world_v108_migration(db_path), db_path)


def seed_world_v109_lab(db_path):
    return _upgrade(seed_world_v108_lab(db_path), db_path)
