// Squad rating: your 15 against the best squad for the same money and the average top-10k team.
const RATE = { key: "", res: null };
// The 0-100 scale, shared by Home's Squad rating and FPL School so the two always agree.
// 50 = the top-10k average, 100 = the best 15 for the money. Below 50 the scale has its own floor: 0 = 30% fewer
// projected points than the top-10k average (RATING_FLOOR). It used to fall at the same rate as the 50-100 half,
// which is set by the (often small) gap between the field and the best squad, so a team a couple of points a week
// behind the field could score close to 0.
// Missing inputs: no top-10k figure (crowd file not saved) -> 100 = the best squad, 0 = no points (as before); no best
// squad yet (FPL School still solving) and ahead of the field -> 50 x your points / the field's (as before).
const RATING_FLOOR = 0.7;
function ratingScore(mine, field, best) {
  let s = null;
  if (field != null && field > 0 && mine <= field) s = 50 * (mine - RATING_FLOOR * field) / ((1 - RATING_FLOOR) * field);
  else if (field != null && best != null && best > field) s = 50 + 50 * (mine - field) / (best - field);
  else if (best) s = 100 * mine / best;
  else if (field) s = 50 * mine / field;
  return s == null ? null : Math.max(0, Math.min(100, Math.round(s)));
}
function ratingWord(s) { return s >= 85 ? "Excellent" : s >= 65 ? "Strong" : s >= 50 ? "Above average" : s >= 35 ? "Below average" : "Needs work"; }
function squadRatingData() {
  const R = D.rating; if (!R || !D.squad.length) return null;
  const key = D.meta.built + "|" + S.mode + "|" + mvKey(SB.moves); if (RATE.key === key) return RATE.res;
  const ids = D.squad.map(s => s.id), gws = R.gws.filter(g => GWS.includes(g));
  const pts = sq => gws.reduce((a, g) => a + bestXI(sq, g, null).pts, 0);
  const mine = pts(ids), best = R.best.weeks.reduce((a, b) => a + b, 0), field = R.field ? R.field.reduce((a, b) => a + b, 0) : null;
  const toScore = v => ratingScore(v, field, best);
  const score = toScore(mine);
  // Uplift (K1): the same squad after Your plan's moves, scored the same way (best XI + captain each week, no lineup
  // choices of yours, so it compares like with like), minus 4 a hit. Hits follow FPL's free-transfer rule from your
  // real free transfers. Moves outside the rating's weeks don't count. No moves: the same number, said as such.
  const mv = SB.moves.filter(m => gws.includes(m.gw));
  let ft = Math.min(5, D.manager.free_transfers), hits = 0;
  const afterPts = gws.reduce((a, g) => {
    const n = mv.filter(m => m.gw === g).length, h = Math.max(0, n - ft);
    hits += h; ft = n > ft ? 1 : Math.min(5, ft - n + 1);
    return a + bestXI(squadAt(g, mv), g, null).pts - 4 * h;
  }, 0);
  const plan = { name: planName(), moves: mv, hits, pts: afterPts, score: toScore(afterPts) };
  const x5 = i => gws.reduce((a, g) => a + xpg(i, g), 0);
  const K = { GKP: 1, DEF: 4, MID: 4, FWD: 2 }, NAME = { GKP: "Goalkeepers", DEF: "Defence", MID: "Midfield", FWD: "Attack" };
  const top = (list, pos) => list.filter(i => P[i]?.pos === pos).map(x5).sort((a, b) => b - a).slice(0, K[pos]).reduce((a, b) => a + b, 0);
  const pos = Object.keys(K).map(k => { const a = top(ids, k), b = top(R.best.squad, k), pct = b ? a / b : 1;
    return { k, name: NAME[k], pct, grade: pct >= 0.95 ? "A" : pct >= 0.85 ? "B" : pct >= 0.75 ? "C" : "D" }; });
  // weakest links: the single transfer that adds most to your squad's best XI + captain over the same weeks
  const bank = D.manager.bank, base = mine;
  const links = ids.map(out => {
    const po = P[out]; if (!po) return null;
    const budget = bank + sellPrice(out), cc = clubCounts(ids.filter(i => i !== out));
    const cands = D.players.filter(p => p.pos === po.pos && !ids.includes(p.id) && p.ok !== false && p.price <= budget + 1e-9 && (cc[p.team] || 0) < 3)
      .sort((a, b) => x5(b.id) - x5(a.id)).slice(0, 12);
    let bestIn = null, gain = 0;
    cands.forEach(p => { const v = pts(ids.map(i => i === out ? p.id : i)) - base; if (v > gain) { gain = v; bestIn = p.id; } });
    return bestIn ? { out, in: bestIn, gain } : null;
  }).filter(Boolean).sort((a, b) => b.gain - a.gain).filter((l, k, arr) => arr.findIndex(x => x.in === l.in) === k).slice(0, 3);
  const own = D.crowd?.top10k?.own, xi0 = bestXI(ids, gws[0], null).xi;
  const tmpl = own ? xi0.reduce((a, i) => a + (own[i] || 0), 0) / xi0.length : null;
  RATE.key = key; RATE.res = { score, mine, best, field, gws, pos, links, tmpl, budget: R.budget, plan };
  return RATE.res;
}
function squadRatingPanel() {
  const r = squadRatingData(); if (!r) return "";
  const word = ratingWord(r.score);
  const n = i => esc(P[i]?.name || "?");
  return `<div class="panel rating"><div class="bar"><h3>${term("rating", "Squad rating")}</h3><span class="muted">GW${r.gws[0]}–${r.gws[r.gws.length - 1]}, no transfers</span></div>
    <div class="rate-top">
      <div class="rate-badge" role="img" aria-label="Squad rating ${r.score} out of 100, ${word}"><div class="rate-score" style="--p:${r.score}"><b>${r.score}</b><span>/100</span></div><small>${word}</small></div>
      <div class="kpis">
        <div class="kpi"><span class="lbl">Your squad</span><b>${f1(r.mine)}</b><span class="delta muted">projected points</span></div>
        ${r.field != null ? `<div class="kpi"><span class="lbl">Top-10k average</span><b>${f1(r.field)}</b><span class="delta ${r.mine >= r.field ? "up" : "down"}">you're ${f1(Math.abs(r.mine - r.field))} ${r.mine >= r.field ? "ahead" : "behind"}</span></div>` : ""}
        <div class="kpi"><span class="lbl">Best for ${money(r.budget)}</span><b>${f1(r.best)}</b><span class="delta muted">${f1(r.best - r.mine)} more than yours</span></div>
        <div class="kpi"><span class="lbl">With ${esc(r.plan.name)}</span><b>${r.plan.score}<small>/100</small></b><span class="delta ${r.plan.pts - r.mine > 0.05 ? "up" : "muted"}">${r.plan.moves.length
          ? `${sgn(r.plan.pts - r.mine)} pts${r.plan.hits ? ` after ${r.plan.hits} hit${r.plan.hits > 1 ? "s" : ""}` : ""}`
          : "no moves planned"}</span></div>
      </div>
    </div>
    ${r.plan.moves.length ? `<p class="rate-uplift"><span class="lbl">${r.score} → ${r.plan.score} with ${esc(r.plan.name)}</span> ${r.plan.moves.map(m => `<span class="rl-move">GW${m.gw}: <button data-p="${m.out}" class="linkish">${n(m.out)}</button> <span class="muted">→</span> <button data-p="${m.in}" class="linkish">${n(m.in)}</button></span>`).join(" · ")}</p>` : ""}
    <div class="rate-pos">${r.pos.map(p => `<div><span class="grade g-${p.grade}">${p.grade}</span><span><b>${p.name}</b><small>${Math.round(p.pct * 100)}% of the best</small></span></div>`).join("")}</div>
    ${r.links.length ? `<span class="lbl">Weakest links</span><ul class="rate-links">${r.links.map(l => `<li><span class="rl-move"><button data-p="${l.out}" class="pname linkish">${n(l.out)}</button> <span class="muted">→</span> <button data-p="${l.in}" class="linkish">${n(l.in)}</button> <span class="muted">${money(P[l.in].price)}</span></span><span class="rl-gain up">+${f1(l.gain)}<small> over ${r.gws.length} GWs</small></span><button class="btn sm" data-rateplan="${l.out}:${l.in}">Add to plan</button></li>`).join("")}</ul>` : ""}
    <p class="note">50 = the average top-10k team (from their last published teams), 100 = the best 15 you could buy for the same money and hold for these weeks, 0 = 30% fewer projected points than the top-10k average. Best XI and captain each week. "With ${esc(r.plan.name)}" scores the squad after its moves the same way, minus 4 a hit.${r.tmpl != null ? ` Your XI's average top-10k ownership is ${r.tmpl.toFixed(0)}%${r.tmpl > 55 ? ": quite template" : r.tmpl < 30 ? ": lots of differentials" : ""}.` : ""}</p></div>`;
}
