// FL-156 (ideas 1 and 10): saved Players views (columns and order, search, filters, sort, forecast period), column
// reordering, old fpl.cols carried forward, and the density preference. Device storage only.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function setup(saved = {}) {
  const mem = { ...saved };
  const ctx = vm.createContext({ location: { hash: '' }, matchMedia: () => ({ matches: false }),
    localStorage: { getItem: k => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = v; } },
    document: { querySelector: () => null, querySelectorAll: () => [] } });
  for (const file of ['core/state', 'core/model', 'core/plan', 'components/ui', 'components/tags', 'views/players']) {
    vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  }
  vm.runInContext(`
    T = { 1: { id: 1, name: 'One', short: 'ONE', fx: { 11: [{ opp: 1, home: true, fdr: 3 }] } } };
    const pl = (id, price, x) => ({ id, name: 'P' + id, full: 'P' + id, team: 1, pos: 'MID', price, xp: { 11: x }, xp1: x, form: 1, pts: id,
      xg: 0, xa: 0, xgi90_4: 0, own: id, nailed: 90, xmin: 80, status: 'a', price_proj: [0] });
    const players = [pl(1, 5, 3), pl(2, 6, 2), pl(3, 7, 1)];
    D = { players, squad: [], meta: { next_gw: 11, team_id: 1, built: '2026-11-13T00:00:00Z', price_deadlines: [] }, manager: { bank: 0, free_transfers: 1 }, crowd: null, plans: {} };
    P = Object.fromEntries(players.map(p => [p.id, p])); MINE = new Set(); GWS = [11];
    SB = { gw: 11, moves: [], ov: {}, chips: {}, rules: { locked: [], banned: [] } }; PG = GWS;
    term = (k, t) => t; playerTags = () => ''; stateView = () => '';`, ctx);
  return { run: e => vm.runInContext(e, ctx), mem };
}
const headers = html => [...html.matchAll(/<th class="sort[^"]*" data-sort="(\w+)"/g)].map(m => m[1]);

test('old column choices carry forward; unknown keys are ignored; order is kept', () => {
  const { run } = setup({ 'fpl.cols': JSON.stringify(['pts', 'gone', 'price', 'pts']) });
  assert.equal(run('JSON.stringify(colsOn())'), '["pts","price"]');
  assert.deepEqual(headers(run('vPlayers()')), ['name', 'pts', 'price']);
});

test('reordering columns moves them in the table, within bounds', () => {
  const { run } = setup({ 'fpl.cols': JSON.stringify(['team', 'price', 'pts']) });
  run('colMove("pts", -1)');
  assert.equal(run('JSON.stringify(colsOn())'), '["team","pts","price"]');
  run('colMove("team", -1)');                     // already first: no change
  assert.equal(run('JSON.stringify(colsOn())'), '["team","pts","price"]');
  assert.deepEqual(headers(run('vPlayers()')), ['name', 'team', 'pts', 'price']);
  assert.match(run('vPlayers()'), /aria-label="Move Team left" disabled/);
});

test('a saved view restores columns, order, search, filters, sort and the period; default clears them', () => {
  const { run, mem } = setup();
  run('store.set("fpl.cols", ["price", "pts"]); S.q = "P"; S.maxp = "6"; S.own = "diff"; S.sort = "price"; S.dir = 1; setForecast(3)');
  assert.equal(run('pvSaveAs("Cheap", "new")'), true);
  run('pvSelect("")');                            // default
  assert.equal(run('JSON.stringify([S.q, S.maxp, S.own, S.sort, S.dir, S.xh])'), '["","","any","xp5",-1,3]');   // period left alone
  assert.equal(run('JSON.stringify(colsOn())'), run('JSON.stringify(colsDefault())'));
  run('setForecast(6)');
  run('pvSelect("Cheap")');
  assert.equal(run('JSON.stringify([S.q, S.maxp, S.own, S.sort, S.dir, S.xh])'), '["P","6","diff","price",1,3]');
  assert.equal(run('JSON.stringify(colsOn())'), '["price","pts"]');
  assert.equal(JSON.parse(mem['fpl.playerview']), 'Cheap');
  assert.equal(JSON.parse(mem['fpl.horizon'] ?? 'null'), null);   // the Planner's horizon never written
});

test('changed, update, rename (no duplicates) and delete', () => {
  const { run } = setup();
  run('pvSaveAs("A", "new")');
  assert.equal(run('pvChanged()'), false);
  run('S.minform = "4"');
  assert.equal(run('pvChanged()'), true);
  assert.match(run("vPlayers()"), /data-pvact="update">Update view/);
  run('pvUpdate()');
  assert.equal(run('pvChanged()'), false);
  run('pvSelect(""); pvSaveAs("B", "new")');
  assert.equal(run('pvSaveAs("a", "rename")'), false);      // clashes with A, case aside
  assert.match(run('S.pvMsg'), /already a view called "A"/);
  assert.equal(run('pvSaveAs("C", "rename")'), true);
  assert.equal(run('JSON.stringify(pvList().map(v => v.name))'), '["A","C"]');
  assert.equal(run('pvSaveAs("   ", "new")'), false);
  run('pvDelete()');
  assert.equal(run('JSON.stringify(pvList().map(v => v.name))'), '["A"]');
  assert.equal(run('pvActive()'), null);
});

test('a view with a dropped column or sort, or broken storage, loads safely', () => {
  const bad = { name: 'Old', state: { cols: ['gone', 'pts'], sort: 'gone', dir: 5, pos: 'XYZ' } };
  const { run } = setup({ 'fpl.playerviews': JSON.stringify([bad, null, { name: '' }]) });
  assert.equal(run('pvList().length'), 1);
  run('pvSelect("Old")');
  assert.equal(run('JSON.stringify([colsOn(), S.sort, S.dir, S.pos])'), '[["pts"],"xp5",-1,"ALL"]');
  assert.equal(setup({ 'fpl.playerviews': '{not json' }).run('pvList().length'), 0);
});

test('density: compact by default, comfortable remembered, only on Players', () => {
  assert.doesNotMatch(setup().run('vPlayers()'), /dens-comfy/);
  const { run } = setup({ 'fpl.pdensity': '"comfy"' });
  assert.match(run('vPlayers()'), /class="panel explorer dens-comfy"/);
  assert.match(run('vPlayers()'), /data-dens="comfy" aria-pressed="true"/);
});
