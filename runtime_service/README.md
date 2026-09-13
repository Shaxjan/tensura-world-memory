# Tensura Always-On Runtime Service

Provider-neutral runtime transport for Tensura World Memory.

Current service version: `0.2.0`.

## Purpose

Normal gameplay must not wait for a GitHub Actions runner. This service stays online and owns turn processing once `runtime/transport_mode.json` is activated with `mode = always_on_service`.

Two inputs are supported:

1. `POST /github-webhook` — bridge for the current ChatGPT/GitHub workflow. A gameplay chat creates one `q-*` request commit; GitHub sends a push webhook; the service processes the exact request immediately and pushes journal/session/receipt back to `main`.
2. `POST /turn` — direct authenticated API for a future game client. The request, engine event, session state and receipt are committed together after the synchronous engine result is available.

Until activation, the service is fail-closed: `/health` works, but gameplay processing is not authoritative. Existing GitHub Actions remains the owner of normal turns.

## Recommended first deployment

Use one small always-on Linux VPS/container with Docker and persistent local disk for the repository checkout. This matches the current Python + Git runtime directly, avoids serverless cold-start semantics, and preserves one in-process authoritative lock.

Reasonable alternatives are Railway or Fly.io with one continuously running instance. Free services that sleep when idle are not suitable for the synchronous gameplay path. Vercel Functions and Cloudflare Workers/Durable Objects are not drop-in hosts for the current long-lived Python + Git worker; they may become useful later after the persistence/coordination layer is redesigned for multiplayer.

Keep exactly one service replica for this version. Horizontal scaling requires a distributed lock and a different authoritative write coordinator.

## Runtime requirements

- one Linux host / one service replica;
- Docker + Docker Compose, or Python 3.12 + Git;
- outbound HTTPS access to GitHub;
- inbound HTTPS endpoint for GitHub webhook;
- repository token with Contents read/write permission;
- a random GitHub webhook secret;
- optional random API token for `/turn`.

## Safety guarantees in v0.2.0

The v1.0.12 engine remains the only gameplay mutation engine. The service adds transport-level guarantees around it:

- fresh `main` sync before ownership and turn processing;
- one serialized process lock for the current single-world runtime;
- receipt-based idempotency for webhook requests;
- existing v1.0.12 `event_key` duplicate guard and `expected_last_gameplay_turn_key` stale-context guard;
- independent full checkpoint + journal deterministic replay/hash validation after the engine runs and before any successful Git push;
- if the processor or replay gate fails, local pointer/session/journal artifacts are discarded and restored from authoritative `main` before a `failed` receipt is committed;
- structured latency telemetry contains request identifiers and stage timings, never the player's raw text;
- activation refuses a deployed endpoint whose service version, engine version or journal seq is stale.

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

The compose file binds the application to `127.0.0.1:8080` and includes a local `/health` container healthcheck. Put Nginx/Caddy in front of it and expose only HTTPS publicly.

Health check:

```bash
curl https://YOUR_RUNTIME_HOST/health
```

Before activation it should report:

- `service = tensura-always-on-runtime`
- `service_version = 0.2.0`
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

## Structured latency telemetry

Each processed turn emits one JSON log record with `type = tensura_runtime_latency`. It contains source, status, request path, event key when known, and stage timings such as:

- `lock_wait`
- `sync_main`
- `processor`
- `replay_validation`
- `commit_push`
- `total`

Failure records identify only an error class. Player `raw_text` is deliberately excluded.

## Local integration rehearsal

Run the transport through a temporary shadow copy of authoritative runtime:

```bash
python3 runtime_service/rehearsal.py --repo-root .
```

The rehearsal verifies:

- current LIVE replay/hash before the test;
- one shadow fast request advances the shadow journal exactly once;
- the generated receipt is `executed`;
- full replay/hash validation succeeds after the shadow turn;
- processing the same request again is idempotent and does not advance journal;
- source `runtime_state.json` and `session_state.json` remain byte-for-byte unchanged.

CI runs this rehearsal on every runtime-service PR.

## Activation

Do not activate until a real deployed HTTPS endpoint has passed health and end-to-end smoke tests.

First verify `/health`, then run:

```bash
python3 runtime_service/activate_transport.py --repo-root . activate \
  --health-url https://YOUR_RUNTIME_HOST/health
```

The activation helper requires service `0.2.0` and verifies the endpoint against the local authoritative engine version and journal seq. Review the generated `runtime/transport_mode.json`, commit it on a dedicated activation branch, and merge it only after the deployed endpoint is confirmed.

After the marker reaches `main`:

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

## Security / operational rules

- Never expose port 8080 directly to the internet; terminate TLS at a reverse proxy.
- Keep one replica until distributed locking exists.
- Do not place GitHub/API/webhook secrets in the repository or container image.
- The service uses `GIT_ASKPASS`; the Git remote URL contains no token.
- A webhook delivery does not itself change gameplay state. Only the existing engine processor and committed runtime journal event do.
- Receipt `failed` or `superseded` means the turn is not authoritative and must not be narrated as executed.
- Do not activate transport just because CI is green; deployment health and a real endpoint smoke test are mandatory.
