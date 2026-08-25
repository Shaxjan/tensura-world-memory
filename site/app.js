import { resetState, respondToRena } from './engine.js';

const KEY = 'tensura.playable.alpha.zero-cost.v1';
const chat = document.querySelector('#chat');
const form = document.querySelector('#composer');
const input = document.querySelector('#input');
const reset = document.querySelector('#reset');

function loadState() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : resetState();
  } catch {
    return resetState();
  }
}

let state = loadState();

function saveState() {
  localStorage.setItem(KEY, JSON.stringify(state));
}

function message(role, text) {
  const el = document.createElement('div');
  el.className = `msg ${role}`;
  el.textContent = text;
  chat.appendChild(el);
}

function renderTranscript() {
  chat.replaceChildren();
  if (!state.transcript.length) {
    message('system', 'Sandbox-сцена. Рена перед тобой. Скажи что-нибудь.');
  } else {
    for (const row of state.transcript) {
      message(row.role === 'player' ? 'player' : 'rena', row.text);
    }
  }
  chat.scrollTop = chat.scrollHeight;
}

function renderStats() {
  document.querySelector('#turns').textContent = state.turn;
  document.querySelector('#memories').textContent = state.memories.length;
  for (const axis of ['trust', 'respect', 'affection', 'irritation']) {
    document.querySelector(`#${axis}`).textContent = state.relationship[axis] ?? 0;
  }
}

async function loadHud() {
  try {
    const res = await fetch('./live-snapshot.json', { cache: 'no-store' });
    if (!res.ok) return;
    const live = await res.json();
    document.querySelector('#hud-time').textContent = live?.hud?.time?.display || 'UNKNOWN';
    document.querySelector('#hud-place').textContent = live?.hud?.location?.display || 'UNKNOWN';
    document.querySelector('#hud-money').textContent = live?.hud?.money?.on_person_display || 'UNKNOWN';
    document.querySelector('#hud-elsewhere').textContent = live?.hud?.money?.elsewhere_display || 'UNKNOWN';
  } catch {
    // The committed fallback HUD remains visible if the snapshot cannot load.
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  const result = respondToRena(text, state);
  state = result.state;
  saveState();
  renderTranscript();
  renderStats();
  input.value = '';
  input.focus();
});

reset.addEventListener('click', () => {
  if (!confirm('Сбросить только этот sandbox-диалог? LIVE runtime не изменится.')) return;
  state = resetState();
  saveState();
  renderTranscript();
  renderStats();
});

renderTranscript();
renderStats();
loadHud();
