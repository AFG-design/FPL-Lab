// Price-change wording: one "close to a change" cut-off and one update time on every page (audit finding C2).
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const root = new URL('../site/js/', import.meta.url);
const read = f => readFileSync(new URL(f, root), 'utf8');
const files = readdirSync(root, { recursive: true }).map(String).filter(f => f.endsWith('.js')).map(f => f.replaceAll('\\', '/'));

function ctx() {
  const c = vm.createContext({});
  // ukTime is the app's own UK date format (shell/nav.js); take just that line so no DOM is needed
  vm.runInContext(read('shell/nav.js').split('\n').find(l => l.startsWith('const ukTime =')), c);
  vm.runInContext(read('core/plan.js'), c);
  return expr => vm.runInContext(expr, c);
}

test('the cut-off is defined once, in plan.js, and is 75', () => {
  const run = ctx();
  assert.equal(run('PRICE_NEAR'), 75);
  assert.equal((read('core/plan.js').match(/PRICE_NEAR\s*=/g) || []).length, 1);
  for (const [v, rise, fall] of [[74.9, false, false], [75, true, false], [77, true, false], [100, true, false],
    [-74.9, false, false], [-75, false, true], [-77, false, true], [null, false, false], [undefined, false, false]]) {
    assert.equal(run(`priceRising(${v})`), rise, `priceRising(${v})`);
    assert.equal(run(`priceFalling(${v})`), fall, `priceFalling(${v})`);
  }
});

test('no page compares a price projection with its own 75 or 80', () => {
  const bare = /(>=\s*(75|80)\b|<=\s*-(75|80)\b)/, price = /price_proj|\bpr\b|\bprIn\b|\bprOut\b/;
  for (const f of files.filter(f => f !== 'core/plan.js')) {
    read(f).split('\n').forEach((line, i) => {
      if (price.test(line)) assert.doesNotMatch(line, bare, `${f}:${i + 1} has its own price cut-off`);
    });
  }
});

test('every page that flags a near price change uses the shared test', () => {
  for (const f of ['views/stats.js', 'views/week.js', 'views/planner.js', 'components/moves-summary.js', 'components/watchlist.js']) {
    assert.match(read(f), /priceRising\(|priceFalling\(/, f);
  }
});

test('Stats, Players and Deadlines take the update time from the one helper', () => {
  for (const f of ['views/stats.js', 'views/players.js', 'views/live.js']) assert.match(read(f), /priceUpdateTxt\(/, f);
  // no page adds its own offset to the listed time any more
  for (const f of files.filter(f => f !== 'core/plan.js')) assert.doesNotMatch(read(f), /pending_night[^\n]*\+\s*90|01:30/, f);
});

// the three call sites: Stats and Players pass the time with the day, Deadlines without (its list is grouped by day)
for (const [label, iso, full, clock] of [
  ['winter (GMT)', '2026-11-12T00:00:00+00:00', 'around Thu 12 Nov, 00:00', 'around 00:00'],
  ['summer (BST)', '2026-10-22T23:00:00+00:00', 'around Fri 23 Oct, 00:00', 'around 00:00'],
  ['FPL "Z" form', '2027-04-10T23:00:00Z', 'around Sun 11 Apr, 00:00', 'around 00:00'],
]) {
  test(`same update time on all three pages, ${label}`, () => {
    const run = ctx();
    const stats = run(`priceUpdateTxt(${JSON.stringify(iso)})`), players = run(`priceUpdateTxt(${JSON.stringify(iso)})`),
      deadlines = run(`priceUpdateTxt(${JSON.stringify(iso)}, false)`);
    assert.equal(stats, full);
    assert.equal(players, stats);
    assert.equal(deadlines, clock);
    assert.ok(stats.endsWith(deadlines.replace('around ', '')), 'same clock time with and without the day');
    assert.equal(run(`priceUpdateAt(${JSON.stringify(iso)}).getTime()`), new Date(iso).getTime(), 'the listed time, no offset');
  });
}

test('missing or unreadable time gives no text rather than a guess', () => {
  const run = ctx();
  for (const v of ['null', 'undefined', '""', '"not a date"']) {
    assert.equal(run(`priceUpdateAt(${v})`), null);
    assert.equal(run(`priceUpdateTxt(${v})`), '');
  }
});

test('Players and Stats name the same night: the update after the build, not after now', () => {
  const ctx = vm.createContext({ location: { hash: '' }, document: { querySelector: () => ({ addEventListener() {} }) } });
  for (const f of ['core/state', 'shell/nav', 'core/plan']) {
    try { vm.runInContext(readFileSync(new URL(`../site/js/${f}.js`, import.meta.url), 'utf8'), ctx); } catch (e) { /* nav.js touches the DOM; only its helpers are needed */ }
  }
  const deadlines = ['2026-11-11T00:00:00Z', '2026-11-12T00:00:00Z'];
  // built the evening before: the figures are for the 11th, whatever the clock says now
  vm.runInContext(`D = { meta: { built: '2026-11-10T19:39:57Z', price_deadlines: ${JSON.stringify(deadlines)} }, prices: { pending_night: '2026-11-11T00:00:00+00:00' } }`, ctx);
  assert.equal(vm.runInContext('nextPriceUpdate()', ctx), '2026-11-11T00:00:00+00:00');
  vm.runInContext(`D.prices = {}`, ctx);
  assert.equal(vm.runInContext('nextPriceUpdate()', ctx), '2026-11-11T00:00:00Z');
  vm.runInContext(`D.meta.built = '2026-11-11T08:00:00Z'`, ctx);
  assert.equal(vm.runInContext('nextPriceUpdate()', ctx), '2026-11-12T00:00:00Z');
  vm.runInContext(`D.meta.price_deadlines = []`, ctx);
  assert.equal(vm.runInContext('nextPriceUpdate()', ctx), null);
});
