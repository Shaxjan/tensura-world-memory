from v06_engine import WorldV06

class WorldV07(WorldV06):
    """v0.7: source-grounded cutover baselines and explicit calibration debt."""

    def build_gm_packet(self, player_id: str="player"):
        packet=super().build_gm_packet(player_id)
        claims=[]
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='actor_position_claims'").fetchone():
            region=str(self.actor(player_id)["region_id"])
            claims=[
                {"actor":str(r["actor_key"]),"name":str(r["display_name"]),"precision":str(r["precision"]),"status":str(r["status"])}
                for r in self.db.execute(
                    "SELECT actor_key,display_name,precision,status FROM actor_position_claims WHERE region_id=? ORDER BY actor_key LIMIT 12",
                    (region,)
                )
            ]
        packet["perceivable"]["position_claims"]=claims
        packet["constraints"]["baseline_authority"]="Imported history and prospective mechanics are separate; mechanical calibration is never retroactive canon."
        return packet
