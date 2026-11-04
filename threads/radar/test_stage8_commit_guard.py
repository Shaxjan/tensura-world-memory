"""Fail-closed stage-8 Git commit allowlist; no Git writes in unit tests."""
import unittest
from stage8_commit_guard import allowed_paths


class Stage8CommitContractTests(unittest.TestCase):
    def report(self):
        return {
            "result": "STAGED_UNCOMMITTED",
            "editorial_approval": False,
            "no_git_push_performed": True,
            "simulation": False,
            "new_roots": 1, "baseline": 459, "candidate_roots": 460,
            "added_ids": ["19999887766553322"],
            "snapshots": ["windsor-promoted-20261025T060000Z-0123456789abcdef.json"],
        }

    def test_single_root_is_staged_only_as_index_snapshot_and_reserve(self):
        allow = allowed_paths(self.report())
        self.assertIn("threads/radar/index/posts.jsonl", allow)
        self.assertIn("threads/radar/reserve/automated-current-screening.json", allow)
        self.assertIn("threads/radar/snapshots/windsor-promoted-20261025T060000Z-0123456789abcdef.json", allow)
        self.assertEqual(len(allow), 6)

    def test_unsafe_status_or_editorial_approval_cannot_stage(self):
        for key, value in (
            ("result", "NO_NEW_ROOTS"),
            ("editorial_approval", True),
            ("no_git_push_performed", False),
            ("simulation", True),
        ):
            with self.subTest(key=key):
                source = self.report()
                source[key] = value
                with self.assertRaises(ValueError):
                    allowed_paths(source)

    def test_bad_counts_and_root_ids_block(self):
        for key, value in (
            ("new_roots", True),
            ("new_roots", 51),
            ("baseline", 458),
            ("candidate_roots", 459),
            ("added_ids", []),
            ("added_ids", ["not_a_post_id"]),
        ):
            with self.subTest(key=key):
                source = self.report()
                source[key] = value
                with self.assertRaises(ValueError):
                    allowed_paths(source)

    def test_snapshot_path_traversal_and_duplicates_block(self):
        for filenames in (
            ["../windsor-promoted-20261025T060000Z-0123456789abcdef.json"],
            ["windsor-promoted-20261025T060000Z-0123456789abcdef.json"] * 2,
            ["windsor-20261025T060000Z-fake.json"],
        ):
            with self.subTest(filenames=filenames):
                source = self.report()
                source["snapshots"] = filenames
                with self.assertRaises(ValueError):
                    allowed_paths(source)

    def test_explicit_simulation_is_allowed_only_in_simulation_mode(self):
        source = self.report()
        source["simulation"] = True
        with self.assertRaises(ValueError):
            allowed_paths(source)
        self.assertIn("threads/radar/index/manifest.json",
                      allowed_paths(source, simulation=True))


if __name__ == "__main__":
    unittest.main()
