#!/usr/bin/env python3
"""Read-only five-root inbox promotion rehearsal. Never edits checkout."""
import json
import shutil
import tempfile
from pathlib import Path
from radar import build, verify

ROOT = Path(__file__).resolve().parents[2]
radar = ROOT / "threads/radar"
inbox = sorted((radar / "inbox").glob("windsor-*-retrieved.json"))
assert len(inbox) >= 2, "Expected at least two saved inbox files"
with tempfile.TemporaryDirectory(prefix="radar-promotion-rehearsal-") as tmp:
    scratch = Path(tmp)
    for rel in ["posts.json", "threads/full-posts-verified.json", "threads/posts-by-format.json",
                "threads/radar/index/posts.jsonl", "threads/radar/index/editorial.jsonl",
                "threads/radar/index/manifest.json",
                "threads/radar/snapshots/author-continuations-2026-10-23.json"]:
        dest = scratch / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    target = scratch / "threads/radar/snapshots"
    target.mkdir(parents=True, exist_ok=True)
    for source in (radar / "snapshots").glob("windsor-*.json"):
        shutil.copy2(source, target / source.name)
    for n, source in enumerate(inbox):
        doc = json.loads(source.read_text(encoding="utf-8"))
        assert doc.get("account") == "mirpottera"
        assert doc.get("state") == "INBOX_NOT_INDEXED"
        assert doc.get("source") == "Windsor.ai Threads"
        assert doc.get("count") == len(doc.get("posts", []))
        assert doc.get("full_account_export_confirmed") is not True
        # Preserve original rows and timestamps; only change quarantine envelope.
        doc.pop("state", None)
        doc["source_inbox_file"] = source.name
        (target / ("windsor-promoted-" + str(n) + "-" + source.stem + ".json")).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    result = build(scratch)
    check = verify(scratch)
    assert result["total_author_roots"] == 459, result
    assert check["posts"] == 459, check
    print(json.dumps({"status": "REHEARSAL_PASS", "roots": 459,
                      "new_roots": 5, "source_inboxes": len(inbox),
                      "source_checkout_modified": False}, indent=2))
