"""Offline tests for the Stage B radar index (no Chrome, network or external API)."""
import json
import tempfile
import unittest
from pathlib import Path

from radar import build, read_jsonl, search, verify


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class RadarStageBTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "threads"
        self.snap = self.base / "radar" / "snapshots" / "windsor-2026-10-13_to_2026-10-20.json"
        self.full = {
            "total_posts": 1, "total_parts": 2,
            "posts": [{
                "post_id": "111", "url": "https://www.threads.com/post/111",
                "published_at": "2026-10-12T08:00:00+0000",
                "media_type": "TEXT_POST", "full_text_original": "Молли подарила часы. Реклама.",
                "full_text_editorial": "Молли подарила Гарри часы.",
                "original_first_text": "Молли подарила Гарри часы.",
                "parts_count": 2, "metrics": {"views": 500},
                "completeness": {"review_reasons": []},
            }],
        }
        self.formats = {"formats": {"TEXT_POST": [{"post_id": "111"}], "REPOST_FACADE": [{"post_id": "r0"}]}}
        self.new = {
            "count": 2, "retrieval_date_utc": "2026-10-20",
            "posts": [
                {"post_id": "222", "post_media_type": "TEXT_POST",
                 "post_permalink": "https://www.threads.com/post/222",
                 "post_timestamp": "2026-10-19T14:00:00+0000",
                 "post_text": "Хагрид сделал фотоальбом для Гарри.", "post_views": 100},
                {"post_id": "r1", "post_media_type": "REPOST_FACADE",
                 "post_permalink": "https://www.threads.com/post/r1",
                 "post_timestamp": "2026-10-19T16:00:00+0000",
                 "post_text": None, "post_views": 0},
            ],
        }
        self.editor = {"posts": [
            {"id": "scheduled-watch", "date": "2026-10-21", "slot": "15:00",
             "status": "scheduled", "topic": "Молли и часы", "angle": "Другая точка зрения"},
            {"id": "already-published", "date": "2026-10-12", "slot": "11:00",
             "status": "published", "topic": "Хагрид и фотоальбом"},
        ]}
        self.save()

    def save(self):
        dump(self.base / "full-posts-verified.json", self.full)
        dump(self.base / "posts-by-format.json", self.formats)
        dump(self.root / "posts.json", self.editor)
        dump(self.snap, self.new)

    def test_build_counts_and_repost_exclusion(self):
        counts = build(self.root)
        self.assertEqual(counts["total_author_roots"], 2)
        self.assertEqual(counts["snapshot_reposts"], 1)
        self.assertEqual(counts["journal_state_counts"], {"scheduled": 1, "published": 1})
        self.assertEqual(verify(self.root)["posts"], 2)
        self.assertEqual({x["post_id"] for x in read_jsonl(self.base / "radar" / "index" / "posts.jsonl")}, {"111", "222"})

    def test_scheduled_remains_unpublished_and_independent(self):
        build(self.root)
        journal = read_jsonl(self.base / "radar" / "index" / "editorial.jsonl")
        card = next(x for x in journal if x["journal_id"] == "scheduled-watch")
        self.assertEqual(card["state"], "scheduled")
        self.assertIsNone(card["linked_post_id"])
        self.assertEqual(card["link_status"], "unresolved")

    def test_full_original_preserved_separately_from_editorial(self):
        build(self.root)
        post = read_jsonl(self.base / "radar" / "index" / "posts.jsonl")[0]
        self.assertIn("Реклама", post["original_text"])
        self.assertNotIn("Реклама", post["search_text"])

    def test_search_finds_both_archived_and_scheduled_topics(self):
        build(self.root)
        matches = search(self.root, "Молли часы", limit=10)
        self.assertTrue(any(m.get("post_id") == "111" for m in matches))
        self.assertTrue(any(m.get("journal_id") == "scheduled-watch" and m["state"] == "scheduled" for m in matches))

    def test_rebuild_is_idempotent(self):
        a = build(self.root)
        folder = self.base / "radar" / "index"
        before = [(p.name, p.read_bytes()) for p in sorted(folder.glob("*"))]
        b = build(self.root)
        after = [(p.name, p.read_bytes()) for p in sorted(folder.glob("*"))]
        self.assertEqual(a, b)
        self.assertEqual(before, after)

    def test_duplicate_new_ids_fail_before_writing(self):
        self.new["posts"].append(dict(self.new["posts"][0]))
        self.new["count"] += 1
        self.save()
        with self.assertRaises(ValueError):
            build(self.root)
        self.assertFalse((self.base / "radar" / "index" / "posts.jsonl").exists())

    def test_historical_mismatch_fails(self):
        self.formats["formats"]["TEXT_POST"][0]["post_id"] = "not-found"
        self.save()
        with self.assertRaises(ValueError):
            build(self.root)


if __name__ == "__main__":
    unittest.main()
