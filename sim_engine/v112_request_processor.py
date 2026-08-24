from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from v100_handoff import runtime_state_hash_v100
from v100_repository import journal_filename
from v112_receipt import write_receipt
from v112_repository import load_repository_runtime_v112

LEGACY_REQUEST_FORMAT = "TENSURA_TURN_REQUEST"
FAST_REQUEST_FORMAT = "TENSURA_FAST_TURN_REQUEST"


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("request must be object")
    return data


def _current_last_gameplay_turn_key(session: dict[str, Any]) -> str | None:
    turn = session.get("last_turn")
    if not isinstance(turn, dict):
        return None
    key = turn.get("event_key")
    return str(key) if isinstance(key, str) and key else None


def _payload(req: dict[str, Any]) -> tuple[dict[str, Any], str]:
    nested = req.get("request")
    top_raw = req.get("raw_text")
    if isinstance(nested, dict):
        if top_raw is not None:
            nested_raw = nested.get("raw_text")
            if nested_raw is not None and nested_raw != top_raw:
                raise ValueError("conflicting nested and top-level raw_text")
        return dict(nested), "nested_request"
    if isinstance(top_raw, str) and top_raw:
        return {"raw_text": top_raw}, "compat_top_level_raw_text"
    raise ValueError("request payload missing; expected request object or top-level raw_text")


def _decode_request(
    req: dict[str, Any], pointer: dict[str, Any], session: dict[str, Any]
) -> tuple[int, str, str, dict[str, Any], str]:
    fmt = req.get("format")
    if req.get("schema_version") != 1:
        raise ValueError("bad runtime request schema")
    event_key, event_type = req.get("event_key"), req.get("event_type")
    if not isinstance(event_key, str) or not event_key or len(event_key) > 160:
        raise ValueError("request missing/invalid event_key")
    if not isinstance(event_type, str) or not event_type:
        raise ValueError("request missing event_type")
    payload, payload_mode = _payload(req)

    next_seq = int(pointer.get("journal_seq", -1)) + 1
    if fmt == LEGACY_REQUEST_FORMAT:
        seq = req.get("seq")
        if not isinstance(seq, int) or seq < 1:
            raise ValueError("bad legacy request seq")
        if seq != next_seq:
            raise RuntimeError(f"request seq mismatch: expected {next_seq}, got {seq}")
        return seq, event_key, event_type, payload, f"legacy_explicit_seq:{payload_mode}"

    if fmt != FAST_REQUEST_FORMAT:
        raise ValueError("bad runtime request format")
    if "seq" in req:
        raise ValueError("fast request must not pre-allocate journal seq")
    request_id = req.get("request_id")
    if request_id is not None and (not isinstance(request_id, str) or not request_id or len(request_id) > 160):
        raise ValueError("optional fast request_id must be a non-empty string")
    expected = req.get("expected_last_gameplay_turn_key")
    if expected is not None and not isinstance(expected, str):
        raise ValueError("expected_last_gameplay_turn_key must be string or null")
    current = _current_last_gameplay_turn_key(session)
    if expected != current:
        raise RuntimeError(
            "fast_request_stale_gameplay_context: "
            f"expected_last_gameplay_turn_key={expected!r}, current={current!r}"
        )
    return next_seq, event_key, event_type, payload, f"fast_auto_seq:{payload_mode}"


def process_request(repo_root: str | Path, request_path: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    req_path = Path(request_path)
    if not req_path.is_absolute():
        req_path = root / req_path
    req = _load(req_path)

    pointer_path = root / "runtime/runtime_state.json"
    pointer = _load(pointer_path)
    if pointer.get("engine_version") != "1.0.12":
        raise RuntimeError("v1.0.12 request processor requires engine 1.0.12")
    session_path = root / str(pointer.get("session_state") or "runtime/session_state.json")
    session_before = _load(session_path)
    if int(session_before.get("journal_seq", -1)) != int(pointer.get("journal_seq", -2)):
        raise RuntimeError("stale session before request processing")
    if str(session_before.get("head_state_hash") or "") != str(pointer.get("head_state_hash") or ""):
        raise RuntimeError("session/pointer head mismatch before request processing")

    seq, event_key, event_type, payload, request_mode = _decode_request(req, pointer, session_before)
    journal_path = root / str(pointer["journal_dir"]) / journal_filename(seq)
    if journal_path.exists():
        raise RuntimeError("journal event already exists")

    with tempfile.TemporaryDirectory() as td:
        world, loaded, meta = load_repository_runtime_v112(root, Path(td) / "live.db")
        try:
            if loaded["head_state_hash"] != pointer["head_state_hash"]:
                raise RuntimeError("pointer changed during load")
            duplicate = world.db.execute(
                "SELECT seq FROM runtime_journal WHERE event_key=?", (event_key,)
            ).fetchone()
            if duplicate is not None:
                raise RuntimeError(f"duplicate event_key already committed at seq {int(duplicate['seq'])}")
            executed = world.execute_runtime_event(seq, event_key, event_type, payload)
            entry = executed["journal"]
            if runtime_state_hash_v100(world, int(pointer["source_live_version"])) != entry["after_hash"]:
                raise RuntimeError("event after hash mismatch")
            session = world.build_session_state_v112(
                journal_seq=seq,
                head_state_hash=entry["after_hash"],
                last_event=entry,
            )
        finally:
            world.close()

    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pointer.update({
        "engine_version": "1.0.12",
        "journal_seq": seq,
        "head_state_hash": entry["after_hash"],
        "last_event": str(Path(pointer["journal_dir"]) / journal_filename(seq)),
        "last_request": str(req_path.relative_to(root)),
        "session_state": "runtime/session_state.json",
    })
    wp = pointer.setdefault("write_protocol", {})
    wp["runtime_fast_path"] = True
    wp["fast_request_auto_sequence"] = True
    wp["fast_request_last_turn_guard"] = True
    wp["fast_request_schema_repair"] = True
    wp["request_receipts"] = True
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "runtime/session_state.json").write_text(
        json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    receipt = write_receipt(
        root,
        req_path,
        status="executed",
        seq=seq,
        event_key=event_key,
        request_mode=request_mode,
    )
    return {
        "ok": True,
        "seq": seq,
        "event_key": event_key,
        "request_mode": request_mode,
        "journal_path": str(journal_path.relative_to(root)),
        "receipt": receipt["receipt"],
        "before_hash": entry["before_hash"],
        "after_hash": entry["after_hash"],
        "result_status": (entry.get("result") or {}).get("status"),
        "replay_before": meta["replay"].get("replayed", 0),
        "previous_last_gameplay_turn_key": _current_last_gameplay_turn_key(session_before),
        "new_last_gameplay_turn_key": _current_last_gameplay_turn_key(session),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--request", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    result = process_request(args.repo_root, args.request)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
