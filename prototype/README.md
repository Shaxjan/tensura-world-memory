# Tensura Playable Alpha — Fast Local Prototype

This is a deliberately small playable vertical slice. It exists to get back to playing before the full production Character Agent runtime is finished.

## What it is

- local browser chat with Rena;
- starts from the current authoritative LIVE checkpoint+journal as read-only source;
- immediately forks into a temporary `SANDBOX_NON_AUTHORITATIVE` database;
- prospectively activates the v1.0.13 candidate Character Agent only inside that temp DB;
- treats the browser conversation as a direct same-scene dialogue with Rena;
- uses the real engine-owned routing gate, Character Agent contract validator and candidate decision commit path;
- keeps private emotion/relationship state out of the public response;
- rebuilds the sandbox from LIVE and replays all stored structured decisions after every turn; hash mismatch fails the turn;
- never writes `runtime/**`.

## What is intentionally simplified

The first playable provider is `Rena Agent Lite v1`, a deterministic local policy. It is not an LLM and it does not claim to solve open-ended character dialogue. It exists so the full gameplay loop can be exercised now without an API key, VPS, model latency or non-deterministic replay.

The provider is behind the same structured Character Agent boundary that a later real model will use. Replacing Agent Lite should not grant the model direct world authority.

The sandbox also materializes Rena in the current local scene as an explicit test fixture. This is **not** a claim that current LIVE Rena is physically there.

## Run

From repository root:

```bash
python3 prototype/app.py
```

Open:

```text
http://127.0.0.1:8787/
```

Optional:

```bash
python3 prototype/app.py --port 9000
```

## Tests

```bash
python3 -m unittest -v prototype/test_prototype.py
```

The tests verify multi-turn dialogue, Rena's refusal boundary, sandbox memory, deterministic replay, reset, UNKNOWN wedding boundary and byte-for-byte preservation of `runtime/runtime_state.json` + `runtime/session_state.json`.

## Promotion rule

Do not point this prototype at LIVE. The production path still needs real accepted-player-turn reciprocal awareness, a real provider/failure policy, and an explicit activation/cutover gate.
