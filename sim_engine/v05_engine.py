from v04_engine import WorldV04
from v05_intent import IntentGroundingMixin
from v05_power import TensuraPowerHealingMixin
from v05_society import WitnessRelationshipRoutineMixin
from v05_bridge import V05CommandClockContextImportMixin


class WorldV05(
    V05CommandClockContextImportMixin,
    IntentGroundingMixin,
    WitnessRelationshipRoutineMixin,
    TensuraPowerHealingMixin,
    WorldV04,
):
    """v0.5: grounded intents, Tensura-facing power layer, named evidence, relationships, routines, GM packets and import audit."""
    pass
