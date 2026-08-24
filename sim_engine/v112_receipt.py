from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

RECEIPT_FORMAT = "TENSURA_REQUEST_RECEIPT"


def receipt_path(repo_root: str | Path, request_path: str | Path) -> Path:
    root = Path(repo_root).resolve()
    req = Path(request_path)
    if not req.is_absolute():
        req = root / req
    return root / "runtime/request_receipts" / f"{req.stem}.receipt.json"


def _request_meta(request_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(request_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_receipt(
    repo_root: str | Path,
    request_path: str | Path,
    *,
    status: str,
    seq: int | None = None,
    event_key: str | None = None,
    request_mode: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    req = Path(request_path)
    if not req.is_absolute():
        req = root / req
    meta = _request_meta(req)
    out = {
        "format": RECEIPT_FORMAT,
        "schema_version": 1,
        "request_path": str(req.relative_to(root)),
        "request_format": meta.get("format"),
        "event_key": event_key or meta.get("event_key"),
        "status": status,
        "seq": seq,
        "request_mode": request_mode,
        "error": error,
        "authoritative_gameplay_change": status == "executed",
    }
    path = receipt_path(root, req)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"receipt": str(path.relative_to(root)), **out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--request", required=True)
    ap.add_argument("--status", choices=["executed", "failed", "superseded"], required=True)
    ap.add_argument("--seq", type=int)
    ap.add_argument("--event-key")
    ap.add_argument("--request-mode")
    ap.add_argument("--error")
    ap.add_argument("--error-file")
    args = ap.parse_args()
    error = args.error
    if args.error_file:
        text = Path(args.error_file).read_text(encoding="utf-8", errors="replace")
        error = text[-4000:]
    result = write_receipt(
        args.repo_root,
        args.request,
        status=args.status,
        seq=args.seq,
        event_key=args.event_key,
        request_mode=args.request_mode,
        error=error,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
