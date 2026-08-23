from pathlib import Path

from v03_seed import seed_world
from v05_seed import seed_world_v05
from v06_engine import WorldV06


def seed_world_v06_lab(db_path):
    root = Path(__file__).resolve().parent
    base = seed_world_v05(db_path)
    base.db.executescript((root / "v06_schema.sql").read_text(encoding="utf-8"))
    base.db.commit(); base.close()
    return WorldV06(db_path)


def seed_world_v06_migration(db_path):
    """Regional scaffold only: no fake v0.4/v0.5 character/power seed is imported."""
    root = Path(__file__).resolve().parent
    base = seed_world(db_path)
    base.db.executescript((root / "v04_schema.sql").read_text(encoding="utf-8"))
    base.db.executescript((root / "v05_schema.sql").read_text(encoding="utf-8"))
    base.db.executescript((root / "v06_schema.sql").read_text(encoding="utf-8"))
    base.db.commit(); base.close()
    return WorldV06(db_path)
