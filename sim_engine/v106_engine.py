from v105_engine import WorldV105
from v106_runtime import V106RuntimeMixin
from v106_schemafix import V106ProductionSchemaMixin


class WorldV106(V106ProductionSchemaMixin, V106RuntimeMixin, WorldV105):
    """v1.0.6: intent grounding repair for safe named targets and robust known-local travel."""
    pass
