from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

FORMAT = "TENSURA_RUNTIME_TRANSPORT_MODE"
SCHEMA_VERSION = 1
SERVICE_VERSION = "0.1.0"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_health(url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "tensura-transport-activation/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"health returned HTTP {resp.status}")
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError("health payload is not healthy")
    if data.get("service") != "tensura-always-on-runtime":
        raise RuntimeError("unexpected service identity")
    if data.get("service_version") != SERVICE_VERSION:
        raise RuntimeError(f"service version mismatch: {data.get('service_version')}")
    return data


def activate(repo_root: Path, health_url: str) -> dict:
    root = repo_root.resolve()
    pointer = _load(root / "runtime/runtime_state.json")
    session = _load(root / "runtime/session_state.json")
    if session.get("journal_seq") != pointer.get("journal_seq"):
        raise RuntimeError("session/pointer seq mismatch")
    if session.get("head_state_hash") != pointer.get("head_state_hash"):
        raise RuntimeError("session/pointer hash mismatch")
    health = fetch_health(health_url)
    if str(health.get("engine_version")) != str(pointer.get("engine_version")):
        raise RuntimeError("service clone engine version is stale")
    if int(health.get("journal_seq", -1)) != int(pointer.get("journal_seq", -2)):
        raise RuntimeError("service clone journal seq is stale")

    marker = {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "mode": "always_on_service",
        "service": "tensura-always-on-runtime",
        "service_version": SERVICE_VERSION,
        "health_verified": True,
        "engine_version_at_activation": pointer.get("engine_version"),
        "journal_seq_at_activation": pointer.get("journal_seq"),
        "head_state_hash_at_activation": pointer.get("head_state_hash"),
        "activated_at_unix": int(time.time()),
        "github_actions_role": "fallback_only_do_not_execute_normal_turns",
        "rollback_mode": "github_actions",
    }
    out = root / "runtime/transport_mode.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return marker


def deactivate(repo_root: Path, reason: str) -> dict:
    root = repo_root.resolve()
    pointer = _load(root / "runtime/runtime_state.json")
    marker = {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "mode": "github_actions",
        "service": "tensura-always-on-runtime",
        "service_version": SERVICE_VERSION,
        "health_verified": False,
        "engine_version_at_activation": pointer.get("engine_version"),
        "journal_seq_at_activation": pointer.get("journal_seq"),
        "head_state_hash_at_activation": pointer.get("head_state_hash"),
        "activated_at_unix": int(time.time()),
        "reason": reason,
        "github_actions_role": "authoritative_turn_processor",
    }
    out = root / "runtime/transport_mode.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return marker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    sub = ap.add_subparsers(dest="command", required=True)
    a = sub.add_parser("activate")
    a.add_argument("--health-url", required=True)
    d = sub.add_parser("deactivate")
    d.add_argument("--reason", required=True)
    args = ap.parse_args()
    root = Path(args.repo_root)
    if args.command == "activate":
        result = activate(root, args.health_url)
    else:
        result = deactivate(root, args.reason)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
