from v08_engine import WorldV08


class WorldV09(WorldV08):
    """v0.9: guarded prospective mechanics + portable runtime handoff."""

    def build_gm_packet(self, player_id: str = "player"):
        packet = super().build_gm_packet(player_id)
        policies = []
        if self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='mechanic_feature_policy'"
        ).fetchone():
            policies = [
                {
                    "feature": str(r["feature"]),
                    "mode": str(r["mode"]),
                    "authority": str(r["authority"]),
                    "status": str(r["status"]),
                    "command": str(r["command"]) if r["command"] is not None else None,
                }
                for r in self.db.execute(
                    "SELECT feature,mode,authority,status,command FROM mechanic_feature_policy ORDER BY feature"
                )
            ]
        gates = []
        if self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cutover_gate'"
        ).fetchone():
            gates = [
                {"code": str(r["gate_code"]), "status": str(r["status"]), "class": str(r["classification"])}
                for r in self.db.execute(
                    "SELECT gate_code,status,classification FROM cutover_gate ORDER BY gate_code"
                )
            ]
        packet["migration"]["mechanic_policy"] = policies
        packet["migration"]["cutover_gates"] = gates
        packet["constraints"]["mechanic_authority"] = (
            "NON_CANON_MECHANICAL values may govern future resolution but must never be narrated as historical canon. "
            "guarded_unknown features stay unavailable until a causal observation or explicit calibration exists."
        )
        return packet
