from v03_engine import DAY, WorldV03
from v04_checks import SkillsCombatMixin
from v04_law import LawAppointmentsMixin
from v04_memory import MemoryCanonMixin
from v04_commands import CommandTimeContextMixin


class WorldV04(
    CommandTimeContextMixin,
    MemoryCanonMixin,
    LawAppointmentsMixin,
    SkillsCombatMixin,
    WorldV03,
):
    """Simulation Engine v0.4: v0.3 world + validated player-facing rules."""
    pass
