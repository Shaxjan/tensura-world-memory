"""Offline tests for the full-corpus integration gate; no network or source edits."""
import json
import unittest

from integration_gate import execute, validate_inventory
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


class NativeInventoryContractTests(unittest.TestCase):
    def sample(self):
        return {
            "status": "PENDING_NATIVE_ACCEPTANCE",
            "conflicts": [],
            "baseline_roots": 454,
            "unique_pending_roots": 2,
            "expected_roots_after_verified_promotion": 456,
            "distinct_repost_facades": 1,
            "pending_roots": [{"post_id": "18058181561570070"},
                              {"post_id": "17899242612398487"}],
            "index_modified": False, "source_promoted": False,
            "source_completeness_unverified": True,
        }

    def test_native_inventory_contract_accepts_consistent_report(self):
        self.assertEqual(validate_inventory(self.sample(), 454)["pending_roots"], 2)

    def test_native_inventory_contract_rejects_boolean_and_fractional_counts(self):
        for value in (True, 2.5, -1, "2"):
            with self.subTest(value=value):
                report = self.sample()
                report["unique_pending_roots"] = value
                with self.assertRaises(ValueError):
                    validate_inventory(report, 454)

    def test_native_inventory_contract_rejects_missing_or_duplicate_roots(self):
        for roots in ([], [{"post_id": "18058181561570070"}] * 2):
            with self.subTest(roots=roots):
                report = self.sample()
                report["pending_roots"] = roots
                with self.assertRaises(ValueError):
                    validate_inventory(report, 454)

    def test_native_inventory_contract_rejects_mismatched_baseline_or_writes(self):
        for key, value in (("baseline_roots", 453), ("index_modified", True),
                           ("source_promoted", True), ("conflicts", [{"post_id": "1"}])):
            with self.subTest(key=key):
                report = self.sample()
                report[key] = value
                with self.assertRaises(ValueError):
                    validate_inventory(report, 454)


if __name__ == "__main__":
    unittest.main()
