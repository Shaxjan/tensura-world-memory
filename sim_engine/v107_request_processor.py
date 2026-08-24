from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from v100_handoff import runtime_state_hash_v100
from v100_repository import journal_filename
from v107_repository import load_repository_runtime_v107

REQUEST_FORMAT = "TENSURA_TURN_REQUEST"


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("request must be object")
    return data


def process_request(repo_root: str | Path, request_path: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    req_path = Path(request_path)
    if not req_path.is_absolute():
        req_path = root / req_path
    req = _load(req_path)
    if req.get("format") != REQUEST_FORMAT or req.get("schema_version") != 1:
        raise ValueError("bad runtime request format")
    seq = req.get("seq")
    if not isinstance(seq, int) or seq < 1:
        raise ValueError("bad request seq")
    event_key, event_type, payload = req.get("event_key"), req.get("event_type"), req.get("request")
    if not isinstance(event_key, str) or not event_key or not isinstance(event_type, str) or not isinstance(payload, dict):
        raise ValueError("request missing event fields")

    pointer_path = root / "runtime/runtime_state.json"
    pointer = _load(pointer_path)
    if pointer.get("engine_version") != "1.0.7":
        raise RuntimeError("v1.0.7 request processor requires engine 1.0.7")
    expected = int(pointer.get("journal_seq", -1)) + 1
    if seq != expected:
        raise RuntimeError(f"request seq mismatch: expected {expected}, got {seq}")
    journal_path = root / str(pointer["journal_dir"]) / journal_filename(seq)
    if journal_path.exists():
        raise RuntimeError("journal event already exists")

    with tempfile.TemporaryDirectory() as td:
        world, loaded_pointer, meta = load_repository_runtime_v107(root, Path(td) / "live.db")
        try:
            if loaded_pointer["head_state_hash"] != pointer["head_state_hash"]:
                raise RuntimeError("pointer changed during load")
            executed = world.execute_runtime_event(seq, event_key, event_type, payload)
            entry = executed["journal"]
            after_hash = runtime_state_hash_v100(world, int(pointer["source_live_version"]))
            if after_hash != entry["after_hash"]:
                raise RuntimeError("event after hash mismatch")
            session_state = world.build_session_state_v107(
                journal_seq=seq,
                head_state_hash=entry["after_hash"],
                last_event=entry,
            )
        finally:
            world.close()

    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pointer["engine_version"] = "1.0.7"
    pointer["journal_seq"] = seq
    pointer["head_state_hash"] = entry["after_hash"]
    pointer["last_event"] = str(Path(pointer["journal_dir"]) / journal_filename(seq))
    pointer["last_request"] = str(req_path.relative_to(root))
    pointer["session_state"] = "runtime/session_state.json"
    pointer["write_protocol"]["request_queue"] = True
    pointer["write_protocol"]["session_fast_path"] = True
    pointer["write_protocol"]["living_scene"] = True
    pointer["write_protocol"]["character_core"] = True
    pointer["write_protocol"]["character_autonomy"] = True
    pointer["write_protocol"]["intent_grounding_repair"] = True
    pointer["write_protocol"]["causal_encounter_memory"] = True
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "runtime/session_state.json").write_text(
        json.dumps(session_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return {
        "ok": True,
        "seq": seq,
        "event_key": event_key,
        "event_type": event_type,
        "journal_path": str(journal_path.relative_to(root)),
        "session_state": "runtime/session_state.json",
        "before_hash": entry["before_hash"],
        "after_hash": entry["after_hash"],
        "result_status": (entry.get("result") or {}).get("status"),
        "replay_before": meta["replay"].get("replayed", 0),
    }


def main() -> None:
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
