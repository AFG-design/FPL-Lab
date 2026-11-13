// FL-156 (idea 26): player details beside the Players table on wide screens only; labelled rank; the forecast period's
// fixtures; FPL's flag shown as given; the planner action only for players you own.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function setup(wide) {
  const mem = {};
  const ctx = vm.createContext({ location: { hash: '' }, matchMedia: q => ({ matches: /min-width: 1280px/.test(q) ? wide : false }),
    localStorage: { getItem: k => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = v; } },
    document: { querySelector: () => null, querySelectorAll: () => [] } });
  for (const file of ['core/state', 'core/model', 'core/plan', 'components/ui', 'components/tags', 'components/watchlist', 'views/players']) {
    vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  }
  vm.runInContext(`
    const F = [{ opp: 1, home: true, xgf: 1, xga: 1, fdr: 3 }];
    T = { 1: { id: 1, name: 'Club One', short: 'ONE', fx: { 11: F, 12: F, 13: F } }, 2: { id: 2, name: 'Club Two', short: 'TWO', fx: { 11: F, 13: F } } };
    const pl = (id, team, pos, x, extra = {}) => ({ id, name: 'P' + id, full: 'Player ' + id, team, pos, price: 5, xp: { 11: x, 12: x, 13: x }, xp1: x,
      form: 1, pts: 1, xg: 0, xa: 0, xgi90_4: 0, own: 1, nailed: 88, xmin: 80, p_start: 0.9, status: 'a', price_proj: [0], ...extra });
    const players = [pl(1, 1, 'MID', 3), pl(2, 2, 'MID', 5, { status: 'd', chance: null, news: 'Knock' }), pl(3, 1, 'DEF', 2)];
    D = { players, squad: [{ id: 1, sell: 5.1 }], meta: { next_gw: 11, team_id: 1, built: '2026-11-13T00:00:00Z', price_deadlines: [] },
      manager: { bank: 0, free_transfers: 1 }, crowd: null, plans: {} };
    P = Object.fromEntries(players.map(p => [p.id, p])); MINE = new Set([1]); GWS = [11, 12, 13];
    SB = { gw: 11, moves: [], ov: {}, chips: {}, rules: { locked: [], banned: [] } }; PG = GWS;
    term = (k, t) => t; playerTags = () => ''; stateView = () => ''; syncPush = () => {};
    S.xh = 3;`, ctx);
  return e => vm.runInContext(e, ctx);
}

test('wide screen: the panel opens beside the table and marks the row; narrow: no panel (the sheet opens instead)', () => {
  let run = setup(true);
  run('S.side = 2');
  let html = run('vPlayers()');
  assert.match(html, /^<div class="pl-split">/);
  assert.match(html, /<tr class="sel">/);
  assert.match(html, /data-pside="2" aria-expanded="true"/);
  run = setup(false);
  run('S.side = 2');
  html = run('vPlayers()');
  assert.doesNotMatch(html, /pl-split|plSide|data-pside="2" aria-expanded/);
});

test("panel: labelled rank, the period's fixtures with a blank, FPL's flag as given", () => {
  const run = setup(true);
  const html = run('playerSide(2)');
  assert.match(html, /xP next 3/);
  assert.match(html, /#1 of 2 MIDs on this/);             // 10 (5 + blank 0 + 5) beats 9
  assert.equal((html.match(/<li><span class="muted">GW/g) || []).length, 3);
  assert.match(html, />!<\/span> <span class="note">Knock/);   // no chance given: "!", never 0%
  assert.doesNotMatch(html, /Plan a replacement/);
  assert.match(html, /data-p="2">Full details/);
  assert.match(run('playerSide(1)'), /data-plan-replace="1">Plan a replacement/);
  assert.match(run('playerSide(1)'), /you sell at £5\.1m/);
});

test('a player who has left the data closes the panel', () => {
  const run = setup(true);
  run('S.side = 99');
  assert.doesNotMatch(run('vPlayers()'), /pl-split/);
  assert.equal(run('S.side'), null);
});
