from __future__ import annotations

import argparse
import json
import queue
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from server import RuntimeService as ProductionRuntimeService
from validate_runtime import validate_runtime


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object in {path}")
    return data


class ShadowRuntimeService(ProductionRuntimeService):
    """Production processing path without network sync or Git push."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.branch = "main"
        self.remote = "origin"
        self.required_mode = "always_on_service"
        self.queue: queue.Queue[tuple[str, str | None]] = queue.Queue(maxsize=16)
        self.lock = threading.RLock()
        self.started_at = time.time()
        self.last_result: dict[str, Any] | None = None

    def _sync_main(self) -> None:
        return None

    def _commit_and_push(self, message: str, *, include_request: str | None = None) -> str:
        return "shadow-no-push"


def rehearse(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    original_pointer = (root / "runtime/runtime_state.json").read_bytes()
    original_session = (root / "runtime/session_state.json").read_bytes()
    live_pointer = _load(root / "runtime/runtime_state.json")
    live_session = _load(root / "runtime/session_state.json")
    start_seq = int(live_pointer["journal_seq"])
    expected_last = (live_session.get("last_turn") or {}).get("event_key")
    if not isinstance(expected_last, str) or not expected_last:
        raise RuntimeError("LIVE has no authoritative last gameplay turn key")

    # Prove the source runtime is replayable before making the shadow copy.
    source_validation = validate_runtime(root)

    with tempfile.TemporaryDirectory() as td:
        shadow = Path(td) / "repo"
        shadow.mkdir()
        shutil.copytree(root / "runtime", shadow / "runtime")
        shutil.copytree(root / "sim_engine", shadow / "sim_engine")
        (shadow / "runtime/transport_mode.json").write_text(
            json.dumps(
                {
                    "format": "TENSURA_RUNTIME_TRANSPORT_MODE",
                    "schema_version": 1,
                    "mode": "always_on_service",
                    "service": "tensura-always-on-runtime",
                    "service_version": "0.2.0",
                    "health_verified": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        request_rel = "runtime/requests/q-always-on-local-rehearsal.json"
        request = {
            "format": "TENSURA_FAST_TURN_REQUEST",
            "schema_version": 1,
            "event_key": "always-on-local-rehearsal-greeting",
            "event_type": "player_turn",
            "expected_last_gameplay_turn_key": expected_last,
            "request": {"raw_text": "Обращаюсь к Борге: «Доброе утро»."},
        }
        request_path = shadow / request_rel
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        service = ShadowRuntimeService(shadow)
        first = service.process_existing_request(request_rel, delivery_id="local-rehearsal-1")
        if not first.get("ok"):
            raise RuntimeError(f"shadow turn failed: {first}")

        pointer_after = _load(shadow / "runtime/runtime_state.json")
        if int(pointer_after["journal_seq"]) != start_seq + 1:
            raise RuntimeError("shadow service did not append exactly one journal event")
        receipt_path = shadow / "runtime/request_receipts/q-always-on-local-rehearsal.receipt.json"
        receipt = _load(receipt_path)
        if receipt.get("status") != "executed" or not receipt.get("authoritative_gameplay_change"):
            raise RuntimeError("shadow service did not create executed receipt")

        replay_after = validate_runtime(shadow)
        second = service.process_existing_request(request_rel, delivery_id="local-rehearsal-duplicate")
        pointer_second = _load(shadow / "runtime/runtime_state.json")
        if not second.get("idempotent"):
            raise RuntimeError("duplicate request was not idempotent")
        if int(pointer_second["journal_seq"]) != start_seq + 1:
            raise RuntimeError("idempotent duplicate advanced journal")

    if (root / "runtime/runtime_state.json").read_bytes() != original_pointer:
        raise RuntimeError("local rehearsal mutated LIVE runtime pointer")
    if (root / "runtime/session_state.json").read_bytes() != original_session:
        raise RuntimeError("local rehearsal mutated LIVE session")

    return {
        "ok": True,
        "live_seq_unchanged": start_seq,
        "shadow_executed_seq": start_seq + 1,
        "source_replay_ok": source_validation["ok"],
        "post_turn_replay_ok": replay_after["ok"],
        "duplicate_idempotent": True,
        "live_files_unchanged": True,
        "commit": first.get("commit"),
        "telemetry_status": (first.get("telemetry") or {}).get("status"),
    }


def main() -> None:
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
