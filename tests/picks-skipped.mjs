// FL-070: weeks whose picks couldn't be fetched are listed in review.skipped / vs_model.skipped. Review and You vs the
// model say so, instead of "appears after the first gameweek finishes" or a generic "isn't ready".
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const src = f => readFileSync(new URL(`../site/js/${f}`, import.meta.url), 'utf8');
function ctx(D) {
  const c = vm.createContext({ D: { history: [{ gw: 1, pts: 50 }], live: null, meta: {}, ...D }, S: {}, P: {},
    esc: String, icon: () => '', term: (_, t) => t, liveState: () => null, f1: n => n.toFixed(1) });
  vm.runInContext(src('components/ui.js'), c);
  return c;
}
test('Review says which weeks were left out', () => {
  const c = ctx({ review: { weeks: [], transfers: [], totals: {}, skipped: [3, 4] } });
  vm.runInContext(src('views/review.js'), c);
  const html = c.vReview();
  assert.match(html, /Your picks for GW3, GW4 couldn't be fetched this update, so those weeks are left out/);
  assert.doesNotMatch(html, /appears after the first gameweek finishes/);
});
test('Review in older data (no skipped list) keeps its first-week message', () => {
  const c = ctx({ review: { weeks: [], transfers: [], totals: {} } });
  vm.runInContext(src('views/review.js'), c);
  assert.match(c.vReview(), /appears after the first gameweek finishes/);
});
test('You vs the model says which weeks were left out', () => {
  const c = ctx({ vs_model: { weeks: [], skipped: [9] } });
  vm.runInContext(src('views/vsmodel.js'), c);
  const html = c.vVsModel();
  assert.match(html, /GW9 left out: your picks or that week's scores couldn't be fetched this update/);
});
