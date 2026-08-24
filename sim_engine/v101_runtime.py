from __future__ import annotations

import re
from typing import Any

from v03_engine import dumps, loads


LOCAL_TRAVEL_DEFAULT_MINUTES = 12

# Source-grounded aliases from memory/places.json. These are place identities only;
# travel duration is prospective mechanical calibration, not historical canon.
EURAZANIA_PLACES = {
    "eurazania_borga_big_training_yard": {
        "name": "большой тренировочный двор Борги",
        "aliases": ("большой тренировочный двор", "двор Борги", "тренировочный двор Борги"),
        "source": "memory/places.json",
    },
    "eurazania_small_training_yard": {
        "name": "малый боевой/тренировочный двор",
        "aliases": ("малый тренировочный двор", "малый боевой двор", "малый боевой тренировочный двор"),
        "source": "memory/places.json",
    },
    "eurazania_west_training_field": {
        "name": "западное тренировочное поле",
        "aliases": ("западное тренировочное поле", "западный тренировочный двор"),
        "source": "memory/places.json",
    },
    "eurazania_carrion_palace": {
        "name": "дворец Кариона",
        "aliases": ("дворец Кариона", "ко дворцу Кариона", "в дворец Кариона"),
        "source": "memory/places.json",
    },
    "eurazania_trade_street": {
        "name": "торговая улица",
        "aliases": ("торговая улица", "на торговую улицу"),
        "source": "memory/places.json",
    },
    "eurazania_evening_market_square": {
        "name": "вечерняя рыночная площадь",
        "aliases": ("вечерняя рыночная площадь", "рыночная площадь"),
        "source": "memory/places.json",
    },
    "eurazania_hotel_district": {
        "name": "район гостиниц / post-yards",
        "aliases": ("район гостиниц", "гостиничный район"),
        "source": "memory/places.json",
    },
}


def _norm(text: str | None) -> str:
    s = (text or "").casefold().replace("ё", "е")
    s = re.sub(r"[^a-zа-я0-9]+", " ", s)
    return " ".join(s.split())


