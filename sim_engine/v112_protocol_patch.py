from __future__ import annotations

import argparse
from pathlib import Path


def _once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"protocol patch expected exactly one match, got {count}: {old[:80]!r}")
    return text.replace(old, new, 1)


def patched_protocol(text: str) -> str:
    text = _once(
        text,
        "# Tensura World Memory — Authoritative Runtime v1.0.11 Protocol",
        "# Tensura World Memory — Authoritative Runtime v1.0.12 Protocol",
    )
    text = _once(text, "Для v1.0.11:\n", "Для v1.0.12:\n")
    text = _once(
        text,
        "- `runtime/requests/q-<request-id>.json` — нормальные v1.0.11 fast requests без client-allocated seq;\n- `runtime/requests/rNNNNNN.json` — legacy/recovery requests с явным seq;",
        "- `runtime/requests/q-<request-id>.json` — нормальные fast requests без client-allocated seq; canonical payload: `request.raw_text`;\n- `runtime/requests/rNNNNNN.json` — legacy/recovery requests с явным seq;\n- `runtime/request_receipts/<request>.receipt.json` — неавторитетный transport receipt (`executed` / `failed` / `superseded`), не заменяющий journal/session;",
    )
    text = _once(
        text,
        "### Нормальный synchronized fast path v1.0.11",
        "### Нормальный synchronized fast path v1.0.12",
    )
    text = _once(
        text,
        "2. Создать ровно один уникальный `runtime/requests/q-<request-id>.json` формата `TENSURA_FAST_TURN_REQUEST`.\n3. Fast request **не содержит `seq`**. Он содержит дословный `raw_text`, уникальный `event_key` и `expected_last_gameplay_turn_key`.",
        "2. Создать ровно один уникальный `runtime/requests/q-<request-id>.json` формата `TENSURA_FAST_TURN_REQUEST`. Повторно enqueue того же действия до transport result запрещён.\n3. Fast request **не содержит `seq`** и не требует отдельный `request_id`. Canonical shape: уникальный `event_key`, `event_type`, `expected_last_gameplay_turn_key` и объект `request` с дословным `request.raw_text`. Для recovery v1.0.12 допускает top-level `raw_text` только если `request` object отсутствует; конфликт двух форм reject'ится.",
    )
    text = _once(
        text,
        "7. После подтверждённой обработки прочитать свежий `runtime/session_state.json` один раз и проверить, что `last_turn.event_key` равен отправленному `event_key`. Затем выдать обычную игровую сцену.",
        "7. После обработки сначала проверить `runtime/request_receipts/<request>.receipt.json`. `failed`/`superseded` означает: gameplay event не подтверждён и повтор автоматически запрещён. При `executed` прочитать свежий `runtime/session_state.json` и проверить, что `last_turn.event_key` равен отправленному `event_key`. Затем выдать обычную игровую сцену.\n8. Если receipt ещё отсутствует, не создавать второй request для того же пользовательского действия. Повтор допустим только после явного transport failure/recovery и синхронизации.",
    )
    text = _once(
        text,
        "Legacy `runtime/requests/rNNNNNN.json` с client-allocated `seq` сохраняется только для recovery/backward compatibility. Нормальный v1.0.11 ход использует `q-*` и server-side sequence allocation.",
        "Legacy `runtime/requests/rNNNNNN.json` с client-allocated `seq` сохраняется только для recovery/backward compatibility. Нормальный v1.0.12 ход использует один `q-*` и server-side sequence allocation. Три request-файла инцидента 24.08.2026 (`r000019`, `q-...001`, `q-...002`) являются unprocessed transport failures и после v1.0.12 помечаются `superseded`; их нельзя исполнять автоматически.",
    )
    marker = "Обычный synchronized путь после подтверждённого предыдущего хода: **enqueue q-request → authoritative processing → один postflight session read**."
    text = _once(
        text,
        marker,
        marker + "\n\nv1.0.12 Reliability Repair уточняет контракт: `request_id` не обязателен; canonical payload — `request.raw_text`; top-level `raw_text` принимается только как compatibility normalization; workflow сначала идентифицирует request на triggering SHA, затем синхронизируется со свежим `main`; каждый достигший processor request получает transport receipt. Gameplay semantics при этом не меняются.",
    )
    activation = """Activation v1.0.11:\n- transport-only, 0 игровых минут;\n- `before_hash == after_hash` для gameplay state;\n- не является действием Арлекино или NPC;\n- не меняет место, деньги, память, personality, relationships или уже записанные NPC-response;\n- сохраняет последний gameplay `last_turn`;\n- включает auto-sequenced `q-*` requests и `expected_last_gameplay_turn_key` guard;\n- legacy `rNNNNNN` остаётся recovery/backward-compatible путём.\n"""
    text = _once(
        text,
        activation,
        activation + """\nActivation v1.0.12:\n- transport-only, 0 игровых минут, `before_hash == after_hash`;\n- не исполняет задним числом `r000019`/два `q` инцидента и помечает их transport receipts как `superseded`;\n- не меняет последний gameplay `last_turn`, место, деньги, память, personality, relationships или NPC-response;\n- исправляет schema contract fast request и вводит receipts;\n- возвращает runtime-turn workflow к доказанному full-checkout/setup-python path, сохраняя auto-seq и stale gameplay guard.\n""",
    )
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    path = Path(args.repo_root).resolve() / "MASTER_SAVE_PROTOCOL.md"
    old = path.read_text(encoding="utf-8")
    new = patched_protocol(old)
    if args.check:
        print("v1.0.12 protocol patch check: OK")
        return
    path.write_text(new, encoding="utf-8")
    print("v1.0.12 protocol patch applied")


if __name__ == "__main__":
    main()
