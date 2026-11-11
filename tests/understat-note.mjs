import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

// The note on Stats > Shots and Set pieces: how much of the season Understat covers, and a warning when it's behind.
function note(meta) {
  const ctx = vm.createContext({ location: { hash: '' }, document: { querySelector: () => ({ addEventListener() {} }) } });
  for (const file of ['core/state', 'views/stats']) vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  ctx.meta = meta;
  return vm.runInContext('D = { meta }; understatNote()', ctx);
}
const built = '2026-11-10T19:39:57+00:00';

test('up to date: plain note with coverage and date', () => {
  const t = note({ built, finished_fixtures: 100, understat: { matches: 100, built: '2026-11-10T19:38:00Z' } });
  assert.equal(t, 'Data from Understat (100 of 100 finished matches, last updated 10 Nov).');
});
test('a few hours behind on a matchday is not a warning', () => {
  const t = note({ built, finished_fixtures: 100, understat: { matches: 96, built: '2026-11-10T07:00:00Z' } });
  assert.match(t, /^Data from Understat \(96 of 100 finished matches/);
});
test('behind for over 36 hours: warning with the date and the count', () => {
  const t = note({ built, finished_fixtures: 100, understat: { matches: 89, built: '2026-11-01T20:46:53Z' } });
  assert.match(t, /warn-t/);
  assert.match(t, /hasn't updated since 1 Nov: 89 of 100 finished matches/);
});
test('behind with no update time counts as stale, never fresh', () => {
  assert.match(note({ built, finished_fixtures: 100, understat: { matches: 89 } }), /hasn't updated since an unknown date/);
});
test('no Understat data says so', () => {
  assert.equal(note({ built, finished_fixtures: 100, understat: null }), 'Understat data is unavailable.');
  assert.equal(note({ built, finished_fixtures: 100 }), 'Understat data is unavailable.');
});
test('older data.json without the finished count shows matches only', () => {
  assert.equal(note({ built, understat: { matches: 89, built: '2026-11-01T20:46:53Z' } }), 'Data from Understat (89 matches, last updated 1 Nov).');
});
