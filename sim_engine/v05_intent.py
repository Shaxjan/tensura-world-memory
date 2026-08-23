from __future__ import annotations

import re
from typing import Any

from v03_engine import dumps


class IntentGroundingMixin:
    """Deterministic text -> command proposal. Missing facts remain missing."""

    def _entity_mentions(self, text: str, table: str, id_field: str = "id") -> list[dict[str, str]]:
        low = text.casefold()
        rows = self.db.execute(f"SELECT {id_field} AS id,name FROM {table} ORDER BY LENGTH(name) DESC,id").fetchall()
        found = []
        for r in rows:
            name = str(r["name"])
            rid = str(r["id"])
            if name.casefold() in low or re.search(rf"(?<![\w-]){re.escape(rid.casefold())}(?![\w-])", low):
                found.append({"id": rid, "name": name})
        return found

    def _region_mentions(self, text: str) -> list[dict[str, str]]:
        return self._entity_mentions(text, "regions")

    def _actor_mentions(self, text: str, exclude: str | None = None) -> list[dict[str, str]]:
        rows = self._entity_mentions(text, "actors")
        return [r for r in rows if r["id"] != exclude]

    def _commodity_mentions(self, text: str) -> list[dict[str, str]]:
        return self._entity_mentions(text, "commodities")

    @staticmethod
    def _number_mentions(text: str) -> list[int]:
        return [int(x) for x in re.findall(r"(?<!\d)(\d{1,6})(?!\d)", text)]

    def propose_text_intent(self, actor_id: str, raw_text: str) -> dict[str, Any]:
        text = " ".join(str(raw_text).strip().split())
        low = text.casefold()
        command = None
        params: dict[str, Any] = {}
        missing: list[str] = []
        ambiguities: list[str] = []
        grounding: dict[str, Any] = {}

        travel_words = ("иду", "еду", "отправляюсь", "поеду", "пойду", "ухожу", "уезжаю", "travel", "go to")
        buy_words = ("покупаю", "купить", "купи", "buy")
        attack_words = ("атакую", "ударяю", "бью", "нападаю", "attack")
        social_words = ("убежда", "убед", "уговари", "прошу", "запуг", "обман", "convince", "persuade", "intimidat", "deceiv")
        wait_words = ("жду", "подожду", "wait")
        heal_words = ("лечу", "перевязыва", "исцеля", "оказать помощь", "heal", "first aid")

        if any(w in low for w in travel_words):
            command = "travel"
            hits = self._region_mentions(text)
            if len(hits) == 1:
                params["destination"] = hits[0]["id"]
                grounding["destination"] = hits[0]["name"]
            elif len(hits) == 0:
                missing.append("destination")
            else:
                ambiguities.append("destination:" + ",".join(x["id"] for x in hits))

        elif any(w in low for w in buy_words):
            command = "buy"
            goods = self._commodity_mentions(text)
            nums = self._number_mentions(text)
            if len(goods) == 1:
                params["commodity"] = goods[0]["id"]
                grounding["commodity"] = goods[0]["name"]
            elif not goods:
                missing.append("commodity")
            else:
                ambiguities.append("commodity:" + ",".join(x["id"] for x in goods))
            if len(nums) == 1:
                params["qty"] = nums[0]
                grounding["qty"] = str(nums[0])
            elif not nums:
                missing.append("qty")
            else:
                ambiguities.append("qty:multiple_numbers")

        elif any(w in low for w in attack_words):
            command = "strike"
            targets = self._actor_mentions(text, exclude=actor_id)
            if len(targets) == 1:
                params["target"] = targets[0]["id"]
                grounding["target"] = targets[0]["name"]
            elif not targets:
                missing.append("target")
            else:
                ambiguities.append("target:" + ",".join(x["id"] for x in targets))
            nonlethal = any(w in low for w in ("не убивая", "без убийства", "оглуш", "nonlethal", "knock out"))
            lethal = any(w in low for w in ("убиваю", "насмерть", "смертельн", "lethal", "kill"))
            if nonlethal and lethal:
                ambiguities.append("mode:conflicting_lethality")
            elif nonlethal:
                params["mode"] = "nonlethal"
                grounding["mode"] = "explicit_nonlethal"
            elif lethal:
                params["mode"] = "lethal"
                grounding["mode"] = "explicit_lethal"
            else:
                missing.append("mode")

        elif any(w in low for w in social_words):
            command = "social"
            targets = self._actor_mentions(text, exclude=actor_id)
            if len(targets) == 1:
                params["target"] = targets[0]["id"]
                grounding["target"] = targets[0]["name"]
            elif not targets:
                missing.append("target")
            else:
                ambiguities.append("target:" + ",".join(x["id"] for x in targets))
            if any(w in low for w in ("запуг", "intimidat")):
                approach = "intimidation"
            elif any(w in low for w in ("обман", "deceiv")):
                approach = "deception"
            else:
                approach = "persuasion"
            params["approach"] = approach
            params["goal_text"] = text
            grounding["approach"] = "keyword_rule"
            grounding["goal_text"] = "verbatim"

        elif any(w in low for w in heal_words):
            command = "treat"
            targets = self._actor_mentions(text, exclude=None)
            targets = [t for t in targets if t["id"] != actor_id] or ([{"id": actor_id, "name": str(self.actor(actor_id)["name"])}] if any(w in low for w in ("себя", "себе", "myself")) else [])
            if len(targets) == 1:
                params["target"] = targets[0]["id"]
                grounding["target"] = targets[0]["name"]
            elif not targets:
                missing.append("target")
            else:
                ambiguities.append("target:" + ",".join(x["id"] for x in targets))
            params["method"] = "magic" if any(w in low for w in ("маг", "исцеля", "heal magic")) else "first_aid"
            grounding["method"] = "keyword_rule"

        elif any(w in low for w in wait_words):
            command = "wait"
            nums = self._number_mentions(text)
            if len(nums) == 1 and any(w in low for w in ("минут", "minute")):
                params["minutes"] = nums[0]
                grounding["minutes"] = str(nums[0])
            else:
                missing.append("minutes")

        status = "ready" if command and not missing and not ambiguities else "needs_clarification" if command else "unsupported"
        cur = self.db.execute(
            "INSERT INTO intent_proposals(world_minute,actor_id,raw_text,status,command,params_json,missing_json,ambiguities_json,grounding_json) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (self.now, actor_id, text, status, command, dumps(params), dumps(missing), dumps(ambiguities), dumps(grounding)),
        )
        self.db.commit()
        return {
            "proposal_id": int(cur.lastrowid), "status": status, "command": command,
            "params": params, "missing": missing, "ambiguities": ambiguities, "grounding": grounding,
        }

    def submit_text_intent(self, actor_id: str, raw_text: str) -> dict[str, Any]:
        proposal = self.propose_text_intent(actor_id, raw_text)
        if proposal["status"] != "ready":
            return {"accepted": False, "reason": proposal["status"], "proposal": proposal}
        result = self.submit_player_command(actor_id, str(proposal["command"]), dict(proposal["params"]))
        return {"accepted": bool(result.get("accepted")), "proposal": proposal, "engine": result}

    def validate_external_intent(self, actor_id: str, raw_text: str, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Reject an LLM proposal unless deterministic parsing supports the same command/grounded params."""
        canonical = self.propose_text_intent(actor_id, raw_text)
        if canonical["status"] != "ready":
            return {"valid": False, "reason": canonical["status"], "canonical": canonical}
        if command != canonical["command"]:
            return {"valid": False, "reason": "command_not_grounded", "canonical": canonical}
        expected = canonical["params"]
        if set(params) != set(expected):
            return {"valid": False, "reason": "parameter_schema_mismatch", "canonical": canonical}
        for key, value in expected.items():
            if params.get(key) != value:
                return {"valid": False, "reason": f"parameter_not_grounded:{key}", "canonical": canonical}
        return {"valid": True, "canonical": canonical}
