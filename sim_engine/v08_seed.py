from pathlib import Path

from v07_seed import seed_world_v07_lab, seed_world_v07_migration
from v08_engine import WorldV08


def _upgrade(base, db_path):
    root = Path(__file__).resolve().parent
    base.db.executescript((root / "v08_schema.sql").read_text(encoding="utf-8"))
    base.db.commit()
    base.close()
    return WorldV08(db_path)


def seed_world_v08_migration(db_path):
    return _upgrade(seed_world_v07_migration(db_path), db_path)


def seed_world_v08_lab(db_path):
    return _upgrade(seed_world_v07_lab(db_path), db_path)
