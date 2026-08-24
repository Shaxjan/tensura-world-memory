from v100_engine import WorldV100
from v101_runtime import V101RuntimeMixin


class WorldV101(V101RuntimeMixin, WorldV100):
    """v1.0.1: live-stability hotfix over the v1.0 authoritative runtime."""
    pass
