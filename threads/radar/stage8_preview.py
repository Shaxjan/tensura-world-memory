#!/usr/bin/env python3
"""Stage 8: READ-ONLY candidate rebuild from saved inbox files.

No Git operations, no pushes, no writes to the source checkout.
Candidate inputs and derived index live exclusively in a temporary directory.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from integration_gate import clone_inputs, validate_inventory
from radar import build, verify, read_jsonl

ROOT = Path(__file__).resolve().parents[2]
NAMES = ("posts.jsonl", "editorial.jsonl", "manifest.json")
INBOX_NAME = re.compile(r"^windsor-.*-retrieved\.json$")
MAX_PENDING_ROOTS = 50
MAX_INBOX_FILES = 200


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def inventorize(root: Path) -> dict:
    script = Path(__file__).with_name("inbox_inventory.js")
    completed = subprocess.run(
        ["node", str(script), str(root / "threads/radar")],
        cwd=root, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, check=False,
    )
    if completed.returncode:
        raise RuntimeError("Read-only inbox inventory rejected input: " +
                           completed.stderr[-1500:])
    return json.loads(completed.stdout)


def preserved_source_pairs(radar: Path, inboxes: list[Path]) -> set[str]:
    """Verify previous promotions still match the immutable raw inbox bytes."""
    incoming = {p.name: p for p in inboxes}
    seen = set()
    for snap in sorted((radar / "snapshots").glob("windsor-*.json")):
        doc = read_json(snap)
        name = doc.get("source_inbox_file")
        if name is None:
            continue
        if (not isinstance(name, str) or not INBOX_NAME.fullmatch(name)
            or name in seen or name not in incoming):
            raise ValueError("Missing, duplicate or invalid promoted source provenance")
        raw = read_json(incoming[name])
        if raw.get("state") != "INBOX_NOT_INDEXED":
            raise ValueError("Previous source no longer has quarantine state")
        expected = {k: v for k, v in raw.items() if k != "state"}
        expected["source_inbox_file"] = name
        if "source_inbox_sha256" in doc:
            expected["source_inbox_sha256"] = hashlib.sha256(incoming[name].read_bytes()).hexdigest()
        if doc != expected:
            raise ValueError("Promoted source differs from immutable inbox: " + name)
        seen.add(name)
    return seen


def preview(root: Path = ROOT) -> dict:
    root = root.resolve()
    radar = root / "threads/radar"
    index = radar / "index"
    baseline = read_jsonl(index / "posts.jsonl")
    old_index_hashes = {
        name: hashlib.sha256((index / name).read_bytes()).hexdigest()
        for name in NAMES
    }
    incoming_dir = radar / "inbox"
    inboxes = sorted(p for p in incoming_dir.iterdir()
                     if p.is_file() and INBOX_NAME.fullmatch(p.name))
    if not inboxes or len(inboxes) > MAX_INBOX_FILES:
        raise ValueError("Missing inbox or too many saved inbox files")
    already = preserved_source_pairs(radar, inboxes)
    inventory = inventorize(root)
    checked = validate_inventory(inventory, len(baseline))
    pending = {row["post_id"] for row in inventory["pending_roots"]}
    if checked["pending_roots"] > MAX_PENDING_ROOTS:
        raise ValueError("Unusually large new-post batch requires explicit review")
    candidates = [p for p in inboxes if p.name not in already]
    if not pending:
        return {
            "result": "NO_NEW_ROOTS", "baseline_roots": len(baseline),
            "candidate_roots": len(baseline), "pending_ids": [],
            "unpromoted_inbox_files": [p.name for p in candidates],
            "metrics_only_updates_not_promoted": bool(candidates),
            "source_checkout_modified": False, "index_sha256": old_index_hashes,
        }
    if not candidates:
        raise ValueError("New roots found without an unpromoted source file")
    with tempfile.TemporaryDirectory(prefix="radar-stage8-preview-") as folder:
        scratch = Path(folder)
        clone_inputs(root, scratch)
        out = scratch / "threads/radar/snapshots"
        promoted = []
        for source in candidates:
            raw = source.read_bytes()
            doc = json.loads(raw)
            if (doc.get("state") != "INBOX_NOT_INDEXED"
                or doc.get("account") != "mirpottera"
                or doc.get("source") != "Windsor.ai Threads"):
                raise ValueError("Untrusted inbound snapshot")
            received = doc.get("data_fetched_at_utc")
            if not isinstance(received, str) or not re.fullmatch(
                r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d", received
            ):
                raise ValueError("Malformed provider timestamp")
            stamp = received.replace("-", "").replace(":", "") + "Z"
            digest = hashlib.sha256(raw).hexdigest()[:16]
            name = f"windsor-promoted-{stamp}-{digest}.json"
            destination = out / name
            if destination.exists():
                raise ValueError("Candidate destination already exists")
            doc.pop("state")
            doc["source_inbox_file"] = source.name
            doc["source_inbox_sha256"] = hashlib.sha256(raw).hexdigest()
            destination.write_text(
                json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            promoted.append(name)
        counts = build(scratch)
        checked_index = verify(scratch)
        updated = read_jsonl(scratch / "threads/radar/index/posts.jsonl")
        old_ids = {str(x["post_id"]) for x in baseline}
        new_ids = {str(x["post_id"]) for x in updated}
        if (counts["total_author_roots"] != len(baseline) + len(pending)
            or checked_index["posts"] != counts["total_author_roots"]
            or new_ids - old_ids != pending or old_ids - new_ids):
            raise ValueError("Candidate rebuild lost, replaced or duplicated published IDs")
        # Recheck source checkout: the rehearsal is never permitted to write there.
        if any(hashlib.sha256((index / name).read_bytes()).hexdigest() != digest
               for name, digest in old_index_hashes.items()):
            raise ValueError("Source checkout changed during read-only preview")
        return {
            "result": "CANDIDATE_PASS", "baseline_roots": len(baseline),
            "candidate_roots": len(updated), "pending_ids": sorted(pending),
            "candidate_snapshots": promoted,
            "source_checkout_modified": False, "index_sha256": old_index_hashes,
            "source_completeness_unverified": True,
            "editorial_approval_granted": False,
            "action": "MANUAL_REVIEW_BEFORE_ANY_PROMOTION",
        }


def main() -> None:
    print(json.dumps(preview(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
