// FL-144 follow-up: the decision journal labels Wildcard weeks (moves free, a rebuild) as it does Free Hit weeks.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const src = fs.readFileSync(new URL('../site/js/views/vsmodel.js', import.meta.url), 'utf8');
function panel(chip) {
  const week = { gw: 10, chip, hits: 0, you: { moves: [], captain: 1 }, model: null, both: [], yours: [], skipped: [], players: { 1: { xp1: 5 } } };
  const ctx = vm.createContext({ D: { journal: { weeks: [week] }, meta: {} }, P: { 1: { name: 'A' } }, S: {}, store: { get: () => null, set() {} },
    esc: String, f1: x => (+x).toFixed(1), sgn: String, term: (_, t) => t });
  vm.runInContext(src, ctx);
  return vm.runInContext('journalPanel(10, false)', ctx);
}

test('journal: Wildcard and Free Hit weeks are labelled, other weeks are not', () => {
  assert.match(panel('wildcard'), /<b>Wildcard:<\/b> these moves were free/);
  assert.match(panel('freehit'), /<b>Free Hit:<\/b> these moves were for this week only/);
  const plain = panel(null);
  assert.doesNotMatch(plain, /Wildcard:|Free Hit:/);
});