class V101RuntimeMixin:
    """v1.0.1 live-stability hotfix.

    Known local destinations are finite engine actions, not indefinite pending
    resolutions. Unknown destinations remain guarded by the v1.0 bridge.
    """

    def _current_local_text_v101(self, player_id: str) -> str | None:
        row = self.db.execute(
            "SELECT place_text FROM scene_local_state WHERE actor_id=?", (player_id,)
        ).fetchone()
        return str(row[0]) if row and row[0] is not None else None

    def _match_known_local_place_v101(self, player_id: str, raw_text: str) -> dict[str, Any] | None:
        actor = self.actor(player_id)
        if str(actor["region_id"]) != "eurazania":
            return None
        low = _norm(raw_text)
        if not any(stem in low for stem in ("иду", "пойду", "направля", "возвращ", "ухожу", "подхожу")):
            return None

        matches: list[tuple[str, dict[str, Any]]] = []
        for key, place in EURAZANIA_PLACES.items():
            if any(_norm(alias) in low for alias in place["aliases"]):
                matches.append((key, place))
        if len(matches) == 1:
            key, place = matches[0]
            return {"key": key, **place, "match_basis": "explicit_canonical_alias"}
        if len(matches) > 1:
            return None

        # Hotfix for the exact live continuity bug: v159 says Arlequino leaves
        # lodging heading to Borga. In that context a bare "training yard"
        # resolves to the canonically named big training yard of Borga. This
        # does NOT assert Borga's instantaneous presence there.
        if "тренировочн" in low and "двор" in low:
            current = _norm(self._current_local_text_v101(player_id))
            if "borga" in current or "борг" in current:
                place = EURAZANIA_PLACES["eurazania_borga_big_training_yard"]
                return {
                    "key": "eurazania_borga_big_training_yard",
                    **place,
                    "match_basis": "saved_v159_borga_destination_context",
                }
        return None

    def _existing_equivalent_pending_v101(self, player_id: str, raw_text: str) -> dict[str, Any] | None:
        target = _norm(raw_text)
        rows = self.db.execute(
            "SELECT p.id,p.target_text,a.turn_key FROM scene_pending_resolution p "
            "JOIN scene_actions a ON a.id=p.scene_action_id "
            "WHERE a.actor_id=? AND p.status IN ('pending','deferred') AND p.resolution_kind='local_navigation' "
            "ORDER BY p.id DESC LIMIT 8",
            (player_id,),
        ).fetchall()
        for row in rows:
            if _norm(row["target_text"]) == target:
                return {"pending_id": int(row["id"]), "turn_key": str(row["turn_key"]), "target_text": row["target_text"]}
        return None

    def _execute_known_local_travel_v101(self, turn_key: str, raw_text: str, player_id: str,
                                         destination: dict[str, Any]) -> dict[str, Any]:
        old = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if old is not None:
            return self._load_turn_public(old, replayed=True)

        origin = self._current_local_text_v101(player_id)
        already_there = _norm(destination["name"]) in _norm(origin)
        minutes = 0 if already_there else LOCAL_TRAVEL_DEFAULT_MINUTES
        start_minute = int(self.now)

        cur = self.db.execute(
            "INSERT INTO gm_turns(turn_key,player_id,raw_text,status,created_at) VALUES(?,?,?,?,?)",
            (turn_key, player_id, str(raw_text), "received", self.now),
        )
        turn_id = int(cur.lastrowid)
        action_cur = self.db.execute(
            "INSERT INTO scene_actions(turn_key,world_minute,actor_id,action_kind,raw_text,components_json,resolution_mode,status,effect_json,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                turn_key, self.now, player_id, "local_travel", str(raw_text),
                dumps([{
                    "kind": "local_travel",
                    "destination_key": destination["key"],
                    "destination_text": destination["name"],
                    "source": destination["source"],
                    "match_basis": destination["match_basis"],
                    "travel_minutes": minutes,
                }]),
                "engine_resolved_local_travel", "in_progress", "{}", self.now,
            ),
        )
        action_id = int(action_cur.lastrowid)
        self.db.commit()

        if minutes:
            self.advance(minutes)
        self.db.execute(
            "INSERT OR REPLACE INTO scene_local_state(actor_id,place_text,certainty,source_path,updated_at) VALUES(?,?,?,?,?)",
            (player_id, destination["name"], "prospective_engine_arrival", destination["source"], self.now),
        )
        effect = {
            "outcome": "already_at_destination" if already_there else "arrived",
            "origin_text": origin,
            "destination_key": destination["key"],
            "destination_text": destination["name"],
            "travel_minutes": minutes,
            "started_at": start_minute,
            "arrived_at": int(self.now),
            "place_source": destination["source"],
            "time_basis": "prospective_local_city_default_v1.0.1" if minutes else "same_place_no_time_advance",
            "does_not_assert": ["Borga presence", "NPC encounter", "exact street geometry"],
        }
        self.db.execute(
            "UPDATE scene_actions SET status='resolved',effect_json=? WHERE id=?",
            (dumps(effect), action_id),
        )
        self.db.commit()
        checkpoint = self.write_checkpoint(player_id, turn_id=turn_id, kind="v101_local_travel")
        packet = self.build_gm_packet(player_id)
        contract = {
            "state_authority": "engine_v1.0.1_local_travel",
            "player_text_verbatim": str(raw_text),
            "must_preserve": ["arrival", "engine travel time", "money/region from GM packet", "UNKNOWN NPC presence"],
            "may_add": ["sensory description consistent with destination and visible state"],
            "forbidden": ["invent Borga presence", "invent payment", "invent encounter", "change player intent"],
        }
        public = {
            "status": "executed",
            "accepted": True,
            "turn_key": turn_key,
            "scene_action_id": action_id,
            "result": effect,
            "gm_packet": packet,
            "narration_contract": contract,
            "checkpoint": checkpoint,
        }
        self.db.execute(
            "UPDATE gm_turns SET status='executed',proposal_json=?,validation_json=?,engine_result_json=?,gm_packet_json=?,"
            "narration_contract_json=?,checkpoint_hash=?,public_result_json=?,completed_at=? WHERE id=?",
            (
                dumps({"action_kind": "local_travel", "destination": destination}),
                dumps({"valid": True, "reason": "v101_known_local_destination"}),
                dumps(effect), dumps(packet), dumps(contract), checkpoint["state_hash"], dumps(public), self.now, turn_id,
            ),
        )
        self.db.commit()
        return public

    def process_player_turn(self, turn_key: str, raw_text: str, *, player_id: str = "player",
                            external_intent: dict[str, Any] | None = None):
        old = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if old is not None:
            return self._load_turn_public(old, replayed=True)

        destination = self._match_known_local_place_v101(player_id, raw_text)
        if destination is not None:
            if external_intent is not None:
                return {
                    "status": "needs_clarification", "accepted": False,
                    "reason": "external_intent_not_needed_for_known_local_travel", "turn_key": turn_key,
                }
            return self._execute_known_local_travel_v101(turn_key, raw_text, player_id, destination)

        existing = self._existing_equivalent_pending_v101(player_id, raw_text)
        if existing is not None:
            # A repeated command must not spawn an identical unresolved action.
            return {
                "status": "scene_pending", "accepted": True, "turn_key": turn_key,
                "reused_pending": True, "pending_id": existing["pending_id"],
                "original_turn_key": existing["turn_key"], "target_text": existing["target_text"],
                "gm_packet": self.build_gm_packet(player_id),
            }
        return super().process_player_turn(turn_key, raw_text, player_id=player_id, external_intent=external_intent)
