# Tensura Always-On Runtime Service

Provider-neutral runtime transport for Tensura World Memory.

## Purpose

Normal gameplay must not wait for a GitHub Actions runner. This service stays online and owns turn processing once `runtime/transport_mode.json` is activated with `mode = always_on_service`.

Two inputs are supported:

1. `POST /github-webhook` — bridge for the current ChatGPT/GitHub workflow. A gameplay chat creates one `q-*` request commit; GitHub sends a push webhook; the service processes the exact request immediately and pushes journal/session/receipt back to `main`.
2. `POST /turn` — direct authenticated API for a future game client. The request, engine event, session state and receipt are committed together after the synchronous engine result is available.

Until activation, the service is fail-closed: `/health` works, but gameplay processing returns `transport_mode_not_active`. Existing GitHub Actions remains authoritative.

## Runtime requirements

- one Linux host / one service replica;
- Docker + Docker Compose, or Python 3.12 + Git;
- outbound HTTPS access to GitHub;
- inbound HTTPS endpoint for GitHub webhook;
- repository token with Contents read/write permission;
- a random GitHub webhook secret;
- optional random API token for `/turn`.

For the current single-world runtime, do not run multiple replicas. The service serializes turns in one worker process. Horizontal scaling requires a distributed lock/state backend and is deliberately out of scope for this first cutover.

## Environment

Copy `.env.example` to `.env` outside version control and set:

- `GITHUB_REPOSITORY=Shaxjan/tensura-world-memory`
- `GITHUB_TOKEN=...`
- `TENSURA_GITHUB_WEBHOOK_SECRET=...`
- `TENSURA_API_TOKEN=...` for direct `/turn`
- `TENSURA_BRANCH=main`

Never commit real secrets.

## Docker

From the repository root:

```bash
cd runtime_service
docker compose up -d --build
```

The compose file binds the application to `127.0.0.1:8080`. Put Nginx/Caddy in front of it and expose only HTTPS publicly.

Health check:

```bash
curl https://YOUR_RUNTIME_HOST/health
```

Before activation it should report:

- `service = tensura-always-on-runtime`
- `service_version = 0.1.0`
- current engine version and journal seq
- `transport_mode = github_actions`
- `processing_enabled = false`

## GitHub webhook

Repository webhook target:

`https://YOUR_RUNTIME_HOST/github-webhook`

Configure:

- Content type: `application/json`
- Secret: exact `TENSURA_GITHUB_WEBHOOK_SECRET`
- Event: push only
- SSL verification: enabled

The service validates `X-Hub-Signature-256`, accepts only pushes to the configured branch, extracts exactly one `runtime/requests/r*.json` or `q-*.json`, and is idempotent through request receipts.

## Activation

Do not activate until the deployed `/health` sees the same engine version and journal seq as current GitHub LIVE.

```bash
python3 runtime_service/activate_transport.py --repo-root . activate \
  --health-url https://YOUR_RUNTIME_HOST/health
```

Review the generated `runtime/transport_mode.json`, commit it on a dedicated activation branch, merge it, then send one ordinary gameplay action. After the marker reaches `main`:

- the always-on service begins processing;
- GitHub Actions detects `always_on_service` and does not execute normal turns;
- GitHub remains the append-only journal/audit/rollback store.

## Rollback

If the service is unhealthy, switch transport ownership back before accepting more turns:

```bash
python3 runtime_service/activate_transport.py --repo-root . deactivate \
  --reason "always-on service unavailable"
```

Commit the resulting `runtime/transport_mode.json`. GitHub Actions then resumes authoritative turn processing.

## Direct API

`POST /turn` requires:

`Authorization: Bearer <TENSURA_API_TOKEN>`

Body:

```json
{
  "raw_text": "Что делаешь?",
  "event_key": "optional-client-event-key",
  "expected_last_gameplay_turn_key": "optional-optimistic-guard"
}
```

If the optimistic guard is omitted, the service binds the request to the current authoritative last gameplay turn immediately before execution.

## Security / operational rules

- Never expose port 8080 directly to the internet; terminate TLS at a reverse proxy.
- Keep one replica until distributed locking exists.
- Do not place GitHub/API/webhook secrets in the repository or container image.
- The service uses `GIT_ASKPASS`; the Git remote URL contains no token.
- A webhook delivery does not itself change gameplay state. Only the existing engine processor and committed runtime journal event do.
- Receipt `failed` or `superseded` means the turn is not authoritative and must not be narrated as executed.
