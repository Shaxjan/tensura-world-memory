from v112_engine import WorldV112
from v113_runtime import V113RuntimeMixin


class WorldV113(V113RuntimeMixin, WorldV112):
    """v1.0.13 candidate: grounded Character Agent runtime bridge; not LIVE.

    Before the explicit v1.0.13 activation event this class must behave exactly
    like WorldV112. Old v1.0.12 journal events may call build_gm_packet while
    replaying, and exposing v1.0.13 metadata before activation would change the
    persisted turn payload and therefore the authoritative state hash.
    """

    def _character_agent_active_v113(self) -> bool:
        return self.character_agent_state_v113("rena") is not None

    def build_gm_packet(self, player_id: str = "player"):
        if not self._character_agent_active_v113():
            return WorldV112.build_gm_packet(self, player_id)
        return super().build_gm_packet(player_id)
