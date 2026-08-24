from __future__ import annotations

from v03_engine import loads


class V106ProductionSchemaMixin:
    """Production schema adapter for v1.0.6 player-known lead lookup."""

    def _known_player_lead_v106(self, destination_key: str) -> bool:
        rows = self.db.execute(
            "SELECT f.value_json FROM actor_knowledge k JOIN facts f ON f.key=k.fact_key "
            "WHERE k.actor_id='player' ORDER BY k.learned_at DESC LIMIT 24"
        ).fetchall()
        for row in rows:
            value = loads(row[0], {})
            if isinstance(value, dict) and isinstance(value.get("lead"), dict):
                if value["lead"].get("destination_key") == destination_key:
                    return True
        return False
