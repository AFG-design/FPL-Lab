// FL-110: Re-plan and the strategy tab's pick measure moves this week against rolling the transfer, with
// plan_rules.min_profit (it replaced an undocumented 0.5 in the browser). Uses the shipped WASM solver.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import makeHighs from "../site/vendor/highs.js";
import solver from "../site/plan-solver.js";

const highs = await makeHighs();
function planner(x16, rules) {
  const positions = ["GKP", "GKP", ...Array(5).fill("DEF"), ...Array(5).fill("MID"), ...Array(3).fill("FWD"), "MID"];
  // 9 (a starting midfielder) projects 4 a week; 16 (not owned) projects x16. 8 is the captain at 8.
  const players = positions.map((pos, i) => ({ id: i + 1, pos, team: i + 1, price: 5, ok: true,
    xp: Object.fromEntries([10, 11, 12].map(g => [g, i === 15 ? x16 : i === 7 ? 8 : 4])) }));
  const ctx = vm.createContext({ location: { hash: "" }, setTimeout, window: { FPLSolver: solver }, highs, players, rules });
  for (const file of ["core/state", "core/model", "core/plan", "views/planner", "views/planner-views"]) {
    vm.runInContext(readFileSync(new URL("../site/js/" + file + ".js", import.meta.url), "utf8"), ctx);
  }
  vm.runInContext(`
    D = { players, squad: players.slice(0, 15).map(p => ({ id: p.id, sell: 5 })), manager: { bank: 0, free_transfers: 1 },
      plan_rules: rules, crowd: null };
    P = Object.fromEntries(players.map(p => [p.id, p]));
    GWS = PG = [10, 11, 12];
    SB = { rules: { locked: [], banned: [] }, ov: {}, moves: [] };
    SOLVE.highs = highs;
  `, ctx);
  return expr => vm.runInContext(expr, ctx);
}
const RULES = { ft_value: 1.5, min_profit: 1, hit_gain: 2, tie: 0.1, safe_budget: 0, chase_budget: 2, strategy: {} };

// Over 3 GWs, signing 16 (4.9) for 9 (4) now gains 0.9 a week. Against never transferring that is 2.7 less the free
// transfer it doesn't bank (1.5) = +1.2, which cleared the rule; against rolling (sign him next week instead) it's
// only +0.9, and rolling itself is +0.3 against never transferring, so no moves at all.
test("Re-plan: a signing worth +0.9 over rolling the transfer isn't made (it was: +1.2 over never transferring)", async () => {
  const run = planner(4.9, RULES);
  const res = await run(`optimiseMoves("balanced", { ov: {}, poolExtra: [] })`);
  assert.equal(res.moves.length, 0, JSON.stringify(res.moves));   // (arrays from the vm context: compare lengths)
});

test("Re-plan: a signing worth +3 a week over rolling is made this week", async () => {
  const run = planner(7, RULES);
  const res = await run(`optimiseMoves("balanced", { ov: {}, poolExtra: [] })`);
  assert.ok(res.moves.some(m => m.gw === 10 && m.in === 16), JSON.stringify(res.moves));
});

test("the tab's pick: fewest moves within min_profit of the best, none without min_profit", () => {
  const run = planner(4, RULES);
  run(`D.plans = { roll: { vs_roll: 0 }, one: { vs_roll: 1.2 }, two: { vs_roll: 2.0 } }`);
  assert.equal(run(`recommendedPlan("balanced")`), "one");          // the 0.5 it replaced picked "two"
  run(`D.plan_rules = { ...D.plan_rules, min_profit: 0.5 }`);
  assert.equal(run(`recommendedPlan("balanced")`), "two");
  run(`delete D.plan_rules.min_profit`);
  assert.equal(run(`recommendedPlan("balanced")`), null);
});
