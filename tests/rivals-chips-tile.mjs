import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const CHIPS_PRE = 'const CHIP_SHORT = { wildcard: "WC", freehit: "FH", bboost: "BB", "3xc": "TC" }; const CHIP_NAME = { wildcard: "Wildcard", freehit: "Free Hit", bboost: "Bench Boost", "3xc": "Triple Captain" };\n';  // core/plan.js
const src = CHIPS_PRE + readFileSync(new URL('../site/js/views/rivals.js', import.meta.url), 'utf8');
const ctx = vm.createContext({});
vm.runInContext(src, ctx);
const txt = F => vm.runInContext(`fieldHitsTxt(${JSON.stringify(F)})`, ctx);

test('chips tile labels the hit figure and shows no points average', () => {
  assert.equal(txt({ hits: 0.1, avg_pts: 0 }), 'avg hit cost −0.1 pts a team');
  assert.equal(txt({ hits: 0 }), 'avg hit cost 0 pts a team');
  assert.doesNotMatch(src, /avg_pts/);
});

test('missing hits figure prints nothing', () => {
  for (const F of [{}, { hits: null }, { hits: 'x' }, null]) assert.equal(txt(F), '');
  assert.equal(vm.runInContext('fieldHitsTxt(undefined)', ctx), '');
  assert.equal(vm.runInContext('fieldHitsTxt({hits: NaN})', ctx), '');
});
