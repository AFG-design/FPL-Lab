import assert from 'node:assert/strict';
import test from 'node:test';
import { fixture } from './support/decision-fixture.mjs';
test('bench estimate uses four actual bench players and double projections once', () => {
  const run = fixture(['views/chips']);
  const a = run('benchBoostWeek(11)'), b = run('benchBoostWeek(12)');
  assert.equal(a.bench.length,4); assert.equal(b.total,2*a.total);
  assert.equal(a.total,a.bench.reduce((n,p)=>n+p.xp,0));
  assert.match(run('benchBoostCompare()'), /not the additional points attributable/);
});
test('blank, missing projection, planned moves, unavailable chip and read-only state', () => {
  const run = fixture(['views/chips']);
  run('SB.moves = [{gw:11,out:8,in:16}]; T[1].fx[11] = []; P[1].xp[11] = 0');
  const before = run('JSON.stringify(SB)');
  assert.equal(run('benchBoostWeek(11).moves.length'),1);
  assert.equal(run('benchBoostWeek(11).bench.find(p=>p.id===1).xp'),0);
  assert.equal(run('JSON.stringify(SB)'),before);
  run('D.chips[0].available=false; D.chips[0].used=2');
  assert.match(run('benchBoostWeek(11).unavailable'),/used in GW2/);
  run('delete P[2].xp[11]'); assert.match(run('benchBoostWeek(11).error'),/no projection/);
  assert.match(run('benchBoostWeek(30).error'),/No player projections/);
});
