from v02_autonomy import AutonomyMixin
from v02_planning import PlanningMixin
from v02_social import SocialMixin
from v02_base import BaseWorld, format_money, format_world_minute


class SimulationV02(AutonomyMixin, PlanningMixin, SocialMixin, BaseWorld):
    pass
