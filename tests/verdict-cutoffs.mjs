// FL-127: one-week calls (captain, lineup) use CUT_WEEK, a plan's gain uses CUT_PLAN; both tested in tools/verdict_check.py.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const src = readFileSync(new URL('../site/js/core/plan.js', import.meta.url), 'utf8');
const pick = name => { const i = src.indexOf(name); return src.slice(i, src.indexOf('\n}\n', i) + 3); };
const c = vm.createContext({});
vm.runInContext(src.slice(src.indexOf('const CUT_WEEK'), src.indexOf('\n', src.indexOf('const CUT_WEEK'))) + '\n' + pick('function verdict('), c);

test('one-week scale: Coin flip under 1.5, Marginal 1.5 to 2, Strong from 2', () => {
  for (const [g, t] of [[0, 'Coin flip'], [1.2, 'Coin flip'], [1.5, 'Marginal'], [1.9, 'Marginal'], [2, 'Strong'], [3.4, 'Strong']])
    assert.equal(vm.runInContext(`verdict(${g}, ...CUT_WEEK).t`, c), t, `gap ${g}`);
});

test('plan scale (the default) is unchanged: Marginal from 1, Strong from 3', () => {
  for (const [g, t] of [[0.9, 'Coin flip'], [1, 'Marginal'], [2.9, 'Marginal'], [3, 'Strong']])
    assert.equal(vm.runInContext(`verdict(${g}).t`, c), t, `gain ${g}`);
});

test('Home and the Planner captain table use the one-week scale, not hard-coded numbers', () => {
  for (const f of ['views/week.js', 'views/planner.js']) {
    const s = readFileSync(new URL(`../site/js/${f}`, import.meta.url), 'utf8');
    assert.doesNotMatch(s, /verdict\([^)]*,\s*1,\s*0\.4\)/, f);
  }
});
