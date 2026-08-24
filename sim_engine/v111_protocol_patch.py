from __future__ import annotations

import argparse
from pathlib import Path


TITLE_110 = "# Tensura World Memory — Authoritative Runtime v1.0.10 Protocol"
TITLE_111 = "# Tensura World Memory — Authoritative Runtime v1.0.11 Protocol"

FAST_SECTION = """## 3. Быстрый игровой ход

### Нормальный synchronized fast path v1.0.11

Если игровой чат уже держит последний подтверждённый `runtime/session_state.json` в контексте, **предварительно перечитывать `runtime/runtime_state.json` для каждого обычного хода не требуется**.

1. Взять `last_turn.event_key` из последнего подтверждённого session state как `expected_last_gameplay_turn_key`.
2. Создать ровно один уникальный `runtime/requests/q-<request-id>.json` формата `TENSURA_FAST_TURN_REQUEST`.
3. Fast request **не содержит `seq`**. Он содержит дословный `raw_text`, уникальный `event_key` и `expected_last_gameplay_turn_key`.
4. Workflow `Tensura Runtime Turn` под authoritative concurrency lock читает свежий LIVE-pointer и сам назначает `seq = journal_seq + 1` непосредственно перед выполнением.
5. Processor сравнивает `expected_last_gameplay_turn_key` с текущим `session_state.last_turn.event_key`. Zero-time technical activation не меняет `last_turn` и не ломает fast path.
6. Если другой **игровой** ход уже произошёл, guard обязан завершить request ошибкой **до** engine mutation/journal write. Нельзя молча переигрывать действие на изменившемся gameplay-контексте.
7. После подтверждённой обработки прочитать свежий `runtime/session_state.json` один раз и проверить, что `last_turn.event_key` равен отправленному `event_key`. Затем выдать обычную игровую сцену.

### Recovery / новый чат

Полный pointer/session preflight нужен, если:
- это новый или несинхронизированный чат;
- неизвестен последний подтверждённый `last_turn.event_key`;
- fast guard вернул conflict;
- workflow/commit завершился ошибкой;
- seq/hash/session выглядят несогласованно.

Тогда сначала перечитать `runtime/runtime_state.json` + `runtime/session_state.json`, при необходимости выполнить full replay, и только после синхронизации явно повторить действие. Старый эффект вслепую не повторять.

Legacy `runtime/requests/rNNNNNN.json` с client-allocated `seq` сохраняется только для recovery/backward compatibility. Нормальный v1.0.11 ход использует `q-*` и server-side sequence allocation.

Нельзя выдавать игровой исход до подтверждённого runtime event/session state.
"""

FAST_MODEL_SECTION = """## 11B. Runtime Fast Path v1

v1.0.11 меняет транспорт, а не gameplay semantics. Living Scene, Character Core, autonomy, memory и Causal NPC Response продолжают работать по правилам v1.0.10.

Fast request имеет формат `TENSURA_FAST_TURN_REQUEST` и хранится как immutable `runtime/requests/q-<unique-id>.json`.

Главные инварианты:
- journal seq назначает только authoritative processor под общей runtime concurrency lock;
- gameplay chat не резервирует seq заранее;
- `expected_last_gameplay_turn_key` защищает от выполнения поверх другого уже совершённого player turn;
- technical zero-time activation может безопасно оказаться между двумя ходами, если последний gameplay turn не изменился;
- guard conflict не создаёт journal event и не меняет pointer/session/gameplay state;
- fast path не ослабляет replay/hash/UNKNOWN/player-control/causal-knowledge правила;
- GitHub Actions остаётся текущим authoritative transport и всё ещё имеет runner-startup floor; v1.0.11 сокращает лишние round-trip, но не обещает фиксированные 1–5 секунд на hosted Actions.

Обычный synchronized путь после подтверждённого предыдущего хода: **enqueue q-request → authoritative processing → один postflight session read**.
"""

