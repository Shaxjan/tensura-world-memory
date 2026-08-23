from pathlib import Path

from v09_seed import seed_world_v09_lab, seed_world_v09_migration
from v10_engine import WorldV10


def _upgrade(base, db_path):
    root = Path(__file__).resolve().parent
    base.db.executescript((root / "v10_schema.sql").read_text(encoding="utf-8"))
    base.db.commit()
    base.close()
    return WorldV10(db_path)


def seed_world_v10_migration(db_path):
    return _upgrade(seed_world_v09_migration(db_path), db_path)


def seed_world_v10_lab(db_path):
    return _upgrade(seed_world_v09_lab(db_path), db_path)
