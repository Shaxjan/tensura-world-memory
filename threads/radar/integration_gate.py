#!/usr/bin/env python3
"""Offline, read-only full-corpus integration gate for the Threads radar.

Run inside a COMPLETE local clone. All rebuilds happen in a temporary copy;
nothing is published, merged or written to the source archive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from radar import build, verify

ROOT = Path(__file__).resolve().parents[2]
INDEX_FILES = ("posts.jsonl", "editorial.jsonl", "manifest.json")
PYTHON_TESTS = ("test_continuations.py", "test_radar.py", "test_snapshot_consistency.py")
NODE_TESTS = (
    "semantic.test.js",
    "reserve.test.js",
    "snapshot_intake.test.js",
    "reserve-current.test.js",
    "semantic-safety.test.js",
    "snapshot-safety.test.js",
    "reserve-freshness.test.js",
    "inbox_check.test.js",
    "watch_check.test.js",
    "inbox_delivery.test.js",
    "delivery-replay-2026-10-25.test.js",
    "inbox_inventory.test.js",
)


def copy_input(src: Path, dest: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError("Missing full-corpus input: " + str(src))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def clone_inputs(source_root: Path, scratch: Path) -> int:
    required = (
        "posts.json", "threads/full-posts-verified.json",
        "threads/posts-by-format.json",
        *(f"threads/radar/index/{n}" for n in INDEX_FILES),
    )
    for rel in required:
        copy_input(source_root / rel, scratch / rel)
    snapshots = source_root / "threads" / "radar" / "snapshots"
    inputs = sorted(snapshots.glob("windsor-*.json"))
    if not inputs:
        raise ValueError("Full integration gate requires saved Windsor snapshots")
    for path in inputs:
        copy_input(path, scratch / "threads" / "radar" / "snapshots" / path.name)
    continuations = snapshots / "author-continuations-2026-10-23.json"
    if continuations.exists():
        copy_input(continuations, scratch / "threads" / "radar" / "snapshots" / continuations.name)
    return len(inputs)


def run_suite(command: list[str], root: Path, timeout: int = 180) -> dict:
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    completed = subprocess.run(
        command, cwd=root, env=environment, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Native command failed (" + str(completed.returncode) + "): "
            + " ".join(command) + "\n"
            + (completed.stdout + "\n" + completed.stderr)[-5000:]
        )
    return {
        "command": " ".join(command), "exit_code": 0,
        "stdout_tail": completed.stdout[-900:], "stderr_tail": completed.stderr[-900:],
    }


def execute(root: Path, *, run_tests: bool = True) -> dict:
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    current_index = root / "threads" / "radar" / "index"
    expected = {
        name: (current_index / name).read_bytes() for name in INDEX_FILES
    }
    with tempfile.TemporaryDirectory(prefix="mir-pottera-radar-integration-") as tmp:
        scratch = Path(tmp)
        count = clone_inputs(root, scratch)
        first = build(scratch)
        checked = verify(scratch)
        if checked["posts"] != first["total_author_roots"]:
            raise ValueError("Rebuilt post count and verification disagree")
        differences = [
            name for name in INDEX_FILES
            if (scratch / "threads" / "radar" / "index" / name).read_bytes() != expected[name]
        ]
        if differences:
            raise ValueError("Full-corpus rebuild differs from checked-in index: "
                             + ", ".join(differences))
        # Test byte-for-byte reproducibility after an independent second build.
        second = build(scratch)
        if first != second:
            raise ValueError("Repeated rebuild returned different counts")
        if any(
            (scratch / "threads" / "radar" / "index" / name).read_bytes()
            != expected[name] for name in INDEX_FILES
        ):
            raise ValueError("Repeated full-corpus rebuild is not byte-identical")
    output = {
        "result": "PASS",
        "mode": "native_full_corpus_rebuild_in_temporary_directory",
        "original_archive_not_modified": True,
        "source_snapshot_files": count,
        "author_roots": first["total_author_roots"],
        "historical_roots": first["historic_posts"],
        "journal_cards": first["journal_cards"],
        "probable_continuations": first.get("author_continuation_parts", 0),
        "rebuilds": 2,
        "exact_index_bytes_match": True,
        "checked_in_sha256": {
            name: hashlib.sha256(expected[name]).hexdigest() for name in INDEX_FILES
        },
        "native_test_suites": [],
    }
    if run_tests:
        output["native_test_suites"].append(run_suite(
            [sys.executable, "-B", "-m", "unittest", "discover",
             "-s", "threads/radar", "-p", "test_*.py"], root,
        ))
        output["native_test_suites"].append(run_suite(
            ["node", "--test",
             *(str(Path("threads") / "radar" / name) for name in NODE_TESTS)],
            root,
        ))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline, read-only Stage 5 native integration gate"
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--skip-tests", action="store_true",
                        help="Check full-corpus build only (still runs twice)")
    args = parser.parse_args()
    try:
        result = execute(args.repo_root.resolve(), run_tests=not args.skip_tests)
    except Exception as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
