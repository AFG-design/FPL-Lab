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
  balanced: "Goes for the most points.",
  safe: "Sticks close to what managers around your rank own, so one popular haul can't sink you. Good for protecting a rank.",
  chase: "Backs differentials the managers around you don't own, and keeps the popular players you already have. More swing for slightly fewer projected points. Good when you need to climb.",
};
const mk = (k, mode = S.mode) => mode === "balanced" || !D.plans[`${mode}_${k}`] ? k : `${mode}_${k}`;
const planLabel = key => { const [m, k] = key.includes("_") ? key.split("_") : ["balanced", key]; return (m === "balanced" ? "" : MODES[m] + ": ") + PLAN_LABEL[k]; };
function verdict(g, strong = 3, marg = 1) {
  return g >= strong ? { t: "Strong", c: "good" } : g >= marg ? { t: "Marginal", c: "warn" } : { t: "Coin flip", c: "mut" };
}
const vPill = v => `<span class="pill ${v.c}">${v.t}</span>`;
function variance(pos, x) { return pos === "MID" ? 1.9 * x + 0.23 * x * x : ({ GKP: 2.8, DEF: 3.3, FWD: 3.8 }[pos] || 3) * x; }
function spreadVsField(mult, g) {
  const F = D.crowd ? (D.crowd.near?.n >= 100 ? D.crowd.near : D.crowd.top10k) : null;
  if (!F) return null;
  let v = 0;
  D.players.forEach(p => { const x = xpg(p.id, g); if (x <= 0) return; const d = (mult[p.id] || 0) - (F.eo[p.id] || 0) / 100; if (d) v += variance(p.pos, x) * d * d; });
  return Math.sqrt(v);
}
function recommendedPlan(mode = S.mode) {
  const pl = D.plans || {};
  const keys = ["roll", "one", "two", "three"].map(k => mk(k, mode)).filter(k => pl[k]);
  if (!keys.length) return null;
  const best = keys.reduce((a, k) => pl[k].vs_roll > pl[a].vs_roll ? k : a, keys[0]);
  for (const k of keys) if (pl[k].vs_roll >= pl[best].vs_roll - 0.5) return k;  // fewer moves when it's close
  return best;
}
const mvKey = mv => mv.map(m => `${m.gw}:${m.out}>${m.in}`).sort().join(",");
const sameMoves = (a, b) => mvKey(a) === mvKey(b);

