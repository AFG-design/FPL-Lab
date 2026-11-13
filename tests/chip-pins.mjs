// FL-005: chips pinned to a gameweek, in the browser optimiser (the shipped HiGHS build) and in the Planner's scoring.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import makeHighs from "../site/vendor/highs.js";
import solver from "../site/plan-solver.js";

const highs = await makeHighs();
const RULES = JSON.parse(readFileSync(new URL("./fixtures/plan_rules.json", import.meta.url), "utf8"));
const settings = solver.settingsFrom(RULES);
// 15 owned (ids 1-15) on 2 xP a week, the bench (2nd keeper 2, and 3 outfielders) on 1; five better players to buy
// (16-20, 6 xP, £5m like everyone, one per position plus an extra MID and FWD), each from a club of his own
const pos = ["GKP", "GKP", "DEF", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "MID", "FWD", "FWD", "FWD"];
const GW = [10, 11, 12];
const players = {};
pos.forEach((p, k) => { players[k + 1] = { pos: p, team: k + 1, price: 5, ok: true, xp: Object.fromEntries(GW.map(g => [g, [1, 6, 11, 14].includes(k) ? 1 : 2])) }; });
["GKP", "DEF", "MID", "MID", "FWD"].forEach((p, k) => { players[16 + k] = { pos: p, team: 16 + k, price: 5, ok: true, xp: Object.fromEntries(GW.map(g => [g, 6])) }; });
const base = { ...settings, players, squad: pos.map((_, k) => k + 1), sell: {}, bank: 0, ft0: 1, gws: GW, locked: [], banned: [], maxHits: 0 };
const run = inp => solver.solve(highs, inp);

test("bench boost and triple captain add the bench and a second armband, nothing else", async () => {
  const hold = { ...base, maxMovesWeek: 0 };
  const a = await run(hold), b = await run({ ...hold, chips: { bboost: 11 } }), c = await run({ ...hold, chips: { "3xc": 12 } });
  assert.equal(Math.round((b.value - a.value) * 10) / 10, 1 + 1 + 1 + 1);   // the bench: 4 players on 1 xP
  assert.equal(Math.round((c.value - a.value) * 10) / 10, 2);               // the captain's 2 xP once more
  assert.equal(b.weeks[1].chip, "bboost");
});

test("wildcard: that week's moves are free and banked transfers are kept", async () => {
  const r = await run({ ...base, chips: { wildcard: 10 } });
  const w10 = r.moves.filter(m => m.gw === 10);
  assert.ok(w10.length >= 4, `rebuilds on the wildcard (${w10.length} moves)`);
  assert.equal(r.weeks[0].hits, 0);
  assert.equal(r.weeks[1].ft, 2);    // 1 kept + 1 for the new week
  const no = await run(base);         // no chip and no hits allowed: one move a week at most
  assert.ok(no.moves.filter(m => m.gw === 10).length <= 1);
  assert.ok(r.value > no.value);
});

test("free hit: a squad for one week, the old squad back after, within the money", async () => {
  const r = await run({ ...base, maxMovesWeek: 0, chips: { freehit: 11 } });
  const w = r.weeks.find(x => x.gw === 11);
  assert.equal(w.chip, "freehit");
  for (const i of [16, 17, 18, 19, 20]) assert.ok(w.squad.includes(i), `free hit squad has ${i}`);
  assert.deepEqual(r.weeks[2].squad.slice().sort((a, b) => a - b), base.squad);   // back to the 15 you own
  assert.equal(r.moves.length, 0);   // no real transfers
  assert.equal(r.weeks[2].ft, 3);    // GW10 1, rolled to 2 for GW11, kept through the free hit and +1 for GW12
  // the money holds: 15 x £5m with an empty bank
  const tight = { ...base, maxMovesWeek: 0, chips: { freehit: 11 }, players: { ...players, 16: { ...players[16], price: 6 } } };
  const t = await run(tight);
  assert.ok(!t.weeks[1].squad.includes(16), "can't afford the £6m keeper with £75m");
});

