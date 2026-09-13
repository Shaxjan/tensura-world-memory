from __future__ import annotations

import json
import os
import queue
import time
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app import Handler, REQUEST_RE, RuntimeService as BaseRuntimeService, _json_load, _run
from validate_runtime import validate_runtime

SERVICE_VERSION = "0.2.0"


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)


class RuntimeService(BaseRuntimeService):
    """Production transport wrapper with fail-closed persistence hardening.

    A webhook can arrive immediately after the activation marker is pushed while
    this process still has the previous local clone. Therefore enqueue itself
    must not decide transport ownership. The worker syncs fresh main first and
    only then checks the authoritative transport marker.

    The existing v1.0.12 processor remains the only gameplay mutation engine.
    This wrapper adds an independent deterministic replay gate before Git push,
    restores the checkout from authoritative main before writing any failure
    receipt, and emits structured latency telemetry without player raw text.
    """

    def health(self) -> dict[str, Any]:
        data = super().health()
        data["service_version"] = SERVICE_VERSION
        return data

    def enqueue(self, request_path: str, delivery_id: str | None = None) -> dict[str, Any]:
        if not REQUEST_RE.match(request_path):
            raise ValueError("invalid runtime request path")
        self.queue.put_nowait((request_path, delivery_id))
        return {
            "accepted": True,
            "request_path": request_path,
            "delivery_id": delivery_id,
            "execution_guard": "fresh_main_transport_mode_in_worker",
        }

    def _emit_telemetry(
        self,
        *,
        status: str,
        source: str,
        request_path: str,
        timings: dict[str, float],
        delivery_id: str | None = None,
        event_key: str | None = None,
        error_class: str | None = None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "type": "tensura_runtime_latency",
            "service": "tensura-always-on-runtime",
            "service_version": SERVICE_VERSION,
            "status": status,
            "source": source,
            "request_path": request_path,
            "delivery_id": delivery_id,
            "event_key": event_key,
            "latency_ms": timings,
        }
        if error_class:
            record["error_class"] = error_class
        print(json.dumps(record, ensure_ascii=False, sort_keys=True), flush=True)
        return record

    def _discard_local_runtime_mutations(self) -> None:
        """Restore a dedicated worker checkout to fresh authoritative main.

        reset --hard restores tracked pointer/session files. git clean removes
        only runtime artifacts that may have been created by a failed local
        processor attempt. The worker checkout is dedicated to this service.
        """

        self._sync_main()
        _run(
            [
                "git",
                "clean",
                "-fd",
                "--",
                "runtime/journal",
                "runtime/request_receipts",
                "runtime/requests",
                ".runtime-service-result.json",
            ],
            self.repo_root,
        )

    def _commit_failure_from_clean_main(
        self,
        request_path: str,
        *,
        error: str,
        message: str,
        direct_request: dict[str, Any] | None = None,
    ) -> str | None:
        self._discard_local_runtime_mutations()
        include_request: str | None = None
        if direct_request is not None:
            request_file = self.repo_root / request_path
            request_file.parent.mkdir(parents=True, exist_ok=True)
            request_file.write_text(
                json.dumps(direct_request, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            include_request = request_path
        self._write_receipt(request_path, status="failed", error=error)
        return self._commit_and_push(message, include_request=include_request)

    def process_existing_request(self, request_path: str, *, delivery_id: str | None = None) -> dict[str, Any]:
        total_started = time.perf_counter()
        timings: dict[str, float] = {}
        lock_started = time.perf_counter()
        with self.lock:
            timings["lock_wait"] = _elapsed_ms(lock_started)
            sync_started = time.perf_counter()
            self._sync_main()
            timings["sync_main"] = _elapsed_ms(sync_started)

            if not self.enabled():
                timings["total"] = _elapsed_ms(total_started)
                telemetry = self._emit_telemetry(
                    status="ignored",
                    source="github_webhook",
                    request_path=request_path,
                    delivery_id=delivery_id,
                    timings=timings,
                )
                return {
                    "ok": False,
                    "ignored": True,
                    "reason": "transport_mode_not_active",
                    "mode": self.mode(),
                    "telemetry": telemetry,
                }

            req = self.repo_root / request_path
            if not req.exists():
                raise FileNotFoundError(request_path)
            receipt = self._receipt_path(request_path)
            if receipt.exists():
                existing = _json_load(receipt)
                timings["total"] = _elapsed_ms(total_started)
                telemetry = self._emit_telemetry(
                    status="idempotent",
                    source="github_webhook",
                    request_path=request_path,
                    delivery_id=delivery_id,
                    event_key=existing.get("event_key"),
                    timings=timings,
                )
                return {"ok": True, "idempotent": True, "receipt": existing, "telemetry": telemetry}

            processor = self._processor_for_engine()
            out = self.repo_root / ".runtime-service-result.json"
            out.unlink(missing_ok=True)
            processor_started = time.perf_counter()
            proc = _run(
                ["python3", processor, "--repo-root", ".", "--request", request_path, "--out", str(out)],
                self.repo_root,
                check=False,
            )
            timings["processor"] = _elapsed_ms(processor_started)
            if proc.returncode != 0:
                error = (proc.stderr or proc.stdout or "runtime processor failed")[-4000:]
                rollback_started = time.perf_counter()
                commit = self._commit_failure_from_clean_main(
                    request_path,
                    error=error,
                    message=f"Runtime request failure receipt {Path(request_path).name}",
                )
                timings["rollback_failure_receipt_push"] = _elapsed_ms(rollback_started)
                timings["total"] = _elapsed_ms(total_started)
                telemetry = self._emit_telemetry(
                    status="failed",
                    source="github_webhook",
                    request_path=request_path,
                    delivery_id=delivery_id,
                    error_class="processor_failed",
                    timings=timings,
                )
                return {
                    "ok": False,
                    "request_path": request_path,
                    "delivery_id": delivery_id,
                    "error": error,
                    "commit": commit,
                    "telemetry": telemetry,
                }

            result = _json_load(out)
            replay_started = time.perf_counter()
            try:
                replay = validate_runtime(self.repo_root)
                timings["replay_validation"] = _elapsed_ms(replay_started)
            except Exception as exc:
                timings["replay_validation"] = _elapsed_ms(replay_started)
                error = f"post_processor_replay_validation_failed: {type(exc).__name__}: {exc}"
                rollback_started = time.perf_counter()
                commit = self._commit_failure_from_clean_main(
                    request_path,
                    error=error,
                    message=f"Runtime replay validation failure {Path(request_path).name}",
                )
                timings["rollback_failure_receipt_push"] = _elapsed_ms(rollback_started)
                timings["total"] = _elapsed_ms(total_started)
                telemetry = self._emit_telemetry(
                    status="failed",
                    source="github_webhook",
                    request_path=request_path,
                    delivery_id=delivery_id,
                    event_key=result.get("event_key"),
                    error_class="replay_validation_failed",
                    timings=timings,
                )
                return {
                    "ok": False,
                    "request_path": request_path,
                    "delivery_id": delivery_id,
                    "error": error,
                    "commit": commit,
                    "telemetry": telemetry,
                }

            commit_started = time.perf_counter()
            commit = self._commit_and_push(f"Runtime event {Path(request_path).stem}")
            timings["commit_push"] = _elapsed_ms(commit_started)
            session = _json_load(self.repo_root / "runtime/session_state.json")
            timings["total"] = _elapsed_ms(total_started)
            telemetry = self._emit_telemetry(
                status="executed",
                source="github_webhook",
                request_path=request_path,
                delivery_id=delivery_id,
                event_key=result.get("event_key"),
                timings=timings,
            )
            return {
                "ok": True,
                "request_path": request_path,
                "delivery_id": delivery_id,
                "result": result,
                "replay_validation": replay,
                "commit": commit,
                "session_seq": session.get("journal_seq"),
                "last_turn_event_key": (session.get("last_turn") or {}).get("event_key"),
                "telemetry": telemetry,
            }

    def process_direct_turn(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_text = payload.get("raw_text")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError("raw_text required")

        total_started = time.perf_counter()
        timings: dict[str, float] = {}
        lock_started = time.perf_counter()
        with self.lock:
            timings["lock_wait"] = _elapsed_ms(lock_started)
            sync_started = time.perf_counter()
            self._sync_main()
            timings["sync_main"] = _elapsed_ms(sync_started)
            if not self.enabled():
                raise RuntimeError(f"transport mode is {self.mode()}, not {self.required_mode}")

            session_before = _json_load(self.repo_root / "runtime/session_state.json")
            current_key = (session_before.get("last_turn") or {}).get("event_key")
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
            request_file = self.repo_root / request_path
            request_file.parent.mkdir(parents=True, exist_ok=True)
            request_file.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            processor = self._processor_for_engine()
            out = self.repo_root / ".runtime-service-result.json"
            out.unlink(missing_ok=True)
            processor_started = time.perf_counter()
            proc = _run(
                ["python3", processor, "--repo-root", ".", "--request", request_path, "--out", str(out)],
                self.repo_root,
                check=False,
            )
            timings["processor"] = _elapsed_ms(processor_started)
            if proc.returncode != 0:
                error = (proc.stderr or proc.stdout or "runtime processor failed")[-4000:]
                rollback_started = time.perf_counter()
                commit = self._commit_failure_from_clean_main(
                    request_path,
                    error=error,
                    message=f"Runtime direct turn failure {Path(request_path).stem}",
                    direct_request=request,
                )
                timings["rollback_failure_receipt_push"] = _elapsed_ms(rollback_started)
                timings["total"] = _elapsed_ms(total_started)
                telemetry = self._emit_telemetry(
                    status="failed",
                    source="direct_api",
                    request_path=request_path,
                    event_key=event_key,
                    error_class="processor_failed",
                    timings=timings,
                )
                raise RuntimeError(
                    json.dumps(
                        {
                            "error": "direct_turn_failed",
                            "commit": commit,
                            "detail": error,
                            "telemetry": telemetry,
                        },
                        ensure_ascii=False,
                    )
                )

            result = _json_load(out)
            replay_started = time.perf_counter()
            try:
                replay = validate_runtime(self.repo_root)
                timings["replay_validation"] = _elapsed_ms(replay_started)
            except Exception as exc:
                timings["replay_validation"] = _elapsed_ms(replay_started)
                error = f"post_processor_replay_validation_failed: {type(exc).__name__}: {exc}"
                rollback_started = time.perf_counter()
                commit = self._commit_failure_from_clean_main(
                    request_path,
                    error=error,
                    message=f"Runtime direct replay validation failure {Path(request_path).stem}",
                    direct_request=request,
                )
                timings["rollback_failure_receipt_push"] = _elapsed_ms(rollback_started)
                timings["total"] = _elapsed_ms(total_started)
                telemetry = self._emit_telemetry(
                    status="failed",
                    source="direct_api",
                    request_path=request_path,
                    event_key=event_key,
                    error_class="replay_validation_failed",
                    timings=timings,
                )
                raise RuntimeError(
                    json.dumps(
                        {
                            "error": "direct_turn_replay_validation_failed",
                            "commit": commit,
                            "detail": error,
                            "telemetry": telemetry,
                        },
                        ensure_ascii=False,
                    )
                )

            commit_started = time.perf_counter()
            commit = self._commit_and_push(
                f"Runtime direct turn {Path(request_path).stem}", include_request=request_path
            )
            timings["commit_push"] = _elapsed_ms(commit_started)
            session = _json_load(self.repo_root / "runtime/session_state.json")
            timings["total"] = _elapsed_ms(total_started)
            telemetry = self._emit_telemetry(
                status="executed",
                source="direct_api",
                request_path=request_path,
                event_key=event_key,
                timings=timings,
            )
            return {
                "ok": True,
                "commit": commit,
                "result": result,
                "replay_validation": replay,
                "session": session,
                "telemetry": telemetry,
            }


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
    print(
        json.dumps(
            {
                "service": "tensura-always-on-runtime",
                "service_version": SERVICE_VERSION,
                "listen": f"{host}:{port}",
                "repo": str(repo_root),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
