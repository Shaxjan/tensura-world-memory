#!/usr/bin/env python3
"""Lightweight guardrail for TENSURA_CURRENT_SCENE transitions.

Usage:
    python runtime/continuity/validate_transition.py OLD_SCENE.json NEW_SCENE.json DELTA.json

This is intentionally conservative. It catches resets/teleports/day jumps/money jumps that
lack an explicit delta cause. It does not attempt to replace narrative causal reasoning.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TRACKED_NPC_FIELDS = ("presence", "awake", "sleeping", "clothing_state", "position")
REPAIR_CLASSES = {"STATE_RECONCILIATION", "ASSISTANT_CONTINUITY_ERROR_REPAIR", "PLAYER_RETCON", "CLARIFICATION"}


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def day(scene: dict):
    value = (scene.get("time") or {}).get("day")
    return int(value) if isinstance(value, int) else None


def npc_transition_keys(delta: dict) -> set[str]:
    rows = (((delta.get("changes") or {}).get("npc_transitions")) or [])
    return {str(row.get("npc_key")) for row in rows if isinstance(row, dict) and row.get("npc_key")}


def validate(old: dict, new: dict, delta: dict) -> list[str]:
    errors: list[str] = []

    if old.get("format") != "TENSURA_CURRENT_SCENE" or new.get("format") != "TENSURA_CURRENT_SCENE":
        errors.append("old/new scene must use format TENSURA_CURRENT_SCENE")

    if delta.get("format") != "TENSURA_TURN_DELTA":
        errors.append("delta must use format TENSURA_TURN_DELTA")

    if delta.get("source_scene_id") != old.get("scene_id"):
        errors.append("delta.source_scene_id does not match current scene")

    classification = str(delta.get("classification") or "")
    elapsed = delta.get("elapsed_minutes", 0)
    try:
        elapsed = float(elapsed)
    except Exception:
        errors.append("elapsed_minutes is not numeric")
        elapsed = 0

    old_day, new_day = day(old), day(new)
    if old_day is not None and new_day is not None and old_day != new_day:
        if not delta.get("time_jump_reason") and classification not in REPAIR_CLASSES:
            errors.append("T+ day changed without time_jump_reason")

    if elapsed > 180 and not delta.get("time_jump_reason"):
        errors.append("large elapsed time requires time_jump_reason")

    old_loc = old.get("location") or {}
    new_loc = new.get("location") or {}
    if old_loc != new_loc and classification not in REPAIR_CLASSES:
        changes = delta.get("changes") or {}
        if not changes.get("location") and not delta.get("time_jump_reason"):
            errors.append("location changed without location delta or timeskip cause")

    old_money = old.get("money") or {}
    new_money = new.get("money") or {}
    if old_money != new_money and classification not in REPAIR_CLASSES:
        money_events = ((delta.get("changes") or {}).get("money_events")) or []
        if not money_events:
            errors.append("money changed without money_events")

    old_entities = old.get("present_entities") or {}
    new_entities = new.get("present_entities") or {}
    transition_keys = npc_transition_keys(delta)
    all_keys = set(old_entities) | set(new_entities)
    for key in sorted(all_keys):
        before = old_entities.get(key)
        after = new_entities.get(key)
        if before is None or after is None:
            if key not in transition_keys and classification not in REPAIR_CLASSES:
                errors.append(f"NPC {key} entered/left scene without npc_transition")
            continue
        changed = [field for field in TRACKED_NPC_FIELDS if before.get(field) != after.get(field)]
        if changed and key not in transition_keys and classification not in REPAIR_CLASSES:
            errors.append(f"NPC {key} changed {changed} without npc_transition")

    old_player = old.get("player") or {}
    new_player = new.get("player") or {}
    if old_player.get("state") != new_player.get("state"):
        allowed_nonvoluntary = classification in {"SLEEP_RESOLUTION", "STATE_RECONCILIATION", "ASSISTANT_CONTINUITY_ERROR_REPAIR", "PLAYER_RETCON"}
        player_input = delta.get("player_input") or {}
        if not allowed_nonvoluntary and not player_input.get("contains_voluntary_player_action"):
            errors.append("player physical state changed without explicit voluntary player action or allowed resolution")

    if (delta.get("player_input") or {}).get("is_ooc") and classification == "NORMAL_TURN":
        if old != new:
            errors.append("OOC NORMAL_TURN must not mutate the in-world scene")

    return errors


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: validate_transition.py OLD_SCENE NEW_SCENE DELTA", file=sys.stderr)
        return 2
    old, new, delta = map(load, sys.argv[1:])
    errors = validate(old, new, delta)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "errors": []}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
