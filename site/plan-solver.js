/* FPL Lab browser optimiser: the same model as optimise.py, built as an LP for HiGHS (WebAssembly).
   Works in the browser (window.FPLSolver) and in Node (module.exports) for testing. */
(function (root) {
  const SHAPE = { GKP: 2, DEF: 5, MID: 5, FWD: 3 };
  const XI_MIN = { GKP: 1, DEF: 3, MID: 2, FWD: 1 };
  const XI_MAX = { GKP: 1, DEF: 5, MID: 5, FWD: 3 };
  const POOL = { GKP: 10, DEF: 26, MID: 30, FWD: 16 };

  function variance(pos, x) { return pos === "MID" ? 1.9 * x + 0.23 * x * x : ({ GKP: 2.8, DEF: 3.3, FWD: 3.8 }[pos] || 3) * x; }

  /* input: { players:{id:{pos,team,price,xp:{gw:x},ok}}, squad:[ids], sell:{id:£m}, bank, ft0, gws:[..],
              locked:[ids], banned:[ids], captains:{gw:id}, maxHits: 0|1|2|null(any), eo:{id:frac}|null, lam,
              haulW, hitMargin, nailW (strategy extras), decay, benchW, ftValue, maxMovesWeek, poolExtra:[ids] } */
  function buildLP(inp) {
    const P = inp.players, gws = inp.gws, W = gws.map((_, w) => w);
    const decay = inp.decay ?? 0.9, benchW = inp.benchW ?? 0.1, ftValue = inp.ftValue ?? 1.5, hit = 4;
    const locked = new Set(inp.locked || []), banned = new Set(inp.banned || []);
    const pool = new Set(inp.squad);
    (inp.poolExtra || []).forEach(i => P[i] && pool.add(i));
    locked.forEach(i => P[i] && pool.add(i));
    Object.values(inp.captains || {}).forEach(i => P[i] && pool.add(i));
    for (const pos in POOL) {
      const c = Object.keys(P).map(Number).filter(i => P[i].pos === pos && P[i].ok && !banned.has(i));
      c.sort((a, b) => gws.reduce((s, g) => s + (P[b].xp[g] || 0), 0) - gws.reduce((s, g) => s + (P[a].xp[g] || 0), 0));
      c.slice(0, POOL[pos]).forEach(i => pool.add(i));
    }
    const ids = [...pool];
    const inSquad = new Set(inp.squad);
    const sp = i => (inp.sell && inp.sell[i] != null ? inp.sell[i] : P[i].price);
    const n = x => (Math.round(x * 1e6) / 1e6);
    const term = (c, v) => (c >= 0 ? ` + ${n(c)} ${v}` : ` - ${n(-c)} ${v}`);
    const obj = [], cons = [], bin = [], gen = [];
    let k = 0;
    const con = (lhs, op, rhs) => cons.push(` c${k++}:${lhs} ${op} ${n(rhs)}`);
    const sq = (i, w) => `s_${i}_${w}`, xi = (i, w) => `x_${i}_${w}`, cp = (i, w) => `c_${i}_${w}`;
    const ti = (i, w) => `i_${i}_${w}`, to = (i, w) => `o_${i}_${w}`;
    const eoW = inp.eoWeeks ?? 2;

    for (const w of W) {
      const g = gws[w], d = Math.pow(decay, w);
      for (const i of ids) {
        [sq(i, w), xi(i, w), cp(i, w), ti(i, w), to(i, w)].forEach(v => bin.push(v));
        const prev = w === 0 ? null : sq(i, w - 1), init = inSquad.has(i) ? 1 : 0;
        // squad flow
        if (prev) con(` ${sq(i, w)} - ${prev} - ${ti(i, w)} + ${to(i, w)}`, "=", 0);
        else con(` ${sq(i, w)} - ${ti(i, w)} + ${to(i, w)}`, "=", init);
        if (prev) con(` ${to(i, w)} - ${prev}`, "<=", 0); else con(` ${to(i, w)}`, "<=", init);
        con(` ${ti(i, w)} + ${to(i, w)}`, "<=", 1);
        con(` ${xi(i, w)} - ${sq(i, w)}`, "<=", 0);
        con(` ${cp(i, w)} - ${xi(i, w)}`, "<=", 0);
        if (banned.has(i)) con(` ${sq(i, w)}`, "=", 0);
        if (locked.has(i)) con(` ${sq(i, w)}`, "=", 1);
        if (!P[i].ok) con(` ${ti(i, w)}`, "=", 0);
        const x = P[i].xp[g] || 0;
        let cx = d * (x - benchW * x), cc = d * x, cs = d * benchW * x;
        if (inp.eo && inp.lam && w < eoW && x > 0) {
          const v = variance(P[i].pos, x), e = inp.eo[i] || 0;
          const kx = 1 - 2 * e, kc = 3 - 2 * e;
          // chase (lam < 0) only rewards differentials, never dropping what the field owns
          cx -= inp.lam * d * v * (inp.lam < 0 ? Math.max(0, kx) : kx);
          cc -= inp.lam * d * v * (inp.lam < 0 ? Math.max(0, kc) : kc);
        }
        // strategy extras (see optimise.py): Chase rewards the chance of 10+ points, double for the captain;
        // Play safe marks down starters who may not play
        if (inp.haulW) { const h = (P[i].p10 && P[i].p10[g]) || 0; cx += d * inp.haulW * h; cc += d * inp.haulW * h; }
        if (inp.nailW) cx -= d * inp.nailW * (1 - Math.min(100, P[i].nailed ?? 100) / 100) * x;
        if (cx) obj.push(term(cx, xi(i, w)));
        if (cc) obj.push(term(cc, cp(i, w)));
        if (cs) obj.push(term(cs, sq(i, w)));
      }
      for (const pos in SHAPE) {
        const ps = ids.filter(i => P[i].pos === pos);
        con(ps.map(i => ` + ${sq(i, w)}`).join(""), "=", SHAPE[pos]);
        con(ps.map(i => ` + ${xi(i, w)}`).join(""), ">=", XI_MIN[pos]);
        con(ps.map(i => ` + ${xi(i, w)}`).join(""), "<=", XI_MAX[pos]);
      }
      con(ids.map(i => ` + ${xi(i, w)}`).join(""), "=", 11);
      con(ids.map(i => ` + ${cp(i, w)}`).join(""), "=", 1);
      const cap = inp.captains && inp.captains[g];
      if (cap && ids.includes(cap)) con(` ${cp(cap, w)}`, "=", 1);
      const teams = [...new Set(ids.map(i => P[i].team))];
      teams.forEach(t => con(ids.filter(i => P[i].team === t).map(i => ` + ${sq(i, w)}`).join(""), "<=", 3));
      // bank
      const bk = `b_${w}`, prevBk = w === 0 ? null : `b_${w - 1}`;
      let lhs = ` ${bk}` + (prevBk ? ` - ${prevBk}` : "");
      ids.forEach(i => { lhs += term(-sp(i), to(i, w)) + term(P[i].price, ti(i, w)); });
      con(lhs, "=", w === 0 ? inp.bank : 0);
      // free transfers and hits
      const nw = ids.map(i => ` + ${ti(i, w)}`).join("");
      con(nw, "<=", inp.maxMovesWeek ?? 4);
      con(` h_${w} + f_${w}` + ids.map(i => ` - ${ti(i, w)}`).join(""), ">=", 0);
      con(` f_${w + 1} - f_${w} + ${ids.map(i => ti(i, w)).join(" + ")} - h_${w}`, "<=", 1);
      if (inp.maxHits != null) con(` h_${w}`, "<=", inp.maxHits);
      obj.push(term(-d * (hit + (inp.hitMargin || 0)), `h_${w}`));
      gen.push(`h_${w}`);
    }
    obj.push(term(ftValue, `f_${gws.length}`));
    for (let w = 0; w <= gws.length; w++) gen.push(`f_${w}`);
    const bounds = [` f_0 = ${inp.ft0}`];
    for (let w = 1; w <= gws.length; w++) bounds.push(` 1 <= f_${w} <= 5`);
    W.forEach(w => bounds.push(` h_${w} >= 0`, ` b_${w} >= 0`));
    const lp = `Maximize\n obj:${obj.join("")}\nSubject To\n${cons.join("\n")}\nBounds\n${bounds.join("\n")}\nGeneral\n ${gen.join(" ")}\nBinary\n ${bin.join(" ")}\nEnd\n`;
    return { lp, ids };
  }

  function readSolution(inp, ids, sol) {
    const v = name => Math.round((sol.Columns[name] && sol.Columns[name].Primal) || 0);
    const moves = [], weeks = [];
    inp.gws.forEach((g, w) => {
      const ins = ids.filter(i => v(`i_${i}_${w}`)), outs = ids.filter(i => v(`o_${i}_${w}`));
      const used = new Set();
      ins.forEach(i => {
        const o = outs.find(x => !used.has(x) && inp.players[x].pos === inp.players[i].pos);
        if (o != null) { used.add(o); moves.push({ gw: g, out: o, in: i }); }
      });
      weeks.push({ gw: g, xi: ids.filter(i => v(`x_${i}_${w}`)), captain: ids.find(i => v(`c_${i}_${w}`)), hits: v(`h_${w}`), ft: v(`f_${w}`) });
    });
    return { moves, weeks, objective: sol.ObjectiveValue };
  }

  // HiGHS (wasm) sometimes aborts or runs off its memory on a real input; the module can't be trusted after that,
  // so each retry gets a fresh instance (makeHighs) and different options.
  const TRIES = [
    { mip_rel_gap: 0.001, time_limit: 25, presolve: "on" },
    { mip_rel_gap: 0.001, time_limit: 25, presolve: "on", random_seed: 7 },
    { mip_rel_gap: 0.01, time_limit: 25, presolve: "on", random_seed: 7 },
  ];
  const complete = r => r.weeks.length > 0 && r.weeks.every(w => w.xi.length === 11 && w.captain != null && w.xi.includes(w.captain));
  // Optimal, or out of time but still holding a full plan; anything else is a failure
  function accept(inp, ids, sol) {
    if (!sol || !/^(Optimal|Time limit)/i.test(sol.Status)) throw new Error("No plan found (" + (sol && sol.Status) + ")");
    const r = readSolution(inp, ids, sol);
    if (!complete(r) || !Number.isFinite(r.objective)) throw new Error("No plan found (" + sol.Status + ", no full lineup)");
    return r;
  }
  async function solve(highs, inp, makeHighs) {
    const { lp, ids } = buildLP(inp);
    let err;
    for (let t = 0; t < TRIES.length; t++) {
      try {
        if (t && makeHighs) highs = await makeHighs();
        const r = accept(inp, ids, highs.solve(lp, TRIES[t]));
        r.attempts = t + 1;
        return r;
      } catch (e) {
        err = e;
        if (/^No plan found/.test(e.message || "")) throw e;  // solved but unusable: another seed won't help
      }
    }
    throw err;
  }

  const api = { buildLP, readSolution, solve };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.FPLSolver = api;
})(typeof window !== "undefined" ? window : globalThis);
