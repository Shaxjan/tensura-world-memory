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
from datetime import date, datetime, timezone
from urllib.parse import urlsplit
from pathlib import Path
from continuations import attach_author_continuations

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
    snapshots = [snapshot_path] if snapshot_path else sorted((radar / "snapshots").glob("windsor-*.json"))
    if not snapshots:
        raise ValueError("No saved Windsor snapshots; refusing to build an incomplete index")
    for snapshot_file in snapshots:
        if not snapshot_file.exists():
            raise ValueError(f"Missing source snapshot: {snapshot_file}")
    snapshot_documents = [load_json(source) for source in snapshots]
    if snapshot_path is None:
        # Filename ordering is not chronology: ``windsor-import-...`` sorts after
        # ``windsor-2026-...``, potentially overwriting newer metrics with old.
        paired = sorted(
            zip(snapshots, snapshot_documents),
            key=lambda pair: (pair[1].get("retrieval_date_utc", ""), pair[0].name),
        )
        snapshots = [source for source, _ in paired]
        snapshot_documents = [doc for _, doc in paired]

    full = load_json(base / "full-posts-verified.json")
    formats = load_json(base / "posts-by-format.json")
    editor = load_json(root / "posts.json")

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

    # Keep the newest snapshot value for a post ID while retaining earlier rows.
    fresh_by_id = {}
    for snapshot in snapshot_documents:
        if snapshot.get("account") not in (None, "mirpottera"):
            raise ValueError("Snapshot belongs to an unexpected Threads account")
        retrieval_day = snapshot.get("retrieval_date_utc")
        try:
            day = date.fromisoformat(retrieval_day)
            if day.isoformat() != retrieval_day:
                raise ValueError("Invalid snapshot retrieval date")
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid snapshot retrieval date") from exc
        rows = snapshot["posts"]
        ensure_unique(rows, "post_id")
        if snapshot.get("count") != len(rows):
            raise ValueError("New snapshot is incomplete")
        for row in rows:
            media = row.get("post_media_type")
            if media not in {"TEXT_POST", "IMAGE", "VIDEO", "CAROUSEL_ALBUM", "REPOST_FACADE"}:
                raise ValueError("Unexpected snapshot media type")
            try:
                post_day = datetime.strptime(row["post_timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc).date()
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Invalid snapshot post timestamp") from exc
            if post_day > day:
                raise ValueError("Snapshot retrieval predates published post")
            permalink = row.get("post_permalink")
            url = urlsplit(permalink) if isinstance(permalink, str) else None
            if (not url or url.scheme != "https" or url.hostname not in ("threads.com", "www.threads.com")
                    or not url.path.startswith(("/post/", "/@mirpottera/post/"))):
                raise ValueError("Unexpected snapshot post permalink")
            if media != "REPOST_FACADE" and not (row.get("post_text") or "").strip():
                raise ValueError("Author root has no text")
            views = row.get("post_views")
            if views is not None and (isinstance(views, bool) or not isinstance(views, (int, float)) or views < 0):
                raise ValueError("Invalid snapshot views")
            previous = fresh_by_id.get(row["post_id"])
            if previous is not None:
                stable_fields = ("post_timestamp", "post_text", "post_permalink", "post_media_type")
                changed = [field for field in stable_fields if (previous.get(field) or "") != (row.get(field) or "")]
                if changed:
                    raise ValueError(
                        f"Conflicting snapshots for {row['post_id']}: {', '.join(changed)}. "
                        "Do not silently replace previously published content."
                    )
            # Updated views are allowed; text, link, media type and timestamp are immutable here.
            fresh_by_id[row["post_id"]] = row
    fresh_rows = list(fresh_by_id.values())
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
            "source": "windsor_root_snapshot", "url": p["post_permalink"],
            "published_at": p["post_timestamp"], "media_type": p["post_media_type"],
            "original_text": p.get("post_text") or "", "search_text": p.get("post_text") or "",
            "parts_count": 1, "chain_complete": False,
            "metrics": {"views": p.get("post_views")},
            "quality_flags": ["author_replies_not_yet_reconciled"],
        })
    ensure_unique(posts, "post_id")
    continuation_path = radar / "snapshots" / "author-continuations-2026-10-23.json"
    attachment = attach_author_continuations(posts, continuation_path)
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
    # Fail closed: a missing snapshot or a replaced source must never silently
    # remove previously published IDs or change their immutable content.
    old_index_file = out / "posts.jsonl"
    if old_index_file.exists():
        previous = read_jsonl(old_index_file)
        new_posts_by_id = {p["post_id"]: p for p in posts}
        for old in previous:
            now = new_posts_by_id.get(old["post_id"])
            if now is None:
                raise ValueError("Rebuild would discard published post IDs")
            for field in ("original_text", "url", "published_at", "media_type", "source"):
                if old.get(field) != now.get(field):
                    raise ValueError(f"Rebuild changed immutable {field} for {old['post_id']}")
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
        "author_continuation_parts": attachment["parts"],
        "author_continuation_roots": attachment["roots"],
    }
    snapshot_paths = [
        str(p.relative_to(root)).replace("\\", "/") if p.is_relative_to(root) else str(p)
        for p in snapshots
    ]
    snapshot_date = max(
        (doc.get("retrieval_date_utc", "") for doc in snapshot_documents), default=""
    )
    continuation_source = (
        str(continuation_path.relative_to(root)).replace("\\", "/")
        if continuation_path.exists() else None
    )
    # Preserve reviewed provenance notes verbatim when all source identity fields
    # and recorded counts are identical. Otherwise generate fresh limitations.
    # This prevents a no-op rebuild from erasing the reviewed manifest.
    same_sources = (
        old_manifest.get("counts") == counts
        and old_manifest.get("source_snapshot") == snapshot_paths
        and old_manifest.get("generated_date_utc") == snapshot_date
        and old_manifest.get("source_author_continuations") == continuation_source
        and isinstance(old_manifest.get("limitations"), list)
    )
    limitations = old_manifest["limitations"] if same_sources else [
        f"{attachment['parts']} probable author continuations may be searched but are not fully verified",
        "Later self-replies and conversational comments must not be appended to root post text",
        "New root chains remain chain_complete=false until independently verified",
        "Unlinked journal cards remain independent, and scheduled is not proof of publication",
        f"Publication data after {snapshot_date} is not indexed; sync remains manual",
        "Semantic comparison is heuristic; literary canon and narrative originality need editor approval",
    ]
    manifest = {
        "schema_version": 1, "account": "mirpottera",
        "source_commit": old_manifest.get("source_commit"),
        "full_archive_blob_sha": old_manifest.get("full_archive_blob_sha"),
        "posts_journal_blob_sha": old_manifest.get("posts_journal_blob_sha"),
        "source_snapshot": snapshot_paths,
        "source_types": ["verified_full_chain", "Windsor.ai Threads", "editorial posts.json"],
        "generated_date_utc": snapshot_date,
        "counts": counts,
        "limitations": limitations,
        "source_author_continuations": continuation_source,
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
    if counts.get("author_continuation_parts", 0) != sum(len(p.get("author_continuation_parts", [])) for p in posts):
        raise ValueError("Continuation parts mismatch")
    if counts.get("author_continuation_roots", 0) != sum(bool(p.get("author_continuation_parts")) for p in posts):
        raise ValueError("Continuation roots mismatch")
    ids = {p["post_id"] for p in posts}
    historic = load_json(root / "threads" / "full-posts-verified.json")
    original_by_id = {p["post_id"]: p for p in historic["posts"]}
    if {p["post_id"] for p in posts if p["source"] == "verified_full_chain"} != set(original_by_id):
        raise ValueError("Verified historical root ID set differs from source")
    for p in posts:
        if not p.get("url") or not p.get("published_at") or p["state"] != "published":
            raise ValueError(f"Malformed published post {p.get('post_id')}")
        if p.get("source") == "verified_full_chain":
            original = original_by_id[p["post_id"]]
            if (p["original_text"] != (original.get("full_text_original") or original.get("original_first_text") or "")
                    or p["search_text"] != (original.get("full_text_editorial") or original.get("original_first_text") or "")
                    or p["url"] != original["url"] or p["parts_count"] != original["parts_count"]
                    or p.get("chain_complete") is not True):
                raise ValueError(f"Historical post differs from verified source {p['post_id']}")
        elif p.get("source") == "windsor_root_snapshot":
            if p.get("chain_complete") is not False:
                raise ValueError(f"Unverified new chain falsely marked complete {p['post_id']}")
        else:
            raise ValueError(f"Unexpected indexed source {p['post_id']}")
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
        ("published", p["post_id"], (p["search_text"] or "") + "\n" + (p["original_text"] or ""))
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
            matches = conn.execute("SELECT kind,entity_id FROM docs WHERE docs MATCH ?", (expression,)).fetchall()
    except sqlite3.OperationalError:
        matches = [(kind, entity_id) for kind, entity_id, body in entries if any(prefix(t) in body.lower().replace("ё", "е") for t in terms)]

    scored = []
    for kind, entity_id in matches:
        entry = post_by_id[entity_id] if kind == "published" else journal_by_id[entity_id]
        body = ((entry["search_text"] or "") + "\n" + (entry["original_text"] or "")) if kind == "published" else " ".join([entry["topic"], entry["angle"], entry["text"]])
        text_tokens = keywords(body)
        coverage = sum(any(w.startswith(prefix(t)) for w in text_tokens) for t in terms) / len(terms)
        if kind == "published":
            scored.append({"kind": kind, "post_id": entity_id, "state": entry["state"], "url": entry["url"], "date": entry["published_at"], "coverage": round(coverage, 3), "excerpt": (entry["search_text"] or entry["original_text"])[:360], "matched_in_original_only": not all(any(w.startswith(prefix(t)) for w in keywords(entry["search_text"])) for t in terms)})
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
