from pathlib import Path

from v08_seed import seed_world_v08_lab, seed_world_v08_migration
from v09_engine import WorldV09


def _upgrade(base, db_path):
    root = Path(__file__).resolve().parent
    base.db.executescript((root / "v09_schema.sql").read_text(encoding="utf-8"))
    base.db.commit()
    base.close()
    return WorldV09(db_path)


def seed_world_v09_migration(db_path):
    return _upgrade(seed_world_v08_migration(db_path), db_path)


def seed_world_v09_lab(db_path):
    return _upgrade(seed_world_v08_lab(db_path), db_path)