ACTIVATION_111 = """Activation v1.0.11:
- transport-only, 0 игровых минут;
- `before_hash == after_hash` для gameplay state;
- не является действием Арлекино или NPC;
- не меняет место, деньги, память, personality, relationships или уже записанные NPC-response;
- сохраняет последний gameplay `last_turn`;
- включает auto-sequenced `q-*` requests и `expected_last_gameplay_turn_key` guard;
- legacy `rNNNNNN` остаётся recovery/backward-compatible путём.

"""


def patch_protocol_text(text: str) -> str:
    if TITLE_111 in text:
        out = text
    else:
        if TITLE_110 not in text:
            raise RuntimeError("MASTER protocol is neither v1.0.10 nor already v1.0.11")
        out = text.replace(TITLE_110, TITLE_111, 1)
        out = out.replace("Для v1.0.10:\n- `engine_version = 1.0.10`;", "Для v1.0.11:\n- `engine_version = 1.0.11`;", 1)
        out = out.replace(
            "- `runtime/requests/rNNNNNN.json` — входящие пользовательские команды;",
            "- `runtime/requests/q-<request-id>.json` — нормальные v1.0.11 fast requests без client-allocated seq;\n- `runtime/requests/rNNNNNN.json` — legacy/recovery requests с явным seq;",
            1,
        )

        start = out.find("## 3. Быстрый игровой ход")
        end = out.find("\n## 4. Обязательный HUD", start)
        if start < 0 or end < 0:
            raise RuntimeError("MASTER protocol fast-turn section markers not found")
        out = out[:start] + FAST_SECTION.rstrip() + "\n" + out[end:]

        marker_12 = "\n## 12. Version continuity / activation"
        if marker_12 not in out:
            raise RuntimeError("MASTER protocol section 12 marker not found")
        if "## 11B. Runtime Fast Path v1" not in out:
            out = out.replace(marker_12, "\n\n" + FAST_MODEL_SECTION.rstrip() + "\n" + marker_12, 1)

        marker_13 = "\n## 13. Именованные NPC и локальный поиск"
        if marker_13 not in out:
            raise RuntimeError("MASTER protocol section 13 marker not found")
        if "Activation v1.0.11:" not in out:
            out = out.replace(marker_13, "\n" + ACTIVATION_111 + marker_13, 1)

        prohibition_marker = "- пропускать обязательный HUD."
        extra = (
            "- заранее назначать journal seq в нормальном v1.0.11 fast request;\n"
            "- выполнять fast request поверх другого gameplay turn при несовпадении `expected_last_gameplay_turn_key`;\n"
            "- считать отсутствие preflight pointer read разрешением обходить authoritative processor/replay/hash;\n"
        )
        if prohibition_marker not in out:
            raise RuntimeError("MASTER protocol prohibition tail marker not found")
        if "заранее назначать journal seq в нормальном v1.0.11 fast request" not in out:
            out = out.replace(prohibition_marker, extra + prohibition_marker, 1)

    required = [
        TITLE_111,
        "`engine_version = 1.0.11`",
        "TENSURA_FAST_TURN_REQUEST",
        "expected_last_gameplay_turn_key",
        "server-side sequence allocation",
        "Activation v1.0.11:",
        "## 11B. Runtime Fast Path v1",
    ]
    missing = [x for x in required if x not in out]
    if missing:
        raise RuntimeError("patched MASTER protocol missing invariants: " + ", ".join(missing))
    return out


def patch_master(repo_root: str | Path, *, check_only: bool = False) -> dict:
    root = Path(repo_root).resolve()
    path = root / "MASTER_SAVE_PROTOCOL.md"
    before = path.read_text(encoding="utf-8")
    after = patch_protocol_text(before)
    changed = after != before
    if not check_only and changed:
        path.write_text(after, encoding="utf-8")
    return {
        "ok": True,
        "changed": changed,
        "check_only": check_only,
        "title": TITLE_111,
        "fast_request_format": "TENSURA_FAST_TURN_REQUEST",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    print(patch_master(args.repo_root, check_only=args.check))


if __name__ == "__main__":
    main()
