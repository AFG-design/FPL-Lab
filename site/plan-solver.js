/* FPL Lab browser optimiser: the same model as optimise.py, built as an LP for HiGHS (WebAssembly).
   Works in the browser (window.FPLSolver) and in Node (module.exports) for testing. */
(function (root) {
  const SHAPE = { GKP: 2, DEF: 5, MID: 5, FWD: 3 };
  const XI_MIN = { GKP: 1, DEF: 3, MID: 2, FWD: 1 };
  const XI_MAX = { GKP: 1, DEF: 5, MID: 5, FWD: 3 };
  // FL-075: the shortlist sizes, decay, bench weight, hit cost, weekly move cap, ownership horizon, FT value and the
  // variance formula all come from the build (data.json plan_rules, optimise.planner_settings), so the browser solves
  // with the same maths as the server's plans. They used to be copies here (a smaller shortlist, eoWeeks 2), and
  // Re-plan could find a worse plan than the server's Balanced one. Missing (a data.json from before FL-075): the
  // solver refuses with a reason instead of guessing.
  const NEEDED = ["pool", "decay", "benchW", "hit", "maxMovesWeek", "eoWeeks", "ftValue", "variance", "varianceOther"];
  function settingsFrom(rules) {
    if (!rules) return null;
    const s = { pool: rules.pool, decay: rules.decay, benchW: rules.bench_w, hit: rules.hit, maxMovesWeek: rules.max_moves_week,
      eoWeeks: rules.eo_weeks, ftValue: rules.ft_value, variance: rules.variance, varianceOther: rules.variance_other };
    return NEEDED.every(k => s[k] != null) ? s : null;
  }
  function variance(inp, pos, x) { const [a, b] = inp.variance[pos] || inp.varianceOther; return a * x + b * x * x; }
  // {team: how many over 3 the squad holds now}, for the clubs where it holds more than 3 (FL-074)
  function clubOver(squad, P) {
    const n = {};
    squad.forEach(i => { const t = P[i].team; n[t] = (n[t] || 0) + 1; });
    return Object.fromEntries(Object.entries(n).filter(([, c]) => c > 3).map(([t, c]) => [t, c - 3]));
  }

  /* input: { players:{id:{pos,team,price,xp:{gw:x},ok}}, squad:[ids], sell:{id:£m}, bank, ft0, gws:[..],
              locked:[ids], banned:[ids], captains:{gw:id}, maxHits: 0|1|2|null(any), eo:{id:frac}|null, lam,
              haulW, hitMargin, nailW (strategy extras), decay, benchW, ftValue, maxMovesWeek, week1Moves (fixes the
              number of moves in the first gameweek, as optimise.py's week1_moves), poolExtra:[ids],
              freezeAfter: no moves from this week index on (optimise.py freeze_after; FL-147's best 15 for the money),
              floor: minimum plan value (plain xP over the plan, minus 4 per hit, plus ftValue per FT banked at the end),
              the same measure as optimise.py's VALUE; the strategies use it as their points budget,
              chips: {wildcard|freehit|bboost|3xc: gw} the weeks you pinned a chip to (FL-005), by FPL's rules:
                wildcard  that week's transfers are free (no hits, no weekly cap) and your banked free transfers are
                          kept (FPL since 2024/25), so next week you have one more, up to 5
                freehit   a squad for that week only, within the money the squad is worth then (bank plus its value:
                          your selling price for players you own, the buying price for planned signings); the squad
                          goes back the week after, transfers are free and banked ones kept, as for the wildcard
                bboost    the bench's projected points count too
                3xc       the captain's points count three times
              One chip a gameweek; a pin outside the plan's weeks is ignored. Server plans (optimise.py) carry no
              chips: pins are yours, applied here and in the Planner's scoring (plan.js) } */
  const CHIPS = ["wildcard", "freehit", "bboost", "3xc"];
  function chipWeeks(inp) {
    const at = {};
    CHIPS.forEach(c => { const g = inp.chips && inp.chips[c]; if (g != null && inp.gws.includes(+g)) {
      if (at[+g]) throw new Error(`two chips pinned to GW${g} (${at[+g]} and ${c}); FPL allows one chip a gameweek`);
      at[+g] = c; } });
    return at;
  }
  function buildLP(inp) {
    const missing = NEEDED.filter(k => inp[k] == null);
    if (missing.length) throw new Error(`planner settings missing from this data update (${missing.join(", ")}); try again after the next refresh`);
    const P = inp.players, gws = inp.gws, W = gws.map((_, w) => w), POOL = inp.pool;
    const decay = inp.decay, benchW = inp.benchW, ftValue = inp.ftValue, hit = inp.hit;
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
    const eoW = inp.eoWeeks;
    const chipAt = chipWeeks(inp);
    const fz = (i, w) => `z_${i}_${w}`;   // Free Hit squad (only in a Free Hit week)
    // the squad's value at the start of week w as a linear expression (bank + value of the squad held after week w-1)
    const val = i => (inSquad.has(i) ? sp(i) : P[i].price);

    for (const w of W) {
      const g = gws[w], d = Math.pow(decay, w), chip = chipAt[g];
      const fh = chip === "freehit", own = fh ? fz : sq;   // the squad the XI is picked from this week
      for (const i of ids) {
        [sq(i, w), xi(i, w), cp(i, w), ti(i, w), to(i, w)].forEach(v => bin.push(v));
        if (fh) { bin.push(fz(i, w)); if (banned.has(i) || !P[i].ok) con(` ${fz(i, w)}`, "=", 0); }
        const prev = w === 0 ? null : sq(i, w - 1), init = inSquad.has(i) ? 1 : 0;
        // squad flow
        if (prev) con(` ${sq(i, w)} - ${prev} - ${ti(i, w)} + ${to(i, w)}`, "=", 0);
        else con(` ${sq(i, w)} - ${ti(i, w)} + ${to(i, w)}`, "=", init);
        if (prev) con(` ${to(i, w)} - ${prev}`, "<=", 0); else con(` ${to(i, w)}`, "<=", init);
        con(` ${ti(i, w)} + ${to(i, w)}`, "<=", 1);
        con(` ${xi(i, w)} - ${own(i, w)}`, "<=", 0);
        con(` ${cp(i, w)} - ${xi(i, w)}`, "<=", 0);
        if (banned.has(i)) con(` ${sq(i, w)}`, "=", 0);
        if (locked.has(i)) con(` ${sq(i, w)}`, "=", 1);
        if (!P[i].ok) con(` ${ti(i, w)}`, "=", 0);
        const x = P[i].xp[g] || 0;
        // bench boost: every squad player scores, so the whole squad counts in full and the XI adds nothing more;
        // triple captain: the armband counts twice on top of the XI, not once
        let cx = chip === "bboost" ? 0 : d * (x - benchW * x), cc = d * x * (chip === "3xc" ? 2 : 1), cs = d * (chip === "bboost" ? 1 : benchW) * x;
        if (inp.eo && inp.lam && w < eoW && x > 0) {
          const v = variance(inp, P[i].pos, x), e = inp.eo[i] || 0;
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
        if (cs) obj.push(term(cs, own(i, w)));
      }
      for (const pos in SHAPE) {
        const ps = ids.filter(i => P[i].pos === pos);
        con(ps.map(i => ` + ${sq(i, w)}`).join(""), "=", SHAPE[pos]);
        if (fh) con(ps.map(i => ` + ${fz(i, w)}`).join(""), "=", SHAPE[pos]);
        con(ps.map(i => ` + ${xi(i, w)}`).join(""), ">=", XI_MIN[pos]);
        con(ps.map(i => ` + ${xi(i, w)}`).join(""), "<=", XI_MAX[pos]);
      }
      con(ids.map(i => ` + ${xi(i, w)}`).join(""), "=", 11);
      con(ids.map(i => ` + ${cp(i, w)}`).join(""), "=", 1);
      const cap = inp.captains && inp.captains[g];
      if (cap && ids.includes(cap)) con(` ${cp(cap, w)}`, "=", 1);
      // club limit (FL-074, as optimise.py): 3 from a club, but a squad already holding more from one club (a real
      // move between Premier League clubs) may keep them in a gameweek with no transfers; any gameweek with a
      // transfer (m_w = 1) must end with at most 3 from every club
      const teams = [...new Set(ids.map(i => P[i].team))];
      if (fh) {
        // Free Hit: the real squad holds (no transfers), the week's squad is z: 3 a club, and it can't cost more than
        // the bank plus what the held squad is worth
        con(ids.map(i => ` + ${ti(i, w)} + ${to(i, w)}`).join(""), "=", 0);
        teams.forEach(t => con(ids.filter(i => P[i].team === t).map(i => ` + ${fz(i, w)}`).join(""), "<=", 3));
        let budget = ids.map(i => term(P[i].price, fz(i, w))).join("");
        if (w === 0) con(budget, "<=", inp.bank + inp.squad.reduce((a, i) => a + val(i), 0));
        else con(budget + ` - b_${w - 1}` + ids.map(i => term(-val(i), sq(i, w - 1))).join(""), "<=", 0);
      }
      const extra = clubOver(inp.squad, P);
      if (Object.keys(extra).length) {
        bin.push(`m_${w}`);
        con(ids.map(i => ` + ${ti(i, w)}`).join("") + ` - 15 m_${w}`, "<=", 0);
      }
      teams.forEach(t => {
        const lhs = ids.filter(i => P[i].team === t).map(i => ` + ${sq(i, w)}`).join("");
        if (extra[t]) con(lhs + ` + ${extra[t]} m_${w}`, "<=", 3 + extra[t]);
        else con(lhs, "<=", 3);
      });
      // bank
      const bk = `b_${w}`, prevBk = w === 0 ? null : `b_${w - 1}`;
      let lhs = ` ${bk}` + (prevBk ? ` - ${prevBk}` : "");
      ids.forEach(i => { lhs += term(-sp(i), to(i, w)) + term(P[i].price, ti(i, w)); });
      con(lhs, "=", w === 0 ? inp.bank : 0);
      // free transfers and hits
      const nw = ids.map(i => ` + ${ti(i, w)}`).join("");
      const free = chip === "wildcard" || fh;   // transfers cost nothing and banked FTs are kept
      if (chip !== "wildcard") con(nw, "<=", inp.maxMovesWeek);
      if (w === 0 && inp.week1Moves != null) con(nw, "=", inp.week1Moves);   // e.g. 0: roll this week (FL-110)
      if (inp.freezeAfter != null && w >= inp.freezeAfter) con(nw, "=", 0);   // FL-147: rebuild, then hold (optimise.py freeze_after)
      if (free) { con(` h_${w}`, "=", 0); con(` f_${w + 1} - f_${w}`, "<=", 1); }
      else {
        con(` h_${w} + f_${w}` + ids.map(i => ` - ${ti(i, w)}`).join(""), ">=", 0);
        con(` f_${w + 1} - f_${w} + ${ids.map(i => ti(i, w)).join(" + ")} - h_${w}`, "<=", 1);
      }
      if (inp.maxHits != null) con(` h_${w}`, "<=", inp.maxHits);
      obj.push(term(-d * (hit + (inp.hitMargin || 0)), `h_${w}`));
      gen.push(`h_${w}`);
    }
    obj.push(term(ftValue, `f_${gws.length}`));
    if (inp.floor != null) {
      let val = "";
      W.forEach(w => { const g = gws[w], c = chipAt[g], own = c === "freehit" ? fz : sq; ids.forEach(i => { const x = P[i].xp[g] || 0;
        if (x) val += (c === "bboost" ? term(x, own(i, w)) : term(x, xi(i, w))) + term(x * (c === "3xc" ? 2 : 1), cp(i, w)); }); val += term(-hit, `h_${w}`); });
      val += term(ftValue, `f_${gws.length}`);
      con(val, ">=", inp.floor);
    }
    for (let w = 0; w <= gws.length; w++) gen.push(`f_${w}`);
    const bounds = [` f_0 = ${inp.ft0}`];
    for (let w = 1; w <= gws.length; w++) bounds.push(` 1 <= f_${w} <= 5`);
    W.forEach(w => bounds.push(` h_${w} >= 0`, ` b_${w} >= 0`));
    const lp = `Maximize\n obj:${obj.join("")}\nSubject To\n${cons.join("\n")}\nBounds\n${bounds.join("\n")}\nGeneral\n ${gen.join(" ")}\nBinary\n ${bin.join(" ")}\nEnd\n`;
    return { lp, ids, chipAt };
  }

  function readSolution(inp, ids, sol, chipAt = chipWeeks(inp)) {
    const v = name => Math.round((sol.Columns[name] && sol.Columns[name].Primal) || 0);
    const moves = [], weeks = [];
    inp.gws.forEach((g, w) => {
      const ins = ids.filter(i => v(`i_${i}_${w}`)), outs = ids.filter(i => v(`o_${i}_${w}`));
      const used = new Set();
      ins.forEach(i => {
        const o = outs.find(x => !used.has(x) && inp.players[x].pos === inp.players[i].pos);
        if (o != null) { used.add(o); moves.push({ gw: g, out: o, in: i }); }
      });
      const chip = chipAt[g] || null, squad = ids.filter(i => v(`${chip === "freehit" ? "z" : "s"}_${i}_${w}`));
      weeks.push({ gw: g, xi: ids.filter(i => v(`x_${i}_${w}`)), captain: ids.find(i => v(`c_${i}_${w}`)), hits: v(`h_${w}`), ft: v(`f_${w}`), chip, squad });
    });
    const ftEnd = v(`f_${inp.gws.length}`), ftValue = inp.ftValue;
    const x = (i, g) => inp.players[i]?.xp[g] || 0;
    const pts = weeks.reduce((a, w) => a + (w.chip === "bboost" ? w.squad : w.xi).reduce((b, i) => b + x(i, w.gw), 0)
      + x(w.captain, w.gw) * (w.chip === "3xc" ? 2 : 1) - inp.hit * w.hits, 0);
    return { moves, weeks, objective: sol.ObjectiveValue, ftLeft: ftEnd, value: pts + ftValue * ftEnd };
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
  function accept(inp, ids, sol, chipAt) {
    if (!sol || !/^(Optimal|Time limit)/i.test(sol.Status)) throw new Error("No plan found (" + (sol && sol.Status) + ")");
    const r = readSolution(inp, ids, sol, chipAt);
    if (!complete(r) || !Number.isFinite(r.objective)) throw new Error("No plan found (" + sol.Status + ", no full lineup)");
    return r;
  }
  async function solve(highs, inp, makeHighs) {
    const { lp, ids, chipAt } = buildLP(inp);
    let err;
    for (let t = 0; t < TRIES.length; t++) {
      try {
        if (t && makeHighs) highs = await makeHighs();
        const r = accept(inp, ids, highs.solve(lp, TRIES[t]), chipAt);
        r.attempts = t + 1;
        return r;
      } catch (e) {
        err = e;
        if (/^No plan found/.test(e.message || "")) throw e;  // solved but unusable: another seed won't help
      }
    }
    throw err;
  }

  const api = { buildLP, readSolution, solve, settingsFrom, chipWeeks, CHIPS };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.FPLSolver = api;
})(typeof window !== "undefined" ? window : globalThis);
