from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from v111_activate import activate_v111
from v111_repository import load_repository_runtime_v111
from v111_request_processor import FAST_REQUEST_FORMAT, process_request


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rehearse_v111(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    live_pointer = _load(root / "runtime/runtime_state.json")
    live_session = _load(root / "runtime/session_state.json")
    if live_pointer.get("engine_version") != "1.0.10":
        raise RuntimeError("v1.0.11 LIVE rehearsal requires current v1.0.10 runtime")
    if int(live_session.get("journal_seq", -1)) != int(live_pointer.get("journal_seq", -2)):
        raise RuntimeError("LIVE session/pointer seq mismatch")
    if str(live_session.get("head_state_hash") or "") != str(live_pointer.get("head_state_hash") or ""):
        raise RuntimeError("LIVE session/pointer head mismatch")

    base_seq = int(live_pointer["journal_seq"])
    live_head = str(live_pointer["head_state_hash"])
    old_last_key = str((live_session.get("last_turn") or {}).get("event_key") or "")
    if not old_last_key:
        raise RuntimeError("LIVE rehearsal requires an existing last gameplay turn")
    world_minute = int(((live_session.get("hud") or {}).get("time") or {}).get("world_minute", -1))
    cash = int(((live_session.get("hud") or {}).get("money") or {}).get("on_person_copper", -1))
    place = str(((live_session.get("hud") or {}).get("location") or {}).get("place") or "")

    with tempfile.TemporaryDirectory() as td:
        shadow = Path(td) / "repo"
        shadow.mkdir(parents=True)
        shutil.copytree(root / "runtime", shadow / "runtime")

        activation = activate_v111(shadow)
        if not activation.get("ok") or activation.get("already_active"):
            raise RuntimeError("v1.0.11 shadow activation failed")
        if int(activation["journal_seq"]) != base_seq + 1:
            raise RuntimeError("v1.0.11 activation seq mismatch")
        if str(activation["head_state_hash"]) != live_head or not activation.get("gameplay_hash_unchanged"):
            raise RuntimeError("v1.0.11 activation changed gameplay hash")

        activated_pointer = _load(shadow / "runtime/runtime_state.json")
        activated_session = _load(shadow / "runtime/session_state.json")
        if activated_pointer.get("engine_version") != "1.0.11":
            raise RuntimeError("v1.0.11 activation did not switch engine")
        if (activated_session.get("last_turn") or {}).get("event_key") != old_last_key:
            raise RuntimeError("v1.0.11 activation replaced last gameplay turn")
        transport = activated_session.get("transport_runtime") or {}
        if transport.get("optimistic_guard") != "expected_last_gameplay_turn_key":
            raise RuntimeError("v1.0.11 transport metadata missing guard")

        fast_key = "rehearsal-v111-fast-greeting"
        fast_path = shadow / "runtime/requests/q-rehearsal-v111-fast-greeting.json"
        fast_path.write_text(json.dumps({
            "format": FAST_REQUEST_FORMAT,
            "schema_version": 1,
            "request_id": "rehearsal-v111-fast-greeting",
            "event_key": fast_key,
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": old_last_key,
            "request": {"raw_text": "Обращаюсь к Борге: «Доброе утро»."},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        processed = process_request(shadow, fast_path)
        if processed.get("request_mode") != "fast_auto_seq":
            raise RuntimeError("v1.0.11 fast request did not use auto sequence")
        if int(processed["seq"]) != base_seq + 2:
            raise RuntimeError("v1.0.11 fast request allocated wrong seq")
        if processed.get("previous_last_gameplay_turn_key") != old_last_key:
            raise RuntimeError("v1.0.11 fast request guard used wrong prior gameplay turn")
        if processed.get("new_last_gameplay_turn_key") != fast_key:
            raise RuntimeError("v1.0.11 fast request did not become last gameplay turn")

        session_after = _load(shadow / "runtime/session_state.json")
        pointer_after = _load(shadow / "runtime/runtime_state.json")
        if int(((session_after.get("hud") or {}).get("time") or {}).get("world_minute", -2)) != world_minute:
            raise RuntimeError("fast greeting changed world minute")
        if int(((session_after.get("hud") or {}).get("money") or {}).get("on_person_copper", -2)) != cash:
            raise RuntimeError("fast greeting changed cash")
        if str(((session_after.get("hud") or {}).get("location") or {}).get("place") or "") != place:
            raise RuntimeError("fast greeting changed place")
        action = (session_after.get("last_turn") or {}).get("action_result") or {}
        response = action.get("npc_response") or {}
        if action.get("outcome") != "npc_response_resolved" or response.get("surface_text") != "Доброе утро.":
            raise RuntimeError("v1.0.10 gameplay semantics did not survive fast path")
        if response.get("relationship_delta") is not None or response.get("emotion") is not None:
            raise RuntimeError("fast path introduced social inference")
        if list((session_after.get("scene") or {}).get("pending_resolutions") or []):
            raise RuntimeError("fast greeting left pending resolution")

        # The new repository head must replay cleanly from the v1.0.11 compact base.
        verify_db = Path(td) / "verify-live.db"
        world, replay_pointer, meta = load_repository_runtime_v111(shadow, verify_db)
        try:
            if replay_pointer["head_state_hash"] != pointer_after["head_state_hash"]:
                raise RuntimeError("v1.0.11 shadow replay pointer mismatch")
            if not meta["replay"].get("ok"):
                raise RuntimeError("v1.0.11 shadow replay failed")
        finally:
            world.close()

        # Stale gameplay context must fail before a new journal event/state transition.
        stale_path = shadow / "runtime/requests/q-rehearsal-v111-stale.json"
        stale_path.write_text(json.dumps({
            "format": FAST_REQUEST_FORMAT,
            "schema_version": 1,
            "request_id": "rehearsal-v111-stale",
            "event_key": "rehearsal-v111-stale-event",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": old_last_key,
            "request": {"raw_text": "Обращаюсь к Борге: «Доброе утро»."},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pointer_before_stale = _load(shadow / "runtime/runtime_state.json")
        session_before_stale = _load(shadow / "runtime/session_state.json")
        stale_error = None
        try:
            process_request(shadow, stale_path)
        except RuntimeError as exc:
            stale_error = str(exc)
        if not stale_error or "fast_request_stale_gameplay_context" not in stale_error:
            raise RuntimeError("stale fast request did not fail closed")
        if _load(shadow / "runtime/runtime_state.json") != pointer_before_stale:
            raise RuntimeError("stale fast request mutated pointer")
        if _load(shadow / "runtime/session_state.json") != session_before_stale:
            raise RuntimeError("stale fast request mutated session")
        if (shadow / pointer_before_stale["journal_dir"] / f"j{base_seq + 3:06d}.json").exists():
            raise RuntimeError("stale fast request wrote journal event")

    return {
        "ok": True,
        "source_engine": "1.0.10",
        "source_seq": base_seq,
        "activation_seq": base_seq + 1,
        "fast_turn_seq": base_seq + 2,
        "source_head": live_head,
        "world_minute": world_minute,
        "last_gameplay_turn_before": old_last_key,
        "last_gameplay_turn_after": fast_key,
        "fast_request_mode": "fast_auto_seq",
        "preflight_pointer_read_required": False,
        "stale_guard_verified": True,
        "stale_guard_mutated_state": False,
        "v110_greeting_semantics_preserved": True,
        "replay_verified": True,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = rehearse_v111(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
