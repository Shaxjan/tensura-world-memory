"""Regression tests for the read-only stage-8 candidate gate."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from integration_gate import clone_inputs
from stage8_preview import ROOT, preview


class Stage8CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="stage8-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        clone_inputs(ROOT, self.root)
        actual = ROOT / "threads/radar/inbox"
        target = self.root / "threads/radar/inbox"
        target.mkdir(parents=True, exist_ok=True)
        for src in actual.glob("windsor-*-retrieved.json"):
            shutil.copy2(src, target / src.name)
        self.index = self.root / "threads/radar/index/posts.jsonl"
        self.before = self.index.read_bytes()
        self.count = len(self.before.splitlines())

    def add_synthetic(self, *, altered_known=False):
        previous = json.loads((self.root / "threads/radar/inbox" /
            "windsor-20261025T003529Z-eddca5900dc17028-retrieved.json"
        ).read_text(encoding="utf-8"))
        existing = next(p for p in previous["posts"]
                        if p["post_media_type"] == "TEXT_POST")
        item = dict(existing)
        if altered_known:
            item["post_text"] = item["post_text"] + " altered"
            item["post_timestamp"] = existing["post_timestamp"]
        else:
            item.update({
                "post_id": "19999887766554433",
                "post_text": "Синтетическая проверочная публикация",
                "post_permalink": "https://www.threads.com/@mirpottera/post/Stage8Fixture",
                "post_timestamp": "2026-10-25T05:00:00+0000",
            })
        item["data_fetched_at"] = "2026-10-25T06:00:00"
        document = {
            "schema_version": 1, "account": "mirpottera",
            "source": "Windsor.ai Threads", "source_account_id": "28902703019346338",
            "state": "INBOX_NOT_INDEXED", "data_fetched_at_utc": "2026-10-25T06:00:00",
            "retrieval_date_utc": "2026-10-25",
            "period_utc": ["2026-10-25", "2026-10-25"] if not altered_known else
                          [existing["post_timestamp"][:10], existing["post_timestamp"][:10]],
            "count": 1, "read_fields": previous["read_fields"], "posts": [item],
        }
        target = self.root / "threads/radar/inbox/windsor-stage8-synthetic-retrieved.json"
        target.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return target

    def test_legacy_inboxes_are_noop_after_promotion(self):
        answer = preview(self.root)
        self.assertEqual(answer["result"], "NO_NEW_ROOTS")
        self.assertEqual(answer["baseline_roots"], self.count)
        self.assertEqual(answer["pending_ids"], [])
        self.assertEqual(self.index.read_bytes(), self.before)

    def test_new_root_is_accepted_only_in_temporary_candidate(self):
        self.add_synthetic()
        answer = preview(self.root)
        self.assertEqual(answer["result"], "CANDIDATE_PASS")
        self.assertEqual(answer["candidate_roots"], self.count + 1)
        self.assertEqual(answer["pending_ids"], ["19999887766554433"])
        self.assertFalse(answer["source_checkout_modified"])
        self.assertFalse(answer["editorial_approval_granted"])
        self.assertEqual(self.index.read_bytes(), self.before)
        self.assertFalse(list((self.root / "threads/radar/snapshots").glob(
            "*stage8-synthetic*")))

    def test_candidate_output_contains_only_temporary_verified_files(self):
        self.add_synthetic()
        out = self.root.parent / (self.root.name + "-validated")
        self.addCleanup(lambda: shutil.rmtree(out, ignore_errors=True))
        answer = preview(self.root, prepared_dir=out)
        self.assertEqual(answer["result"], "CANDIDATE_PASS")
        self.assertEqual(answer["rebuilds"], 2)
        self.assertEqual(len(list((out / "threads/radar/snapshots").glob("windsor-*.json"))), 1)
        self.assertEqual(len(list((out / "threads/radar/index").iterdir())), 3)
        self.assertEqual(self.index.read_bytes(), self.before)

    def test_cannot_stage_candidate_inside_source(self):
        self.add_synthetic()
        with self.assertRaises(ValueError):
            preview(self.root, prepared_dir=self.root / "untrusted")
        self.assertEqual(self.index.read_bytes(), self.before)

    def test_conflicting_existing_post_blocks_everything(self):
        self.add_synthetic(altered_known=True)
        with self.assertRaises(RuntimeError):
            preview(self.root)
        self.assertEqual(self.index.read_bytes(), self.before)

    def test_modified_original_inbox_is_not_treated_as_immutable(self):
        path = self.root / "threads/radar/inbox/windsor-2026-10-24-retrieved.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["posts"][0]["post_text"] += " injected"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(ValueError):
            preview(self.root)
        self.assertEqual(self.index.read_bytes(), self.before)

    def test_missing_original_inbox_blocks_provenance(self):
        (self.root / "threads/radar/inbox/windsor-2026-10-24-retrieved.json").unlink()
        with self.assertRaises(ValueError):
            preview(self.root)


if __name__ == "__main__":
    unittest.main()
