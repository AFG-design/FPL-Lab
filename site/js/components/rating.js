// Squad rating: your 15 against the best squad for the same money and the average top-10k team.
const RATE = { key: "", res: null };
function squadRatingData() {
  const R = D.rating; if (!R || !D.squad.length) return null;
  const key = D.meta.built + "|" + S.mode; if (RATE.key === key) return RATE.res;
  const ids = D.squad.map(s => s.id), gws = R.gws.filter(g => GWS.includes(g));
  const pts = sq => gws.reduce((a, g) => a + bestXI(sq, g, null).pts, 0);
  const mine = pts(ids), best = R.best.weeks.reduce((a, b) => a + b, 0), field = R.field ? R.field.reduce((a, b) => a + b, 0) : null;
  const score = Math.max(0, Math.min(100, Math.round(field != null && best > field ? 50 + 50 * (mine - field) / (best - field) : 100 * mine / best)));
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
  RATE.key = key; RATE.res = { score, mine, best, field, gws, pos, links, tmpl, budget: R.budget };
  return RATE.res;
}
function squadRatingPanel() {
  const r = squadRatingData(); if (!r) return "";
  const word = r.score >= 85 ? "Excellent" : r.score >= 65 ? "Strong" : r.score >= 50 ? "Above average" : r.score >= 35 ? "Below average" : "Needs work";
  const n = i => esc(P[i]?.name || "?");
  return `<div class="panel rating"><div class="bar"><h3>${term("rating", "Squad rating")}</h3><span class="muted">GW${r.gws[0]}–${r.gws[r.gws.length - 1]}, no transfers</span></div>
    <div class="rate-top">
      <div class="rate-badge" role="img" aria-label="Squad rating ${r.score} out of 100, ${word}"><div class="rate-score" style="--p:${r.score}"><b>${r.score}</b><span>/100</span></div><small>${word}</small></div>
      <div class="kpis">
        <div class="kpi"><span class="lbl">Your squad</span><b>${f1(r.mine)}</b><span class="delta muted">projected points</span></div>
        ${r.field != null ? `<div class="kpi"><span class="lbl">Top-10k average</span><b>${f1(r.field)}</b><span class="delta ${r.mine >= r.field ? "up" : "down"}">you're ${f1(Math.abs(r.mine - r.field))} ${r.mine >= r.field ? "ahead" : "behind"}</span></div>` : ""}
        <div class="kpi"><span class="lbl">Best for ${money(r.budget)}</span><b>${f1(r.best)}</b><span class="delta muted">${f1(r.best - r.mine)} more than yours</span></div>
      </div>
    </div>
    <div class="rate-pos">${r.pos.map(p => `<div><span class="grade g-${p.grade}">${p.grade}</span><span><b>${p.name}</b><small>${Math.round(p.pct * 100)}% of the best</small></span></div>`).join("")}</div>
    ${r.links.length ? `<span class="lbl">Weakest links</span><ul class="rate-links">${r.links.map(l => `<li><span class="rl-move"><button data-p="${l.out}" class="pname linkish">${n(l.out)}</button> <span class="muted">→</span> <button data-p="${l.in}" class="linkish">${n(l.in)}</button> <span class="muted">${money(P[l.in].price)}</span></span><span class="rl-gain up">+${f1(l.gain)}<small> over ${r.gws.length} GWs</small></span><button class="btn sm" data-rateplan="${l.out}:${l.in}">Add to plan</button></li>`).join("")}</ul>` : ""}
    <p class="note">50 = the average top-10k team (from their last published teams), 100 = the best 15 you could buy for the same money and hold for these weeks. Best XI and captain each week.${r.tmpl != null ? ` Your XI's average top-10k ownership is ${r.tmpl.toFixed(0)}%${r.tmpl > 55 ? ": quite template" : r.tmpl < 30 ? ": lots of differentials" : ""}.` : ""}</p></div>`;
}
