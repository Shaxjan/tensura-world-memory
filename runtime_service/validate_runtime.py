from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object in {path}")
    return data


def validate_runtime(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    pointer = _load(root / "runtime/runtime_state.json")
    session_path = root / str(pointer.get("session_state") or "runtime/session_state.json")
    session = _load(session_path)

    if str(pointer.get("engine_version")) != "1.0.12":
        raise RuntimeError(f"unsupported engine version: {pointer.get('engine_version')}")
    if int(session.get("journal_seq", -1)) != int(pointer.get("journal_seq", -2)):
        raise RuntimeError("session/pointer seq mismatch")
    if str(session.get("head_state_hash") or "") != str(pointer.get("head_state_hash") or ""):
        raise RuntimeError("session/pointer head mismatch")

    sim_engine = root / "sim_engine"
    sim_engine_text = str(sim_engine)
    if sim_engine_text not in sys.path:
        sys.path.insert(0, sim_engine_text)

    from v112_repository import load_repository_runtime_v112  # noqa: E402

    with tempfile.TemporaryDirectory() as td:
        world, loaded, meta = load_repository_runtime_v112(root, Path(td) / "replay-verify.db")
        try:
            if str(loaded.get("head_state_hash") or "") != str(pointer.get("head_state_hash") or ""):
                raise RuntimeError("full replay head mismatch")
            replay = meta.get("replay") or {}
            if not replay.get("ok"):
                raise RuntimeError("full replay did not report ok")
        finally:
            world.close()

    return {
        "ok": True,
        "engine_version": pointer.get("engine_version"),
        "journal_seq": pointer.get("journal_seq"),
        "head_state_hash": pointer.get("head_state_hash"),
        "replayed": int((meta.get("replay") or {}).get("replayed", 0)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = validate_runtime(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
