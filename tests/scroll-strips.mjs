// FL-122: option strips on Fixtures and Stats show that they scroll, and on phones the Fixtures table starts with
// fixtures rather than Avg and Matches. The Planner's tabs are left alone (FL-090).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const read = f => readFileSync(new URL(`../site/${f}`, import.meta.url), 'utf8');

function strip({ scrollWidth, clientWidth, scrollLeft = 0 }) {
  const cls = new Set(), handlers = {};
  return { scrollWidth, clientWidth, scrollLeft, cls, handlers,
    classList: { toggle: (c, on) => (on ? cls.add(c) : cls.delete(c)) },
    querySelector: () => null, addEventListener: (ev, fn) => { handlers[ev] = fn; } };
}
function run(rows) {
  const c = vm.createContext({ document: { querySelectorAll: () => rows } });
  vm.runInContext(read('js/components/ui.js'), c);
  vm.runInContext('scrollStrips("#app .seg")', c);
}

test('a strip wider than its box fades the side with more; one that fits gets no fade', () => {
  const wide = strip({ scrollWidth: 500, clientWidth: 300 }), fits = strip({ scrollWidth: 300, clientWidth: 300 });
  run([wide, fits]);
  assert.deepEqual([...wide.cls], ['more-r']);
  assert.deepEqual([...fits.cls], []);
  wide.scrollLeft = 100; wide.handlers.scroll();
  assert.deepEqual([...wide.cls].sort(), ['more-l', 'more-r']);
  wide.scrollLeft = 200; wide.handlers.scroll();
  assert.deepEqual([...wide.cls], ['more-l']);
});

test('the fade is applied on Fixtures and Stats only, never the Planner', () => {
  const ev = read('js/shell/events.js');
  assert.match(ev, /if \(S\.view === "fixtures" \|\| S\.view === "stats"\) scrollStrips\("#app \.seg"\)/);
  const css = read('styles/views.css');
  for (const side of ['more-r', 'more-l']) assert.match(css, new RegExp(`:is\\(\\.view-fixtures, \\.view-stats\\) \\.seg\\.${side} \\{ mask-image`));
  assert.doesNotMatch(css, /planner[^{]*more-[rl]/);
});

test('phones: Avg and Matches come after the first three fixtures; desktop keeps them first', () => {
  const c = vm.createContext({ S: {}, D: {}, GWS: [] });
  vm.runInContext(read('js/views/fixtures.js'), c);
  const lead = (n, phone) => vm.runInContext(`fxLead(${n}, ${phone})`, c);
  assert.equal(lead(6, true), 3);
  assert.equal(lead(2, true), 2);   // a short window: summary after all of them
  assert.equal(lead(6, false), 0);
  assert.equal(vm.runInContext('fxPhone()', c), false);   // no matchMedia: desktop order, never a crash
});
