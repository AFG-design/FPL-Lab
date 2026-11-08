import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function setup(chance, status = 'i') {
  const ctx = vm.createContext({ location: { hash: '' }, document: { querySelector: () => ({ addEventListener() {} }) } });
  for (const file of ['core/state', 'core/model', 'components/player-sheet', 'components/watchlist', 'views/vsmodel', 'views/tpaths']) {
    vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  }
  ctx.chance = chance; ctx.status = status;
  vm.runInContext(`P = {1: {id: 1, name: 'Player', team: 1, pos: 'GKP', chance, status, news: '',
    xmin: 30, xp1: 2, s_min: [90,90,0], xp: {11: 2}, xp_detail: {mins: 2}, p_start: .8}};
    T = {1: {name: 'Club', short: 'CLB', fx: {11: [{opp: 1, home: true, xgf: 1.2, xga: 1.1}]}}}; PG = [11];`, ctx);
  return expr => vm.runInContext(expr, ctx);
}

for (const chance of [null, undefined, 0, 25, 75, 100]) {
  test(`FPL chance ${chance}: compact and sentence displays preserve its meaning`, () => {
    const run = setup(chance), expected = chance == null ? '!' : `${chance}%`;
    assert.equal(run('fplChance(P[1].chance)'), expected);
    assert.ok(run('flag(P[1])').includes(`>${expected}</span>`));
    assert.ok(run('jFlag(P[1])').includes(`>${expected}</span>`));
    const before = run('JSON.stringify(P[1])');
    const html = run('whyXP(P[1], 11)');
    if (chance == null) {
      assert.match(html, /FPL lists him as flagged, with no chance given/);
      assert.match(html, /FPL news since: flagged, no chance given/);
      assert.doesNotMatch(html, /FPL lists him at 0%|flagged at 0%/);
    } else {
      assert.ok(html.includes(`FPL lists him at ${chance}%`));
      assert.ok(html.includes(`flagged at ${chance}%`));
    }
    assert.equal(run('JSON.stringify(P[1])'), before);
  });
}

test('available player without a chance stays unflagged', () => {
  const run = setup(null, 'a');
  assert.equal(run('flag(P[1])'), '');
  assert.equal(run('jFlag(P[1])'), '');
  assert.doesNotMatch(run('whyXP(P[1], 11)'), /FPL lists him|no chance given/);
});

test('news is escaped while unknown chance stays unknown', () => {
  const run = setup(null);
  run(`P[1].news = '<img src=x onerror=alert(1)>'`);
  const html = run('whyXP(P[1], 11)');
  assert.match(html, /no chance given/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img/);
});

test('saved-path messages use reported chances; planner comparison assumptions are unchanged', () => {
  const run = setup(null);
  assert.equal(run(`chanceOf('i', null)`), 0);
  assert.equal(run(`chanceOf('d', null)`), 50);
  assert.equal(run(`chanceOf('a', null)`), 100);
  let changes = run(`tpChanges({deps: {1: ['d', 75, 1, {}]}})`);
  assert.equal(changes.worse.length, 1);
  assert.equal(changes.worse[0], 'Player: now injured, no chance given (was 75%)');
  run(`P[1].chance = 0`);
  changes = run(`tpChanges({deps: {1: ['d', 75, 1, {}]}})`);
  assert.equal(changes.worse[0], 'Player: now 0% to play (was 75%)');
  run(`P[1].chance = 75; P[1].status = 'd'`);
  changes = run(`tpChanges({deps: {1: ['i', null, 1, {}]}})`);
  assert.equal(changes.better[0], 'Player: now 75% to play (was injured, no chance given)');
});
