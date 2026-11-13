// FL-147: the FPL School tab: the review maths, every "can't show it" message, and the optimiser's freezeAfter.
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
  pl(12, 'MID', 1, 5, 1), ...[13, 14, 15].map(i => pl(i, 'FWD', i - 10, 7, 5))];
function setup(D) {
  const P = {}; D.players.forEach(p => { P[p.id] = p; });
  const ctx = { D, P, esc: s => String(s), f1: x => (+x).toFixed(1), money: x => '£' + (+x).toFixed(1) + 'm',
    sgn: x => (x > 0 ? '+' : '') + (+x).toFixed(1), render: () => {} };
  vm.createContext(ctx); vm.runInContext(src, ctx); return ctx;
}
const D = { players: [...squad, pl(99, 'MID', 6, 5.5, 6)], rating: { gws: GWS, field: [60, 60] },
  school: { relay: 'https://relay.example', others: [[200, 'Newbie', 'DEF', 9, 4.0]] } };
const picks = ids => ({ picks: ids.map(element => ({ element })), entry_history: { event: 10, bank: 5 } });
const entry = { name: 'Test XI', player_first_name: 'A', player_last_name: 'B', current_event: 10 };

test('review: the move, the money (assumed prices) and a player with no projection', () => {
  const c = setup(D);
  const ids = squad.map(p => p.id); ids[6] = 200;   // swap a defender for an unprojected one
  const r = c.schoolReview(123, entry, picks(ids));
  assert.equal(r.move.in, 99);
  assert.equal(r.budget.toFixed(1), (0.5 + squad.reduce((a, p) => a + p.price, 0) - 4.5 + 4.0).toFixed(1));
  assert.deepEqual([...r.notProjected], ['Newbie']);
  r.best = 300; r.bestNote = null;
  assert.ok(r.mine < 120);   // behind the field: scored against the floor (0 = 70% of the field's 120)
  assert.equal(c.schoolScore(r), Math.max(0, Math.round(50 * (r.mine - 84) / 36)));
  r.mine = 150;              // ahead of the field: between the field (50) and the best (100)
  assert.equal(c.schoolScore(r), Math.round(50 + 50 * (150 - 120) / (300 - 120)));
});

test('rating scale: 0 at 30% under the field, 50 at the field, 100 at the best, same for Home and FPL School', () => {
  const c = setup(D);
  // field 280, best 300: the old scale put 20 behind at 0; now 0 is 196 (70% of 280)
  assert.equal(c.ratingScore(280, 280, 300), 50);
  assert.equal(c.ratingScore(300, 280, 300), 100);
  assert.equal(c.ratingScore(290, 280, 300), 75);
  assert.equal(c.ratingScore(260, 280, 300), Math.round(50 * (260 - 196) / 84));   // 38, was 0
  assert.equal(c.ratingScore(196, 280, 300), 0);
  assert.equal(c.ratingScore(150, 280, 300), 0);
  assert.equal(c.ratingScore(320, 280, 300), 100);
  // missing inputs keep their old fallbacks
  assert.equal(c.ratingScore(150, null, 300), 50);         // no top-10k figure: share of the best
  assert.equal(c.ratingScore(140, 120, null), 58);         // no best yet, ahead of the field
  assert.equal(c.ratingScore(100, null, null), null);
  assert.equal(c.ratingWord(38), 'Below average');
});

test('no relay, errors and results are all said', () => {
  let c = setup({ ...D, school: { relay: null, others: [] } });
  assert.match(c.vSchool(), /relay isn't set up yet/);
  c = setup(D);
  vm.runInContext('SCHOOL.err = "FPL has no team 5."', c);
  assert.match(c.vSchool(), /role="alert">FPL has no team 5\./);
  vm.runInContext('SCHOOL.err = ""; SCHOOL.res = schoolReview(123, ' + JSON.stringify(entry) + ', ' + JSON.stringify(picks(squad.map(p => p.id))) + '); SCHOOL.res.bestNote = "x failed"', c);
  const html = c.vSchool();
  assert.match(html, /private and can be lower \(assumed\)/);
  assert.match(html, /X failed\./);
  assert.match(html, /One move/);
  assert.throws(() => setup({ ...D, rating: {} }).schoolReview(1, entry, picks([1])), /no rating gameweeks/);
});

test('plan-solver: freezeAfter holds the squad from that week', () => {
  const ps = fs.readFileSync(new URL('../site/plan-solver.js', import.meta.url), 'utf8');
  const ctx = { globalThis: {} }; vm.createContext(ctx); vm.runInContext(ps, ctx);
  const S = ctx.FPLSolver || ctx.globalThis.FPLSolver;
  const players = {}; D.players.forEach(p => { players[p.id] = { pos: p.pos, team: p.team, price: p.price, xp: p.xp, ok: true }; });
  const base = { players, squad: [], sell: {}, bank: 100, ft0: 5, gws: GWS, pool: { GKP: 2, DEF: 5, MID: 6, FWD: 3 }, decay: 1, benchW: 0.1,
    hit: 0, maxMovesWeek: 15, eoWeeks: 1, ftValue: 0, variance: {}, varianceOther: 0 };
  const a = S.buildLP(base).lp, b = S.buildLP({ ...base, freezeAfter: 1 }).lp;
  const eq = lp => (lp.match(/ = 0$/gm) || []).length;
  assert.ok(eq(b) > eq(a));
});
