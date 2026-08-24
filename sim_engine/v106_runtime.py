from __future__ import annotations

import re
from typing import Any

from v03_engine import dumps, loads
from v100_handoff import runtime_state_hash_v100
from v101_runtime import EURAZANIA_PLACES, _norm

ENGINE_VERSION_V106 = "1.0.6"
BAD_TURN_KEY_V106 = "chat-20260824-go-small-training-yard-r000006"


def _tokens_v106(text: str) -> set[str]:
    return set(re.findall(r"[a-zа-я0-9]+", _norm(text)))


def _single_name_forms_v106(name: str) -> set[str]:
    word = _norm(name)
    if not word or " " in word:
        return {word} if word else set()
    forms = {word}
    if word.endswith("а") and len(word) > 2:
        stem = word[:-1]
        forms |= {stem + s for s in ("а", "ы", "е", "у", "ой", "ою")}
    elif word.endswith("я") and len(word) > 2:
        stem = word[:-1]
        forms |= {stem + s for s in ("я", "и", "е", "ю", "ей", "ею")}
    return forms


class V106RuntimeMixin:
    """v1.0.6: repair false named-target grounding and robust known-local travel parsing."""

    def _safe_named_mentions_v106(self, text: str) -> list[dict[str, str]]:
        low = _norm(text)
        tokens = _tokens_v106(text)
        rows = self.db.execute(
            "SELECT actor_key,display_name FROM actor_position_claims ORDER BY LENGTH(display_name) DESC"
        ).fetchall()
        out: list[dict[str, str]] = []
        for row in rows:
            key, name = str(row["actor_key"]), str(row["display_name"])
            n = _norm(name)
            matched = False
            if " " in n:
                matched = bool(re.search(r"(?:^| )" + re.escape(n) + r"(?: |$)", low))
            else:
                matched = bool(tokens & _single_name_forms_v106(name))
            if matched:
                out.append({"id": key, "name": name})
        return out

    def _known_player_lead_v106(self, destination_key: str) -> bool:
        rows = self.db.execute(
            "SELECT f.value_json FROM knowledge k JOIN facts f ON f.key=k.fact_key "
            "WHERE k.actor_id='player' ORDER BY k.learned_at DESC LIMIT 24"
        ).fetchall()
        for row in rows:
            value = loads(row[0], {})
            if isinstance(value, dict) and isinstance(value.get("lead"), dict):
                if value["lead"].get("destination_key") == destination_key:
                    return True
        return False

    def _match_known_local_place_v101(self, player_id: str, raw_text: str) -> dict[str, Any] | None:
        direct = super()._match_known_local_place_v101(player_id, raw_text)
        if direct is not None:
            return direct
        if str(self.actor(player_id)["region_id"]) != "eurazania":
            return None
        low = _norm(raw_text)
        tokens = _tokens_v106(raw_text)
        moving = any(stem in low for stem in ("иду", "пойду", "направля", "возвращ", "ухожу", "подхожу")) or bool(tokens & {"илу", "йду"})
        if not moving:
            return None

        matches: list[tuple[str, dict[str, Any]]] = []
        for key, place in EURAZANIA_PLACES.items():
            if any(_norm(alias) in low for alias in place["aliases"]):
                matches.append((key, place))
        if len(matches) == 1:
            key, place = matches[0]
            return {"key": key, **place, "match_basis": "v106_typo_tolerant_canonical_alias"}
        if len(matches) > 1:
            return None

        small = "eurazania_small_training_yard"
        if (
            self._known_player_lead_v106(small)
            and "мал" in low
            and "тренировоч" in low
            and any(x in low for x in ("лагер", "двор", "площад"))
        ):
            place = EURAZANIA_PLACES[small]
            return {"key": small, **place, "match_basis": "v106_causal_known_lead_lexical_repair"}
        return None

    def propose_scene_action(self, player_id: str, raw_text: str) -> dict[str, Any]:
        proposal = super().propose_scene_action(player_id, raw_text)
        if not isinstance(proposal, dict) or proposal.get("status") != "ready":
            return proposal
        safe = {x["id"]: x for x in self._safe_named_mentions_v106(raw_text)}
        cleaned_pending = []
        for p in list(proposal.get("pending") or []):
            row = dict(p)
            target_key = row.get("target_key")
            if target_key and target_key not in safe:
                row["target_key"] = None
                row["target_text"] = None
                row["grounding_repair"] = "v106_removed_unmentioned_named_target"
            cleaned_pending.append(row)
        proposal = dict(proposal)
        proposal["pending"] = cleaned_pending
        components = []
        for c in list(proposal.get("components") or []):
            row = dict(c)
            target = row.get("target")
            if isinstance(target, dict) and target.get("id") not in safe:
                row["target"] = None
            components.append(row)
        proposal["components"] = components
        return proposal

    def _repair_bad_pending_v106(self) -> dict[str, Any]:
        turn = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (BAD_TURN_KEY_V106,)).fetchone()
        if turn is None:
            return {"status": "not_present", "turn_key": BAD_TURN_KEY_V106}
        raw = str(turn["raw_text"])
        if any(x["id"] == "rena" for x in self._safe_named_mentions_v106(raw)):
            raise RuntimeError("repair guard failed: Rena is actually mentioned in source turn")
        action = self.db.execute("SELECT * FROM scene_actions WHERE turn_key=?", (BAD_TURN_KEY_V106,)).fetchone()
        if action is None:
            return {"status": "no_scene_action", "turn_key": BAD_TURN_KEY_V106}
        rows = self.db.execute(
            "SELECT * FROM scene_pending_resolution WHERE scene_action_id=? AND status='pending' ORDER BY id",
            (int(action["id"]),),
        ).fetchall()
        repaired = []
        for row in rows:
            if str(row["target_key"] or "") == "rena":
                self.db.execute(
                    "UPDATE scene_pending_resolution SET status='cancelled_parser_false_positive',resolved_at=? WHERE id=?",
                    (self.now, int(row["id"])),
                )
                repaired.append(int(row["id"]))
        if repaired:
            self.db.execute(
                "UPDATE scene_actions SET status='superseded_parser_repair',effect_json=? WHERE id=?",
                (dumps({"outcome":"no_effect","reason":"v106_false_named_target_repair","time_advanced":0}), int(action["id"])),
            )
            self.db.execute(
                "UPDATE gm_turns SET status='superseded_parser_repair',completed_at=? WHERE turn_key=?",
                (self.now, BAD_TURN_KEY_V106),
            )
        self.db.commit()
        return {
            "status": "repaired" if repaired else "nothing_to_repair",
            "turn_key": BAD_TURN_KEY_V106,
            "cancelled_pending_ids": repaired,
            "time_advanced": 0,
            "player_choice": False,
            "original_action_executed": False,
        }

    def activate_intent_grounding_repair_v106(self) -> dict[str, Any]:
        start = int(self.now)
        repair = self._repair_bad_pending_v106()
        if int(self.now) != start:
            raise RuntimeError("intent grounding repair activation advanced world time")
        return {
            "status": "executed",
            "accepted": True,
            "activation": "intent_grounding_repair_v106",
            "world_minute": int(self.now),
            "repair": repair,
            "time_advanced": 0,
            "player_choice": False,
            "does_not_assert": ["movement success", "new player action", "Rena involvement"],
        }

    def build_gm_packet(self, player_id="player"):
        base = super().build_gm_packet(player_id)
        base.setdefault("constraints", {})["intent_grounding"] = (
            "Named targets require explicit token/inflection grounding. Substring collisions inside unrelated words are forbidden."
        )
        base["runtime"] = {"engine": ENGINE_VERSION_V106}
        return base

    def _repaired_last_turn_v106(self, old_last_turn: dict[str, Any] | None, activation_result: dict[str, Any] | None):
        if not isinstance(old_last_turn, dict) or old_last_turn.get("event_key") != BAD_TURN_KEY_V106:
            return old_last_turn
        repair = (activation_result or {}).get("repair") or {}
        if repair.get("status") != "repaired":
            return old_last_turn
        out = dict(old_last_turn)
        out["status"] = "superseded_parser_repair"
        out["action_result"] = {
            "outcome": "no_effect_parser_repaired",
            "time_advanced": 0,
            "movement_executed": False,
            "false_target_removed": "rena",
        }
        out["pending_resolutions"] = []
        out["narration_contract"] = {
            "state_authority": "engine_v1.0.6_parser_repair",
            "player_text_verbatim": str((old_last_turn.get("narration_contract") or {}).get("player_text_verbatim") or ""),
            "must_preserve": ["old malformed turn had no movement effect", "false Rena pending is cancelled"],
            "forbidden": ["pretend travel already happened", "restore false Rena target"],
        }
        return out

    def build_session_state_v106(self, *, journal_seq: int, head_state_hash: str, last_event=None, preserved_last_turn=None):
        activation_result = (last_event or {}).get("result") if isinstance(last_event, dict) else None
        repaired_last = self._repaired_last_turn_v106(preserved_last_turn, activation_result)
        state = super().build_session_state_v105(
            journal_seq=journal_seq,
            head_state_hash=head_state_hash,
            last_event=None if (last_event or {}).get("event_type") == "intent_grounding_repair_activation" else last_event,
            preserved_last_turn=repaired_last,
        )
        state["engine_version"] = ENGINE_VERSION_V106
        state["parser_runtime"] = {
            "version": "intent_grounding_v1",
            "safe_named_target_tokens": True,
            "known_local_typo_repair": True,
            "false_pending_repair": True,
        }
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type != "intent_grounding_repair_activation":
            return super().execute_runtime_event(seq, event_key, event_type, request)
        old = self.db.execute("SELECT * FROM runtime_journal WHERE event_key=? OR seq=?", (event_key, int(seq))).fetchone()
        if old:
            if str(old["event_key"]) != event_key or int(old["seq"]) != int(seq):
                raise RuntimeError("journal sequence collision")
            return {"accepted": True, "replayed": True, "journal": self.export_runtime_journal_entry(event_key)}
        source_v = self._source_live_version_v100()
        before = runtime_state_hash_v100(self, source_v)
        result = self.activate_intent_grounding_repair_v106()
        after = runtime_state_hash_v100(self, source_v)
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before, after, self.now),
        )
        self.db.commit()
        return {"accepted": True, "replayed": False, "result": result, "journal": self.export_runtime_journal_entry(event_key)}
