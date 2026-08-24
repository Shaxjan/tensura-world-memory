import hashlib
import hmac
import json
import queue
import tempfile
import unittest
from pathlib import Path

from app import request_paths_from_push, transport_mode, verify_github_signature
from server import RuntimeService as ProductionRuntimeService


class RuntimeServiceUnitTests(unittest.TestCase):
    def test_github_signature(self):
        secret = "secret"
        body = b'{"x":1}'
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_github_signature(secret, body, sig))
        self.assertFalse(verify_github_signature(secret, body, "sha256=bad"))
        self.assertFalse(verify_github_signature("", body, sig))

    def test_request_paths_from_push_exact(self):
        payload = {
            "commits": [
                {"added": ["runtime/requests/q-abc.json", "README.md"], "modified": []},
                {"added": [], "modified": ["runtime/requests/q-abc.json"]},
            ]
        }
        self.assertEqual(request_paths_from_push(payload), ["runtime/requests/q-abc.json"])

    def test_request_paths_reject_nested_or_other_files(self):
        payload = {"commits": [{"added": [
            "runtime/requests/q-x/y.json",
            "runtime/requests/foo.json",
            "runtime/requests/r000021.json",
            "runtime/session_state.json",
        ]}]}
        self.assertEqual(request_paths_from_push(payload), ["runtime/requests/r000021.json"])

    def test_transport_mode_defaults_to_github_actions(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(transport_mode(Path(td)), "github_actions")

    def test_transport_mode_reads_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "runtime").mkdir()
            (root / "runtime/transport_mode.json").write_text(
                json.dumps({"mode": "always_on_service"}), encoding="utf-8"
            )
            self.assertEqual(transport_mode(root), "always_on_service")

    def test_transport_mode_invalid_marker_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "runtime").mkdir()
            (root / "runtime/transport_mode.json").write_text("not-json", encoding="utf-8")
            self.assertEqual(transport_mode(root), "invalid")

    def test_production_enqueue_defers_mode_check_until_worker_sync(self):
        service = object.__new__(ProductionRuntimeService)
        service.queue = queue.Queue(maxsize=2)
        result = service.enqueue("runtime/requests/q-first-after-activation.json", "delivery-1")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["execution_guard"], "fresh_main_transport_mode_in_worker")
        self.assertEqual(service.queue.get_nowait(), ("runtime/requests/q-first-after-activation.json", "delivery-1"))

    def test_production_enqueue_rejects_non_request_path(self):
        service = object.__new__(ProductionRuntimeService)
        service.queue = queue.Queue(maxsize=2)
        with self.assertRaises(ValueError):
            service.enqueue("runtime/session_state.json")


if __name__ == "__main__":
    unittest.main()
