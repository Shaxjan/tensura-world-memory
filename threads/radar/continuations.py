"""Validate and attach near-immediate own-root replies for search only.

Never promote conversations, late replies, or external-root comments.
Do not mark a thread complete merely because one response was found.
"""
import json
from datetime import datetime
from pathlib import Path


def attach_author_continuations(posts, snapshot_path):
    source = Path(snapshot_path)
    if not source.exists():
        return {"parts": 0, "roots": 0}
    doc = json.loads(source.read_text(encoding="utf-8"))
    parts = doc.get("continuations")
    if not isinstance(parts, list) or doc.get("continuation_count") != len(parts):
        raise ValueError("Incomplete author continuation snapshot")
    by_id = {str(p["post_id"]): p for p in posts}
    seen = set()
    grouped = {}
    for item in parts:
        reply_id = str(item.get("reply_id") or "")
        root_id = str(item.get("root_post_id") or "")
        if not reply_id or reply_id in seen:
            raise ValueError("Missing or duplicate continuation reply_id")
        seen.add(reply_id)
        root = by_id.get(root_id)
        if root is None or root.get("source") == "verified_full_chain":
            raise ValueError("Continuation refers to absent/newly incompatible root")
        if (item.get("classification") != "PROBABLE_CONTINUATION"
                or str(item.get("reply_to_id")) != root_id):
            raise ValueError("Conversation reply may not become continuation")
        date_fmt = "%Y-%m-%dT%H:%M:%S%z"
        lag = (datetime.strptime(item["published_at"], date_fmt)
               - datetime.strptime(root["published_at"], date_fmt)).total_seconds()
        if not 0 <= lag <= 90 or not (item.get("original_text") or "").strip():
            raise ValueError("Invalid continuation time or empty text")
        grouped.setdefault(root_id, []).append(item)
    for root_id, continuation_parts in grouped.items():
        root = by_id[root_id]
        continuation_parts.sort(key=lambda x: (x["published_at"], x["reply_id"]))
        root["author_continuation_parts"] = [
            {"reply_id": x["reply_id"], "published_at": x["published_at"],
             "text": x["original_text"]} for x in continuation_parts
        ]
        root["search_text"] += "\n\n" + "\n\n".join(x["original_text"] for x in continuation_parts)
        root["parts_count"] += len(continuation_parts)
        root["continuations_status"] = "PROBABLE_NOT_CHAIN_VERIFIED"
        # Chain completeness must remain False until an independent audit.
    return {"parts": len(parts), "roots": len(grouped)}
