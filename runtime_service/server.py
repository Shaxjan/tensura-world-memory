from __future__ import annotations

import json
import os
import queue
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app import Handler, REQUEST_RE, RuntimeService as BaseRuntimeService


class RuntimeService(BaseRuntimeService):
    """Production transport wrapper.

    A webhook can arrive immediately after the activation marker is pushed while
    this process still has the previous local clone. Therefore enqueue itself
    must not decide transport ownership. The worker syncs fresh main first and
    only then BaseRuntimeService.process_existing_request checks the mode.
    """

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
    print(json.dumps({
        "service": "tensura-always-on-runtime",
        "service_version": "0.1.0",
        "listen": f"{host}:{port}",
        "repo": str(repo_root),
    }, ensure_ascii=False))
    server.serve_forever()


if __name__ == "__main__":
    main()
