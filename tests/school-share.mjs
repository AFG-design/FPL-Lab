// FL-014: the FPL School share card: what goes on it, and what's left off when a piece is missing.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const src = fs.readFileSync(new URL('../site/js/components/rating.js', import.meta.url), 'utf8') + '\n'
  + fs.readFileSync(new URL('../site/js/views/school.js', import.meta.url), 'utf8');
const GWS = [11, 12];
const pl = (id, pos, team, price, x) => ({ id, name: 'P' + id, pos, team, price, xp: Object.fromEntries(GWS.map(g => [g, x])) });
const squad = [pl(1, 'GKP', 1, 4.5, 3), pl(2, 'GKP', 2, 4.0, 1),
  ...[3, 4, 5, 6, 7].map(i => pl(i, 'DEF', i, 4.5, 3.5)), ...[8, 9, 10, 11].map(i => pl(i, 'MID', i, 6, 4)),
  pl(12, 'MID', 1, 5, 1), ...[13, 14, 15].map(i => pl(i, 'FWD', i - 10, 7, 5 + i / 100))];
function setup(D) {
  const P = {}; D.players.forEach(p => { P[p.id] = p; });
  const ctx = { D, P, esc: s => String(s), f1: x => (+x).toFixed(1), money: x => '£' + (+x).toFixed(1) + 'm',
    sgn: x => (x > 0 ? '+' : '') + (+x).toFixed(1), render: () => {} };
  vm.createContext(ctx); vm.runInContext(src, ctx); return ctx;
}
const picks = ids => ({ picks: ids.map(element => ({ element })), entry_history: { event: 10, bank: 5 } });
const entry = { name: 'Test XI', player_first_name: 'A', player_last_name: 'B', current_event: 10 };

test('card: best XI in formation with the captain, bench, rating and the move', () => {
  const D = { players: [...squad, pl(99, 'MID', 6, 5.5, 6)], rating: { gws: GWS, field: [60, 60] }, school: { relay: 'x', others: [[200, 'Newbie', 'DEF', 9, 4.0]] } };
  const c = setup(D);
  const ids = squad.map(p => p.id); ids[6] = 200;
  const r = c.schoolReview(123, entry, picks(ids));
  assert.equal(c.shareCardData(r), null);            // best 15 still working: no card yet
  r.best = 200; r.bestNote = null;
  const d = c.shareCardData(r);
  assert.equal(d.rows.flat().length, 11);
  assert.equal(JSON.stringify(d.rows.map(l => l.length)), "[1,3,4,3]");   // the 3 FWDs, then MIDs at 4 before DEFs at 3.5
  assert.equal(d.rows.flat().filter(p => p.cap).map(p => p.name).join(), 'P15');
  assert.equal(d.rows.flat().find(p => p.name === 'Newbie'), undefined);   // 0 xP, so on the bench
  assert.ok(d.bench.includes('Newbie') && d.bench.length === 4);
  assert.equal(d.score, c.schoolScore(r));
  assert.equal(d.move.in, 'P99');
  assert.match(d.field, /top-10k average \(120\.0\)/);
  assert.equal(d.gw, 11);
});

test('card: missing pieces are left off, never filled in', () => {
  const D = { players: squad, rating: { gws: GWS }, school: { relay: 'x', others: [[200, 'Newbie', 'DEF', 9, 4.0]] } };
  const c = setup(D);
  const ids = squad.map(p => p.id); ids[2] = 200;
  const r = c.schoolReview(5, entry, picks(ids));
  // no top-10k figure: rated against the best 15 alone, and the card has no top-10k line
  r.best = 200; r.bestNote = null; r.field = null;
  const d = c.shareCardData(r);
  assert.equal(d.field, null);
  assert.match(d.best, /^Best 15 for/);
  // neither a top-10k figure nor a best 15: no rating, so no card (the tab shows no buttons)
  r.best = null; r.bestNote = 'failed';
  assert.equal(c.shareCardData(r), null);
  // no projection: shown as missing ("–" on the card), not as 0
  const lu = c.schoolLineup(ids, 11, Object.fromEntries(ids.map(i => [i, c.schoolInfo(i)])));
  assert.equal(lu.xi.length + lu.bench.length, 15);
  assert.equal([...lu.xi, ...lu.bench].find(p => p.name === 'Newbie').xp, null);
});

test('card: their team as picked (the tab pitch) when FPL lists positions 1-15', () => {
  const D = { players: squad, rating: { gws: GWS, field: [60, 60] }, school: { relay: 'x', others: [] } };
  const c = setup(D);
  // 3-5-2 as picked, captain the keeper, bench GK + 3 forwards... a legal shape: GK, 4 DEF, 4 MID, 2 FWD
  const order = [1, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14, 2, 7, 12, 15];
  const pk = { picks: order.map((element, k) => ({ element, position: k + 1, is_captain: element === 1, is_vice_captain: element === 8 })),
    entry_history: { event: 10, bank: 5 } };
  const r = c.schoolReview(9, entry, pk);
  r.best = 200; r.bestNote = null;
  const d = c.shareCardData(r);
  assert.equal(d.picked, true);
  assert.equal(d.pickedGw, 10);
  assert.equal(JSON.stringify(d.rows.map(l => l.length)), '[1,4,4,2]');
  assert.equal(d.rows.flat().filter(p => p.cap).map(p => p.name).join(), 'P1');   // their captain, not the top xP
  assert.equal(d.bench.join(), 'P2,P7,P12,P15');                                  // their bench order
});
