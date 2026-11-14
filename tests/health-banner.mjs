// FL-121: one refresh button, and a one-line phone warning that tests the same condition as the full banner.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const read = f => readFileSync(new URL(`../site/js/${f}`, import.meta.url), 'utf8');
const src = read('data/github.js');
const fn = name => src.slice(src.indexOf(`function ${name}(`), src.indexOf('\n}\n', src.indexOf(`function ${name}(`)) + 3);

function ctx(builtHoursAgo, last = null, running = false) {
  const now = Date.parse('2026-11-14T12:00:00Z');
  const c = vm.createContext({ Date: class extends Date { static now() { return now; } },
    icon: () => '<svg></svg>', HEALTH: { last, running },
    D: { meta: { built: new Date(now - builtHoursAgo * 36e5).toISOString() } } });
  vm.runInContext(fn('healthInfo') + fn('healthBanner'), c);
  return c;
}

test('fresh data and a working refresh: no warning, no banner', () => {
  const c = ctx(1);
  assert.equal(vm.runInContext('healthInfo()', c), null);
  assert.equal(vm.runInContext('healthBanner()', c), '');
});

test('stale data: the short phone line and the full banner say the same age', () => {
  const c = ctx(5);
  const h = vm.runInContext('healthInfo()', c);
  assert.equal(h.short, 'Data 5 hours old');
  assert.equal(h.head, 'Data is 5 hours old.');
  assert.equal(h.bad, false);
  assert.equal(vm.runInContext('healthInfo().short', ctx(50)), 'Data 2 days old');
  assert.equal(vm.runInContext('healthInfo().bad', ctx(7)), true);
});

test('a failed run after the build shows even when the data is fresh', () => {
  const c = ctx(1, { conclusion: 'failure', updated_at: '2026-11-14T11:30:00Z', html_url: 'https://example.invalid/r' });
  const h = vm.runInContext('healthInfo()', c);
  assert.equal(h.short, 'Refresh failed');
  assert.equal(h.bad, true);
});

test('the banner carries no refresh button of its own (the status line has the only one)', () => {
  assert.doesNotMatch(vm.runInContext('healthBanner()', ctx(5)), /data-refresh/);
  const nav = read('shell/nav.js');
  assert.equal((nav.match(/data-refresh="1"/g) || []).length, 1);
});
