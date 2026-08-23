from v07_engine import WorldV07


class WorldV08(WorldV07):
    """v0.8: exact money-boundary reconciliation without guessing unknown float balances."""

    def build_gm_packet(self, player_id: str = "player"):
        packet = super().build_gm_packet(player_id)
        accounts = []
        if self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='financial_account_state'"
        ).fetchone():
            for r in self.db.execute(
                "SELECT account_id,account_type,balance_copper,known_principal_copper,certainty,status "
                "FROM financial_account_state ORDER BY account_id"
            ):
                accounts.append({
                    "account": str(r["account_id"]),
                    "type": str(r["account_type"]),
                    "balance_copper": int(r["balance_copper"]) if r["balance_copper"] is not None else "UNKNOWN",
                    "known_principal_copper": int(r["known_principal_copper"]) if r["known_principal_copper"] is not None else None,
                    "certainty": str(r["certainty"]),
                    "status": str(r["status"]),
                })
        packet["known"]["financial_boundaries"] = accounts
        packet["constraints"]["money_authority"] = (
            "Separate accounts never bleed into personal cash. UNKNOWN entrusted balances remain UNKNOWN "
            "until a causal report/settlement exists."
        )
        return packet
