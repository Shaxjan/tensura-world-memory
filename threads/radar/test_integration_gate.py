"""Offline tests for the full-corpus integration gate; no network or source edits."""
import json
import unittest

from integration_gate import execute
from radar import build
from test_radar import RadarStageBTests


class IntegrationGateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = RadarStageBTests("test_rebuild_is_idempotent")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        build(self.fixture.root)

    def test_gate_rebuilds_scratch_twice_without_touching_source(self):
        folder = self.fixture.root / "threads" / "radar" / "index"
        before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
        result = execute(self.fixture.root, run_tests=False)
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(result["author_roots"], 2)
        self.assertEqual(result["journal_cards"], 2)
        self.assertEqual(result["source_snapshot_files"], 1)
        self.assertEqual(result["rebuilds"], 2)
        self.assertTrue(result["exact_index_bytes_match"])
        self.assertEqual(
            before,
            {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()},
        )

    def test_gate_rejects_tampered_existing_index(self):
        folder = self.fixture.root / "threads" / "radar" / "index"
        posts = folder / "posts.jsonl"
        data = posts.read_text(encoding="utf-8").splitlines()
        first = json.loads(data[0])
        first["original_text"] = "Посторонняя подмена"
        data[0] = json.dumps(first, ensure_ascii=False)
        posts.write_text("\n".join(data) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            execute(self.fixture.root, run_tests=False)

    def test_gate_fails_with_missing_primary_source(self):
        (self.fixture.root / "threads" / "full-posts-verified.json").unlink()
        with self.assertRaises(FileNotFoundError):
            execute(self.fixture.root, run_tests=False)


if __name__ == "__main__":
    unittest.main()
