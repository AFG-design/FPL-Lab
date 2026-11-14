// Rivals redesign: remembered league and its fallback, closest or pinned rival, the Rivalry Moment's lead claim, one
// scoring basis (before hits, 0 v dash, FPL-table fallback, GW check) and the weekly-honours cards. Sample values only.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const CHIPS = 'const CHIP_SHORT = { wildcard: "WC", freehit: "FH", bboost: "BB", "3xc": "TC" }; const CHIP_NAME = { wildcard: "Wildcard", freehit: "Free Hit", bboost: "Bench Boost", "3xc": "Triple Captain" };\n';
const src = CHIPS + readFileSync(new URL('../site/js/views/rivals.js', import.meta.url), 'utf8');
function app({ local = {}, live = null, liveState = null } = {}) {
  const mem = new Map(Object.entries(local).map(([k, v]) => [k, JSON.stringify(v)]));
  const ctx = vm.createContext({
    esc: s => String(s ?? ''), P: {}, T: {}, MINE: new Set(), S: {},
    D: { meta: { team_id: 1, next_gw: 11, cur_gw: 10 }, live },
    store: { get: k => (mem.has(k) ? JSON.parse(mem.get(k)) : null), set: (k, v) => mem.set(k, JSON.stringify(v)) },
    liveState: () => liveState, POLL: {}, console,
  });
  vm.runInContext(src, ctx);
  return ctx;
}
const row = (entry, total, extra = {}) => ({ entry, player: `Manager ${entry}`, team: 'T', total, rank: null, last_rank: null, gw_pts: 50, picks: [[1, 1]], hits: 0, live: null, ...extra });
const L = [{ id: 7, name: 'Big', size: 900, rows: [] }, { id: 8, name: 'Small', size: 12, rows: [] }, { id: 9, name: 'Mid', size: 40, rows: [] }];

