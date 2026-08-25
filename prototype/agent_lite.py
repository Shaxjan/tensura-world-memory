from __future__ import annotations

import hashlib
import re
from typing import Any

from character_agent_contract import DECISION_FORMAT, SCHEMA_VERSION


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().replace("ё", "е")).strip()


def _pick(seed: str, values: list[str]) -> str:
    idx = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % len(values)
    return values[idx]


def _decision(
    context: dict[str, Any],
    *,
    speech_act: str,
    text: str,
    emotion: str = "neutral",
    relationship_delta: dict[str, int] | None = None,
    clock_minutes: int = 0,
) -> dict[str, Any]:
    turn_key = str(context["source_turn_key"])
    utterance_ref = str(context["player_input"]["observation_key"])
    observation_refs = list((context.get("knowledge") or {}).get("current_observation_fact_keys") or [])
    source_refs = sorted(set([utterance_ref, *observation_refs]))
    return {
        "format": DECISION_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "actor_key": "rena",
        "source_turn_key": turn_key,
        "decision_kind": "speak",
        "observable": {
            "speech_act": speech_act,
            "surface_text": text,
            "action_kind": "none",
            "target_key": None,
            "clock_minutes": clock_minutes,
        },
        "grounding": {
            "fact_refs": source_refs,
            "asserted_claims": [],
        },
        "private": {
            "emotion_state": emotion,
            "relationship_delta": relationship_delta or {},
            "memory_proposals": [
                {
                    "kind": "direct_dialogue_turn",
                    "summary": "Arlequino directly addressed Rena in the prototype scene.",
                    "source_fact_refs": source_refs,
                }
            ],
            "rationale": "Prototype Agent Lite: bounded profile-based social policy; no global-world authority.",
        },
    }


def rena_agent_lite(context: dict[str, Any], *, memory_count: int = 0) -> dict[str, Any]:
    """Small deterministic provider used only by the fast playable sandbox.

    It is intentionally limited. The point is to exercise the real Character Agent
    boundary, memory, relationship deltas and deterministic journal replay without
    requiring an external model/API key. Replacing this function with a real provider
    must not change the authority boundary.
    """
    raw = str((context.get("player_input") or {}).get("utterance") or "")
    low = _norm(raw)
    seed = f"{context.get('source_turn_key')}|{memory_count}|{low}"

    if any(x in low for x in ("дай гитар", "отдай гитар", "можно твою гитар", "возьму твою гитар")):
        return _decision(
            context,
            speech_act="refuse",
            text=_pick(seed, [
                "Нет. Это моя гитара. Возьми свою.",
                "Даже не надейся, павлин. Моя гитара остаётся у меня.",
                "Нет. Ты можешь попросить — я могу отказать. Вот сейчас отказываю.",
            ]),
            emotion="amused" if memory_count % 2 == 0 else "guarded",
            relationship_delta={"respect": 1},
        )

    if any(x in low for x in ("привет", "здравств", "доброе утро", "добрый день", "добрый вечер")):
        if memory_count == 0:
            text = _pick(seed, ["Привет, павлин.", "Ну привет.", "Здравствуй. Что на этот раз?"])
        else:
            text = _pick(seed, ["Я здесь. Говори.", "Слушаю тебя, павлин.", "М-м? Что хотел?"])
        return _decision(context, speech_act="greet", text=text, emotion="warm", relationship_delta={"affection": 1})

    if any(x in low for x in ("люблю тебя", "скучал", "скучаю", "обнимаю", "поцел")):
        return _decision(
            context,
            speech_act="comment",
            text=_pick(seed, [
                "Знаю. Но не зазнавайся.",
                "И всё-таки иногда ты умеешь говорить правильные вещи.",
                "Подойди сюда, павлин. Только без спектакля.",
            ]),
            emotion="warm",
            relationship_delta={"affection": 1, "trust": 1},
        )

    if any(x in low for x in ("павлин", "дразн", "хваст", "красив", "великолеп")):
        return _decision(
            context,
            speech_act="tease",
            text=_pick(seed, [
                "Стараешься, павлин. Но можешь лучше.",
                "Вот сейчас было почти убедительно. Почти.",
                "Ты опять решил соревноваться с собственным отражением?",
            ]),
            emotion="amused",
            relationship_delta={"affection": 1},
        )

    if any(x in low for x in ("свадьб", "женить", "замуж", "когда поженим")):
        return _decision(
            context,
            speech_act="comment",
            text=_pick(seed, [
                "Не пытайся получить готовый план там, где его ещё нет.",
                "Мы это обсудим, когда будет что обсуждать. Не раньше.",
                "Ты уже куда-то торопишься? Я — нет.",
            ]),
            emotion="amused",
            relationship_delta={},
        )

    if any(x in low for x in ("что делаешь", "чем занимаешь", "куда идешь", "где была")):
        return _decision(
            context,
            speech_act="answer",
            text=_pick(seed, [
                "Сейчас — разговариваю с тобой. Остальное не выдумывай за меня.",
                "У меня есть свои дела. Если хочешь узнать что-то конкретное — спрашивай конкретно.",
                "Не всё, чем я занимаюсь, обязано вращаться вокруг тебя, павлин.",
            ]),
            emotion="neutral",
            relationship_delta={"respect": 1},
        )

    if "?" in raw or any(low.startswith(x) for x in ("почему", "зачем", "как ", "что ", "кто ", "где ", "когда ")):
        return _decision(
            context,
            speech_act="answer",
            text=_pick(seed, [
                "Спроси конкретнее. Я не собираюсь додумывать вопрос за тебя.",
                "Это слишком расплывчато. Что именно ты хочешь узнать?",
                "Смотря что ты имеешь в виду. Уточни.",
            ]),
            emotion="curious",
            relationship_delta={},
        )

    return _decision(
        context,
        speech_act="comment",
        text=_pick(seed, [
            "Я тебя услышала. Продолжай.",
            "И что ты хочешь от меня после этого?",
            "Хорошо. Теперь говори по существу.",
            "М-м. Допустим. Что дальше?",
        ]),
        emotion="curious",
        relationship_delta={},
    )
