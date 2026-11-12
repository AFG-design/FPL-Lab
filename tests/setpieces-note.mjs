// FL-069: when history/setpieces.json couldn't be used, the Stats set-piece panel says so instead of implying that
// no takers changed. A normal log (or older data with no status) shows no note.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../site/js/views/stats.js', import.meta.url), 'utf8');
function render(setpieces) {
  const ctx = vm.createContext({ D: { setpieces, meta: {} }, T: { 1: { id: 1, name: 'Arsenal' } }, P: { 11: { name: 'Saka' } },
    MINE: new Set(), esc: String, term: (_, t) => t });
  vm.runInContext(source, ctx);
  return vm.runInContext('setPiecesHTML()', ctx);
}
const change = { date: '2026-10-01', team: 1, type: 'pen', old: null, new: 11 };
test('no note when the log loaded, or in older data with no status', () => {
  for (const status of ['ok', 'seeded', undefined]) {
    const html = render({ now: {}, changes: [change], status });
    assert.doesNotMatch(html, /Change history/);
    assert.match(html, /2026-10-01: Arsenal penalties now Saka/);
  }
});
test('says the history is unavailable when the log could not be seeded', () => {
  assert.match(render({ now: {}, changes: [], status: 'seed_failed' }), /Change history unavailable this update/);
});
test('says the list may be out of date when the log is unreadable', () => {
  assert.match(render({ now: {}, changes: [change], status: 'unreadable' }), /may be out of date/);
});
