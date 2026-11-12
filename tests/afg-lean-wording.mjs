// FL-126: AFG says how far it leans in its own words, never with the model's Strong / Marginal / Coin flip scale.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const src = readFileSync(new URL('../site/js/views/afg.js', import.meta.url), 'utf8');

test('the AFG tab never uses the model verdict', () => {
  assert.doesNotMatch(src, /\bverdict\(/);
  assert.doesNotMatch(src, /"(Strong|Marginal|Coin flip)"/);
});

test('AFG lean labels and cut-offs', () => {
  const c = vm.createContext({});
  vm.runInContext(src, c);
  const lean = (g, b, s) => vm.runInContext(`afgLean(${g}, ${b}, ${s})`, c);
  for (const [g, t] of [[1.2, 'Big lean'], [1, 'Big lean'], [0.6, 'Small lean'], [0.4, 'Small lean'], [0.1, 'Barely leans'], [-1, 'Barely leans'], [NaN, 'Barely leans'], [undefined, 'Barely leans']])
    assert.equal(lean(g, 1, 0.4).t, t, `captain gap ${g}`);
  for (const [g, t] of [[1.5, 'Big lean'], [1.4, 'Small lean'], [0.8, 'Small lean'], [0.79, 'Barely leans']])
    assert.equal(lean(g, 1.5, 0.8).t, t, `punt gain ${g}`);
  // never the "good" (green) colour the model uses for Strong
  for (const g of [5, 1, 0]) assert.notEqual(lean(g, 1, 0.4).c, 'good');
});
