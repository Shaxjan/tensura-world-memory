"""Safety regression tests for replaying immutable Windsor snapshots."""
import json
import tempfile
import unittest
from pathlib import Path
from radar import build

def put(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")

class MultiSnapshotIntegrity(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.base = self.root / "threads"
        self.snap = self.base / "radar" / "snapshots"
        self.post = {"post_id":"222","post_media_type":"TEXT_POST","post_permalink":"https://www.threads.com/post/222","post_timestamp":"2026-10-20T08:00:00+0000","post_text":"Первый текст","post_views":12}
        put(self.base / "full-posts-verified.json", {"total_posts":1,"posts":[{"post_id":"111","url":"https://www.threads.com/post/111","published_at":"2026-10-12T08:00:00+0000","media_type":"TEXT_POST","parts_count":1,"full_text_original":"Старый пост"}]})
        put(self.base / "posts-by-format.json", {"formats":{"TEXT_POST":[{"post_id":"111"}]}})
        put(self.root / "posts.json", {"posts":[{"id":"j1","status":"scheduled","topic":"Идея"}]})
        put(self.snap / "windsor-2026-10-20.json", {"count":1,"retrieval_date_utc":"2026-10-20","posts":[self.post]})
    def second(self, changes):
        post=dict(self.post, **changes)
        put(self.snap / "windsor-2026-10-21.json", {"count":1,"retrieval_date_utc":"2026-10-21","posts":[post]})
    def test_metric_refresh_is_allowed(self):
        self.second({"post_views":45})
        self.assertEqual(build(self.root)["total_author_roots"],2)
    def test_text_replacement_is_rejected(self):
        self.second({"post_text":"Подменённый текст"})
        with self.assertRaisesRegex(ValueError,"Conflicting snapshots"):
            build(self.root)
        self.assertFalse((self.base/"radar"/"index"/"posts.jsonl").exists())
    def test_link_replacement_is_rejected(self):
        self.second({"post_permalink":"https://www.threads.com/post/changed"})
        with self.assertRaisesRegex(ValueError,"post_permalink"):
            build(self.root)
