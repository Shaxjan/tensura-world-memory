#!/usr/bin/env python3
"""One-time guarded promotion of validated inboxes. Draft branch only."""
import json
import subprocess
from pathlib import Path
from radar import build, verify, read_jsonl

ROOT = Path(__file__).resolve().parents[2]
RADAR = ROOT / "threads/radar"
EXPECTED = {"18058181561570070", "17899242612398487",
            "18152771278539108", "18472636933140300",
            "17915165559493626"}
def run():
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if branch != "radar-stage-b-index-20261020":
        raise RuntimeError("Refusing promotion outside approved Draft branch")
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    if dirty:
        raise RuntimeError("Refusing promotion with a dirty working tree")
    index_path = RADAR / "index/posts.jsonl"
    before = read_jsonl(index_path)
    before_ids = {str(p["post_id"]) for p in before}
    if len(before) != 454:
        raise RuntimeError("Expected 454 roots before promotion")
    report = json.loads(subprocess.check_output(["node", str(RADAR / "inbox_inventory.js")],
                                                 cwd=ROOT, text=True))
    found = {p["post_id"] for p in report["pending_roots"]}
    if (report["status"] != "PENDING_NATIVE_ACCEPTANCE" or
        report["conflicts"] != [] or found != EXPECTED or
        report["baseline_roots"] != 454):
        raise RuntimeError("Inbox inventory does not match reviewed five roots")
    inbox = sorted((RADAR / "inbox").glob("windsor-*-retrieved.json"))
    if len(inbox) != 2:
        raise RuntimeError("Expected exactly two reviewed snapshots")
    target = RADAR / "snapshots"
    created = []
    try:
        for n, source in enumerate(inbox):
            doc = json.loads(source.read_text(encoding="utf-8"))
            if (doc.get("account") != "mirpottera" or
                doc.get("state") != "INBOX_NOT_INDEXED" or
                doc.get("source") != "Windsor.ai Threads" or
                doc.get("count") != len(doc.get("posts", []))):
                raise RuntimeError("Unsafe inbound snapshot: " + source.name)
            doc.pop("state")
            doc["source_inbox_file"] = source.name
            dest = target / ("windsor-promoted-" + str(n) + "-" + source.stem + ".json")
            if dest.exists():
                raise RuntimeError("Promotion destination exists: " + str(dest))
            dest.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created.append(dest)
        result = build(ROOT)
        verified = verify(ROOT)
        after = read_jsonl(index_path)
        after_ids = {str(p["post_id"]) for p in after}
        if (result["total_author_roots"] != 459 or verified["posts"] != 459
            or after_ids - before_ids != EXPECTED
            or before_ids - after_ids):
            raise RuntimeError("Unsafe promotion result; do not commit")
        print(json.dumps({"status": "PROMOTED_IN_DRAFT_WORKTREE", "roots": 459,
                          "added_ids": sorted(EXPECTED), "snapshots": [p.name for p in created]}))
    except Exception:
        # GitHub Actions checkout is ephemeral; never publish a failing worktree.
        raise

if __name__ == "__main__":
    run()
