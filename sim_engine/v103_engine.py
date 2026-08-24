from v102_engine import WorldV102
from v103_runtime import V103RuntimeMixin
from v103_schemafix import V103ProductionSchemaMixin


class WorldV103(V103ProductionSchemaMixin, V103RuntimeMixin, WorldV102):
    """v1.0.3: persistent causal living scenes + finite local named-NPC search."""
    pass
