#!/usr/bin/env python3
"""Stage 8: prepare validated inbox promotion in ephemeral Draft checkout.

This command never invokes git add, git commit, git push, merge or publishing.
GitHub Actions runs the native full-corpus gate again before any atomic Git commit.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from stage8_preview import ROOT, NAMES, preview, read_json

BRANCH = "radar-stage-b-index-20261020"
RADAR = ROOT / "threads/radar"
RESERVE_OUTPUTS = ("automated-current-ideas.json",
                   "automated-current-screening.json")


def cmd(*args: str) -> str:
    return subprocess.check_output(list(args), cwd=ROOT, text=True).strip()


def synthetic_inbox() -> Path:
    old = read_json(RADAR / "inbox/windsor-20261025T003529Z-eddca5900dc17028-retrieved.json")
    base = next(row for row in old["posts"] if row["post_media_type"] == "TEXT_POST")
    post = dict(base)
    post.update({
        "post_id": "19999887766553322",
        "post_timestamp": "2026-10-25T05:00:00+0000",
        "post_text": "СИНТЕТИЧЕСКАЯ ПРОВЕРКА: Не является реальной публикацией Threads.",
        "post_permalink": "https://www.threads.com/@mirpottera/post/Stage8SimulationOnly",
        "post_views": 0,
        "data_fetched_at": "2026-10-25T06:00:00",
    })
    doc = {
        "schema_version": 1, "account": "mirpottera", "source": "Windsor.ai Threads",
        "source_account_id": "28902703019346338",
        "state": "INBOX_NOT_INDEXED", "data_fetched_at_utc": "2026-10-25T06:00:00",
        "retrieval_date_utc": "2026-10-25",
        "period_utc": ["2026-10-25", "2026-10-25"],
        "count": 1, "read_fields": old["read_fields"], "posts": [post],
    }
    dest = RADAR / "inbox/windsor-20261025T060000Z-stage8-simulation-retrieved.json"
    if dest.exists():
        raise RuntimeError("Simulation file already exists")
    dest.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return dest


def promote_in_ephemeral_checkout(simulate: bool = False) -> dict:
    if cmd("git", "branch", "--show-current") != BRANCH:
        raise RuntimeError("Archive promotion is allowed only on the explicit radar Draft branch")
    status = cmd("git", "status", "--porcelain")
    if status:
        raise RuntimeError("Refusing promotion with uncommitted changes: " + status[:250])
    if simulate:
        initial = preview(ROOT)
        if initial["result"] != "NO_NEW_ROOTS":
            raise RuntimeError("Simulation requires an empty real inbox")
        synthetic_inbox()
    with tempfile.TemporaryDirectory(prefix="mirpottera-stage8-staged-") as tmp:
        staged = Path(tmp) / "verified"
        report = preview(ROOT, prepared_dir=staged)
        if report["result"] == "NO_NEW_ROOTS":
            return {"result": "NO_NEW_ROOTS", "new_roots": 0, "archive_modified": False}
        if report["result"] != "CANDIDATE_PASS" or not report["pending_ids"]:
            raise RuntimeError("No validated new author roots")
        # Verified candidate data are copied only after the independent
        # double-build, hash and old-ID continuity checks in preview().
        staged_snapshots = staged / "threads/radar/snapshots"
        names = report["candidate_snapshots"]
        if (set(p.name for p in staged_snapshots.iterdir()) != set(names)
            or any((RADAR / "snapshots" / n).exists() for n in names)):
            raise RuntimeError("Unexpected or colliding snapshot destination")
        for n in names:
            shutil.copy2(staged_snapshots / n, RADAR / "snapshots" / n)
        for n in NAMES:
            src = staged / "threads/radar/index" / n
            if not src.is_file():
                raise RuntimeError("Missing verified candidate index artifact")
            shutil.copy2(src, RADAR / "index" / n)
        # Generate candidate editorial output from the *new* 460+ root index.
        # No idea can be approved or marked as canon-verified here.
        reserve_stage = Path(tmp) / "reserve"
        done = subprocess.run(
            ["node", str(RADAR / "stage8_rescreen.js"), str(ROOT), str(reserve_stage)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180, check=False,
        )
        if done.returncode:
            raise RuntimeError("Reserve screening failed: " + done.stderr[-1500:])
        screening = json.loads(done.stdout)
        if (screening.get("status") != "SCREENED_UNAPPROVED" or
            screening.get("roots") != report["candidate_roots"] or
            screening.get("ideas") != 30 or
            screening.get("requires_human_approval") is not True):
            raise RuntimeError("Invalid post-index screening output")
        for n in RESERVE_OUTPUTS:
            shutil.copy2(reserve_stage / n, RADAR / "reserve" / n)
        return {
            "result": "STAGED_UNCOMMITTED", "new_roots": len(report["pending_ids"]),
            "added_ids": report["pending_ids"], "baseline": report["baseline_roots"],
            "candidate_roots": report["candidate_roots"],
            "snapshots": names, "editorial_approval": False,
            "no_git_push_performed": True, "simulation": simulate,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true",
                        help="Inject one synthetic post on ephemeral runner; NEVER push")
    args = parser.parse_args()
    report = promote_in_ephemeral_checkout(simulate=args.simulate)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
