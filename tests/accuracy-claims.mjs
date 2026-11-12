// FL-154: accuracy claims on the Model page and in the glossary are computed from data.json or carry the date and
// sample they came from; none is a bare figure that is never recomputed (hallucination-audit-2 N11).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const root = new URL('../site/js/', import.meta.url);
const read = f => readFileSync(new URL(f, root), 'utf8');

function noiseNote(A) {
  const c = vm.createContext({});
  vm.runInContext(read('views/model.js'), c);
  c.A = A;
  return vm.runInContext('noiseNote(A)', c);
}

test('the "how good is 0.4" note is computed from the live accuracy log', () => {
  const A = { weeks: [
    { gw: 7, live: null },
    { gw: 8, live: { corr: 0.45, fpl_corr: 0.38 } },
    { gw: 9, live: { corr: 0.41, fpl_corr: 0.36 } },
    { gw: 10, live: { corr: null, fpl_corr: 0.5 } },   // incomplete week: left out
  ] };
  const t = noiseNote(A);
  assert.match(t, /FPL's own projected points had a correlation of 0\.37/);
  assert.match(t, /live, GW8–9, average of 2 weekly figures/);
  assert.match(t, /against 0\.43 for this model/);
});

test('with no live weeks the note makes no comparison and no claim', () => {
  for (const A of [undefined, {}, { weeks: [] }, { weeks: [{ gw: 5, live: null }] }]) {
    const t = noiseNote(A);
    assert.doesNotMatch(t, /\d\.\d/);
    assert.match(t, /noisy/);
  }
});

test('the old unsourced claims are gone and the odds figure is dated', () => {
  const model = read('views/model.js'), explain = read('components/explain.js');
  assert.doesNotMatch(model, /about as good as public models get/);
  assert.doesNotMatch(explain, /within 10-20%/);
  assert.match(model, /backtest on 22 Oct 2026 \(this season's GW3–7\)[^<]*0\.40 to 0\.42/);
});
