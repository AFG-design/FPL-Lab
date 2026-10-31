// Planner page: view tabs over the editor.
//   My team     your 15 as they are, best XI and captain each week (the baseline every other tab is measured on)
//   Suggested   the server optimiser's plan for one strategy (Balanced / Play safe / Chase rank switch), shown as
//               the XI it leaves you; the switch says when two strategies make the same transfers
//   Compare     your team and the three strategies side by side, week by week
//   Your plan   the full editor (views/planner.js)
//
// Missing or ambiguous data, and what each tab does about it:
//   - No plans for a strategy (build.py skips Play safe and Chase rank when the field-ownership file is missing):
//     that tab says so and offers the editor. It never shows another strategy's plan in its place (plan.js `mk` falls
//     back to Balanced; these tabs deliberately don't use it). validate.py warns on the Health page.
//   - A plan move naming a player no longer in data.json: the move is dropped and the tab says how many were dropped.
//   - Projections resting on assumptions (no return date, no chance given): the pitch marks them as before
//     (dotted xP, "Assumed — no official data"), and My team counts them.
//   - No field ownership (crowd data): the Compare "field ownership" row shows "–" rather than 0%.

const PVIEWS = [["mine", "My team"], ["suggest", "Suggested"], ["compare", "Compare"], ["edit", "Your plan"]];
const PV_MODES = ["balanced", "safe", "chase"];
const PV_VARIANTS = ["roll", "one", "two", "three", "best"];
const PV_VAR_LABEL = { roll: "Roll", one: "1 move", two: "2 moves", three: "3 moves", best: "Optimal" };
const PV = { gw: null, variant: {} };   // gameweek on the pitch and the variant picked per strategy (this visit only)

