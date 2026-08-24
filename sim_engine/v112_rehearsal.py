from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from v112_activate import FAILED_TRANSPORT_REQUESTS, activate_v112
from v112_repository import load_repository_runtime_v112
from v112_request_processor import process_request


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rehearse(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    live_pointer = _load(root / "runtime/runtime_state.json")
    live_session = _load(root / "runtime/session_state.json")
    if live_pointer.get("engine_version") != "1.0.11":
        raise RuntimeError("v1.0.12 LIVE rehearsal requires v1.0.11")
    if int(live_pointer.get("journal_seq", -1)) != 18:
        raise RuntimeError(f"expected current LIVE seq18, got {live_pointer.get('journal_seq')}")
    expected_last = (live_session.get("last_turn") or {}).get("event_key")
    if expected_last != "chat-20260824-repeat-greet-borga-r000017":
        raise RuntimeError("unexpected current LIVE gameplay turn")
    missing = [p for p in FAILED_TRANSPORT_REQUESTS if not (root / p).exists()]
    if missing:
        raise RuntimeError("expected failed transport request files missing: " + ",".join(missing))

    with tempfile.TemporaryDirectory() as td:
        shadow = Path(td) / "repo"
        shadow.mkdir()
        shutil.copytree(root / "runtime", shadow / "runtime")

        activation = activate_v112(shadow)
        pointer = _load(shadow / "runtime/runtime_state.json")
        session = _load(shadow / "runtime/session_state.json")
        if pointer["engine_version"] != "1.0.12" or int(pointer["journal_seq"]) != 19:
            raise RuntimeError("v1.0.12 activation did not land at seq19")
        if pointer["head_state_hash"] != live_pointer["head_state_hash"]:
            raise RuntimeError("transport activation changed gameplay hash")
        if (session.get("last_turn") or {}).get("event_key") != expected_last:
            raise RuntimeError("transport activation replaced gameplay turn")
        for rel in FAILED_TRANSPORT_REQUESTS:
            receipt = shadow / "runtime/request_receipts" / f"{Path(rel).stem}.receipt.json"
            data = _load(receipt)
            if data.get("status") != "superseded" or data.get("authoritative_gameplay_change"):
                raise RuntimeError("failed transport request was not safely superseded")

        canonical_rel = "runtime/requests/q-v112-live-rehearsal-canonical.json"
        canonical = shadow / canonical_rel
        canonical.write_text(json.dumps({
            "format": "TENSURA_FAST_TURN_REQUEST",
            "schema_version": 1,
            "event_key": "v112-live-rehearsal-canonical",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": expected_last,
            "request": {"raw_text": "Обращаюсь к Борге: «Доброе утро»."},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        first = process_request(shadow, canonical_rel)
        if int(first["seq"]) != 20 or first["request_mode"] != "fast_auto_seq:nested_request":
            raise RuntimeError("canonical fast request did not auto-sequence at seq20")
        first_session = _load(shadow / "runtime/session_state.json")
        result = (first_session.get("last_turn") or {}).get("action_result") or {}
        if result.get("outcome") != "npc_response_resolved":
            raise RuntimeError("v1.0.10 response semantics did not survive reliability repair")

        compat_rel = "runtime/requests/q-v112-live-rehearsal-compat.json"
        compat = shadow / compat_rel
        compat.write_text(json.dumps({
            "format": "TENSURA_FAST_TURN_REQUEST",
            "schema_version": 1,
            "event_key": "v112-live-rehearsal-compat",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": "v112-live-rehearsal-canonical",
            "raw_text": "Обращаюсь к Борге: «Доброе утро».",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        second = process_request(shadow, compat_rel)
        if int(second["seq"]) != 21 or second["request_mode"] != "fast_auto_seq:compat_top_level_raw_text":
            raise RuntimeError("compat fast request did not execute at seq21")

        before_pointer = (shadow / "runtime/runtime_state.json").read_bytes()
        before_session = (shadow / "runtime/session_state.json").read_bytes()
        stale_rel = "runtime/requests/q-v112-live-rehearsal-stale.json"
        stale = shadow / stale_rel
        stale.write_text(json.dumps({
            "format": "TENSURA_FAST_TURN_REQUEST",
            "schema_version": 1,
            "event_key": "v112-live-rehearsal-stale",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": expected_last,
            "request": {"raw_text": "test"},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            process_request(shadow, stale_rel)
            raise RuntimeError("stale request unexpectedly executed")
        except RuntimeError as exc:
            if "fast_request_stale_gameplay_context" not in str(exc):
                raise
        if (shadow / "runtime/runtime_state.json").read_bytes() != before_pointer:
            raise RuntimeError("stale request mutated pointer")
        if (shadow / "runtime/session_state.json").read_bytes() != before_session:
            raise RuntimeError("stale request mutated session")
        if (shadow / "runtime/journal/j000022.json").exists():
            raise RuntimeError("stale request created journal event")

        with tempfile.TemporaryDirectory() as dbtd:
            world, loaded, meta = load_repository_runtime_v112(shadow, Path(dbtd) / "verify.db")
            try:
                if loaded["head_state_hash"] != _load(shadow / "runtime/runtime_state.json")["head_state_hash"]:
                    raise RuntimeError("final replay head mismatch")
            finally:
                world.close()

        return {
            "ok": True,
            "live_start_seq": 18,
            "activation_seq": 19,
            "canonical_fast_seq": first["seq"],
            "compat_fast_seq": second["seq"],
            "superseded_requests": FAILED_TRANSPORT_REQUESTS,
            "stale_guard_no_mutation": True,
            "replay_ok": bool(meta["replay"].get("ok")),
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = rehearse(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
