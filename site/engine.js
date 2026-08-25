export const EMPTY_STATE = Object.freeze({
  turn: 0,
  relationship: { trust: 0, respect: 0, affection: 0, irritation: 0 },
  memories: [],
  transcript: [],
});

function norm(text) {
  return String(text || "").toLocaleLowerCase("ru-RU").replaceAll("ё", "е").replace(/\s+/g, " ").trim();
}

function hash(text) {
  let h = 2166136261;
  for (const ch of String(text)) {
    h ^= ch.codePointAt(0);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function pick(seed, values, avoid = null) {
  if (!values.length) return "";
  let i = hash(seed) % values.length;
  if (values.length > 1 && values[i] === avoid) i = (i + 1) % values.length;
  return values[i];
}

function cloneState(state) {
  const source = state || EMPTY_STATE;
  return {
    turn: Number(source.turn || 0),
    relationship: {
      trust: Number(source.relationship?.trust || 0),
      respect: Number(source.relationship?.respect || 0),
      affection: Number(source.relationship?.affection || 0),
      irritation: Number(source.relationship?.irritation || 0),
    },
    memories: Array.isArray(source.memories) ? source.memories.map(x => ({...x})) : [],
    transcript: Array.isArray(source.transcript) ? source.transcript.map(x => ({...x})) : [],
  };
}

function boundedAdd(value, delta) {
  return Math.max(-20, Math.min(20, Number(value || 0) + delta));
}

function classify(low, raw) {
  if (/(дай|отдай|одолжи|можно|возьму|дать).{0,18}гитар/.test(low)) return "guitar_request";
  if (/(привет|здравств|доброе утро|добрый день|добрый вечер)/.test(low)) return "greeting";
  if (/(люблю тебя|скучал|скучаю|обнимаю|поцел)/.test(low)) return "affection";
  if (/(павлин|дразн|хваст|красив|великолеп)/.test(low)) return "tease";
  if (/(свадьб|женить|замуж|когда поженим)/.test(low)) return "wedding";
  if (/(что делаешь|чем занимаешь|куда идешь|где была)/.test(low)) return "activity";
  if (/^(почему|зачем|как |что |кто |где |когда )/.test(low) || String(raw).includes("?")) return "question";
  return "comment";
}

const RESPONSES = {
  guitar_request: [
    "Нет. Это моя гитара. Возьми свою.",
    "Даже не надейся, павлин. Моя гитара остаётся у меня.",
    "Попросить можешь. Получить — нет.",
  ],
  greeting_first: ["Привет, павлин.", "Ну привет.", "Здравствуй. Что на этот раз?"],
  greeting_again: ["Я здесь. Говори.", "Слушаю тебя, павлин.", "М-м? Что хотел?"],
  affection: [
    "Знаю. Но не зазнавайся.",
    "И всё-таки иногда ты умеешь говорить правильные вещи.",
    "Подойди сюда, павлин. Только без спектакля.",
  ],
  tease: [
    "Стараешься, павлин. Но можешь лучше.",
    "Вот сейчас было почти убедительно. Почти.",
    "Ты опять решил соревноваться с собственным отражением?",
  ],
  wedding: [
    "Не пытайся получить готовый план там, где его ещё нет.",
    "Мы это обсудим, когда будет что обсуждать. Не раньше.",
    "Ты уже куда-то торопишься? Я — нет.",
  ],
  activity: [
    "Сейчас — разговариваю с тобой. Остальное не выдумывай за меня.",
    "У меня есть свои дела. Хочешь узнать что-то конкретное — спрашивай конкретно.",
    "Не всё, чем я занимаюсь, обязано вращаться вокруг тебя, павлин.",
  ],
  question: [
    "Спроси конкретнее. Я не собираюсь додумывать вопрос за тебя.",
    "Это слишком расплывчато. Что именно ты хочешь узнать?",
    "Смотря что ты имеешь в виду. Уточни.",
  ],
  comment: [
    "Я тебя услышала. Продолжай.",
    "И что ты хочешь от меня после этого?",
    "Хорошо. Теперь говори по существу.",
    "М-м. Допустим. Что дальше?",
  ],
};

export function resetState() {
  return cloneState(EMPTY_STATE);
}

export function respondToRena(input, previousState) {
  const raw = String(input || "").trim();
  if (!raw) throw new Error("empty_input");
  const state = cloneState(previousState);
  const low = norm(raw);
  const intent = classify(low, raw);
  const lastNpc = [...state.transcript].reverse().find(x => x.role === "rena")?.text || null;
  const seed = `${state.turn + 1}|${intent}|${low}|${state.memories.length}`;

  let speechAct = "comment";
  let emotion = "curious";
  let delta = {};
  let pool = RESPONSES[intent] || RESPONSES.comment;

  if (intent === "guitar_request") {
    speechAct = "refuse"; emotion = state.turn % 2 ? "guarded" : "amused"; delta = { respect: 1 };
  } else if (intent === "greeting") {
    speechAct = "greet"; emotion = "warm"; delta = { affection: 1 };
    pool = state.turn === 0 ? RESPONSES.greeting_first : RESPONSES.greeting_again;
  } else if (intent === "affection") {
    emotion = "warm"; delta = { affection: 1, trust: 1 };
  } else if (intent === "tease") {
    speechAct = "tease"; emotion = "amused"; delta = { affection: 1 };
  } else if (intent === "wedding") {
    emotion = "amused";
  } else if (intent === "activity") {
    speechAct = "answer"; emotion = "neutral"; delta = { respect: 1 };
  } else if (intent === "question") {
    speechAct = "answer"; emotion = "curious";
  }

  const text = pick(seed, pool, lastNpc);
  state.turn += 1;
  for (const [axis, amount] of Object.entries(delta)) {
    state.relationship[axis] = boundedAdd(state.relationship[axis], amount);
  }
  state.memories.push({ turn: state.turn, kind: "direct_dialogue", intent, playerText: raw });
  if (state.memories.length > 40) state.memories = state.memories.slice(-40);
  state.transcript.push({ role: "player", text: raw }, { role: "rena", text, speechAct });
  if (state.transcript.length > 80) state.transcript = state.transcript.slice(-80);

  return {
    observable: { actor: "Рена", speechAct, text },
    private: { emotion, relationshipDelta: delta },
    state,
    invariants: {
      weddingPreferenceStillUnknown: true,
      privateEmotionNotNarratorKnowledge: true,
      relationshipDoesNotImplyObedience: true,
    },
  };
}
