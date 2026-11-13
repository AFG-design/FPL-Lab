// FL-143: the chip ledger (actual), the GW20 divider and the use-now v best-week card (projected).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const src = fs.readFileSync(new URL('../site/js/views/chips.js', import.meta.url), 'utf8');
function setup(D) {
  const ctx = { D, P: { 7: { name: 'Haaland' } }, esc: s => String(s), f1: x => (+x).toFixed(1) };
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  return ctx;
}
const chips = [
  { name: 'Bench Boost', key: 'bboost', from: 1, to: 19, used: 5, available: false },
  { name: 'Triple Captain', key: '3xc', from: 1, to: 19, used: null, available: true },
  { name: 'Free Hit', key: 'freehit', from: 1, to: 19, used: null, available: true },
  { name: 'Bench Boost', key: 'bboost', from: 20, to: 38, used: null, available: false },
];
const D = { meta: { next_gw: 11 }, chips, season_gws: [], gw_info: [
  { gw: 11, bench_xp: 6.2, tc_player: 7, tc_xp: 7.1, squad_playing: 15 },
  { gw: 12, bench_xp: 8.4, tc_player: 7, tc_xp: 9.3, squad_playing: 15 }],
  chip_ledger: [{ key: 'bboost', name: 'Bench Boost', gw: 5, pts: 71, earned: 14, half: 1 },
                { key: 'freehit', name: 'Free Hit', gw: 8, pts: 60, earned: -3, without: 63, half: 1 },
                { key: 'wildcard', name: 'Wildcard', gw: 3, pts: 50, earned: null, why: "a Wildcard changes every later week too, so there's no fair single number", half: 1 },
                { key: '3xc', name: 'Triple Captain', gw: 22, pts: null, earned: null, why: 'pending', half: 2 }] };

test('ledger shows actual earned figures, explains a missing one, and the GW20 divider', () => {
  const html = setup(D).chipLedger();
  assert.match(html, /what they earned \(actual\)/);
  assert.match(html, /<b>\+14<\/b>/);
  assert.match(html, /v your squad before it \(63\)<\/small><\/td><td class="n">GW8<\/td><td class="n">60<\/td><td class="n"><b>-3<\/b>/);
  assert.match(html, /title="a Wildcard changes every later week too, so there's no fair single number">–/);
  assert.match(html, /Pending: GW22 not finished/);
  assert.match(html, /Chips renew at GW20/);
});

test('use-now card is projected, picks the best week, and says Free Hit is not projected', () => {
  const html = setup(D).chipNowVsBest(11);
  assert.match(html, /\(projected\)/);
  assert.match(html, /Triple Captain<\/td><td class="n">7\.1<br><small class="muted">Haaland<\/small><\/td><td class="n">9\.3 in GW12<br><small class="muted">Haaland/);
  assert.match(html, /Free Hit<\/td><td colspan="2" class="muted">Not projected here/);
  assert.doesNotMatch(html, /<td>Bench Boost<\/td>/);   // used this half; the second-half one isn't open yet
});

test('chip cards split by the GW20 divider', () => {
  const ctx = setup(D);
  ctx.chipNowVsBest = () => ''; ctx.chipLedger = () => '';
  const html = vm.runInContext('vChips()', ctx);
  assert.match(html, /Triple Captain[\s\S]*Chips renew at GW20[\s\S]*GW20–38/);
});
