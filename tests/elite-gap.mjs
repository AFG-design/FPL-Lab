// FL-141: top 10k v everyone: ownership gaps, owned-but-benched, chips (sample v everyone), and what it says when the
// sample is old, incomplete or missing.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const src = readFileSync(new URL('../site/js/views/rivals.js', import.meta.url), 'utf8');
const P = { 1: { name: 'Haaland', own: 60, team: 1 }, 2: { name: 'Salah', own: 40, team: 2 }, 3: { name: 'Cheap', own: 30, team: 3 },
  4: { name: 'Rotated', own: 8, team: 4 } };
const ctx = vm.createContext({ P, T: { 1: { short: 'MCI' }, 2: { short: 'LIV' }, 3: { short: 'BOU' }, 4: { short: 'ARS' } },
  MINE: new Set([1]), esc: s => String(s), D: { meta: { cur_gw: 10 } } });
vm.runInContext(src, ctx);
const C = { gw: 10, total_players: 11288044, complete: true, overall_chips: { bboost: 2.5, '3xc': 1.2, freehit: 0.7, wildcard: 1.2 },
  top10k: { n: 2000, own: { 1: 90, 2: 20, 3: 10, 4: 30 }, eo: { 1: 160, 2: 18, 3: 10, 4: 12 }, cap: { 1: 70 }, chips: { bboost: 2.7 }, hits: 0.1 } };
const html = c => vm.runInContext(`eliteGapPanel(${JSON.stringify(c)})`, ctx);

test('ownership gaps both ways, with everyone from FPL', () => {
  const h = html(C);
  assert.match(h, /The top 10k own more[\s\S]*Haaland[\s\S]*<b class="up">\+30<\/b>/);
  assert.match(h, /Everyone owns more[\s\S]*Cheap[\s\S]*<b class="down">-20<\/b>/);
  assert.match(h, /11,288,044 managers/);
});

test('owned but benched = owned - (EO - captaincy)', () => {
  // Rotated: owned 30%, EO 12% with no captaincy -> started 12%, benched 18%
  assert.match(html(C), /Rotated[\s\S]*?<td class="n">30%<\/td><td class="n">12%<\/td><td class="n">18%<\/td>/);
});

test('chips v everyone, and hits said for the sample only', () => {
  const h = html(C);
  assert.match(h, /Bench Boost<\/td><td class="n">2\.7%<\/td><td class="n">2\.5%<\/td>/);
  assert.match(h, /doesn't publish a figure for everyone/);
});

test('old, incomplete or missing samples', () => {
  assert.match(html({ ...C, gw: 9 }), /from GW9/);
  assert.match(html({ ...C, complete: false, failed: 7 }), /Some requests failed when it was taken \(7\)/);
  assert.equal(html({ ...C, top10k: null }), '');
  assert.equal(html({ ...C, top10k: { n: 0, own: {} } }), '');
});
