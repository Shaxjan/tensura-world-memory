#!/usr/bin/env python3
"""Validate and stage ONLY one checked stage-8 batch; never commit or push."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

BRANCH = "radar-stage-b-index-20261020"
FIXED = {
    "threads/radar/index/posts.jsonl",
    "threads/radar/index/editorial.jsonl",
    "threads/radar/index/manifest.json",
    "threads/radar/reserve/automated-current-ideas.json",
    "threads/radar/reserve/automated-current-screening.json",
}
REQUIRED = {
    "threads/radar/index/posts.jsonl",
    "threads/radar/index/manifest.json",
    "threads/radar/reserve/automated-current-ideas.json",
    "threads/radar/reserve/automated-current-screening.json",
}
SIMULATION_INBOX = "threads/radar/inbox/windsor-20261025T060000Z-stage8-simulation-retrieved.json"
SNAPSHOT = re.compile(r"^windsor-promoted-20\d{6}T\d{6}Z-[a-f0-9]{16}\.json$")


def allowed_paths(report: dict, *, simulation: bool = False) -> set[str]:
    if (report.get("result") != "STAGED_UNCOMMITTED"
        or report.get("editorial_approval") is not False
        or report.get("no_git_push_performed") is not True
        or report.get("simulation") is not simulation):
        raise ValueError("Source batch has not passed stage-8 safeguards")
    new = report.get("new_roots")
    before = report.get("baseline")
    after = report.get("candidate_roots")
    ids = report.get("added_ids")
    names = report.get("snapshots")
    if (type(new) is not int or not 1 <= new <= 50
        or type(before) is not int or before < 459
        or type(after) is not int or after != before + new
        or not isinstance(ids, list) or len(ids) != new
        or len(set(ids)) != new
        or not all(isinstance(i, str) and re.fullmatch(r"\d{12,22}", i) for i in ids)
        or not isinstance(names, list) or not 1 <= len(names) <= 200
        or len(set(names)) != len(names)
        or not all(isinstance(n, str) and SNAPSHOT.fullmatch(n) for n in names)):
        raise ValueError("Inconsistent batch, root IDs or snapshot names")
    return FIXED | {"threads/radar/snapshots/" + n for n in names}


def command(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def stage(root: Path, report: dict, *, simulation: bool = False) -> list[str]:
    if command(root, "branch", "--show-current") != BRANCH:
        raise RuntimeError("Git staging prohibited outside approved Draft branch")
    planned = allowed_paths(report, simulation=simulation)
    if command(root, "diff", "--cached", "--name-only"):
        raise RuntimeError("Unexpected previously staged changes")
    modified = set(command(root, "diff", "--name-only").splitlines())
    if not modified <= planned:
        raise RuntimeError("Tracked changes outside prepared candidate artifacts")
    other = set(command(root, "ls-files", "--others", "--exclude-standard").splitlines())
    accepted_untracked = set(planned)
    if simulation:
        accepted_untracked.add(SIMULATION_INBOX)
        if SIMULATION_INBOX not in other:
            raise RuntimeError("Missing expected synthetic-only input")
    if not other <= accepted_untracked:
        raise RuntimeError("Unexpected files in worktree; abort promotion")
    subprocess.run(["git", "add", "--", *sorted(planned)], cwd=root, check=True)
    staged = set(command(root, "diff", "--cached", "--name-only").splitlines())
    expected_sources = {p for p in planned if p.startswith("threads/radar/snapshots/")}
    if (not staged or not staged <= planned or
        not (REQUIRED | expected_sources) <= staged or
        command(root, "diff", "--name-only")):
        raise RuntimeError("Unexpected staged paths, missing sources or unstaged changes")
    return sorted(staged)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[2]
    print(json.dumps({"status": "STAGED_NO_GIT_COMMIT",
                      "files": stage(root, report, simulation=args.simulate),
                      "simulated": args.simulate}, indent=2))


if __name__ == "__main__":
    main()
