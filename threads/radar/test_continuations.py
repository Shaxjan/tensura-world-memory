"""Offline tests for cautious indexing of account-authored continuations."""
import json
import tempfile
import unittest
from pathlib import Path

from continuations import attach_author_continuations


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "author-continuations.json"
        self.posts = [{"post_id": "123", "source": "windsor_root_snapshot",
                       "published_at": "2026-10-13T08:00:00+0000",
                       "search_text": "Начало рассказа", "original_text": "Начало рассказа",
                       "parts_count": 1, "chain_complete": False}]
        self.part = {"reply_id": "456", "root_post_id": "123",
                     "reply_to_id": "123", "published_at": "2026-10-13T08:00:09+0000",
                     "original_text": "Завершение рассказа",
                     "classification": "PROBABLE_CONTINUATION"}
        self.save()

    def save(self, entries=None):
        rows = [self.part] if entries is None else entries
        self.file.write_text(json.dumps({"continuation_count": len(rows),
                                         "continuations": rows}, ensure_ascii=False),
                             encoding="utf-8")

    def test_immediate_reply_added_to_search_not_original(self):
        result = attach_author_continuations(self.posts, self.file)
        self.assertEqual(result, {"parts": 1, "roots": 1})
        self.assertIn("Завершение", self.posts[0]["search_text"])
        self.assertNotIn("Завершение", self.posts[0]["original_text"])
        self.assertFalse(self.posts[0]["chain_complete"])
        self.assertEqual(self.posts[0]["parts_count"], 2)

    def test_unrelated_late_reply_is_refused(self):
        self.part["published_at"] = "2026-10-13T10:00:00+0000"
        self.save()
        with self.assertRaises(ValueError):
            attach_author_continuations(self.posts, self.file)

    def test_nested_conversation_is_refused(self):
        self.part["reply_to_id"] = "999"
        self.save()
        with self.assertRaises(ValueError):
            attach_author_continuations(self.posts, self.file)

    def test_unrecognized_root_is_refused(self):
        self.part["root_post_id"] = "999"
        self.part["reply_to_id"] = "999"
        self.save()
        with self.assertRaises(ValueError):
            attach_author_continuations(self.posts, self.file)

    def test_historic_source_cannot_be_duplicated(self):
        self.posts[0]["source"] = "verified_full_chain"
        with self.assertRaises(ValueError):
            attach_author_continuations(self.posts, self.file)

    def test_duplicate_reply_id_is_refused(self):
        self.save([self.part, dict(self.part)])
        with self.assertRaises(ValueError):
            attach_author_continuations(self.posts, self.file)

    def test_empty_reply_is_refused(self):
        self.part["original_text"] = " "
        self.save()
        with self.assertRaises(ValueError):
            attach_author_continuations(self.posts, self.file)

    def test_optional_snapshot_is_safe(self):
        result = attach_author_continuations(self.posts, self.file.parent / "missing.json")
        self.assertEqual(result, {"parts": 0, "roots": 0})
        self.assertEqual(self.posts[0]["parts_count"], 1)


if __name__ == "__main__":
    unittest.main()
