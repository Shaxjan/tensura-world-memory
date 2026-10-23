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

    def test_original_only_detail_remains_discoverable(self):
        build(self.root)
        matches = search(self.root, "Молли реклама", limit=10)
        matched = [m for m in matches if m.get("post_id") == "111"]
        self.assertTrue(matched, "Full source must be searched to avoid missing a continuation")
        self.assertTrue(matched[0]["matched_in_original_only"])
        self.assertNotIn("Реклама", matched[0]["excerpt"])

    def test_large_fts_candidate_set_does_not_hide_strong_match(self):
        original = self.full["posts"][0]
        self.full["posts"] = []
        for idx in range(360):
            row = dict(original)
            row["post_id"] = str(2000 + idx)
            row["url"] = "https://www.threads.com/post/" + row["post_id"]
            row["full_text_original"] = "Кит просто плавает."
            row["full_text_editorial"] = "Кит просто плавает."
            row["original_first_text"] = "Кит просто плавает."
            self.full["posts"].append(row)
        target = self.full["posts"][-1]
        target["full_text_original"] = "Кит и слон спорят о значении рассказа."
        target["full_text_editorial"] = target["full_text_original"]
        target["original_first_text"] = target["full_text_original"]
        self.full["total_posts"] = len(self.full["posts"])
        self.formats["formats"]["TEXT_POST"] = [
            {"post_id": row["post_id"]} for row in self.full["posts"]
        ]
        self.save()
        build(self.root)
        matches = search(self.root, "кит слон", limit=5)
        self.assertTrue(
            any(m.get("post_id") == target["post_id"] for m in matches),
            "FTS candidate cutoff omitted the strongest late-indexed story",
        )

    def test_rebuild_refuses_missing_previously_indexed_snapshot(self):
        build(self.root)
        posts_path = self.base / "radar" / "index" / "posts.jsonl"
        before = posts_path.read_bytes()
        self.snap.unlink()
        dump(self.snap.parent / "windsor-2026-10-21.json", {
            "count": 1, "retrieval_date_utc": "2026-10-21", "posts": [dict(
                self.new["posts"][1], post_id="333", post_media_type="TEXT_POST",
                post_text="Новый текст", post_views=7)],
        })
        with self.assertRaisesRegex(ValueError, "discard published post IDs"):
            build(self.root)
        self.assertEqual(before, posts_path.read_bytes())

    def test_rebuild_refuses_historical_text_replacement(self):
        build(self.root)
        posts_path = self.base / "radar" / "index" / "posts.jsonl"
        before = posts_path.read_bytes()
        self.full["posts"][0]["full_text_original"] = "Подменённый исходный текст"
        self.save()
        with self.assertRaisesRegex(ValueError, "immutable original_text"):
            build(self.root)
        self.assertEqual(before, posts_path.read_bytes())

    def test_snapshot_rejects_foreign_account(self):
        self.new["account"] = "another_account"
        self.save()
        with self.assertRaisesRegex(ValueError, "unexpected Threads account"):
            build(self.root)

    def test_snapshot_rejects_invalid_calendar_date(self):
        self.new["retrieval_date_utc"] = "2026-02-30"
        self.save()
        with self.assertRaisesRegex(ValueError, "Invalid snapshot retrieval date"):
            build(self.root)

    def test_snapshot_rejects_invalid_earlier_retrieval(self):
        self.new["retrieval_date_utc"] = "2026-10-18"
        self.save()
        with self.assertRaisesRegex(ValueError, "predates published post"):
            build(self.root)

    def test_snapshot_rejects_invalid_views(self):
        self.new["posts"][0]["post_views"] = -1
        self.save()
        with self.assertRaisesRegex(ValueError, "Invalid snapshot views"):
            build(self.root)

    def test_verify_rejects_tampered_historical_original(self):
        build(self.root)
        index = self.base / "radar" / "index" / "posts.jsonl"
        rows = read_jsonl(index)
        rows[0]["original_text"] = "Подмена в индексе"
        index.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Historical post differs from verified source"):
            verify(self.root)

    def test_verify_does_not_accept_unverified_completed_chain(self):
        build(self.root)
        index = self.base / "radar" / "index" / "posts.jsonl"
        rows = read_jsonl(index)
        for row in rows:
            if row["source"] == "windsor_root_snapshot":
                row["chain_complete"] = True
        index.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "falsely marked complete"):
            verify(self.root)

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


    def test_reviewed_manifest_survives_noop_rebuild(self):
        build(self.root)
        manifest = self.base / "radar" / "index" / "manifest.json"
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        doc["limitations"] = ["Reviewed editorial provenance must remain intact"]
        manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        build(self.root)
        renewed = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(renewed["limitations"], ["Reviewed editorial provenance must remain intact"])

    def test_mixed_snapshot_filenames_use_retrieval_date_order(self):
        # A late-named import contains an older view count; it must not win.
        earlier = dict(self.new["posts"][0], post_views=10)
        dump(self.snap.parent / "windsor-import-2026-10-19-old.json", {
            "count": 1, "retrieval_date_utc": "2026-10-19", "posts": [earlier],
        })
        self.new["posts"][0]["post_views"] = 600
        self.new["retrieval_date_utc"] = "2026-10-23"
        self.save()
        build(self.root)
        indexed = read_jsonl(self.base / "radar" / "index" / "posts.jsonl")
        target = next(row for row in indexed if row["post_id"] == "222")
        self.assertEqual(target["metrics"]["views"], 600)
        manifest = json.loads((self.base / "radar" / "index" / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["source_snapshot"][0].endswith("windsor-import-2026-10-19-old.json"))

    def test_manifest_limits_are_regenerated_for_new_snapshot_date(self):
        build(self.root)
        manifest = self.base / "radar" / "index" / "manifest.json"
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        doc["limitations"] = ["Old text describing obsolete snapshot"]
        manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.new["retrieval_date_utc"] = "2026-10-22"
        self.save()
        build(self.root)
        renewed = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(renewed["generated_date_utc"], "2026-10-22")
        self.assertNotIn("Old text describing obsolete snapshot", renewed["limitations"])
        self.assertTrue(any("2026-10-22" in s for s in renewed["limitations"]))

if __name__ == "__main__":
    unittest.main()