// plan keys for a strategy, without the Balanced fallback `mk` applies
// (variants with identical moves, e.g. "2 moves" and "Optimal" when the best plan makes two, are shown once)
function pvKeys(mode) {
  const pl = D.plans || {}, seen = new Set();
  return PV_VARIANTS.map(k => mode === "balanced" ? k : `${mode}_${k}`).filter(k => {
    if (!pl[k]) return false;
    const sig = mvKey(planMoves(pl[k]));
    if (seen.has(sig)) return false;
    seen.add(sig); return true;
  });
}
// the variant the tab opens on: fewest moves within 0.5 of the best (recommendedPlan's rule), only when the
// strategy's own plans exist
function pvKey(mode) {
  const keys = pvKeys(mode); if (!keys.length) return null;
  const want = PV.variant[mode];
  if (want && keys.includes(want)) return want;
  const rec = recommendedPlan(mode);
  return rec && keys.includes(rec) ? rec : keys[0];
}
// run fn with a strategy's lineup and captain rule and no hand-picked captain/bench choices, so these tabs show the
// optimiser's view rather than your edits (the same trick draftSummary uses)
function withMode(mode, fn) {
  const keep = { mode: S.mode, ov: SB.ov };
  S.mode = mode; SB.ov = {};
  try { return fn(); } finally { S.mode = keep.mode; SB.ov = keep.ov; }
}
let _pv = { key: "", res: {} };
function pvCacheKey() { return `${D.meta.built}|${PG.join(",")}|${D.squad.map(s => s.id).join("-")}|${JSON.stringify(PV.variant)}`; }
function pvBase() {
  const key = pvCacheKey();
  if (_pv.key !== key) _pv = { key, res: {} };
  return _pv.res.base || (_pv.res.base = withMode("balanced", () => scoreMoves([])));
}
// A strategy plan as the server optimiser made it: its own XI and captain each week (so the points budgets checked in
// validate.py are what you see). A week the server plan doesn't cover (the 6-GW view of a 5-GW plan) or whose squad
// no longer matches (a dropped move) gets no transfers and the best XI by projected points, and is marked `filled`.
function planScore(pl, moves) {
  const byGw = Object.fromEntries(pl.weeks.map(w => [w.gw, w]));
  let tot = 0;
  const weeks = ftTable(moves).map(r => {
    const sq = squadAt(r.gw, moves), have = new Set(sq), w = byGw[r.gw];
    let team, filled = false;
    if (w && [...w.xi, ...w.bench].every(i => have.has(i)) && w.xi.includes(w.captain)) {
      team = { xi: w.xi, bench: w.bench, cap: w.captain, vice: w.vice, pts: w.xi.reduce((a, i) => a + xpg(i, r.gw), 0) + xpg(w.captain, r.gw) };
    } else { team = withMode("balanced", () => bestXI(sq, r.gw, {})); filled = true; }
    tot += team.pts - 4 * r.hits;
    return { ...r, team, sq, bank: bankAt(r.gw, moves), over: [], filled };
  });
  return { weeks, tot, ftLeft: weeks.length ? weeks[weeks.length - 1].next : 0 };
}
// the rule each strategy plays by, with the numbers from this build (data.plan_rules, set in optimise.py)
function pvRule(mode) {
  const R = D.plan_rules || {}, n = x => (x ?? 0).toFixed(x % 1 ? 1 : 0);
  const profit = R.min_profit != null ? ` It only suggests transfers that beat keeping your squad by at least ${n(R.min_profit)} point${R.min_profit === 1 ? "" : "s"}.` : "";
  if (mode === "safe") return `Never gives up projected points against Balanced. Where two plans are worth the same, it picks the players more managers around your rank own, starters sure to play, and no marginal hits.${profit}`;
  if (mode === "chase") return `Gives up at most ${n(R.chase_budget ?? 4)} projected points against Balanced over the plan, to back differentials and players with a high chance of a big haul. It takes a hit only when it clears the same extra bar as Play safe.${profit}`;
  return `Goes for the most projected points.${profit}`;
}
// one strategy's plan, against the My team baseline
function pvStrat(mode) {
  pvBase();
  if (_pv.res[mode]) return _pv.res[mode];
  const key = pvKey(mode);
  if (!key) return (_pv.res[mode] = { mode, key: null });
  const pl = D.plans[key];
  const wanted = pl.weeks.filter(w => PG.includes(w.gw)).reduce((a, w) => a + (w.in || []).length, 0);
  const raw = planMoves(pl).filter(m => PG.includes(m.gw) && P[m.in] && P[m.out]);
  const moves = cleanMoves(raw);
  const sc = planScore(pl, moves);
  const base = pvBase();
  const gain = sc.tot - base.tot;
  const traits = withMode(mode, () => planTraits(sc));
  const res = { mode, key, moves, sc, gain, conf: verdict(gain, 3, 1), dropped: wanted - moves.length, traits,
    hits: sc.weeks.reduce((a, w) => a + w.hits, 0), filled: sc.weeks.filter(w => w.filled).map(w => w.gw) };
  _pv.res[mode] = res;
  // cost against Balanced with the same number of moves this week (the budget is per option, see strategy_plans);
  // a gap within the solver's rounding room (plan_rules.tie) is shown as level, not as a loss
  if (mode !== "balanced") {
    const bk = key.replace(/^(safe|chase)_/, ""), bp = D.plans[bk];
    if (bp) {
      const bm = cleanMoves(planMoves(bp).filter(m => PG.includes(m.gw) && P[m.in] && P[m.out]));
      const bs = planScore(bp, bm), v = sc.tot - bs.tot;
      res.vsBal = Math.abs(v) <= (D.plan_rules?.tie ?? 0.1) + 0.01 ? 0 : v;
      res.ftVsBal = sc.ftLeft - bs.ftLeft;   // the budget also counts free transfers banked at the end (1.5 each)
    } else res.vsBal = null;
  }
  return res;
}
const pvGw = () => (PV.gw && PG.includes(PV.gw) ? PV.gw : PG[0]);
const pvFresh = (moves, g) => new Set(moves.filter(m => m.gw <= g).map(m => m.in));

