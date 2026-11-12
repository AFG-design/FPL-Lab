// FL-060: after GW38's deadline FPL lists no next gameweek; build.py sends meta.season_over, no forecast weeks and no
// plans. Every view that plans the next gameweek must say the season is over instead of throwing. myTeam() (the planned
// team, core/plan.js) has no week to read then, so here it throws: any view that still calls it fails the test.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const src = f => readFileSync(new URL(`../site/js/${f}`, import.meta.url), 'utf8');
function load(files, meta) {
  const ctx = vm.createContext({
    D: { meta, plans: {}, afg: { gw: null, p: { 1: { m: 3, n: 0 } } }, crowd: null, live: null },
    S: {}, P: {}, GWS: [], PG: [], esc: String, icon: () => '', term: (_, t) => t, console,
    store: { get: () => 'next', set() {} },
    myTeam: () => { throw new TypeError('no forecast week: myTeam() called at season end'); },
  });
  for (const f of files) vm.runInContext(src(f), ctx);
  return ctx;
}
const OVER = { season_over: true, next_gw: null, cur_gw: 38, last_gw: 38, cur_finished: true, proj_gws: [], plan_gws: [] };

test('Planner says the season is over', () => {
  const html = load(['components/ui.js', 'views/planner-views.js'], OVER).vPlanner();
  assert.match(html, /Season over/);
  assert.match(html, /GW38 was the last gameweek, so there is nothing left to plan/);
});
test('AFG suggestion says the season is over', () => {
  const html = load(['components/ui.js', 'views/afg.js'], OVER).vAfg();
  assert.match(html, /nothing left to suggest/);
});
test('Home opens Current GW, and a stored Next deadline view says the season is over', () => {
  const ctx = load(['components/ui.js', 'views/home.js'], OVER);
  ctx.S.home = null;
  assert.equal(vm.runInContext('homeView()', ctx), 'current');
  ctx.S.home = 'next';
  const html = ctx.vHome();
  assert.match(html, /nothing left to plan/);
  assert.doesNotMatch(html, /couldn't be drawn|undefined|null/);
});
test('Rivals: no planned team to compare, without throwing', () => {
  const ctx = load(['components/ui.js', 'views/rivals.js'], OVER);
  assert.equal(vm.runInContext('recTeam()', ctx), null);
  const html = ctx.teamCompare({ player: 'Rival', picks: [[1, 2]] }, { gw: 38 });
  assert.match(html, /Season over: there is no next gameweek to compare your teams for/);
});
test('In season the flag is absent and the views still ask for the planned team', () => {
  const ctx = load(['components/ui.js', 'views/rivals.js'], { next_gw: 12, cur_gw: 11 });
  assert.equal(vm.runInContext('seasonOver()', ctx), false);
  assert.throws(() => vm.runInContext('recTeam()', ctx), /myTeam\(\) called/);
});