test("one chip a gameweek; a pin outside the plan is ignored", () => {
  assert.throws(() => solver.buildLP({ ...base, chips: { bboost: 11, "3xc": 11 } }), /one chip a gameweek/);
  assert.doesNotThrow(() => solver.buildLP({ ...base, chips: { bboost: 30 } }));
});

// the Planner's own scoring (plan.js) and Re-plan, on the same players, in the app's code
function planner() {
  const list = Object.entries(players).map(([id, p]) => ({ id: +id, name: "P" + id, ...p }));
  const ctx = vm.createContext({ location: { hash: "" }, setTimeout, window: { FPLSolver: solver }, highs, list, RULES, GW });
  for (const file of ["core/state", "core/model", "core/plan", "views/planner", "views/planner-views"]) {
    vm.runInContext(readFileSync(new URL("../site/js/" + file + ".js", import.meta.url), "utf8"), ctx);
  }
  vm.runInContext(`
    D = { players: list, squad: list.slice(0, 15).map(p => ({ id: p.id, sell: 5 })), manager: { bank: 0, free_transfers: 1 },
      plan_rules: RULES, meta: { next_gw: 10 },
      chips: [{ key: "wildcard", available: true, from: 2, to: 19 }, { key: "freehit", available: true, from: 2, to: 19 },
              { key: "bboost", available: false, from: 1, to: 19 }, { key: "3xc", available: true, from: 1, to: 19 }],
      crowd: { top10k: { n: 100, cap: {}, eo: {} } } };
    P = Object.fromEntries(list.map(p => [p.id, p]));
    GWS = PG = GW;
    SB = { rules: { locked: [], banned: [] }, ov: {}, moves: [], chips: {} };
    SOLVE.highs = highs;
  `, ctx);
  return expr => vm.runInContext(expr, ctx);
}

test("plan scoring: free hit moves last one week, wildcard moves are free, used chips can't be pinned", () => {
  const run = planner();
  run(`SB.chips = cleanChips({ freehit: 11, wildcard: 10, bboost: 12 })`);
  assert.equal(run(`JSON.stringify(SB.chips)`), '{"freehit":11,"wildcard":10}');   // Bench Boost already used
  run(`SB.moves = cleanMoves([{ gw: 10, out: 3, in: 17 }, { gw: 10, out: 8, in: 18 }, { gw: 11, out: 13, in: 20 }, { gw: 11, out: 9, in: 19 }])`);
  const t = JSON.parse(run(`JSON.stringify(ftTable())`));
  assert.deepEqual(t.map(r => [r.ft, r.n, r.hits, r.chip]), [[1, 2, 0, "wildcard"], [2, 2, 0, "freehit"], [3, 0, 0, null]]);
  assert.equal(run(`squadAt(11).includes(20) && squadAt(11).includes(19)`), true);
  assert.equal(run(`!squadAt(12).includes(20) && !squadAt(12).includes(19) && squadAt(12).includes(17)`), true);   // wildcard stays
  assert.equal(run(`bankAt(12)`), 0);
  // triple captain adds the captain's points once more; keeping the squad plays it too
  run(`SB.chips = cleanChips({ "3xc": 12 }); SB.moves = []; _base = null`);
  const sc = JSON.parse(run(`JSON.stringify(scoreMoves(SB.moves).weeks.map(w => w.team.chipPts))`));
  assert.deepEqual(sc, [0, 0, 2]);
  assert.equal(run(`baseScore().weeks[2].team.chipPts`), 2);
});

test("Re-plan with a free hit pinned: the one-week squad comes back as that week's moves", async () => {
  const run = planner();
  run(`SB.chips = cleanChips({ freehit: 11 })`);
  const res = JSON.parse(await run(`optimiseMoves("balanced", { chips: SB.chips }).then(r => JSON.stringify(r))`));
  const fh = res.moves.filter(m => m.gw === 11);
  assert.ok(fh.length >= 4, `free hit moves: ${fh.length}`);
  run(`SB.moves = cleanMoves(${JSON.stringify(res.moves)})`);
  assert.equal(run(`ftTable()[1].hits`), 0);
  assert.equal(run(`squadAt(12).filter(i => i > 15).length`), res.moves.filter(m => m.gw !== 11).length);   // only real moves stay
});
