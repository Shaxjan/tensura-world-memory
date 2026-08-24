from v10_engine import WorldV10
from v100_runtime import V100RuntimeMixin


class WorldV100(V100RuntimeMixin, WorldV10):
    """v1.0: typed scene resolution + append-only replayable authoritative runtime."""
    pass
