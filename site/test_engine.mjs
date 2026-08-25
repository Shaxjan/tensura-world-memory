import test from 'node:test';
import assert from 'node:assert/strict';
import { resetState, respondToRena } from './engine.js';

test('greeting creates memory and bounded affection', () => {
  const first = respondToRena('Привет', resetState());
  assert.equal(first.observable.speechAct, 'greet');
  assert.equal(first.state.turn, 1);
  assert.equal(first.state.memories.length, 1);
  assert.equal(first.state.relationship.affection, 1);
});

test('Rena can refuse guitar request', () => {
  const out = respondToRena('Дай мне свою гитару', resetState());
  assert.equal(out.observable.speechAct, 'refuse');
  assert.match(out.observable.text, /гитар|Попросить/i);
});

test('wedding preference stays unknown', () => {
  const out = respondToRena('Когда мы поженимся?', resetState());
  assert.equal(out.invariants.weddingPreferenceStillUnknown, true);
  assert.equal(out.private.relationshipDelta.affection, undefined);
});

test('same starting state and input is deterministic', () => {
  const a = respondToRena('Ты павлин', resetState());
  const b = respondToRena('Ты павлин', resetState());
  assert.deepEqual(a, b);
});

test('multi-turn state persists without obedience assumption', () => {
  let state = resetState();
  state = respondToRena('Привет', state).state;
  const second = respondToRena('Отдай гитару', state);
  assert.equal(second.observable.speechAct, 'refuse');
  assert.equal(second.invariants.relationshipDoesNotImplyObedience, true);
  assert.equal(second.state.memories.length, 2);
});
