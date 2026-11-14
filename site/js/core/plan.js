// Plans and the sandbox: one source of truth for every tab.
/* ---------- plans ---------- */
const PLAN_LABEL = { roll: "Roll", one: "1 move", two: "2 moves", three: "3 moves", best: "Optimal" };
function planMoves(pl) {
  const mv = [];
  pl.weeks.forEach(w => {
    const outs = w.out.slice();
    w.in.forEach(i => {
      const k = outs.findIndex(o => P[o]?.pos === P[i]?.pos);
      if (k >= 0) mv.push({ gw: w.gw, out: outs.splice(k, 1)[0], in: i });
    });
  });
  return mv;
}
const MODES = { balanced: "Balanced", safe: "Play safe", chase: "Chase rank" };
const MODE_HELP = {
  balanced: "Goes for the most projected points.",
  get safe() { const f = fieldSample(); return `Never gives up projected points against Balanced; where plans are worth the same it sticks close to what ${f ? f.label : "the field"} own.${f ? "" : " Ownership sample unavailable."}`; },
  get chase() { const f = fieldSample(); return `Gives up a few projected points at most to back differentials ${f ? f.label : "the field"} don't own. Good when you need to climb.${f ? "" : " Ownership sample unavailable."}`; },
};
const mk = (k, mode = S.mode) => mode === "balanced" || !D.plans[`${mode}_${k}`] ? k : `${mode}_${k}`;
const planLabel = key => { const [m, k] = key.includes("_") ? key.split("_") : ["balanced", key]; return (m === "balanced" ? "" : MODES[m] + ": ") + PLAN_LABEL[k]; };
// Cut-offs tested against outcomes on 2024/25 and 2025/26 (FL-127, tools/verdict_check.py, docs/model-log.md 14 Nov).
// One-week calls (captain, lineup): a projected gap under 1.5 points came off 54% of the time, barely better than a
// coin flip; 1.5 to 2 about 60%; 2 or more about 77%. Before FL-127 they were Strong at 1 and Marginal at 0.4, which
// called 55-60% calls Strong. A plan's gain over the plan length keeps 3 / 1: Strong came off 65% (+5.6 real points),
// Marginal 54%, Coin flip 51%.
const CUT_WEEK = [2, 1.5], CUT_PLAN = [3, 1];
function verdict(g, strong = CUT_PLAN[0], marg = CUT_PLAN[1]) {
  return g >= strong ? { t: "Strong", c: "good" } : g >= marg ? { t: "Marginal", c: "warn" } : { t: "Coin flip", c: "mut" };
}
// One confidence scale everywhere (U1): Strong / Marginal / Coin flip from verdict(). v.tag adds a separate, neutral
// pill for context that isn't confidence (e.g. "Field's pick": most managers in the selected sample captain him).
const vPill = v => `<span class="pill ${v.c}">${v.t}</span>${v.tag ? ` <span class="pill mut">${v.tag}</span>` : ""}`;
// the build's variance formula (plan_rules.variance, optimise.VARIANCE: a * x + b * x^2), FL-075
function variance(pos, x) { const R = D.plan_rules, [a, b] = R.variance[pos] || R.variance_other; return a * x + b * x * x; }
// missing ownership sample or variance formula (a data.json older than FL-075): null, and the spread isn't shown
function spreadVsField(mult, g) {
  const F = fieldSample()?.data;
  if (!F || !D.plan_rules?.variance || !D.plan_rules.variance_other) return null;
  let v = 0;
  D.players.forEach(p => { const x = xpg(p.id, g); if (x <= 0) return; const d = (mult[p.id] || 0) - (F.eo[p.id] || 0) / 100; if (d) v += variance(p.pos, x) * d * d; });
  return Math.sqrt(v);
}
// The recommended plan (FL-108) is worked out once in the build (optimise.recommended) and shipped as D.recommended
// ({mode: plan key}), so Home, the Planner, the journal and You vs the model all name the same plan. Missing (a
// strategy with no plans, or a data.json from before FL-108): null, and the tabs show no recommendation, never a guess.
function recommendedPlan(mode = S.mode) {
  const k = D.recommended?.[mode];
  return k && D.plans?.[k] ? k : null;
}
const mvKey = mv => mv.map(m => `${m.gw}:${m.out}>${m.in}`).sort().join(",");
const sameMoves = (a, b) => mvKey(a) === mvKey(b);
// The rest of the plan from gameweek g: how many of the plan's weeks are left (planLeft) and their span for labels
// (planSpan, "GW12–GW15"). A player's xP for a move in gameweek g covers these weeks only. xpFrom(id, g, PG.length) used
// to count PG.length weeks from g, so a GW12 move in a GW11–GW15 plan also counted GW16, past the plan, while its label
// said "over 5 GWs". A g outside the plan's weeks has none left: planLeft is 0 and the figure is 0, never a guess.
const planLeft = g => PG.filter(x => x >= g).length;
const planSpan = g => { const w = PG.filter(x => x >= g); return w.length > 1 ? `GW${w[0]}–GW${w[w.length - 1]}` : w.length ? `GW${w[0]}` : "no weeks"; };