/* ---------- your plan: one source of truth for every tab ---------- */
function sbKey() { return `fpl.sb.${D.meta.team_id}.${D.meta.next_gw}.${D.squad.map(s => s.id).join("-")}`; }
function loadSandbox() {
  const keepGw = SB && PG.includes(SB.gw) ? SB.gw : PG[0], keepSel = SB?.sel ?? null;
  const saved = store.get(sbKey());
  SB = { moves: [], source: "", gw: keepGw, sel: keepSel, q: SB?.q || "", prev: SB?.prev || null, ov: {}, rules: { locked: [], banned: [], maxHits: null } };
  if (saved && Array.isArray(saved.moves)) {
    SB.moves = saved.moves.filter(m => P[m.in] && P[m.out] && GWS.includes(m.gw));
    SB.source = saved.source || "custom"; SB.updated = saved.updated || 0;
    applyExtras(saved);
  } else {
    const rec = recommendedPlan();
    SB.moves = rec ? planMoves(D.plans[rec]) : [];
    SB.source = rec ? "plan:" + rec : "custom";
  }
  sanitize();
}
function sbState() { return { moves: SB.moves, source: SB.source, updated: SB.updated, ov: SB.ov, rules: SB.rules, drafts: store.get(sbKey() + ".drafts") || [] }; }
function applyExtras(src) {
  SB.ov = {};
  Object.entries(src.ov || {}).forEach(([g, o]) => { if (GWS.includes(+g)) SB.ov[+g] = o; });
  SB.rules = Object.assign({ locked: [], banned: [], maxHits: null }, src.rules || {});
  SB.rules.locked = SB.rules.locked.filter(i => P[i]); SB.rules.banned = SB.rules.banned.filter(i => P[i]);
}
function saveSandbox() { SB.updated = Date.now(); _base = null; store.set(sbKey(), sbState()); syncPush(); }
function setOv(g, fn) { SB.ov[g] = SB.ov[g] || { start: [], bench: [] }; fn(SB.ov[g]); saveSandbox(); }
function setPlan(moves, source) {
  SB.prev = { moves: SB.moves.slice(), source: SB.source };
  SB.moves = moves.map(m => ({ ...m })); SB.source = source; SB.sel = null;
  sanitize(); saveSandbox();
}
function editPlan(fn) { fn(); SB.source = "custom"; sanitize(); saveSandbox(); }
function planName() {
  if (SB.source.startsWith("replan:")) return "Re-planned" + (SB.source.endsWith("balanced") ? "" : ` (${MODES[SB.source.split(":")[1]]})`);
  if (SB.source.startsWith("plan:")) { const k = SB.source.slice(5); if (D.plans[k] && sameMoves(planMoves(D.plans[k]), SB.moves)) return planLabel(k) + " plan"; }
  return SB.moves.length ? "Your plan" : "No transfers";
}
function squadAt(gw, moves = SB.moves) {
  const s = D.squad.map(x => x.id);
  moves.filter(m => m.gw <= gw).forEach(m => { const k = s.indexOf(m.out); if (k >= 0) s[k] = m.in; });
  return s;
}
function sellPrice(id) { const s = D.squad.find(x => x.id === id); return s ? s.sell : P[id].price; }
// price-move wording, the same on every page. FPL's projection reaches the change threshold at 100%; our track record
// has almost every 100%+ player moving that night and none from 75–99%, so only 100%+ is called "tonight".
function priceTonight(pr) { return pr != null && Math.abs(pr) >= 100; }
function priceMove(pr) {
  const dir = pr >= 0 ? "rise" : "fall";
  return priceTonight(pr) ? `may ${dir} in price tonight` : `${dir === "rise" ? "rising" : "falling"} in price (${Math.abs(pr).toFixed(0)}% of the way), not likely tonight`;
}
function bankAt(gw, moves = SB.moves) {
  let b = D.manager.bank;
  const base = new Set(D.squad.map(x => x.id)), bought = new Set();
  moves.filter(m => m.gw <= gw).forEach(m => {
    b += (base.has(m.out) && !bought.has(m.out)) ? sellPrice(m.out) : P[m.out].price;
    b -= P[m.in].price; bought.add(m.in);
  });
  return Math.round(b * 10) / 10;
}
function cleanMoves(moves) {
  const ok = [], s = D.squad.map(x => x.id);
  moves.slice().sort((a, b) => a.gw - b.gw).forEach(m => {
    if (s.includes(m.out) && !s.includes(m.in)) { ok.push(m); s[s.indexOf(m.out)] = m.in; }
  });
  return ok;
}
function sanitize() { SB.moves = cleanMoves(SB.moves); }
function ftTable(moves = SB.moves) {
  let ft = Math.min(5, D.manager.free_transfers);
  return PG.map(g => {
    const n = moves.filter(m => m.gw === g).length, hits = Math.max(0, n - ft);
    const row = { gw: g, ft, n, hits };
    ft = n > ft ? 1 : Math.min(5, ft - n + 1);
    row.next = ft;
    return row;
  });
}
function clubCounts(ids) { const c = {}; ids.forEach(i => c[P[i].team] = (c[P[i].team] || 0) + 1); return c; }
// the single scorer used by This week, Planner and Rivals
function scoreMoves(moves) {
  let tot = 0;
  const weeks = ftTable(moves).map(r => {
    const sq = squadAt(r.gw, moves), team = bestXI(sq, r.gw);
    tot += team.pts - 4 * r.hits;
    const over = Object.entries(clubCounts(sq)).filter(([, v]) => v > 3).map(([t]) => T[t].short);
    return { ...r, team, sq, bank: bankAt(r.gw, moves), over };
  });
  return { weeks, tot, ftLeft: weeks.length ? weeks[weeks.length - 1].next : 0 };
}
let _base = null;
const baseScore = () => _base || (_base = scoreMoves([]));
function sandboxSummary() {
  const sc = scoreMoves(SB.moves), base = baseScore();
  sc.weeks.forEach((w, i) => w.base = base.weeks[i].team.pts);
  return { weeks: sc.weeks, tot: sc.tot, baseTot: base.tot, ftLeft: sc.ftLeft };
}
function myTeam() {
  const g = D.meta.next_gw, sc = scoreMoves(SB.moves), w = sc.weeks[0];
  const mult = {}; w.team.xi.forEach(i => mult[i] = 1); mult[w.team.cap] = 2;
  return { ...w.team, g, mult, week: w, moves0: SB.moves.filter(m => m.gw === g), later: SB.moves.filter(m => m.gw !== g), score: sc };
}