function pvTabs() {
  const pv = S.pview;
  return `<div class="seg pviews" role="tablist" aria-label="Planner views">${PVIEWS.map(([k, l]) => {
    let tag = "";
    if (k === "suggest") { const r = pvStrat(S.pstrat); tag = r.key ? `<small class="${r.gain > 0.05 ? "up" : r.gain < -0.05 ? "down" : ""}">${MODES[S.pstrat]} ${sgn(r.gain)}</small>` : `<small>${MODES[S.pstrat]} –</small>`; }
    if (k === "edit" && SB.moves.length) tag = `<small>${SB.moves.length} move${SB.moves.length === 1 ? "" : "s"}</small>`;
    return `<button role="tab" data-pview="${k}" aria-selected="${pv === k}" aria-pressed="${pv === k}">${l}${tag}</button>`;
  }).join("")}</div>`;
}
function pvGwSel(weeks, g) {
  return `<div class="gwsel" role="group" aria-label="Gameweek">${weeks.map(w => `<button data-pvgw="${w.gw}" aria-pressed="${w.gw === g}">GW${w.gw}<small>${w.n ? `${w.n} move${w.n === 1 ? "" : "s"}${w.hits ? ` · −${4 * w.hits}` : ""} · ` : ""}${f1(w.team.pts)} xP</small></button>`).join("")}</div>`;
}

