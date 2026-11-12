// FL-074: the browser solver (plan-solver.js) plans for a squad holding four from one club, as optimise.py does:
// a week with no transfer keeps them, a week with a transfer ends with at most 3 from every club.
import assert from "node:assert/strict";
import test from "node:test";
import makeHighs from "../site/vendor/highs.js";
import { readFileSync } from "node:fs";
import solver from "../site/plan-solver.js";

const highs = await makeHighs();
const SETTINGS = solver.settingsFrom(JSON.parse(readFileSync(new URL("./fixtures/plan_rules.json", import.meta.url), "utf8")));
const POS = [...Array(3).fill("GKP"), ...Array(7).fill("DEF"), ...Array(7).fill("MID"), ...Array(5).fill("FWD")];
const GWS = [11, 12, 13];
function setup(xpOf = {}) {
  const players = {};
  POS.forEach((pos, k) => { const id = k + 1;
    players[id] = { pos, team: [4, 5, 11, 12].includes(id) ? 1 : 100 + id, price: 5, ok: true,
      xp: Object.fromEntries(GWS.map(g => [g, xpOf[id] ?? 4])) }; });
  return { players, squad: [1, 2, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 18, 19, 20] };
}
const club1 = (players, ids) => ids.filter(i => players[i].team === 1).length;
const run = (inp) => solver.solve(highs, { sell: {}, bank: 0, ft0: 1, gws: GWS, maxHits: 0, ...SETTINGS, ...inp });

test("rolling with four from one club has a plan (it was infeasible)", async () => {
  const { players, squad } = setup();
  const r = await run({ players, squad, maxMovesWeek: 0 });   // keep the squad: all four stay
  assert.equal(r.moves.length, 0);
  assert.equal(r.weeks.length, GWS.length);
});

test("any week with a transfer ends with at most 3 from the club", async () => {
  const { players, squad } = setup({ 9: 9 });
  const r = await run({ players, squad });
  let have = new Set(squad);
  for (const w of r.weeks) {
    const mv = r.moves.filter(m => m.gw === w.gw);
    mv.forEach(m => { have.delete(m.out); have.add(m.in); });
    assert.ok(club1(players, [...have]) <= (mv.length ? 3 : 4), `GW${w.gw}: ${club1(players, [...have])} from club 1`);
  }
  assert.ok(have.has(9));
});
