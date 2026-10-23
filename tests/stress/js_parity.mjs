// Node harness for the optimiser stress test.
//   node js_parity.mjs solver <in.json> <out.json>   run site/plan-solver.js (HiGHS) on each case
//   node js_parity.mjs front  <in.json> <out.json>   run the real site/js/core/{model,plan}.js with stubbed globals
// Read-only use of site/: nothing under site/ is modified.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const [task, inFile, outFile] = process.argv.slice(2);
const input = JSON.parse(fs.readFileSync(inFile, "utf8"));

async function solverTask() {
  const FPLSolver = require(path.join(ROOT, "site/plan-solver.js"));
  const HighsFactory = require(path.join(ROOT, "site/vendor/highs.js"));
  // a fresh wasm instance per case: after one Abort() the shared instance is unusable ("null function signature mismatch")
  const fresh = () => HighsFactory({ locateFile: f => path.join(ROOT, "site/vendor", f) });
  const out = {};
  for (const c of input.cases) {
    const inp = { ...c.opts, players: input.players, squad: c.squad, sell: c.sell, bank: c.bank, ft0: c.ft0, gws: c.gws };
    const rec = { name: c.name };
    const t0 = Date.now();
    try {
      const highs = await fresh();
      const { lp, ids } = FPLSolver.buildLP(inp);
      const sol = highs.solve(lp, { mip_rel_gap: 0.001, time_limit: c.time_limit ?? 25, presolve: "on" });
      rec.status = sol && sol.Status;
      rec.secs = (Date.now() - t0) / 1000;
      // what the browser would do with this status
      rec.accepted = !!(sol && /Optimal|Time limit/i.test(sol.Status));
      if (rec.accepted) {
        const v = n => Math.round((sol.Columns[n] && sol.Columns[n].Primal) || 0);
        rec.objective = sol.ObjectiveValue;
        rec.weeks = inp.gws.map((g, w) => ({
          gw: g,
          in: ids.filter(i => v(`i_${i}_${w}`)), out: ids.filter(i => v(`o_${i}_${w}`)),
          xi: ids.filter(i => v(`x_${i}_${w}`)), sq: ids.filter(i => v(`s_${i}_${w}`)),
          captain: ids.find(i => v(`c_${i}_${w}`)), hits: v(`h_${w}`), ft: v(`f_${w}`),
          bank: Math.round(((sol.Columns[`b_${w}`] || {}).Primal || 0) * 10) / 10,
        }));
        rec.ft_end = v(`f_${inp.gws.length}`);
        // and the exact object the page gets from FPLSolver.solve
        const res = FPLSolver.readSolution(inp, ids, sol);
        rec.moves = res.moves;
        rec.pool = ids.length;
      }
    } catch (e) { rec.error = String(e.message || e); rec.secs = (Date.now() - t0) / 1000; }
    out[c.name] = rec;
  }
  return out;
}

function frontTask() {
  const srcModel = fs.readFileSync(path.join(ROOT, "site/js/core/model.js"), "utf8");
  const srcPlan = fs.readFileSync(path.join(ROOT, "site/js/core/plan.js"), "utf8");
  const out = {};
  for (const sc of input.scenarios) {
    const ctx = vm.createContext({ console, Math, Object, Set, Array, Number, JSON, Map, Date, __in: sc });
    const prelude = `
      var P = {}; Object.entries(__in.players).forEach(([k, p]) => P[+k] = Object.assign({ id: +k }, p));
      var T = new Proxy({}, { get: (_, k) => ({ short: "T" + k, fx: {} }) });
      var S = { mode: __in.mode || "balanced" };
      var SB = { moves: [], ov: {} };
      var GWS = __in.gws.slice(), PG = __in.gws.slice();
      var D = { squad: __in.squad.map(id => ({ id, sell: __in.sell[id] })), manager: { bank: __in.bank, free_transfers: __in.ft0 },
                crowd: __in.crowd || null, players: Object.values(P), meta: { team_id: 1, next_gw: GWS[0] }, plans: {} };
    `;
    const footer = `
      ;globalThis.__api = { bestXI, capPick, adjCap, adjXI, scoreMoves, ftTable, bankAt, squadAt, LAM, STRAT, sellPrice,
                            planMoves, setOv: (g, o) => { SB.ov[g] = o; } };`;
    vm.runInContext(prelude + srcModel + "\n" + srcPlan + footer, ctx, { filename: "front.js" });
    const A = ctx.__api;
    const res = {};
    for (const pl of sc.plans) {
      const s = A.scoreMoves(pl.moves);
      res[pl.name] = {
        tot: s.tot, ftLeft: s.ftLeft,
        weeks: s.weeks.map(w => ({ gw: w.gw, ft: w.ft, n: w.n, hits: w.hits, next: w.next, xi: w.team.xi, bench: w.team.bench,
          cap: w.team.cap, vice: w.team.vice, swapped: w.team.swapped, pts: w.team.pts, bank: w.bank, over: w.over, sq: w.sq })),
      };
    }
    // single-squad probes: bestXI on an explicit squad (for the captain-swap census)
    if (sc.probes) {
      res.__probes = sc.probes.map(pr => {
        const t = A.bestXI(pr.squad, pr.gw);
        const order = pr.squad.slice();
        // the optimiser's captain = highest adjCap among the XI (no GKP/DEF preference)
        const optCap = t.xi.slice().sort((a, b) => A.adjCap(b, pr.gw) - A.adjCap(a, pr.gw))[0];
        return { gw: pr.gw, cap: t.cap, swapped: t.swapped, optCap, xi: t.xi, pts: t.pts };
      });
    }
    // bank probes: explicit move lists
    if (sc.bankProbes) {
      res.__bank = sc.bankProbes.map(bp => ({ name: bp.name, bank: sc.gws.map(g => A.bankAt(g, bp.moves)) }));
    }
    res.__consts = { LAM: A.LAM, STRAT: A.STRAT };
    out[sc.name] = res;
  }
  return out;
}

const result = task === "solver" ? await solverTask() : frontTask();
fs.writeFileSync(outFile, JSON.stringify(result));
