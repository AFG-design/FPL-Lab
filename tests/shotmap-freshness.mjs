// FL-155: player shot maps carry the same Understat freshness note as the Stats tabs (#87).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const built = '2026-11-10T19:39:57+00:00';
async function shotMap(meta, shots) {
  const el = { dataset: { pid: '7' }, innerHTML: '' };
  const ctx = vm.createContext({ location: { hash: '' }, document: { querySelector: () => ({ addEventListener() {} }), getElementById: () => el } });
  for (const file of ['core/state', 'views/stats', 'components/shotmap']) vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  ctx.meta = meta;
  ctx.shots = shots;
  vm.runInContext('D = { meta }; SHOTS.data = { players: { 7: shots } }', ctx);
  await vm.runInContext('fillShotMap(7)', ctx);
  return el.innerHTML;
}
const shot = [[90, 50, 0.4, 'G', 'O', 0, '2026-10-30']];
const stale = { built, finished_fixtures: 100, understat: { matches: 89, built: '2026-11-01T20:46:53Z' } };
const fresh = { built, finished_fixtures: 100, understat: { matches: 100, built: '2026-11-10T19:38:00Z' } };

test('stale Understat: the shot map warns, with date and match count', async () => {
  const h = await shotMap(stale, shot);
  assert.match(h, /warn-t/);
  assert.match(h, /hasn't updated since 1 Nov: 89 of 100 finished matches/);
});
test('stale Understat with no shots still warns', async () => {
  const h = await shotMap(stale, []);
  assert.match(h, /No shots this season/);
  assert.match(h, /hasn't updated since 1 Nov/);
});
test('up to date: plain coverage note, no warning', async () => {
  const h = await shotMap(fresh, shot);
  assert.doesNotMatch(h, /warn-t/);
  assert.match(h, /Data from Understat \(100 of 100 finished matches, last updated 10 Nov\)/);
});
test('no Understat meta says so', async () => {
  assert.match(await shotMap({ built }, shot), /Understat data is unavailable/);
});
