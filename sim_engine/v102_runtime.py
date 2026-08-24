from __future__ import annotations

from typing import Any

ENGINE_VERSION_V102 = "1.0.2"
PERSONAL_ELSEWHERE_ACCOUNTS = {
    "vern_instrument_float": {"label": "у Верна", "description": "доверенные деньги на инструменты"},
}


def format_copper_v102(value: int | None) -> str:
    if value is None:
        return "UNKNOWN"
    value = int(value)
    g, rem = divmod(value, 10000)
    s, c = divmod(rem, 100)
    if g:
        return f"{g}g {s:02d}s {c:02d}c"
    if s:
        return f"{s}s {c:02d}c"
    return f"{c}c"


def format_world_minute_v102(world_minute: int) -> str:
    day, minute_of_day = divmod(int(world_minute), 1440)
    hour, minute = divmod(minute_of_day, 60)
    return f"T+{day} ~{hour:02d}:{minute:02d}"


class V102RuntimeMixin:
    """v1.0.2 compact live HUD/read model for the GM."""

    def _location_hud_v102(self, player_id: str) -> dict[str, Any]:
        actor = self.actor(player_id)
        region_id = str(actor["region_id"])
        region = self.db.execute("SELECT name FROM regions WHERE id=?", (region_id,)).fetchone()
        region_name = str(region[0]) if region else region_id
        row = self.db.execute(
            "SELECT place_text,certainty,source_path FROM scene_local_state WHERE actor_id=?", (player_id,)
        ).fetchone()
        place = str(row["place_text"]) if row and row["place_text"] is not None else None
        return {
            "region_id": region_id,
            "region": region_name,
            "place": place,
            "display": place or region_name,
            "certainty": str(row["certainty"]) if row else "region_only",
            "source": str(row["source_path"]) if row else "actors.region_id",
        }

    def _personal_elsewhere_v102(self) -> list[dict[str, Any]]:
        if not self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='financial_account_state'"
        ).fetchone():
            return []
        out = []
        for account_id, meta in PERSONAL_ELSEWHERE_ACCOUNTS.items():
            row = self.db.execute(
                "SELECT * FROM financial_account_state WHERE account_id=?", (account_id,)
            ).fetchone()
            if row is None:
                continue
            balance = int(row["balance_copper"]) if row["balance_copper"] is not None else None
            principal = int(row["known_principal_copper"]) if row["known_principal_copper"] is not None else None
            item = {
                "account_id": account_id,
                "where": meta["label"],
                "description": meta["description"],
                "balance_copper": balance,
                "balance_display": format_copper_v102(balance),
                "known_principal_copper": principal,
                "known_principal_display": format_copper_v102(principal) if principal is not None else None,
                "certainty": str(row["certainty"]),
                "status": str(row["status"]),
            }
            item["display"] = (
                f'{meta["label"]}: остаток UNKNOWN (из переданных {format_copper_v102(principal)})'
                if balance is None and principal is not None else f'{meta["label"]}: {format_copper_v102(balance)}'
            )
            out.append(item)
        return out

    def build_hud_v102(self, player_id: str = "player") -> dict[str, Any]:
        actor = self.actor(player_id)
        cash = int(actor["cash_copper"])
        elsewhere = self._personal_elsewhere_v102()
        return {
            "time": {"world_minute": int(self.now), "display": format_world_minute_v102(self.now)},
            "location": self._location_hud_v102(player_id),
            "money": {
                "on_person_copper": cash,
                "on_person_display": format_copper_v102(cash),
                "elsewhere": elsewhere,
                "elsewhere_display": "; ".join(str(x["display"]) for x in elsewhere)
                if elsewhere else "Нет подтверждённых личных денег вне кошелька",
                "excludes": ["family funds", "project funds", "promo funds", "earmarked gifts/expenses", "payables"],
            },
        }

    def build_gm_packet(self, player_id: str = "player"):
        base = super().build_gm_packet(player_id)
        perceivable = base.get("perceivable") or {}
        bridge = base.get("scene_bridge") or {}
        known = base.get("known") or {}
        return {
            "hud": self.build_hud_v102(player_id),
            "scene": {
                "visible_actors": list(perceivable.get("actors") or [])[:12],
                "visible_events": list(perceivable.get("events") or [])[-8:],
                "position_claims": list(perceivable.get("position_claims") or [])[:12],
                "recent_player_actions": list(bridge.get("recent_player_actions") or [])[-6:],
                "pending_resolutions": list(bridge.get("unresolved_resolutions") or bridge.get("pending_resolutions") or [])[:8],
            },
            "player_known": {
                "facts": list(known.get("facts") or [])[-12:],
                "memories": list(known.get("memories") or [])[-12:],
            },
            "constraints": {
                "unknown_policy": "UNKNOWN stays UNKNOWN; do not infer hidden state.",
                "player_control": "Narrator may not choose Arlequino dialogue, feelings, decisions or significant actions.",
                "state_authority": "Only engine results may change authoritative world state.",
                "hud_required": "Every ordinary game reply must visibly show time, current location, money on person, and personal money elsewhere. Never merge family/project funds into personal money.",
                "technical_noise": "Do not show journal_seq, hashes, engine mode or migration diagnostics during normal play unless there is an error or the user asks.",
            },
            "runtime": {"engine": ENGINE_VERSION_V102},
        }

    def build_session_state_v102(self, *, journal_seq: int, head_state_hash: str, last_event: dict[str, Any] | None = None) -> dict[str, Any]:
        last_turn = None
        if isinstance(last_event, dict):
            public = last_event.get("result") if isinstance(last_event.get("result"), dict) else {}
            packet = public.get("gm_packet") if isinstance(public.get("gm_packet"), dict) else {}
            if "hud" not in packet:
                packet = self.build_gm_packet("player")
            last_turn = {
                "seq": int(last_event.get("seq") or journal_seq),
                "event_key": last_event.get("event_key"),
                "event_type": last_event.get("event_type"),
                "status": public.get("status"),
                "action_result": public.get("result") if isinstance(public.get("result"), dict) else None,
                "visible_actors": list((packet.get("scene") or {}).get("visible_actors") or []),
                "pending_resolutions": list((packet.get("scene") or {}).get("pending_resolutions") or []),
                "narration_contract": public.get("narration_contract"),
            }
        return {
            "format": "TENSURA_SESSION_STATE",
            "schema_version": 1,
            "engine_version": ENGINE_VERSION_V102,
            "journal_seq": int(journal_seq),
            "head_state_hash": str(head_state_hash),
            "hud": self.build_hud_v102("player"),
            "last_turn": last_turn,
            "display_contract": {
                "always_show": ["hud.time.display", "hud.location.display", "hud.money.on_person_display", "hud.money.elsewhere_display"],
                "normal_play_technical_fields_hidden": True,
                "recommended_header": "Время: {time} | Место: {location} | При мне: {on_person} | Мои деньги вне кошелька: {elsewhere}",
            },
        }