test('remembered league; a league that has gone falls back to the smallest of up to 70 and says so', () => {
  assert.equal(app({ local: { 'fpl.league': 9 } }).rvLeague(L).lg.id, 9);
  const gone = app({ local: { 'fpl.league': 5 } }).rvLeague(L);
  assert.equal(gone.lg.id, 8);
  assert.match(gone.note, /isn't in this update/);
  assert.equal(app().rvLeague(L).note, '');   // never chosen: fallback without a warning
});

test('closest rival by season total; a pin wins; a big league says "tracked"', () => {
  const me = row(1, 700, { me: true });
  const lg = { id: 8, size: 4, rows: [me, row(2, 712), row(3, 695), row(4, 640)] };
  assert.equal(app().rvRival(lg, me).r.entry, 3);                     // 5 behind beats 12 ahead
  const pinned = app({ local: { 'fpl.rivalPins': { 8: 4 } } }).rvRival(lg, me);
  assert.deepEqual([pinned.r.entry, pinned.kind], [4, 'Pinned rival']);
  const lost = app({ local: { 'fpl.rivalPins': { 8: 99 } } }).rvRival(lg, me);
  assert.equal(lost.pinLost, true);
  assert.equal(app().rvRival({ ...lg, size: 3000 }, me).kind, 'Closest tracked rival');
});

test('a change of lead is claimed only with comparable ranks before and after', () => {
  const ctx = app(), C = { gw: 10, in_play: false };
  const sc = ctx.rvScores(C);
  const me = row(1, 711, { me: true, rank: 1, last_rank: 2, gw_pts: 68 });
  const rv = row(2, 705, { player: 'Ryan Dresou', rank: 2, last_rank: 1, gw_pts: 60 });
  const lg = { rows: [me, rv] };
  const html = ctx.rvMoment(C, lg, me, { r: rv, kind: 'Closest rival' }, sc);
  assert.match(html, /You lead by 6 points/);
  assert.match(html, /You overtook Ryan in GW10, scoring 68 to Ryan's 60/);
  const noPrior = ctx.rvMoment(C, lg, { ...me, last_rank: null }, { r: { ...rv, last_rank: null }, kind: 'Closest rival' }, sc);
  assert.doesNotMatch(noPrior, /overtook/);
  assert.match(noPrior, /no change of lead is claimed/);
  const rvHit = { ...rv, hits: 4 };
  const hit = ctx.rvMoment(C, { rows: [me, rvHit] }, me, { r: rvHit, kind: 'Closest rival' }, sc);
  assert.match(hit, /before Ryan's −4 hit, which the totals include/);
});

test('one basis: final is FPL before hits; live uses your live score only for the same GW; 0 stays 0; unknown is null', () => {
  const C = { gw: 10, in_play: true };
  const ls = { gross: 0, hits: 4 };
  const ctx = app({ live: { gw: 10, fixtures: [{ started: true }] }, liveState: ls });
  const sc = ctx.rvScores(C);
  assert.equal(sc.phase, 'live');
  assert.equal(sc.gwOf(row(1, 1, { me: true })), 0);                        // a genuine zero
  assert.equal(sc.hitOf(row(1, 1, { me: true })), 4);
  assert.equal(sc.gwOf(row(2, 1, { live: 33 })), 33);
  assert.equal(sc.srcOf(row(3, 1, { live: null, picks: null, gw_pts: 41 })), 'fpl');   // marked fallback
  assert.equal(sc.hitOf(row(3, 1, { picks: null })), null);                  // not known -> dash
  assert.equal(sc.gwOf(row(4, 1, { live: null, gw_pts: null })), null);
  const other = app({ live: { gw: 9, fixtures: [{ started: true }] }, liveState: ls }).rvScores(C);
  assert.equal(other.phase, 'nolive');
  assert.equal(other.gwOf(row(1, 1, { me: true, gw_pts: 12 })), 12);       // live payload for GW9 is never used for GW10
  const pre = app({ live: { gw: 10, fixtures: [{ started: false }] } }).rvScores(C);
  assert.equal(pre.phase, 'pre');
  assert.equal(app().rvScores({ gw: 10, in_play: false }).gwOf(row(5, 1, { gw_pts: 60, live: 99 })), 60);
});

test('award cards: visible medal words, shared medals, nobody qualified, unavailable reasons and partial coverage', () => {
  const ctx = app();
  const W = { gw: 10, coverage: { members: 13, size: 13 } };
  const climb = { status: 'ok', covered: 13, qualified: 4, places: [
    { entry: 2, player: 'Max', value: 4, rank: 1, medal: 'gold', before: 9, after: 5 },
    { entry: 3, player: 'Luke', value: 2, rank: 2, medal: 'silver', before: 13, after: 11 },
    { entry: 1, player: 'Ade', value: 1, rank: 3, medal: 'bronze', before: 2, after: 1 },
    { entry: 4, player: 'Marlon', value: 1, rank: 3, medal: 'bronze', before: 10, after: 9 }] };
  const h = ctx.awardCard('climber', climb, W);
  assert.match(h, /class="medal m-gold">gold</);
  assert.match(h, /Ade · You/);
  assert.match(h, /Max moved from 9th to 5th/);
  assert.match(h, /Ade and Marlon share bronze/);
  assert.match(ctx.awardCard('hits', { status: 'none', covered: 13, qualified: 0, places: [] }, W), /Nobody took a hit/);
  assert.match(ctx.awardCard('climber', { status: 'unavailable', why: "FPL doesn't keep earlier league ranks.", places: [] }, W), /Not available: FPL doesn't keep/);
  const part = ctx.awardCard('wall', { status: 'ok', covered: 20, qualified: 1, places: [{ entry: 5, player: 'X', value: 30, rank: 1, medal: 'gold', gk: 6, df: 24 }] }, { gw: 10, coverage: { members: 22, size: 2844 } });
  assert.match(part, /20 of 2,844 managers covered \(tracked managers only\)/);
  assert.equal(ctx.awWho({ coverage: { members: 22, size: 2844 } }), 'Among 22 tracked managers of 2,844');
  assert.equal(ctx.awVal('totw', { value: -2 }), '−2 pts');
  assert.equal(ctx.awVal('shuffler', { value: 6, chip: 'wildcard' }), '6 · WC');
  assert.equal(ctx.awVal('bench', { value: 1 }), '1 pt');
});