/* ---------- your plan: one source of truth for every tab ---------- */
function sbKey() { return `fpl.sb.${D.meta.team_id}.${D.meta.next_gw}.${D.squad.map(s => s.id).join("-")}`; }
function loadSandbox() {
  const keepGw = SB && PG.includes(SB.gw) ? SB.gw : PG[0], keepSel = SB?.sel ?? null;
  const scope = sbKey(), sameSquad = SB?.scope === scope;
  if (!sameSquad) TP.undo = null;
  const saved = store.get(scope);
  SB = { moves: [], source: "", gw: keepGw, sel: keepSel, q: SB?.q || "", scope, prev: sameSquad ? SB.prev : null, ov: {}, solved: null, chips: {}, rules: { locked: [], banned: [], maxHits: null } };
  if (saved && Array.isArray(saved.moves)) {
    SB.updated = saved.updated || 0;
    applyExtras(saved); SB.sel = keepSel;
  } else {
    const rec = recommendedPlan();
    SB.moves = rec ? planMoves(D.plans[rec]) : [];
    SB.source = rec ? "plan:" + rec : "custom";
  }
  sanitize();
}
// Legacy local/synced plans use the same flat fields. Missing lineup means automatic
// selection, missing overrides mean none, and a missing strategy keeps the device's choice.
function completePlan(src = SB) {
  return JSON.parse(JSON.stringify({ moves: src.moves || [], ov: src.ov || {},
    solved: src.solved || null, mode: MODES[src.mode] ? src.mode : S.mode, chips: src.chips || {} }));
}
function applyPlan(src, source) {
  const plan = completePlan(src);
  SB.chips = cleanChips(plan.chips);
  SB.moves = cleanMoves(plan.moves.filter(m => P[m.in] && P[m.out] && GWS.includes(m.gw)));
  SB.ov = Object.fromEntries(Object.entries(plan.ov).filter(([g]) => GWS.includes(+g)));
  SB.solved = plan.solved; SB.source = source || "custom"; SB.sel = null;
  S.mode = plan.mode; store.set("fpl.mode", S.mode);
}
function rememberPlan() {
  SB.prev = { ...completePlan(), source: SB.source, scope: sbKey(), editing: tpEditing() };
}
function undoPlan() {
  const prev = SB.prev; SB.prev = null;
  if (!prev || prev.scope !== sbKey()) return;
  applyPlan(prev, prev.source); tpEditing(prev.editing || null); saveSandbox();
}
function sbState() { return { ...completePlan(), source: SB.source, updated: SB.updated, rules: SB.rules, drafts: store.get(sbKey() + ".drafts") || [] }; }
function applyExtras(src) {
  applyPlan(src, src.source);
  SB.rules = Object.assign({ locked: [], banned: [], maxHits: null }, src.rules || {});
  SB.rules.locked = SB.rules.locked.filter(i => P[i]); SB.rules.banned = SB.rules.banned.filter(i => P[i]);
}
function saveSandbox() { SB.updated = Date.now(); _base = null; store.set(sbKey(), sbState()); syncPush(); }
function setOv(g, fn) { SB.ov[g] = SB.ov[g] || { start: [], bench: [] }; fn(SB.ov[g]); saveSandbox(); }
// solved: the optimiser's own lineup and captain per week ({gw: {sq, xi, cap}}), kept with the moves it chose them
// for (Re-plan). Anything else that sets or edits the plan clears it, so a lineup never outlives its squad.
function activatePlan(plan, source, editing = null) {
  rememberPlan(); applyPlan(plan, source); tpEditing(editing); saveSandbox();
}
function setPlan(moves, source, solved = null) {
  activatePlan({ moves, solved, ov: SB.ov, chips: SB.chips }, source, tpEditing());
}
function editPlan(fn) { rememberPlan(); fn(); SB.source = "custom"; SB.solved = null; sanitize(); saveSandbox(); }
function planName() {
  if (SB.source.startsWith("replan:")) return "Re-planned" + (SB.source.endsWith("balanced") ? "" : ` (${MODES[SB.source.split(":")[1]]})`);
  if (SB.source.startsWith("plan:")) { const k = SB.source.slice(5); if (D.plans[k] && sameMoves(planMoves(D.plans[k]), SB.moves)) return planLabel(k) + " plan"; }
  return SB.moves.length ? "Your plan" : "No transfers";
}
/* ---------- chips pinned to a gameweek (FL-005) ---------- */
// SB.chips: {wildcard|freehit|bboost|3xc: gw}, saved with the plan. Scored by FPL's rules, the same as the browser
// optimiser (plan-solver.js): a Wildcard or Free Hit week's transfers are free and your banked free transfers are kept
// (FPL since 2024/25); a Free Hit week's moves last that week only, then the squad and bank go back; Bench Boost adds
// the bench's points; Triple Captain counts the captain three times. Missing or ambiguous: a pin for a chip you've
// already used, outside its window (D.chips from/to) or outside the plan's weeks, or a second chip on the same week,
// is dropped when the plan loads (cleanChips) and the Re-plan panel says why; nothing is pinned for you. Server plans
// (D.plans) carry no chips.
const CHIP_NAME = { wildcard: "Wildcard", freehit: "Free Hit", bboost: "Bench Boost", "3xc": "Triple Captain" };
const CHIP_SHORT = { wildcard: "WC", freehit: "FH", bboost: "BB", "3xc": "TC" };
// the chip you can still play in gameweek g ({key, from, to} from D.chips), or null
const chipWindow = (key, g) => (D.chips || []).find(c => c.key === key && c.available && c.from <= g && c.to >= g) || null;
function cleanChips(chips) {
  const out = {}, used = new Set();
  Object.entries(chips || {}).forEach(([k, g]) => {
    g = +g; if (!CHIP_NAME[k] || !PG.includes(g) || !chipWindow(k, g) || used.has(g)) return;
    out[k] = g; used.add(g);
  });
  return out;
}
const chipAt = (g, chips = SB.chips) => Object.keys(chips || {}).find(k => chips[k] === g) || null;
// a move that counts in gameweek gw: all earlier moves, except a Free Hit week's (those last that week only)
const movesFor = (gw, moves, chips) => moves.filter(m => m.gw <= gw && !(chips?.freehit === m.gw && gw > m.gw));
const chipsFor = moves => (moves === SB?.moves ? SB.chips : {}) || {};
function squadAt(gw, moves = SB.moves, chips = chipsFor(moves)) {
  const s = D.squad.map(x => x.id);
  movesFor(gw, moves, chips).forEach(m => { const k = s.indexOf(m.out); if (k >= 0) s[k] = m.in; });
  return s;
}
function sellPrice(id) { const s = D.squad.find(x => x.id === id); return s ? s.sell : P[id].price; }
// FPL's selling price: what you paid plus half of any rise, rounded down to £0.1m (a fall below cost is taken in full)
function fplSell(buy, price) { const b = Math.round(buy * 10), p = Math.round(price * 10); return (p <= b ? p : b + Math.floor((p - b) / 2)) / 10; }
// would a £0.1m fall tonight cost you anything? Not for a squad player whose half-profit rounding absorbs it
function fallCostsYou(id) { const s = D.squad.find(x => x.id === id); return !s || fplSell(s.buy, P[id].price - 0.1) < s.sell; }
// price-move wording, the same on every page. FPL's projection reaches the change threshold at 100%; our track record
// has almost every 100%+ player moving that night and none from 75–99%, so only 100%+ is called "tonight".
function priceTonight(pr) { return pr != null && Math.abs(pr) >= 100; }
// "Close to a price change": one cut-off for every page (Home, Planner, Stats → Prices, the moves summary, the
// watchlist). 75 is a band edge of the track record we show (build.py BANDS: 50–75, 75–90, 90–100, 100+), and it is
// the wider of the two cut-offs that used to be in use (75 and 80), so no alert that showed before has gone.
// Missing projection (null/undefined): never close, so nothing is asserted about that player.
const PRICE_NEAR = 75;
function priceRising(pr) { return pr != null && pr >= PRICE_NEAR; }
function priceFalling(pr) { return pr != null && pr <= -PRICE_NEAR; }
// When the nightly price update happens: the time FPL lists (price_change_deadlines, midnight UK), with no offset.
// Evidence, from the commit history of history/prices.json: on the three nights a build ran soon after the listed
// time (8, 9 and 11 Nov 2026) every change of that night was already in at 00:47, 00:35 and 00:10 UK. The old
// "+90 minutes" (01:30 UK) on Stats had no support. We don't know the exact minute, so the text always says "around".
// Missing or unreadable time: null / "" (callers then leave the time out rather than guess one).
function priceUpdateAt(iso) { const d = iso ? new Date(iso) : null; return d && !isNaN(d) ? d : null; }
// The update that FPL's price projections in this data are for: the first listed update after the data was built
// (prices.pending_night, else the first price_change_deadline after meta.built). Not "after now": on data that has
// gone stale overnight, the figures still describe the night after the build, so that is the night to name.
// Missing: no listed update after the build -> null, and callers leave the time out.
function nextPriceUpdate() {
  const built = new Date(D.meta.built);
  return D.prices?.pending_night || (D.meta.price_deadlines || []).find(d => new Date(d) > built) || null;
}
// "around Thu 12 Nov, 00:00" (UK time); day = false gives "around 00:00" for lists already grouped by day
function priceUpdateTxt(iso, day = true) {
  const d = priceUpdateAt(iso); if (!d) return "";
  return "around " + (day ? ukTime(d) : d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" }));
}
function priceMove(pr) {
  const dir = pr >= 0 ? "rise" : "fall";
  return priceTonight(pr) ? `may ${dir} in price tonight` : `${dir === "rise" ? "rising" : "falling"} in price (${Math.abs(pr).toFixed(0)}% of the way), not likely tonight`;
}
function bankAt(gw, moves = SB.moves, chips = chipsFor(moves)) {
  let b = D.manager.bank;
  const base = new Set(D.squad.map(x => x.id)), bought = new Set();
  movesFor(gw, moves, chips).forEach(m => {
    b += (base.has(m.out) && !bought.has(m.out)) ? sellPrice(m.out) : P[m.out].price;
    b -= P[m.in].price; bought.add(m.in);
  });
  return Math.round(b * 10) / 10;
}
function cleanMoves(moves, chips = SB?.chips || {}) {
  const ok = [], s = D.squad.map(x => x.id);
  let fh = null;   // the Free Hit week's squad, which later weeks don't keep
  moves.slice().sort((a, b) => a.gw - b.gw).forEach(m => {
    const temp = chips.freehit === m.gw, sq = temp ? (fh = fh || s.slice()) : s;
    if (sq.includes(m.out) && !sq.includes(m.in)) { ok.push(m); sq[sq.indexOf(m.out)] = m.in; }
  });
  return ok;
}
function sanitize() { SB.moves = cleanMoves(SB.moves); }
function ftTable(moves = SB.moves, weeks = PG, chips = chipsFor(moves)) {
  let ft = Math.min(5, D.manager.free_transfers);
  return weeks.map(g => {
    const chip = chipAt(g, chips), free = chip === "wildcard" || chip === "freehit";
    const n = moves.filter(m => m.gw === g).length, hits = free ? 0 : Math.max(0, n - ft);
    const row = { gw: g, ft, n, hits, chip };
    ft = free ? Math.min(5, ft + 1) : n > ft ? 1 : Math.min(5, ft - n + 1);
    row.next = ft;
    return row;
  });
}
function clubCounts(ids) { const c = {}; ids.forEach(i => c[P[i].team] = (c[P[i].team] || 0) + 1); return c; }
// the single scorer used by This week, Planner and Rivals
function scoreMoves(moves, solved = moves === SB.moves ? SB.solved : null, chips = chipsFor(moves)) {
  let tot = 0;
  const weeks = ftTable(moves, PG, chips).map(r => {
    const sq = squadAt(r.gw, moves, chips), team = { ...bestXI(sq, r.gw, undefined, solved) };
    // Bench Boost: the bench scores too; Triple Captain: the armband counts once more (team.pts already has x2)
    team.chipPts = r.chip === "bboost" ? team.bench.reduce((a, i) => a + xpg(i, r.gw), 0) : r.chip === "3xc" && team.cap ? xpg(team.cap, r.gw) : 0;
    team.pts += team.chipPts;
    tot += team.pts - 4 * r.hits;
    // more than 3 from a club is only a problem in a week with a transfer: a squad that already holds 4 (a real move
    // between Premier League clubs) can keep them until it next transfers, and then must be back to 3 (FL-074)
    const held = clubCounts(D.squad.map(s => s.id));
    const over = Object.entries(clubCounts(sq)).filter(([t, v]) => v > 3 && (r.n > 0 || v > (held[t] || 0))).map(([t]) => T[t].short);
    return { ...r, team, sq, bank: bankAt(r.gw, moves, chips), over };
  });
  return { weeks, tot, ftLeft: weeks.length ? weeks[weeks.length - 1].next : 0 };
}
let _base = null;
// keeping the squad still plays the Bench Boost and Triple Captain you pinned (they aren't transfers), so "vs no
// transfers" measures the moves alone; a Wildcard or Free Hit with no moves changes nothing
const baseChips = () => Object.fromEntries(Object.entries(SB?.chips || {}).filter(([k]) => k === "bboost" || k === "3xc"));
const baseScore = () => _base || (_base = scoreMoves([], null, baseChips()));
// FL-125: the one "vs no transfers" figure on the Planner, the same measure as data.json's plans[*].vs_none
// (optimise.strategy_plans): projected points over the plan after hits, plus ft_value for each free transfer banked at
// the end, against keeping the squad and picking the best XI each week. Points alone would overstate a plan that
// spends transfers (on 12 Nov, Balanced showed +7.4 where data.json had +5.88). Missing: a data.json from before
// plan_rules.ft_value -> 1.5, optimise.FT_VALUE; validate.py errors when plans are published without it, so the
// fallback only covers an old copy cached on the device.
const ftValue = () => D.plan_rules?.ft_value ?? 1.5;
const gainVsNone = (sc, base) => sc.tot - base.tot + ftValue() * (sc.ftLeft - base.ftLeft);
const GAIN_NOTE = () => `after hits, with each free transfer banked at the end worth ${f1(ftValue())}`;
function sandboxSummary() {
  const sc = scoreMoves(SB.moves), base = baseScore();
  sc.weeks.forEach((w, i) => w.base = base.weeks[i].team.pts);
  return { weeks: sc.weeks, tot: sc.tot, baseTot: base.tot, ftLeft: sc.ftLeft, baseFtLeft: base.ftLeft, gain: gainVsNone(sc, base) };
}
function myTeam() {
  const g = D.meta.next_gw, sc = scoreMoves(SB.moves), w = sc.weeks[0];
  const mult = {}; (w.chip === "bboost" ? [...w.team.xi, ...w.team.bench] : w.team.xi).forEach(i => mult[i] = 1); mult[w.team.cap] = w.chip === "3xc" ? 3 : 2;
  return { ...w.team, g, mult, week: w, moves0: SB.moves.filter(m => m.gw === g), later: SB.moves.filter(m => m.gw !== g), score: sc };
}
