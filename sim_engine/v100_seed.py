from pathlib import Path

from v10_seed import seed_world_v10_lab, seed_world_v10_migration
from v100_engine import WorldV100


def _upgrade(base, db_path):
    root = Path(__file__).resolve().parent
    base.db.executescript((root / "v100_schema.sql").read_text(encoding="utf-8"))
    base.db.commit()
    base.close()
    return WorldV100(db_path)


def seed_world_v100_migration(db_path):
    return _upgrade(seed_world_v10_migration(db_path), db_path)


def seed_world_v100_lab(db_path):
    return _upgrade(seed_world_v10_lab(db_path), db_path)
