// A move's player xP covers the rest of the plan only: from its gameweek to the plan's last week, never past it.
// Before, a GW12 move in a GW11–GW15 plan counted GW12–GW16 (PG.length weeks from GW12) while saying "over 5 GWs".
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function setup() {
  const ctx = vm.createContext({ location: { hash: '' }, matchMedia: () => ({ matches: false }),
    localStorage: { getItem: () => null, setItem: () => {} },
    document: { querySelector: () => null, querySelectorAll: () => [] } });
  for (const file of ['core/state', 'core/model', 'core/plan', 'views/planner']) {
    vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  }
  // 1 xP a week everywhere, so a figure's total is the number of weeks it counted; GW16 lies past the 5-GW plan
  vm.runInContext(`
    const fx = { opp: 2, home: true, xgf: 1, xga: 1, fdr: 3 }, all = { 11: [fx], 12: [fx], 13: [fx], 14: [fx], 15: [fx], 16: [fx] };
    T = { 1: { id: 1, name: 'One', short: 'ONE', fx: all }, 2: { id: 2, name: 'Two', short: 'TWO', fx: all } };
    const pl = (id, pos) => ({ id, name: 'P' + id, full: 'P' + id, team: 1, pos, price: 5, status: 'a', nailed: 90, xgi90_4: 0, dc_rate: 0,
      xp: { 11: 1, 12: 1, 13: 1, 14: 1, 15: 1, 16: 1 }, price_proj: [0] });
    const players = [pl(1, 'DEF'), pl(2, 'DEF')];
    D = { players, squad: [], meta: { next_gw: 11, team_id: 1, built: 'x' }, manager: { bank: 0, free_transfers: 1 }, plans: {} };
    P = Object.fromEntries(players.map(p => [p.id, p])); GWS = [11, 12, 13, 14, 15, 16]; PG = GWS.slice(0, 5);
    term = (k, t) => t; fieldSample = () => null;`, ctx);
  return e => vm.runInContext(e, ctx);
}

test('the rest of the plan from a gameweek: its weeks and its label', () => {
  const run = setup();
  assert.equal(run('planLeft(11)'), 5);
  assert.equal(run('planLeft(12)'), 4);
  assert.equal(run('planLeft(15)'), 1);
  assert.equal(run('planSpan(12)'), 'GW12–GW15');
  assert.equal(run('planSpan(15)'), 'GW15');
  // a gameweek outside the plan has no weeks left: 0, never a guess
  assert.equal(run('planLeft(16)'), 0);
  assert.equal(run('planSpan(16)'), 'no weeks');
});

test('move reasons count only the plan\'s weeks and say which', () => {
  const run = setup();
  assert.match(run('whyIn(1, 11)'), /^5\.0 xP over GW11–GW15/);
  assert.match(run('whyIn(1, 12)'), /^4\.0 xP over GW12–GW15/);   // was 5.0 "over 5 GWs" (GW12–GW16)
  assert.match(run('whyOut(2, 14)'), /2\.0 xP over GW14–GW15/);
});
