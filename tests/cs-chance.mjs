// One clean-sheet formula on the site (B7): the player sheet, the team sheet and the Fixtures code all use
// csChance() with the model's cs_k from data.json (meta.model), and the home factor comes from there too.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const XGA = 1.53;

// model: the meta.model object, or undefined for a data.json built before the field existed
function setup(model) {
  const ctx = vm.createContext({ location: { hash: '' }, document: { querySelector: () => ({ addEventListener() {} }) } });
  for (const file of ['core/state', 'core/model', 'views/fixtures', 'components/player-sheet']) {
    vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  }
  ctx.model = model; ctx.XGA = XGA;
  vm.runInContext(`D = {meta: {league_goals: 1.4, next_gw: 11, ...(model ? {model} : {})}};
    P = {1: {id: 1, name: 'Keeper', team: 1, pos: 'GKP', chance: null, status: 'a', news: '',
      xmin: 90, xp1: 3, s_min: [90,90,90], xp: {11: 3}, xp_detail: {mins: 2, cs: 1}, p_start: .95}};
    T = {1: {name: 'Club', short: 'CLB', att: 1.2, def: 0.8, fx: {11: [{opp: 2, home: true, xgf: 1.2, xga: XGA}]},
             far: [[11, 2, true, 3], [30, 2, true, 3], [31, 2, false, 3]]},
         2: {name: 'Other', short: 'OTH', att: 1.1, def: 1.3, fx: {}, far: []}};
    GWS = [11]; PG = [11];`, ctx);
  return expr => vm.runInContext(expr, ctx);
}
const sheetPct = run => +run('whyXP(P[1], 11)').match(/about a <b>(\d+)%<\/b> clean-sheet chance/)[1];
const gridPct = run => Math.round(run('csChance(T[1].fx[11][0].xga)') * 100);
const swingPct = run => Math.round(run('teamRun(T[1])[11][0].cs') * 100);

test('cs_k 0.9, xGA 1.53: player sheet, Fixtures grid and swings all say 25% (not the plain-Poisson 22%)', () => {
  const run = setup({ home: 1.05, cs_k: 0.9 });
  assert.equal(Math.round(Math.exp(-XGA) * 100), 22);
  assert.equal(sheetPct(run), 25);
  assert.equal(gridPct(run), 25);
  assert.equal(swingPct(run), 25);
});

test('a different cs_k in meta.model changes every display together', () => {
  const run = setup({ home: 1.05, cs_k: 0.5 }), want = Math.round(Math.exp(-0.5 * XGA) * 100);
  assert.equal(want, 47);
  assert.equal(sheetPct(run), want);
  assert.equal(gridPct(run), want);
  assert.equal(swingPct(run), want);
});

test('home advantage for far-fixture estimates comes from meta.model', () => {
  for (const home of [1.05, 1.2]) {
    const run = setup({ home, cs_k: 0.9 });
    const h = run('fxCells(T[1], 30)[0]'), a = run('fxCells(T[1], 31)[0]');
    assert.ok(Math.abs(h.xgf - 1.4 * 1.2 * 1.3 * home) < 1e-9);
    assert.ok(Math.abs(h.xga - 1.4 * 1.1 * 0.8 / home) < 1e-9);
    assert.ok(Math.abs(a.xgf - 1.4 * 1.2 * 1.3 / home) < 1e-9);
    assert.ok(Math.abs(run('teamRun(T[1])[31][0].xga') - 1.4 * 1.1 * 0.8 * home) < 1e-9);
  }
});

test('data.json without meta.model (built before the field existed): the documented fallback, 1.05 and 0.9', () => {
  const run = setup(undefined);
  assert.deepEqual(JSON.parse(run('JSON.stringify(modelSet())')), { home: 1.05, cs_k: 0.9 });
  assert.equal(sheetPct(run), 25);
  assert.equal(gridPct(run), 25);
  assert.ok(Math.abs(run('fxCells(T[1], 30)[0].xgf') - 1.4 * 1.2 * 1.3 * 1.05) < 1e-9);
});

test('no clean-sheet formula or home factor is written out by hand outside core/model.js', () => {
  for (const file of ['views/fixtures', 'components/player-sheet', 'components/team-sheet']) {
    const src = readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8');
    assert.doesNotMatch(src, /Math\.exp\(-\s*(0\.9\s*\*\s*)?x?\.?xga\)/, file);
    assert.doesNotMatch(src, /H = 1\.05/, file);
  }
});
