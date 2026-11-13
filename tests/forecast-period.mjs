// FL-156 (idea 3): one forecast period (Next GW / 3 / 5 / 6) for Players, Compare and the xP table, kept apart from
// the Planner's horizon; missing projections shown as missing, blanks as 0.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function setup(saved = {}) {
  const mem = { ...saved };
  const ctx = vm.createContext({ location: { hash: '' }, matchMedia: () => ({ matches: false }),
    localStorage: { getItem: k => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = v; } },
    document: { querySelector: () => null, querySelectorAll: () => [] } });
  for (const file of ['core/state', 'core/model', 'core/plan', 'components/ui', 'components/tags', 'views/players', 'views/xptable']) {
    vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  }
  // A: 2 a week; B: no projection in GW13 (a fixture, but missing); C: blank in GW12 (no fixture)
  vm.runInContext(`
    const fx = g => [{ opp: 2, home: true, xgf: 1, xga: 1, fdr: 3 }];
    T = { 1: { id: 1, name: 'One', short: 'ONE', fx: { 11: fx(), 12: fx(), 13: fx(), 14: fx(), 15: fx(), 16: fx() } },
          2: { id: 2, name: 'Two', short: 'TWO', fx: { 11: fx(), 13: fx(), 14: fx(), 15: fx(), 16: fx() } } };
    const pl = (id, team, xp, price) => ({ id, name: 'P' + id, full: 'P' + id, team, pos: 'MID', price, xp, xp1: xp[11], xp5: 0, form: 1, pts: 1,
      xg: 0, xa: 0, xgi90_4: 0, xgi90: 0, own: 1, nailed: 90, xmin: 80, mins4: 0, g_xg: 0, goals: 0, assists: 0, dc_rate: 0, dist: {}, status: 'a', price_proj: [0] });
    const players = [pl(1, 1, { 11: 2, 12: 2, 13: 2, 14: 2, 15: 2, 16: 2 }, 5), pl(2, 1, { 11: 3, 12: 3, 14: 3, 15: 3, 16: 3 }, 5),
      pl(3, 2, { 11: 4, 13: 4, 14: 4, 15: 4, 16: 4 }, 10)];
    D = { players, squad: [], meta: { next_gw: 11, team_id: 1, built: '2026-11-13T00:00:00Z', price_deadlines: [] }, manager: { bank: 0, free_transfers: 1 }, crowd: null, plans: {} };
    P = Object.fromEntries(players.map(p => [p.id, p])); MINE = new Set(); GWS = [11, 12, 13, 14, 15, 16];
    SB = { gw: 12, moves: [], ov: {}, chips: {}, rules: { locked: [], banned: [] } };
    PG = GWS.slice(0, S.horizon);
    term = (k, t) => t; playerTags = () => ''; stateView = () => '';`, ctx);
  return { run: e => vm.runInContext(e, ctx), mem };
}

test('totals: a missing projection is left out and marked, a blank counts as 0', () => {
  const { run } = setup();
  run('S.xh = 3');
  assert.equal(run('JSON.stringify(xTotals(P[1], fcGws()))'), '{"sum":6,"n":3,"of":3}');
  assert.equal(run('JSON.stringify(xTotals(P[2], fcGws()))'), '{"sum":6,"n":2,"of":3}');   // GW13 missing
  assert.equal(run('JSON.stringify(xTotals(P[3], fcGws()))'), '{"sum":8,"n":3,"of":3}');   // GW12 blank = 0, known
  assert.match(run('fcTxt(P[2])'), /\*<\/span>$/);
  assert.doesNotMatch(run('fcTxt(P[3])'), /\*/);
  run('S.xh = 1');
  assert.equal(run('fcLabel()'), 'GW11');
  assert.equal(run('fcTot(P[3]).sum'), 4);
});

test('the old 3/5/6 preference carries forward; Next GW is new', () => {
  assert.equal(setup({ 'fpl.xh': '6' }).run('S.xh'), 6);
  assert.equal(setup({ 'fpl.xh': '1' }).run('S.xh'), 1);
  assert.equal(setup({ 'fpl.xh': '4' }).run('S.xh'), 5);
});

test("changing the period never moves the Planner's weeks or the week you're editing", () => {
  const { run, mem } = setup({ 'fpl.horizon': '5' });
  const before = run('JSON.stringify([S.horizon, PG, SB.gw])');
  for (const h of [1, 3, 6, 5]) run(`setForecast(${h})`);
  assert.equal(run('JSON.stringify([S.horizon, PG, SB.gw])'), before);
  assert.equal(mem['fpl.horizon'], '5');
  assert.equal(mem['fpl.xh'], '5');
});

test('Players: the xP column, xP/£m and sorting follow the period, labelled with it', () => {
  const { run } = setup();
  run('S.xh = 1; S.sort = "xp5"; S.dir = -1; store.set("fpl.cols", ["xp1", "xp5", "val"])');
  let html = run('vPlayers()');
  assert.match(html, />xP GW11 ↓</);
  assert.match(html, />xP GW11\/£m</);
  assert.ok(html.indexOf('>P3<') < html.indexOf('>P2<') && html.indexOf('>P2<') < html.indexOf('>P1<'));   // 4 > 3 > 2
  run('S.xh = 6');
  html = run('vPlayers()');
  assert.match(html, />xP next 6 ↓</);
  // P1 12, P2 15 (5 of 6 weeks, marked), P3 20 (GW12 blank)
  assert.ok(html.indexOf('>P3<') < html.indexOf('>P2<') && html.indexOf('>P2<') < html.indexOf('>P1<'));
  assert.match(html, /aria-label="Forecast period"/);
  assert.match(html, /data-xh="1" aria-pressed="false">Next GW/);
  assert.match(html, /data-xh="6" aria-pressed="true">6 GWs/);
});

test('Compare uses the same period and labels it', () => {
  const { run } = setup();
  run('S.xh = 3; S.cmp = [1, 2]');
  const html = run('compareHTML()');
  assert.match(html, /xP next 3/);
  assert.match(html, /Next 3 fixtures/);
});
