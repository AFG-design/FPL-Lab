// FL-156 (idea 13): presets fill in the normal filter bar, say first what they set and clear, keep position, search,
// columns and period; the new Nailed / xMins / Fixtures filters; fixture ranks by attack or clean sheets.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function setup() {
  const mem = {};
  const ctx = vm.createContext({ location: { hash: '' }, matchMedia: () => ({ matches: false }),
    localStorage: { getItem: k => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = v; } },
    document: { querySelector: () => null, querySelectorAll: () => [] } });
  for (const file of ['core/state', 'core/model', 'core/plan', 'components/ui', 'components/tags', 'views/fixtures', 'views/players']) {
    vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  }
  // club 1: easy attack (xgf 3), hard defence (xga 3); club 2: the reverse; club 3: middling; club 4: blank in GW11
  vm.runInContext(`
    const F = (opp, xgf, xga) => [{ opp, home: true, xgf, xga, fdr: 3 }];
    const team = (id, xgf, xga, blank) => ({ id, name: 'Club' + id, short: 'C' + id, att: 1, def: 1,
      fx: blank ? { 12: F(1, xgf, xga) } : { 11: F(1, xgf, xga), 12: F(1, xgf, xga) },
      far: blank ? [[12, 1, true, 3]] : [[11, 1, true, 3], [12, 1, true, 3]] });
    T = { 1: team(1, 3, 3), 2: team(2, 0.5, 0.2), 3: team(3, 1.5, 1.2), 4: team(4, 3, 0.2, true) };
    const pl = (id, team, pos, price, nailed, xmin, own) => ({ id, name: 'P' + id, full: 'P' + id, team, pos, price, nailed, xmin, own,
      xp: { 11: 2, 12: 2 }, xp1: 2, form: 1, pts: 1, xg: 0, xa: 0, xgi90_4: 0, status: 'a', price_proj: [0] });
    const players = [pl(1, 1, 'FWD', 6.0, 80, 85, 30), pl(2, 1, 'DEF', 4.5, 75, 80, 3), pl(3, 2, 'DEF', 4.5, 90, 88, 2),
      pl(4, 2, 'MID', 5.5, 50, 40, 4), pl(5, 3, 'MID', 5.0, 72, 70, 1), pl(6, 4, 'FWD', 9.0, 95, 88, 40)];
    D = { players, squad: [], meta: { next_gw: 11, team_id: 1, built: '2026-11-13T00:00:00Z', price_deadlines: [], league_goals: 1.4 },
      manager: { bank: 0, free_transfers: 1 }, crowd: null, plans: {} };
    P = Object.fromEntries(players.map(p => [p.id, p])); MINE = new Set(); GWS = [11, 12];
    SB = { gw: 11, moves: [], ov: {}, chips: {}, rules: { locked: [], banned: [] } }; PG = GWS;
    term = (k, t) => t; playerTags = () => ''; stateView = () => '';
    store.set('fpl.cols', ['price']); S.xh = 3;`, ctx);
  return e => vm.runInContext(e, ctx);
}
const shown = html => [...html.matchAll(/class="pname linkish">(P\d)</g)].map(m => m[1]);

test('fixture ranks: attack for MID/FWD, clean sheets for GKP/DEF; blanks add nothing', () => {
  const run = setup();
  const r = JSON.parse(run('JSON.stringify(fixtureRanks())'));
  assert.equal(r.att[1], 1);          // 3 + 3 projected goals
  assert.equal(r.def[2], 1);          // two near-certain clean sheets
  assert.ok(r.att[4] > r.att[1]);     // club 4: same rate, one game (blank in GW11)
  run('S.fxtop = "1"');
  assert.deepEqual(shown(run('vPlayers()')).sort(), ['P1', 'P3']);   // FWD at club 1 (attack), DEF at club 2 (defence)
});

test('Budget starters asks first, then sets the cap for the position and Nailed 70+, keeping search and position', () => {
  const run = setup();
  run('S.pos = "DEF"; S.q = "P"; S.minform = "4"; S.team = "1"');
  run('S.presetAsk = "budget"');
  const ask = run('vPlayers()');
  assert.match(ask, /<b>Budget starters<\/b> sets up to £4\.5m, Nailed 70\+, sorted by xP next 2\/£m, and clears Club1, form 4\+/);
  assert.match(ask, /data-preset-apply="budget"/);
  run('presetApply("budget")');
  assert.equal(run('JSON.stringify([S.pos, S.q, S.team, S.minform, S.maxp, S.minnail, S.sort, S.presetAsk])'), '["DEF","P","ALL","","4.5","70","val",null]');
  assert.deepEqual(shown(run('vPlayers()')).sort(), ['P2', 'P3']);
  assert.equal(run('JSON.stringify(colsOn())'), '["price"]');   // columns kept
  assert.equal(run('S.xh'), 3);                                   // period kept
});

test('Low-owned options: under 5% owned and xMins 60+; Strong fixtures: top 6 and Nailed 60+', () => {
  const run = setup();
  run('presetApply("lowown")');
  assert.deepEqual(shown(run('vPlayers()')).sort(), ['P2', 'P3', 'P5']);   // P4 owned 4% but 40 xMins
  run('presetApply("fixtures")');
  assert.equal(run('JSON.stringify([S.own, S.minxmin, S.fxtop, S.minnail])'), '["any","","6","60"]');
});

test('the new filters save in a view and are cleared with the rest', () => {
  const run = setup();
  run('S.minnail = "80"; S.minxmin = "70"; S.fxtop = "4"; pvSaveAs("Mine", "new"); pvSelect("")');
  assert.equal(run('JSON.stringify([S.minnail, S.minxmin, S.fxtop])'), '["","",""]');
  run('pvSelect("Mine")');
  assert.equal(run('JSON.stringify([S.minnail, S.minxmin, S.fxtop])'), '["80","70","4"]');
  assert.match(run('vPlayers()'), /Clear filters \(3\)/);
});
