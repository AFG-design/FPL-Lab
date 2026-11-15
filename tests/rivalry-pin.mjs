import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
function setup() {
  const mem = {};
  const ctx = vm.createContext({ location: { hash: '' }, localStorage: { getItem: k => mem[k] || null, setItem: (k,v) => mem[k] = v } });
  for (const f of ['core/state', 'views/rivals']) vm.runInContext(readFileSync(`site/js/${f}.js`, 'utf8'), ctx);
  vm.runInContext(`
    D = { meta: { team_id: 1, cur_gw: 10, built: new Date().toISOString() }, crowd: { gw: 10, in_play: true,
      leagues: [{ id: 1, name: 'League', size: 2, rows: [
        { me: true, entry: 1, player: 'You', total: 100, rank: 1, picks: [[8,2]], live: 10, hits: 0 },
        { entry: 2, player: 'Rival', total: 100, rank: 2, picks: [[8,1]], live: 10, hits: 0 }] }] },
      live: { gw: 10, fixtures: [{ started: true }] } };
    P = { 8: { name: 'Shared captain', team: 1 } };
    const POLL = {};
    function liveState() { return { gross: 10, hits: 0, xi: [{id:8}], mult: () => 2 }; }
    function rowMatch() { return {left: 1}; }
    rivalryPin('rival', 1, 2);
  `, ctx);
  return s => vm.runInContext(s, ctx);
}
test('pin persists, ties and shared captaincy remain meaningful', () => {
  const run = setup();
  assert.equal(run('store.get(rivalryKey()).entry'), 2);
  const text = run('rivalrySummary()');
  assert.match(text, /Level on gameweek points/);
  assert.match(text, /Shared captain.*you ×2, rival ×1/);
  assert.match(text, /after hits.*provisional/);
});
test('finished and unavailable gameweek data never invent remaining players', () => {
  const run = setup();
  run('D.crowd.in_play = false; D.meta.cur_finished = true');
  assert.match(run('rivalrySummary()'), /Gameweek finished/);
  run('D.crowd.gw = 9');
  assert.match(run('rivalrySummary()'), /unavailable for the current gameweek/);
  assert.equal(run('store.get(rivalryKey()).entry'), 2);
});
test('league pin labels overall lead, can be replaced and removed', () => {
  const run = setup();
  run("rivalryPin('league',1); D.crowd.leagues[0].rows[0].total = 105");
  assert.match(run('rivalrySummary()'), /5 pts ahead of second place/);
  assert.match(run('rivalrySummary()'), /overall standings/);
  run('rivalryPin(null)'); assert.equal(run('rivalrySummary()'), '');
});
