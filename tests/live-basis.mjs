// FL-078: live points on one basis across Home, the live panel, Rivals and Review: before hits (as FPL shows them),
// with provisional bonus, the hit named in a tooltip (and as a small −N beside rivals' scores, for phones).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

function setup({ hits = 4 } = {}) {
  const positions = ['GKP', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'FWD', 'FWD', 'FWD', 'GKP', 'MID', 'DEF', 'FWD'];
  const P = Object.fromEntries(positions.map((pos, i) => [i + 1, { pos, name: `Player ${i + 1}` }]));
  // every starter 2 pts, one with +3 provisional bonus, captain (9) doubled: 11*2 + 2 + 3 = 27 before the hit
  const rows = positions.map((_, i) => ({ id: i + 1, team: i + 1, pos: i + 1, mins: 90, pts: 2, prov: i === 0 ? 3 : 0, mult: i < 11 ? (i === 8 ? 2 : 1) : 0,
    cap: i === 8, vice: i === 9, xp: i < 11 ? 3 : 1 }));
  const fixtures = rows.map(r => ({ h: r.team, a: 99, started: true, done: true, ko: "2026-11-08T15:00:00Z", ev: [] }));
  const D = { history: [], meta: { next_gw: 12, built: "2026-11-08T17:00:00Z" },
    live: { gw: 11, rows, fixtures, hits, in_play: true, finished: false, points: 999, total_before: 100, pts_all: { 1: 30 } },
    crowd: { gw: 11, in_play: true, top10k: { n: 1, eo: { 1: 100 }, own: {}, cap: {} }, near: { n: 0 },
      leagues: [{ id: 1, size: 3, name: "L", rows: [
        { me: true, entry: 1, player: "Me", team: "Mine", live: 999, hits },
        { entry: 2, player: "Hit taker", team: "T2", live: 60, hits: 8, picks: [[1, 1]] },
        { entry: 3, player: "No hit", team: "T3", live: 50, hits: 0, picks: [[1, 1]] }] }] } };
  const ctx = vm.createContext({ store: { get: () => null, set() {} }, POLL: {}, icon: () => '', planName: () => 'Your plan', P, D, S: { field: "top10k" }, MINE: new Set(), esc: String, term: (_, label) => label, f1: n => n.toFixed(1),
    rankFmt: String, xpg: () => 0, myTeam: () => ({ xi: [1], mult: {} }), seasonOver: () => false, watchPanel: () => '', stateView: () => '' });
  for (const name of ['live', 'review', 'rivals']) vm.runInContext(readFileSync(new URL(`../site/js/views/${name}.js`, import.meta.url), 'utf8'), ctx);
  return { D, run: expr => vm.runInContext(expr, ctx) };
}

test('liveState gives the total before hits alongside the after-hit total', () => {
  const s = setup().run('liveState()');
  assert.equal(s.gross, 27);
  assert.equal(s.total, 23);
  assert.equal(s.projGross, 36);            // 11 x 3 + captain 3
  assert.equal(s.proj, 32);
});
test('live panel: headline before the hit, hit in the tooltip, field averages compared on the same basis', () => {
  const html = setup().run('livePanel()');
  assert.match(html, /<b style="font-size:32px" title="Before the −4 hit: 23 after it">27<\/b>/);
  assert.match(html, /of 36\.0 projected/);
  // top-10k average = 100% EO x 30 pts = 30 (EO x points has no hits): you're 3 behind on 27, not 7 on 23
  assert.match(html, /you're 3\.0 behind/);
});
test('no hit: no tooltip', () => {
  const html = setup({ hits: 0 }).run('livePanel()');
  assert.match(html, /<b style="font-size:32px">27<\/b>/);
  assert.doesNotMatch(html, /title="Before/);
});
test("Rivals: your row and theirs are before hits, each hit marked", () => {
  // the redesign (Rivals handoff) gives the hit its own column; the score cell keeps the after-hit tooltip
  const html = setup().run('vRivals()');
  assert.match(html, /title="Before the −4 hit: 23 after it">27<\/td>\s*<td class="n rv-hit"><span class="down">−4<\/span><\/td>/);
  assert.match(html, /title="Before the −8 hit: 52 after it">60<\/td>\s*<td class="n rv-hit"><span class="down">−8<\/span><\/td>/);
  assert.match(html, /<td class="n">50<\/td>\s*<td class="n rv-hit"><span class="muted">0<\/span><\/td>/);   // no hit: plain score, a real 0
  assert.doesNotMatch(html, />999</);                     // your row uses your live squad, not the sampled figure
  assert.match(html, /Points are GW11 points before hits, as FPL shows them; Hit is that manager's transfer cost/);
});
test('Review live panel: before the hit, hit named', () => {
  assert.match(setup().run('vReview()'), /title="Before the −4 hit: 23 after it">27 live pts \(−4 hit\)/);
});
