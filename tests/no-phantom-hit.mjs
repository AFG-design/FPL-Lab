// A hit is only ever the moves beyond your free transfers (FPL's rule), never a -4 booked to bank an extra transfer.
// Found by the property tests (tests/test_plan_properties.py, Chase rank): the browser solver, like optimise.py, could
// take a hit in a week with no moves to raise the next week's free transfers, so with maxHits 1 it rolled in GW11 with
// a "hit" and made 4 moves on 3 free transfers in GW12, where FPL gives 2 and charges -8. Python twin:
// tests/test_no_phantom_hit.py.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import makeHighs from "../site/vendor/highs.js";
import solver from "../site/plan-solver.js";

const S = solver.settingsFrom(JSON.parse(readFileSync(new URL("./fixtures/plan_rules.json", import.meta.url), "utf8")));
const POS = ["GKP", "GKP", "DEF", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "MID", "FWD", "FWD", "FWD"];
const GWS = [11, 12], players = {};
POS.forEach((p, k) => { players[k + 1] = { pos: p, team: k + 1, price: 5, ok: true, xp: { 11: 0.5, 12: 0.5 } }; });
["DEF", "MID", "MID", "FWD", "DEF"].forEach((p, k) => { players[16 + k] = { pos: p, team: 16 + k, price: 5, ok: true, xp: { 11: 0.5, 12: 12 } }; });
const base = { ...S, players, squad: POS.map((_, k) => k + 1), sell: {}, bank: 0, ft0: 1, gws: GWS };

test("roll this week, then at most one hit: no -4 booked in a week without moves", async () => {
  const r = await solver.solve(await makeHighs(), { ...base, maxHits: 1, week1Moves: 0 });
  let ft = 1;
  for (const w of r.weeks) {
    const n = r.moves.filter(m => m.gw === w.gw).length;
    assert.equal(w.ft, ft, `GW${w.gw}: free transfers`);
    assert.equal(w.hits, Math.max(0, n - ft), `GW${w.gw}: ${w.hits} hits for ${n} moves on ${ft} FT`);
    ft = n > ft ? 1 : Math.min(5, ft - n + 1);
  }
  assert.equal(r.weeks[0].hits, 0);
  assert.ok(r.moves.filter(m => m.gw === 12).length <= 3);   // 2 free transfers + one hit
});
