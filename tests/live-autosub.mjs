import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

function setup() {
  const positions = ['GKP', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'FWD', 'FWD', 'FWD', 'GKP', 'MID', 'DEF', 'FWD'];
  const P = Object.fromEntries(positions.map((pos, i) => [i + 1, { pos, name: `Player ${i + 1}` }]));
  const rows = positions.map((_, i) => ({ id: i + 1, team: i + 1, pos: i + 1, mins: 90, pts: 2, prov: 0, mult: i < 11 ? (i === 8 ? 2 : 1) : 0, cap: i === 8, vice: i === 9 }));
  const fixtures = rows.map(r => ({ h: r.team, a: 99, started: true, done: true }));
  rows[4].mins = rows[4].pts = 0;
  rows[12].mins = rows[12].pts = 0;
  fixtures[12].done = fixtures[12].started = false;
  rows[13].pts = 7;
  const D = { history: [], meta: { next_gw: 12 }, live: { gw: 11, rows, fixtures, hits: 4, points: 999, total_before: 100,
    rank_curve: [[10, 150], [100, 140], [1000, 130], [10000, 120], [100000, 110], [1000000, 100]] } };
  const ctx = vm.createContext({ store: { get: () => null, set() {} }, POLL: {}, icon: () => '', planName: () => 'Your plan', P, D, S: {}, MINE: new Set(), esc: String, term: (_, label) => label, myTeam: () => ({ xi: [1], mult: {} }), seasonOver: () => false, watchPanel: () => '' });
  for (const name of ['live', 'review', 'rivals']) vm.runInContext(readFileSync(new URL(`../site/js/views/${name}.js`, import.meta.url), 'utf8'), ctx);
  return { D, rows, fixtures, run: expr => vm.runInContext(expr, ctx), state: () => vm.runInContext('liveState()', ctx) };
}

test('pending first bench player reserves the sub; later points and rank gain do not count', () => {
  const f = setup(), s = f.state();
  assert.equal(s.subs.length, 1);
  assert.equal(s.subs[0].in.id, 13);
  assert.equal(s.subs[0].sure, false);
  assert.equal(s.total, 18);
  assert.equal(s.contribution(s.rows[12]), 0);
  assert.equal(s.contribution(s.rows[13]), 0);
  assert.equal(s.rank.r, 6310);
  // FL-078: shown before the hit, as FPL does; the after-hit total (18) is in the tooltip
  assert.match(f.run('vReview()'), /title="Before the −4 hit: 18 after it">22 live pts \(−4 hit\)/);
  assert.match(f.run('vReview()'), /<b>0<\/b> \(if he plays\)/);
});

test('first bench player plays: points and provisional bonus count', () => {
  const f = setup(); f.rows[12].mins = 20; f.rows[12].pts = 5; f.rows[12].prov = 1; f.fixtures[12].started = true;
  const s = f.state();
  assert.equal(s.subs[0].in.id, 13); assert.equal(s.subs[0].sure, true);
  assert.equal(s.total, 24); assert.equal(s.contribution(s.rows[12]), 6);
  assert.doesNotMatch(f.run('vReview()'), /if he plays/);
});

test('first bench player breaks minimum three defenders: second is used', () => {
  const f = setup(); f.rows[4].mins = 90; f.rows[4].pts = 2; f.rows[1].mins = f.rows[1].pts = 0;
  const s = f.state(); assert.equal(s.subs[0].in.id, 14); assert.equal(s.total, 25);
});

test('keeper waits for reserve keeper, then counts him; no outfield substitution', () => {
  const f = setup(); f.rows[4].mins = 90; f.rows[4].pts = 2; f.rows[0].mins = f.rows[0].pts = 0;
  f.rows[11].mins = f.rows[11].pts = 0; f.fixtures[11].started = f.fixtures[11].done = false;
  let s = f.state(); assert.equal(s.subs[0].in.id, 12); assert.equal(s.subs[0].sure, false); assert.equal(s.total, 18);
  f.rows[11].mins = 90; f.rows[11].pts = 6; f.fixtures[11].started = f.fixtures[11].done = true;
  s = f.state(); assert.equal(s.subs[0].sure, true); assert.equal(s.total, 24);
});

test('finished zero-minute first bench player is skipped', () => {
  const f = setup(); f.fixtures[12].started = f.fixtures[12].done = true;
  assert.equal(f.state().subs[0].in.id, 14);
});

test('starter with a second fixture still to come cannot be replaced', () => {
  const f = setup(); f.fixtures.push({ h: 5, a: 99, started: false, done: false });
  assert.equal(f.state().subs.length, 0); assert.equal(f.state().total, 18);
});

test('normal XI and Bench Boost scoring are unchanged', () => {
  const f = setup(); f.rows[4].mins = 90; f.rows[4].pts = 2;
  assert.equal(f.state().total, 20); assert.equal(f.state().subs.length, 0);
  f.D.live.chip = 'bboost'; assert.equal(f.state().total, 31); assert.equal(f.state().subs.length, 0);
});

test('Rivals uses shared own live total and says every row includes auto-subs (FL-153)', () => {
  const f = setup();
  f.D.crowd = { gw: 11, in_play: true, top10k: { eo: {}, own: {}, cap: {}, n: 1 }, leagues: [{ id: 1, size: 1, rows: [{ me: true, player: 'Me', team: 'Team', live: 999 }] }] };
  const html = f.run('vRivals()');
  assert.match(html, /lg-best" title="Before the −4 hit: 18 after it">22<\/td>\s*<td class="n rv-hit"><span class="down">−4<\/span>/);   // FL-078: before hits
  assert.doesNotMatch(html, />999</);
  assert.match(html, /Live points include provisional bonus and automatic substitutions once a starter's matches are over/);
  assert.doesNotMatch(html, /rivals' live points exclude/);
});