/* ---------- My team ---------- */
function pvMine() {
  const base = pvBase(), g = pvGw(), wk = base.weeks.find(w => w.gw === g), t = wk.team;
  const sq = D.squad.map(s => s.id);
  const asm = sq.filter(i => isAsm(i, g)).length;
  const flagged = sq.filter(i => P[i] && P[i].status !== "a");
  const ft = Math.min(5, D.manager.free_transfers);
  const cards = PV_MODES.map(m => {
    const r = pvStrat(m);
    if (!r.key) return `<button class="opt" data-pview="${m}"><span>${MODES[m]}</span><b>–</b><span>No plan this build</span></button>`;
    const now = r.moves.filter(x => x.gw === PG[0]);
    return `<button class="opt" data-pview="${m}"><span>${MODES[m]} · ${vPill(r.conf)}</span><b class="${r.gain > 0.05 ? "up" : ""}">${sgn(r.gain)}</b><span>${now.length ? now.map(x => `${esc(P[x.in].name)} in`).join(", ") : "Roll this week"}</span></button>`;
  }).join("");
  return `
  <div class="plansum">
    <div class="kpi"><span class="lbl">No transfers · ${PG.length} GWs</span><b>${f1(base.tot)}</b><span class="delta muted">projected, best XI + captain each week</span></div>
    <div class="kpi"><span class="lbl">GW${g} xP</span><b>${f1(t.pts)}</b><span class="delta muted">captain ${esc(P[t.cap]?.name || "–")}</span></div>
    <div class="kpi"><span class="lbl">${term("ft", "Free transfers")}</span><b>${ft}</b><span class="delta muted">for GW${PG[0]}</span></div>
    <div class="kpi"><span class="lbl">Bank</span><b>${money(D.manager.bank)}</b><span class="delta muted">before any moves</span></div>
  </div>
  <div class="grid2">
    <div style="min-width:0;display:grid;gap:10px;align-content:start">
      ${pvGwSel(base.weeks, g)}
      ${pitch(t.xi, t.bench, g, { cap: t.cap, vice: t.vice })}
      <p class="note">Your 15 as they are, with the XI and captain picked for the most projected points each week. Tap a player for his details.${asm ? ` ${asm} projection${asm === 1 ? " rests" : "s rest"} on assumptions (dotted number): FPL hasn't given a return date or chance.` : ""}</p>
    </div>
    <div style="display:grid;gap:20px;min-width:0;align-content:start">
      <div class="panel"><h3>What each strategy would do</h3>
        <p class="note" style="margin-top:0">Projected points over ${PG.length} GWs vs keeping this team, after hits. Tap one to see the XI it leaves you.</p>
        <div class="opts">${cards}</div></div>
      ${flagged.length ? `<div class="panel"><h3>Flagged in your squad</h3><div class="moves">${flagged.map(i => `<div class="move"><button data-p="${i}" style="all:unset;cursor:pointer"><b>${esc(P[i].name)}</b></button><span class="muted">${esc(P[i].news || "flagged")}</span><span class="mono">${f1(xpFrom(i, PG[0], PG.length))} xP / ${PG.length} GWs</span></div>`).join("")}</div></div>` : ""}
    </div>
  </div>`;
}

/* ---------- Suggested: one strategy at a time ---------- */
// which other strategies make exactly the same transfers over the plan (lineups and captains can still differ)
function pvSameAs(mode) {
  const r = pvStrat(mode); if (!r.key) return [];
  return PV_MODES.filter(m => m !== mode).filter(m => { const o = pvStrat(m); return o.key && sameMoves(o.moves, r.moves); });
}
function pvStratSwitch() {
  const cur = S.pstrat;
  const btns = PV_MODES.map(m => {
    const r = pvStrat(m);
    const sub = r.key ? `<small class="${r.gain > 0.05 ? "up" : r.gain < -0.05 ? "down" : ""}">${sgn(r.gain)}</small>` : "<small>no plan</small>";
    return `<button data-pstrat="${m}" aria-pressed="${m === cur}">${MODES[m]}${sub}</button>`;
  }).join("");
  const same = pvSameAs(cur);
  const why = cur === "safe" ? " Play safe can't give up points, so it only differs when a safer plan is worth the same." : cur === "chase" ? " No differential was worth its cost within the budget." : "";
  const sameTxt = same.length ? `Same transfers as ${same.map(m => MODES[m]).join(" and ")}${same.length === PV_MODES.length - 1 ? " this time: the strategies agree" : ""}.${same.includes("balanced") ? why : ""} Lineups and captains can still differ.` : "";
  return `<div class="panel pvstrat"><div class="bar" style="margin:0"><span class="lbl">${term("strategy", "Strategy")}</span>
    <div class="seg pvstratseg" role="group" aria-label="Strategy">${btns}</div></div>
    <p class="note" style="margin:8px 0 0">${pvRule(cur)}${sameTxt ? ` <b>${sameTxt}</b>` : ""}</p></div>`;
}
function pvMissing(mode) {
  const why = mode === "balanced" ? "The optimiser didn't produce any plans in this build." : `No ${MODES[mode]} plans in this build: they need the field-ownership data (managers around your rank), which wasn't available.`;
  return `<div class="panel"><h3>${MODES[mode]}</h3><p class="verdict">${why} Nothing is shown in its place. Try again after the next refresh, or plan it yourself.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" data-pview="edit">Open Your plan</button><button class="btn" data-pview="mine">Back to My team</button></div></div>`;
}
function pvStrategy(mode) {
  const r = pvStrat(mode);
  if (!r.key) return pvStratSwitch() + pvMissing(mode);
  const g = pvGw(), wk = r.sc.weeks.find(w => w.gw === g), t = wk.team, base = pvBase();
  const bw = base.weeks.find(w => w.gw === g);
  const now = r.moves.filter(m => m.gw === g);
  const variants = pvKeys(mode);
  const rec = recommendedPlan(mode);
  const varSeg = variants.length > 1 ? `<div class="bar" style="margin:0 0 6px"><span class="lbl">This week</span><div class="seg" role="group" aria-label="Moves this week">${variants.map(k => {
    const v = k.split("_").pop();
    return `<button data-pvvar="${mode}:${k}" aria-pressed="${k === r.key}">${PV_VAR_LABEL[v]}${k === rec ? " ★" : ""}</button>`;
  }).join("")}</div></div><p class="note" style="margin:0 0 8px">★ the pick: the fewest moves within 0.5 points of the best.</p>` : "";
  const movesHTML = now.length ? now.map(m => `<div class="sugg">
      <div class="sg-top"><div class="move"><span class="out">▼ ${esc(P[m.out].name)}</span><span class="in">▲ <button data-p="${m.in}" style="all:unset;cursor:pointer">${esc(P[m.in].name)}</button></span><span class="muted mono">${money(P[m.in].price)} · <span class="club-dot" style="--club:${clubCol(P[m.in])}" aria-hidden="true"></span>${T[P[m.in].team].short}</span></div>
        <span class="sg-gain ${xpFrom(m.in, g, PG.length) - xpFrom(m.out, g, PG.length) > 0.05 ? "up" : "down"}" title="xP over the rest of the plan, in minus out">${sgn(xpFrom(m.in, g, PG.length) - xpFrom(m.out, g, PG.length))}</span></div>
      <div class="sg-meta"><span class="fx sgfx">${fxChips(P[m.in], g, 4)}</span></div>
      <div class="sg-why"><b>Out:</b> ${whyOut(m.out, g)}<br><b>In:</b> ${whyIn(m.in, g)}</div></div>`).join("")
    : `<p class="muted" style="margin:0">No transfer in GW${g}${wk.next > wk.ft ? `: roll it, so you have ${wk.next} free next week` : ""}.</p>`;
  const timeline = r.sc.weeks.map(w => {
    const mv = r.moves.filter(m => m.gw === w.gw);
    const b = base.weeks.find(x => x.gw === w.gw).team.pts, v = w.team.pts - 4 * w.hits;
    return `<tr><td>GW${w.gw}</td><td style="white-space:normal;min-width:150px">${mv.length ? mv.map(m => `${esc(P[m.out].name)} → <b>${esc(P[m.in].name)}</b>`).join("<br>") : `<span class="muted">${w.next > w.ft ? "Roll" : "No transfer"}</span>`}</td><td class="n">${w.ft}</td><td class="n ${w.hits ? "down" : ""}">${w.hits ? "−" + 4 * w.hits : "0"}</td><td class="n">${money(w.bank)}</td><td>${esc(P[w.team.cap]?.name)}</td><td class="n">${f1(w.team.pts)}</td><td class="n ${v - b > 0.05 ? "up" : v - b < -0.05 ? "down" : ""}">${sgn(v - b)}</td></tr>`;
  }).join("");
  const drafts = getDrafts();
  return `
  ${pvStratSwitch()}
  <div class="plansum">
    <div class="kpi"><span class="lbl">${MODES[mode]} · ${PG.length} GWs</span><b>${f1(r.sc.tot)}</b><span class="delta muted">projected, after hits</span></div>
    <div class="kpi"><span class="lbl">vs My team</span><b class="${r.gain > 0.05 ? "up" : r.gain < -0.05 ? "down" : ""}">${sgn(r.gain)}</b><span class="delta">${vPill(r.conf)}</span></div>
    ${mode === "balanced" ? `<div class="kpi"><span class="lbl">GW${g} xP</span><b>${f1(t.pts)}</b><span class="delta muted">${sgn(t.pts - 4 * wk.hits - bw.team.pts)} vs My team that week</span></div>`
      : `<div class="kpi"><span class="lbl">vs Balanced</span><b class="${r.vsBal < -0.05 ? "down" : ""}">${r.vsBal == null ? "–" : sgn(r.vsBal)}</b><span class="delta muted">${mode === "safe" ? "never below Balanced" : `budget −${f1(D.plan_rules?.chase_budget ?? 4)}`}${r.ftVsBal ? ` · ${Math.abs(r.ftVsBal)} ${r.ftVsBal < 0 ? "fewer" : "more"} ${term("ft", "FT")} banked` : ""}</span></div>`}
    <div class="kpi"><span class="lbl">GW${g} ${term("ft", "transfers")}</span><b>${wk.n}/${wk.ft}</b><span class="delta muted">${wk.hits ? `${wk.hits} hit (−${4 * wk.hits})` : "no hits"} · bank ${money(wk.bank)}</span></div>
  </div>
  ${r.filled.length ? `<p class="note">${r.filled.map(x => "GW" + x).join(", ")} ${r.filled.length === 1 ? "is" : "are"} beyond the optimiser's ${D.plans[r.key].weeks.length}-GW plan: shown with no transfers and the best XI.</p>` : ""}
  ${r.dropped > 0 ? `<p class="verdict" style="border-color:var(--warn)">${r.dropped} move${r.dropped === 1 ? "" : "s"} in this plan named a player who is no longer in the data, so ${r.dropped === 1 ? "it was" : "they were"} left out. The numbers above are without ${r.dropped === 1 ? "it" : "them"}.</p>` : ""}
  <div class="grid2">
    <div style="min-width:0;display:grid;gap:10px;align-content:start">
      ${pvGwSel(r.sc.weeks, g)}
      ${pitch(t.xi, t.bench, g, { cap: t.cap, vice: t.vice, fresh: pvFresh(r.moves, g) })}
      <p class="note">The XI this plan leaves you in GW${g}. A green bar under a shirt marks a player bought in the plan. Confidence is the gain over keeping your team: Strong at 3+ points over ${PG.length} GWs, Marginal at 1–3, otherwise a coin flip.</p>
    </div>
    <div style="display:grid;gap:20px;min-width:0;align-content:start">
      <div class="panel"><div class="bar"><h3>Moves · GW${g}</h3><span class="tag">${MODES[mode]}</span></div>${varSeg}${movesHTML}
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" data-pvuse="${mode}:${r.key}">Use this plan</button><button class="btn" data-pvdraft="${mode}:${r.key}" ${drafts.length >= 3 ? "disabled title=\"3 drafts saved: delete one in Your plan\"" : ""}>Save as draft</button></div>
        <p class="note">Use this plan makes it Your plan (Undo brings the old one back) and opens the editor, where you can tweak it. This week and Rivals follow Your plan.</p></div>
      <details class="panel pvtl" ${PG.length <= 3 ? "open" : ""}><summary>Full ${PG.length}-GW plan</summary>
        <div class="tablebox" style="margin-top:10px"><table><thead><tr><th>GW</th><th>Moves</th><th class="n">FT</th><th class="n">Hits</th><th class="n">Bank</th><th>Captain</th><th class="n">xP</th><th class="n">vs My team</th></tr></thead><tbody>${timeline}</tbody></table></div></details>
    </div>
  </div>`;
}

/* ---------- Compare ---------- */
function pvCompare() {
  const base = pvBase(), eo = fieldEO();
  const baseTraits = withMode("balanced", () => planTraits(base));
  const cols = [{ name: "My team", view: "mine", sc: base, gain: 0, moves: [], traits: baseTraits, hits: 0 },
    ...PV_MODES.map(m => { const r = pvStrat(m); return r.key ? { name: MODES[m], view: m, ...r } : { name: MODES[m], view: m, missing: true }; })];
  if (SB.moves.length) {
    const sc = scoreMoves(SB.moves);
    cols.push({ name: "Your plan", view: "edit", sc, gain: sc.tot - base.tot, moves: SB.moves, conf: verdict(sc.tot - base.tot, 3, 1), traits: planTraits(sc), hits: sc.weeks.reduce((a, w) => a + w.hits, 0) });
  }
  const live = cols.filter(c => !c.missing);
  const best = f => Math.max(...live.map(f));
  const cell = (c, f, fmt, hi = true) => c.missing ? `<td class="n muted">–</td>` : `<td class="n ${hi && live.length > 1 && Math.abs(f(c) - best(f)) < 1e-9 ? "up" : ""}">${fmt(f(c))}</td>`;
  const g0 = PG[0];
  const rows = [
    ["Projected points", c => c.sc.tot, f1],
    ["vs My team", c => c.gain, sgn],
    ["Confidence", null, c => c.conf ? vPill(c.conf) : `<span class="muted">baseline</span>`],
    [`GW${g0} xP`, c => c.sc.weeks[0].team.pts, f1],
    [`GW${g0} captain`, null, c => esc(P[c.sc.weeks[0].team.cap]?.name || "–")],
    ["Hits", c => -c.hits, x => x ? "−" + 4 * -x : "0"],
    ["FT left at the end", c => c.sc.ftLeft, x => String(x)],
    [term("eo", "Field ownership of GW" + g0 + " XI"), null, c => eo ? `${Math.round(c.traits.eo * 100)}%` : "–"],
    ["Chance of 10+ hauls", null, c => f1(c.traits.haul)],
  ];
  const body = rows.map(([l, f, fmt]) => `<tr><td>${l}</td>${cols.map(c => f ? cell(c, f, fmt) : c.missing ? `<td class="n muted">–</td>` : `<td class="n">${fmt(c)}</td>`).join("")}</tr>`).join("");
  const tl = PG.map(g => `<tr><td><b>GW${g}</b></td>${cols.map(c => {
    if (c.missing) return `<td class="n muted">No plan</td>`;
    const w = c.sc.weeks.find(x => x.gw === g), mv = c.moves.filter(m => m.gw === g);
    return `<td class="pvcell"><span class="muted mono">${w.n}/${w.ft} FT · ${money(w.bank)}</span>${mv.length ? mv.map(m => `<span><span class="out">${esc(P[m.out].name)}</span> → <span class="in">${esc(P[m.in].name)}</span></span>`).join("") : `<span class="muted">${c.view === "mine" ? "–" : w.next > w.ft ? "Roll" : "No transfer"}</span>`}</td>`;
  }).join("")}</tr>`).join("");
  return `<div class="panel"><div class="bar"><h3>Side by side · ${PG.length} GWs</h3></div>
    <p class="note" style="margin-top:0">Every column is scored the same way: best XI and captain each week, minus 4 per hit. Green marks the best in each row. "Chance of 10+ hauls" adds up each starter's chance of 10+ points (captain twice) over the plan.</p>
    <div class="tablebox pvcmpbox"><table class="pvcmp"><thead><tr><th></th>${cols.map(c => `<th class="n"><button class="btn" data-pview="${c.view}">${esc(c.name)}</button></th>`).join("")}</tr></thead>
      <tbody>${body}<tr class="pvsep"><td colspan="${cols.length + 1}">Week by week</td></tr>${tl}</tbody></table></div></div>`;
}

/* ---------- page ---------- */
function vPlanner() {
  const pv = S.pview;
  const body = pv === "edit" ? plannerEditor() : pv === "compare" ? pvCompare() : pv === "suggest" ? pvStrategy(S.pstrat) : pvMine();
  return `
  <header class="page-title"><h1>Planner</h1><p>Your team as it is, what each strategy would do, and your own plan, over the next ${PG.length} gameweeks.</p></header>
  <div class="pvhead">${pvTabs()}
    <div class="bar" style="margin:0"><span class="lbl">${term("horizon", "Plan length")}</span>
      <div class="seg" role="group" aria-label="Plan length">${[3, 5, 6].filter(h => h <= GWS.length).map(h => `<button data-horizon="${h}" aria-pressed="${S.horizon === h}">${h} GWs</button>`).join("")}</div></div></div>
  ${body}`;
}
function bindPlannerViews() {
  // keep the open tab in sight when the tab row scrolls sideways (phones)
  const bar = document.querySelector(".pviews"), cur = bar?.querySelector('[aria-pressed="true"]');
  if (bar && cur && bar.scrollWidth > bar.clientWidth) bar.scrollLeft = Math.max(0, cur.offsetLeft - (bar.clientWidth - cur.offsetWidth) / 2);
  const on = (sel, fn) => document.querySelectorAll(sel).forEach(el => el.onclick = () => fn(el));
  on("[data-pview]", b => {
    let v = b.dataset.pview;
    if (PV_MODES.includes(v)) { S.pstrat = v; store.set("fpl.pstrat", v); v = "suggest"; }
    S.pview = v; store.set("fpl.pview", v); if (v !== "edit") SB.sel = null; render(); window.scrollTo({ top: 0 });
  });
  on("[data-pstrat]", b => { S.pstrat = b.dataset.pstrat; store.set("fpl.pstrat", S.pstrat); render(); });
  on("[data-pvgw]", b => { PV.gw = +b.dataset.pvgw; render(); });
  on("[data-pvvar]", b => { const [m, k] = b.dataset.pvvar.split(":"); PV.variant[m] = k; render(); });
  on("[data-pvuse]", b => {
    const [m] = b.dataset.pvuse.split(":"), r = pvStrat(m); if (!r.key) return;
    S.mode = m; store.set("fpl.mode", m);
    setPlan(r.moves, "plan:" + r.key);
    S.pview = "edit"; store.set("fpl.pview", "edit");
    render(); window.scrollTo({ top: 0 });
    toast(`${MODES[m]} plan is now Your plan: ${sgn(r.gain)} over ${PG.length} GWs. Undo is in Your moves.`);
  });
  on("[data-pvdraft]", b => {
    const [m] = b.dataset.pvdraft.split(":"), r = pvStrat(m), ds = getDrafts(); if (!r.key || ds.length >= 3) return;
    ds.push({ name: `${MODES[m]} · ${PV_VAR_LABEL[r.key.split("_").pop()]}`, moves: r.moves.map(x => ({ ...x })), ov: {}, mode: m, saved: Date.now() });
    setDrafts(ds); render(); toast(`Saved as a draft. Compare drafts in Your plan → Drafts.`);
  });
}
