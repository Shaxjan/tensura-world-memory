from __future__ import annotations

import hashlib
import hmac
import json
import os
import queue
import re
import subprocess
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REQUEST_RE = re.compile(r"^runtime/requests/(?:r\d{6}|q-[^/]+)\.json$")


def _json_load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object in {path}")
    return data


def verify_github_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def request_paths_from_push(payload: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    for commit in payload.get("commits") or []:
        if not isinstance(commit, dict):
            continue
        for field in ("added", "modified"):
            for value in commit.get(field) or []:
                if isinstance(value, str) and REQUEST_RE.match(value):
                    found.add(value)
    return sorted(found)


def transport_mode(repo_root: Path) -> str:
    path = repo_root / "runtime/transport_mode.json"
    if not path.exists():
        return "github_actions"
    try:
        value = _json_load(path).get("mode")
    except Exception:
        return "invalid"
    return str(value or "invalid")


def _run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


class RuntimeService:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.branch = os.getenv("TENSURA_BRANCH", "main")
        self.remote = os.getenv("TENSURA_GIT_REMOTE", "origin")
        self.required_mode = os.getenv("TENSURA_REQUIRED_TRANSPORT_MODE", "always_on_service")
        self.queue: queue.Queue[tuple[str, str | None]] = queue.Queue(maxsize=256)
        self.lock = threading.RLock()
        self.started_at = time.time()
        self.last_result: dict[str, Any] | None = None
        self.worker = threading.Thread(target=self._worker_loop, name="tensura-runtime-worker", daemon=True)
        self.worker.start()

    def mode(self) -> str:
        return transport_mode(self.repo_root)

    def enabled(self) -> bool:
        return self.mode() == self.required_mode

    def health(self) -> dict[str, Any]:
        pointer: dict[str, Any] = {}
        try:
            pointer = _json_load(self.repo_root / "runtime/runtime_state.json")
        except Exception:
            pass
        return {
            "ok": True,
            "service": "tensura-always-on-runtime",
            "service_version": "0.1.0",
            "uptime_seconds": int(time.time() - self.started_at),
            "transport_mode": self.mode(),
            "processing_enabled": self.enabled(),
            "queue_depth": self.queue.qsize(),
            "engine_version": pointer.get("engine_version"),
            "journal_seq": pointer.get("journal_seq"),
            "last_result": self.last_result,
        }

    def enqueue(self, request_path: str, delivery_id: str | None = None) -> dict[str, Any]:
        if not REQUEST_RE.match(request_path):
            raise ValueError("invalid runtime request path")
        if not self.enabled():
            return {"accepted": False, "reason": "transport_mode_not_active", "mode": self.mode()}
        self.queue.put_nowait((request_path, delivery_id))
        return {"accepted": True, "request_path": request_path, "delivery_id": delivery_id}

    def _worker_loop(self) -> None:
        while True:
            request_path, delivery_id = self.queue.get()
            try:
                self.last_result = self.process_existing_request(request_path, delivery_id=delivery_id)
            except Exception as exc:  # service must stay alive after one bad request
                self.last_result = {
                    "ok": False,
                    "request_path": request_path,
                    "delivery_id": delivery_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            finally:
                self.queue.task_done()

    def _sync_main(self) -> None:
        _run(["git", "fetch", self.remote, self.branch], self.repo_root)
        _run(["git", "reset", "--hard", f"{self.remote}/{self.branch}"], self.repo_root)

    def _receipt_path(self, request_path: str) -> Path:
        return self.repo_root / "runtime/request_receipts" / f"{Path(request_path).stem}.receipt.json"

    def _processor_for_engine(self) -> str:
        engine = str(_json_load(self.repo_root / "runtime/runtime_state.json").get("engine_version"))
        if engine == "1.0.12":
            return "sim_engine/v112_request_processor.py"
        raise RuntimeError(f"always-on service does not support engine {engine}")

    def _write_receipt(self, request_path: str, *, status: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        cmd = [
            "python3",
            "sim_engine/v112_receipt.py",
            "--repo-root",
            ".",
            "--request",
            request_path,
            "--status",
            status,
        ]
        if result:
            if result.get("seq") is not None:
                cmd += ["--seq", str(result["seq"])]
            if result.get("event_key"):
                cmd += ["--event-key", str(result["event_key"])]
            if result.get("request_mode"):
                cmd += ["--request-mode", str(result["request_mode"])]
        if error:
            cmd += ["--error", error[-4000:]]
        _run(cmd, self.repo_root)

    def _commit_and_push(self, message: str, *, include_request: str | None = None) -> str | None:
        paths = [
            "runtime/journal",
            "runtime/runtime_state.json",
            "runtime/session_state.json",
            "runtime/request_receipts",
        ]
        if include_request:
            paths.append(include_request)
        _run(["git", "add", "--", *paths], self.repo_root)
        diff = _run(["git", "diff", "--cached", "--quiet"], self.repo_root, check=False)
        if diff.returncode == 0:
            return None
        _run(["git", "commit", "-m", message], self.repo_root)
        push = _run(["git", "push", self.remote, f"HEAD:{self.branch}"], self.repo_root, check=False)
        if push.returncode != 0:
            pull = _run(["git", "pull", "--rebase", self.remote, self.branch], self.repo_root, check=False)
            if pull.returncode != 0:
                _run(["git", "rebase", "--abort"], self.repo_root, check=False)
                raise RuntimeError(f"push rejected and rebase failed: {pull.stderr[-1200:]}")
            push2 = _run(["git", "push", self.remote, f"HEAD:{self.branch}"], self.repo_root, check=False)
            if push2.returncode != 0:
                raise RuntimeError(f"push failed after rebase: {push2.stderr[-1200:]}")
        return _run(["git", "rev-parse", "HEAD"], self.repo_root).stdout.strip()

    def process_existing_request(self, request_path: str, *, delivery_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            self._sync_main()
            if not self.enabled():
                return {"ok": False, "ignored": True, "reason": "transport_mode_not_active", "mode": self.mode()}
            req = self.repo_root / request_path
            if not req.exists():
                raise FileNotFoundError(request_path)
            receipt = self._receipt_path(request_path)
            if receipt.exists():
                existing = _json_load(receipt)
                return {"ok": True, "idempotent": True, "receipt": existing}

            processor = self._processor_for_engine()
            out = self.repo_root / ".runtime-service-result.json"
            proc = _run(
                ["python3", processor, "--repo-root", ".", "--request", request_path, "--out", str(out)],
                self.repo_root,
                check=False,
            )
            if proc.returncode != 0:
                error = (proc.stderr or proc.stdout or "runtime processor failed")[-4000:]
                self._write_receipt(request_path, status="failed", error=error)
                commit = self._commit_and_push(f"Runtime request failure receipt {Path(request_path).name}")
                return {"ok": False, "request_path": request_path, "delivery_id": delivery_id, "error": error, "commit": commit}

            result = _json_load(out)
            self._write_receipt(request_path, status="executed", result=result)
            commit = self._commit_and_push(f"Runtime event {Path(request_path).stem}")
            session = _json_load(self.repo_root / "runtime/session_state.json")
            return {
                "ok": True,
                "request_path": request_path,
                "delivery_id": delivery_id,
                "result": result,
                "commit": commit,
                "session_seq": session.get("journal_seq"),
                "last_turn_event_key": (session.get("last_turn") or {}).get("event_key"),
            }

    def process_direct_turn(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_text = payload.get("raw_text")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError("raw_text required")
        with self.lock:
            self._sync_main()
            if not self.enabled():
                raise RuntimeError(f"transport mode is {self.mode()}, not {self.required_mode}")
            session = _json_load(self.repo_root / "runtime/session_state.json")
            current_key = (session.get("last_turn") or {}).get("event_key")
            expected = payload.get("expected_last_gameplay_turn_key", current_key)
            event_key = payload.get("event_key")
            if not isinstance(event_key, str) or not event_key:
                event_key = f"api-{int(time.time())}-{uuid.uuid4().hex[:10]}"
            request_name = f"q-api-{uuid.uuid4().hex}.json"
            request_path = f"runtime/requests/{request_name}"
            request = {
                "format": "TENSURA_FAST_TURN_REQUEST",
                "schema_version": 1,
                "event_key": event_key,
                "event_type": "player_turn",
                "expected_last_gameplay_turn_key": expected,
                "request": {"raw_text": raw_text},
            }
            (self.repo_root / request_path).write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            processor = self._processor_for_engine()
            out = self.repo_root / ".runtime-service-result.json"
            proc = _run(
                ["python3", processor, "--repo-root", ".", "--request", request_path, "--out", str(out)],
                self.repo_root,
                check=False,
            )
            if proc.returncode != 0:
                error = (proc.stderr or proc.stdout or "runtime processor failed")[-4000:]
                self._write_receipt(request_path, status="failed", error=error)
                commit = self._commit_and_push(f"Runtime direct turn failure {Path(request_path).stem}", include_request=request_path)
                raise RuntimeError(f"direct turn failed; receipt committed at {commit}: {error}")

            result = _json_load(out)
            self._write_receipt(request_path, status="executed", result=result)
            commit = self._commit_and_push(f"Runtime direct turn {Path(request_path).stem}", include_request=request_path)
            session = _json_load(self.repo_root / "runtime/session_state.json")
            return {"ok": True, "commit": commit, "result": result, "session": session}


class Handler(BaseHTTPRequestHandler):
    service: RuntimeService
    webhook_secret: str
    api_token: str

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"http {self.address_string()} {fmt % args}")

    def _reply(self, status: int, data: dict[str, Any]) -> None:
        body = (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 1_000_000:
            raise ValueError("invalid content length")
        return self.rfile.read(length)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._reply(HTTPStatus.OK, self.service.health())
            return
        self._reply(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        try:
            body = self._body()
            if self.path == "/github-webhook":
                if not verify_github_signature(self.webhook_secret, body, self.headers.get("X-Hub-Signature-256")):
                    self._reply(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "bad_signature"})
                    return
                if self.headers.get("X-GitHub-Event") != "push":
                    self._reply(HTTPStatus.ACCEPTED, {"ok": True, "ignored": True, "reason": "not_push"})
                    return
                payload = json.loads(body.decode("utf-8"))
                if payload.get("ref") != f"refs/heads/{self.service.branch}":
                    self._reply(HTTPStatus.ACCEPTED, {"ok": True, "ignored": True, "reason": "other_branch"})
                    return
                paths = request_paths_from_push(payload)
                if not paths:
                    self._reply(HTTPStatus.ACCEPTED, {"ok": True, "ignored": True, "reason": "no_runtime_request"})
                    return
                if len(paths) != 1:
                    self._reply(HTTPStatus.CONFLICT, {"ok": False, "error": "expected_one_runtime_request", "paths": paths})
                    return
                result = self.service.enqueue(paths[0], self.headers.get("X-GitHub-Delivery"))
                self._reply(HTTPStatus.ACCEPTED, result)
                return

            if self.path == "/turn":
                auth = self.headers.get("Authorization", "")
                if not self.api_token or not hmac.compare_digest(auth, f"Bearer {self.api_token}"):
                    self._reply(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                    return
                payload = json.loads(body.decode("utf-8"))
                result = self.service.process_direct_turn(payload)
                self._reply(HTTPStatus.OK, result)
                return

            self._reply(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
        except queue.Full:
            self._reply(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "queue_full"})
        except Exception as exc:
            self._reply(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def main() -> None:
    repo_root = Path(os.getenv("TENSURA_REPO_PATH", "/srv/tensura"))
    webhook_secret = os.getenv("TENSURA_GITHUB_WEBHOOK_SECRET", "")
    api_token = os.getenv("TENSURA_API_TOKEN", "")
    if not webhook_secret:
        raise SystemExit("TENSURA_GITHUB_WEBHOOK_SECRET is required")
    service = RuntimeService(repo_root)
    Handler.service = service
    Handler.webhook_secret = webhook_secret
    Handler.api_token = api_token
    host = os.getenv("TENSURA_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(json.dumps({"service": "tensura-always-on-runtime", "listen": f"{host}:{port}", "repo": str(repo_root)}, ensure_ascii=False))
    server.serve_forever()


if __name__ == "__main__":
    main()
