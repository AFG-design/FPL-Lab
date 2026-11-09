// Exercise Re-plan's orchestration and the shipped WASM solver together.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import makeHighs from "../site/vendor/highs.js";
import solver from "../site/plan-solver.js";

const highs = await makeHighs();
function planner() {
  const positions = ["GKP", "GKP", ...Array(5).fill("DEF"), ...Array(5).fill("MID"), ...Array(3).fill("FWD"), "MID"];
  const players = positions.map((pos, i) => ({
    id: i + 1, pos, team: i + 1, price: 5, ok: true,
    // 8 is the best current captain; 16 is a profitable planned signing.
    xp: { 10: i === 15 ? 20 : i === 7 ? 8 : 4, 11: i === 15 ? 20 : i === 7 ? 8 : 4 },
  }));
  const ctx = vm.createContext({ location: { hash: "" }, setTimeout,
    window: { FPLSolver: solver }, highs, players });
  for (const file of ["core/state", "core/model", "core/plan", "views/planner", "views/planner-views"]) {
    vm.runInContext(readFileSync(new URL("../site/js/" + file + ".js", import.meta.url), "utf8"), ctx);
  }
  vm.runInContext(`
    D = { players, squad: players.slice(0, 15).map(p => ({ id: p.id, sell: 5 })),
      manager: { bank: 0, free_transfers: 1 },
      crowd: { top10k: { n: 100, cap: {}, eo: Object.fromEntries(players.map(p => [p.id, 50])) } } };
    P = Object.fromEntries(players.map(p => [p.id, p]));
    GWS = PG = [10, 11];
    SB = { rules: { locked: [], banned: [] }, ov: {}, moves: [{ gw: 10, out: 9, in: 16 }] };
    SOLVE.highs = highs;
  `, ctx);
  return expr => vm.runInContext(expr, ctx);
}

for (const mode of ["balanced", "safe", "chase"]) {
  for (const captain of [16, 9]) {
    test(`${mode}: Re-plan honours captain ${captain === 16 ? "planned signing" : "current squad player"} with an independent baseline`, async () => {
      const run = planner();
      const result = await run(`optimiseMoves("${mode}", { ov: { 10: { cap: ${captain} }, 11: { cap: ${captain} } }, poolExtra: [16] })`);
      assert.equal(result.none.moves.length, 0);
      for (const week of result.none.weeks) {
        assert.equal(week.captain, 8, "baseline captains the best projected current player");
        assert.equal(week.xi.length, 11);
        assert.ok(week.xi.includes(8));
        assert.ok(!week.xi.includes(16));
      }
      for (const gw of [10, 11]) {
        assert.equal(result.solved[gw].cap, captain);
        assert.ok(result.solved[gw].xi.includes(captain));
        assert.equal(result.solved[gw].sq.length, 15);
      }
      assert.ok(result.moves.some(m => m.gw === 10 && m.in === 16));
    });
  }
}
