#!/usr/bin/env python3
"""Threads editorial radar: reproducible index and transparent lexical search.

Stage B only. Lexical matches do NOT establish a semantic duplicate or NEW_STORY.
Requires Python 3.10+; no third-party packages, credentials or browser processes.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STOP = {"и", "в", "на", "по", "с", "к", "о", "за", "не", "а", "но", "или", "что", "это", "как", "из", "от", "для", "же", "он", "она", "его", "её"}
TOKEN = re.compile(r"(?u)\b\w{2,}\b")


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def ensure_unique(rows: list[dict], field: str) -> None:
    values = [row.get(field) for row in rows]
    if any(not v for v in values) or len(set(values)) != len(values):
        raise ValueError(f"Missing or duplicate {field}")


def build(root: Path = REPO, snapshot_path: Path | None = None) -> dict:
    base = root / "threads"
    radar = base / "radar"
    if snapshot_path is None:
        snapshot_path = radar / "snapshots" / "windsor-2026-10-13_to_2026-10-20.json"

    full = load_json(base / "full-posts-verified.json")
    formats = load_json(base / "posts-by-format.json")
    editor = load_json(root / "posts.json")
    snapshot = load_json(snapshot_path)

    historical = full["posts"]
    ensure_unique(historical, "post_id")
    if full.get("total_posts") != len(historical):
        raise ValueError("The verified archive's declared count does not match its posts")

    historical_ids = {p["post_id"] for p in historical}
    format_rows = [
        p for key, group in formats["formats"].items()
        for p in group if key != "REPOST_FACADE"
    ]
    ensure_unique(format_rows, "post_id")
    if set(p["post_id"] for p in format_rows) != historical_ids:
        raise ValueError("Verified roots and old Windsor roots differ: reconcile sources first")

    fresh_rows = snapshot["posts"]
    ensure_unique(fresh_rows, "post_id")
    if snapshot.get("count") != len(fresh_rows):
        raise ValueError("New snapshot is incomplete")
    new_rows = [p for p in fresh_rows if p["post_id"] not in historical_ids]
    new_author = [p for p in new_rows if p["post_media_type"] != "REPOST_FACADE"]

    posts = []
    for p in historical:
        posts.append({
            "schema_version": 1, "post_id": p["post_id"], "state": "published",
            "source": "verified_full_chain", "url": p["url"],
            "published_at": p["published_at"], "media_type": p["media_type"],
            "original_text": p.get("full_text_original") or p.get("original_first_text") or "",
            "search_text": p.get("full_text_editorial") or p.get("original_first_text") or "",
            "parts_count": p["parts_count"], "chain_complete": True,
            "metrics": p.get("metrics"), "quality_flags": p.get("completeness", {}).get("review_reasons") or [],
        })
    for p in new_author:
        posts.append({
            "schema_version": 1, "post_id": p["post_id"], "state": "published",
            "source": "windsor_root_2026-10-20", "url": p["post_permalink"],
            "published_at": p["post_timestamp"], "media_type": p["post_media_type"],
            "original_text": p.get("post_text") or "", "search_text": p.get("post_text") or "",
            "parts_count": 1, "chain_complete": False,
            "metrics": {"views": p.get("post_views")},
            "quality_flags": ["author_replies_not_yet_reconciled"],
        })
    ensure_unique(posts, "post_id")
    posts.sort(key=lambda p: (p["published_at"], p["post_id"]))

    url_to_id = {p["url"]: p["post_id"] for p in posts}
    journal = []
    ensure_unique(editor["posts"], "id")
    for p in editor["posts"]:
        url = p.get("url") or p.get("post_permalink") or p.get("thread_url")
        linked_id = url_to_id.get(url)
        journal.append({
            "schema_version": 1, "journal_id": p["id"],
            "date": p.get("date"), "slot": p.get("slot"),
            "state": p.get("status", "unknown"), "topic": p.get("topic") or "",
            "angle": p.get("angle") or "", "text": p.get("final_text") or "",
            "format": p.get("format") or "", "url": url or None,
            "linked_post_id": linked_id,
            "link_status": "confirmed_url" if linked_id else "unresolved",
            "original_metadata": p.get("notes"),
        })
    journal.sort(key=lambda p: (str(p["date"] or ""), p["journal_id"]))

    out = radar / "index"
    write_jsonl(out / "posts.jsonl", posts)
    write_jsonl(out / "editorial.jsonl", journal)
    old_manifest = load_json(out / "manifest.json") if (out / "manifest.json").exists() else {}
    counts = {
        "snapshot_records": len(fresh_rows),
        "snapshot_reposts": len(new_rows) - len(new_author),
        "historic_posts": len(historical),
        "new_author_roots": len(new_author),
        "total_author_roots": len(posts),
        "journal_cards": len(journal),
        "journal_state_counts": dict(Counter(p["state"] for p in journal)),
        "duplicate_ids": 0,
        "unresolved_journal_links": sum(not p["linked_post_id"] for p in journal),
    }
    manifest = {
        "schema_version": 1, "account": "mirpottera",
        "source_commit": old_manifest.get("source_commit"),
        "full_archive_blob_sha": old_manifest.get("full_archive_blob_sha"),
        "posts_journal_blob_sha": old_manifest.get("posts_journal_blob_sha"),
        "source_snapshot": str(snapshot_path.relative_to(root)).replace("\\", "/") if snapshot_path.is_relative_to(root) else str(snapshot_path),
        "source_types": ["verified_full_chain", "Windsor.ai Threads", "editorial posts.json"],
        "generated_date_utc": snapshot.get("retrieval_date_utc"),
        "counts": counts,
        "limitations": [
            "New roots only: replies after 12 October not reconciled",
            "Journal records without matching URL remain independent; historical scheduled status is preserved",
            "Semantic story-angle metadata and full-corpus meaning scores are not yet verified",
            "Live Windsor.ai snapshot values may be cached",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return counts


def verify(root: Path = REPO) -> dict:
    path = root / "threads" / "radar" / "index"
    posts = read_jsonl(path / "posts.jsonl")
    journal = read_jsonl(path / "editorial.jsonl")
    manifest = load_json(path / "manifest.json")
    ensure_unique(posts, "post_id")
    ensure_unique(journal, "journal_id")
    counts = manifest["counts"]
    if len(posts) != counts["total_author_roots"] or len(journal) != counts["journal_cards"]:
        raise ValueError("Index count differs from manifest")
    if dict(Counter(p["state"] for p in journal)) != counts["journal_state_counts"]:
        raise ValueError("Editorial status mismatch")
    if counts["unresolved_journal_links"] != sum(not p["linked_post_id"] for p in journal):
        raise ValueError("Unresolved editorial link mismatch")
    ids = {p["post_id"] for p in posts}
    for p in posts:
        if not p.get("url") or not p.get("published_at") or p["state"] != "published":
            raise ValueError(f"Malformed published post {p.get('post_id')}")
    for p in journal:
        if p["linked_post_id"] and p["linked_post_id"] not in ids:
            raise ValueError(f"Broken journal link {p['journal_id']}")
    return {"ok": True, "posts": len(posts), "journal": len(journal), "states": counts["journal_state_counts"], "unresolved_journal_links": counts["unresolved_journal_links"]}


def keywords(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower().replace("ё", "е")) if t not in STOP]


def prefix(word: str) -> str:
    return word[:max(3, len(word)-2)] if len(word) >= 5 else word


def search(root: Path, query: str, limit: int = 8) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    path = root / "threads" / "radar" / "index"
    posts = read_jsonl(path / "posts.jsonl")
    journal = read_jsonl(path / "editorial.jsonl")
    terms = list(dict.fromkeys(keywords(query)))
    if not terms:
        return []
    post_by_id = {p["post_id"]: p for p in posts}
    journal_by_id = {p["journal_id"]: p for p in journal}
    entries = [
        ("published", p["post_id"], p["search_text"] or p["original_text"])
        for p in posts
    ] + [
        ("editorial", p["journal_id"], " ".join([p["topic"], p["angle"], p["text"]]))
        for p in journal
    ]
    matches = []
    # FTS5 is an accelerator, not a semantic similarity engine.
    try:
        with sqlite3.connect(":memory:") as conn:
            conn.execute('CREATE VIRTUAL TABLE docs USING fts5(kind UNINDEXED, entity_id UNINDEXED, body, tokenize="unicode61")')
            conn.executemany("INSERT INTO docs(kind,entity_id,body) VALUES (?,?,?)", entries)
            expression = " OR ".join(prefix(t) + "*" for t in terms)
            matches = conn.execute("SELECT kind,entity_id FROM docs WHERE docs MATCH ? LIMIT 350", (expression,)).fetchall()
    except sqlite3.OperationalError:
        matches = [(kind, entity_id) for kind, entity_id, body in entries if any(prefix(t) in body.lower().replace("ё", "е") for t in terms)]

    scored = []
    for kind, entity_id in matches:
        entry = post_by_id[entity_id] if kind == "published" else journal_by_id[entity_id]
        body = (entry["search_text"] or entry["original_text"]) if kind == "published" else " ".join([entry["topic"], entry["angle"], entry["text"]])
        text_tokens = keywords(body)
        coverage = sum(any(w.startswith(prefix(t)) for w in text_tokens) for t in terms) / len(terms)
        if kind == "published":
            scored.append({"kind": kind, "post_id": entity_id, "state": entry["state"], "url": entry["url"], "date": entry["published_at"], "coverage": round(coverage, 3), "excerpt": body[:360]})
        else:
            scored.append({"kind": kind, "journal_id": entity_id, "state": entry["state"], "url": entry["url"], "date": entry["date"], "coverage": round(coverage, 3), "excerpt": (entry["topic"] + ": " + entry["angle"])[:360], "link_status": entry["link_status"]})
    return sorted(scored, key=lambda row: (-row["coverage"], row["kind"] != "editorial", str(row["date"] or ""), row.get("post_id", row.get("journal_id", ""))))[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage B Threads radar. Lexical candidates only; no automatic originality verdict.")
    parser.add_argument("--repo-root", type=Path, default=REPO)
    sub = parser.add_subparsers(dest="cmd", required=True)
    builder = sub.add_parser("build", help="Rebuild deterministic indexes from unchanged source archives")
    builder.add_argument("--snapshot", type=Path)
    sub.add_parser("verify", help="Check index integrity and editorial status isolation")
    finder = sub.add_parser("search", help="Find preliminary lexical matches, including scheduled stories")
    finder.add_argument("query")
    finder.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    if args.cmd == "build":
        result = build(root, args.snapshot.resolve() if args.snapshot else None)
    elif args.cmd == "verify":
        result = verify(root)
    else:
        result = {"query": args.query, "match_type": "lexical_candidates_not_semantic_verdict", "matches": search(root, args.query, args.limit)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
