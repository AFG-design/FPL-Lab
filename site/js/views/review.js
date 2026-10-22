// Season review.
/* ---------- Season ---------- */
function rankChart(h) {
  const W = 640, H = 220, pad = { l: 64, r: 16, t: 14, b: 28 };
  const ranks = h.map(x => x.rank), lo = Math.log10(Math.min(...ranks)), hi = Math.log10(Math.max(...ranks)), span = Math.max(0.3, hi - lo);
  const y = r => pad.t + (Math.log10(r) - (lo - 0.05)) / (span + 0.1) * (H - pad.t - pad.b);
  const x = i => pad.l + (h.length === 1 ? 0 : i / (h.length - 1)) * (W - pad.l - pad.r);
  const ticks = [];
  for (let e = Math.floor(lo); e <= Math.ceil(hi); e++) [1, 2, 5].forEach(m => { const v = m * 10 ** e; if (Math.log10(v) >= lo - 0.05 && Math.log10(v) <= hi + 0.05) ticks.push(v); });
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Overall rank by gameweek">
    ${ticks.map(t => `<line class="grid" x1="${pad.l}" x2="${W - pad.r}" y1="${y(t)}" y2="${y(t)}"/><text x="${pad.l - 8}" y="${y(t) + 4}" text-anchor="end">${t >= 1e6 ? t / 1e6 + "m" : t >= 1e3 ? t / 1e3 + "k" : t}</text>`).join("")}
    <polyline points="${h.map((d, i) => `${x(i)},${y(d.rank)}`).join(" ")}" fill="none" class="s1" stroke-width="2.5"/>
    ${h.map((d, i) => `<circle cx="${x(i)}" cy="${y(d.rank)}" r="${i === h.length - 1 ? 5 : 3}" fill="${i === h.length - 1 ? "var(--armband)" : "var(--turf-2)"}"/><text x="${x(i)}" y="${H - 8}" text-anchor="middle">${d.gw}</text>`).join("")}</svg>`;
}
function vReview() {
  const h = D.history, L = D.live, R = D.review, mx = Math.max(...h.map(x => x.pts));
  const live = L && !L.finished ? `<div class="panel"><div class="bar"><h3>GW${L.gw} live</h3><span class="muted">${L.points} pts · average ${L.average ?? "–"}</span></div>
    <div class="tablebox"><table><thead><tr><th>Player</th><th class="n">Mins</th><th class="n">BPS</th><th class="n">Bonus</th><th class="n">Pts</th><th class="n">Counted</th></tr></thead><tbody>${L.rows.map(r => `<tr><td><span class="pname">${esc(P[r.id]?.name || r.id)}</span>${r.cap ? ' <span class="pill warn">C</span>' : r.vice ? ' <span class="pill mut">V</span>' : ""}${r.pos > 11 ? ' <span class="muted">bench</span>' : ""}</td><td class="n">${r.mins}</td><td class="n">${r.bps}</td><td class="n">${r.bonus}</td><td class="n">${r.pts}</td><td class="n"><b>${r.pts * r.mult}</b></td></tr>`).join("")}</tbody></table></div>
    <p class="note">As of the last update. Bonus is provisional until FPL confirms it.</p></div>` : "";
  if (!R || !R.weeks.length) return live + `<div class="panel"><p class="muted">Your review appears after the first gameweek finishes.</p></div>`;
  const w = R.weeks[R.weeks.length - 1], Tt = R.totals;
  const nm = id => esc(P[id]?.name || "?");
  const lines = [];
  lines.push(w.cap_lost > 0 ? ["warn", `Captain: ${nm(w.captain)} scored ${w.cap_pts}. ${nm(w.best_cap)} would have scored ${w.best_cap_pts} (−${w.cap_lost}).${w.model_cap && w.model_cap !== w.captain ? ` The model's pick was ${nm(w.model_cap)}.` : ""}`] : ["good", `Captain: ${nm(w.captain)} was the best choice in your XI (${w.cap_pts} pts).`]);
  lines.push(w.bench_pts >= 8 && w.chip !== "bboost" ? ["warn", `Bench: ${w.bench_pts} points left on the bench.`] : ["good", `Bench: only ${w.bench_pts} points left on the bench.`]);
  if (w.moves.length) { const net = w.moves.reduce((a, m) => a + m.in_pts - m.out_pts, 0) - w.hits; lines.push([net >= 0 ? "good" : "warn", `Transfers: ${w.moves.map(m => `${nm(m.out)} → ${nm(m.in)} (${m.out_pts} → ${m.in_pts})`).join(", ")}${w.hits ? `, −${w.hits} hit` : ""}. Net ${net >= 0 ? "+" : ""}${net} this week.`]); }
  else if (w.wildcard || w.freehit) lines.push(["info", `${w.wildcard ? "Wildcard" : "Free Hit"} week: ${w.n_tx} changes.`]);
  else lines.push(["info", "Transfers: none made."]);
  if (w.xi_proj != null) lines.push(["info", `Model: your starting XI was projected ${f1(w.xi_proj)} (before captain) and scored ${w.xi_actual}.`]);
  const best = R.transfers.slice().sort((a, b) => b.gain - a.gain).slice(0, 5), worst = R.transfers.slice().sort((a, b) => a.gain - b.gain).slice(0, 5);
  const txl = list => `<div class="tablebox"><table><thead><tr><th>GW</th><th>Move</th><th class="n">GWs</th><th class="n">Net</th></tr></thead><tbody>${list.map(t => `<tr><td>${t.gw}${t.wildcard ? ' <span class="tag">WC</span>' : ""}</td><td>${nm(t.out)} → ${nm(t.in)}</td><td class="n">${t.gws}</td><td class="n ${t.gain >= 0 ? "up" : "down"}">${t.gain > 0 ? "+" : ""}${t.gain}</td></tr>`).join("")}</tbody></table></div>`;
  return `${live}
  <div class="grid2">
    <div class="panel"><div class="bar"><h2>GW${w.gw} review</h2><span class="muted">${w.pts} pts${w.hits ? ` (−${w.hits})` : ""} · average ${w.avg ?? "–"} · your best possible ${w.best_possible}</span></div>
      <ul class="alerts">${lines.map(([c, t]) => `<li class="${c}"><span>${t}</span></li>`).join("")}</ul></div>
    <div class="panel"><h3>Season so far</h3>
      <div class="kpis">
        <div class="kpi"><span class="lbl">Lost to captaincy</span><b class="${Tt.cap_lost > 0 ? "down" : ""}">${Tt.cap_lost}</b><span class="delta muted">vs best captain in your XI</span></div>
        <div class="kpi"><span class="lbl">Left on bench</span><b>${Tt.bench}</b><span class="delta muted">excluding Bench Boost</span></div>
        <div class="kpi"><span class="lbl">Transfers net</span><b class="${Tt.tx_gain - Tt.hits >= 0 ? "up" : "down"}">${Tt.tx_gain - Tt.hits >= 0 ? "+" : ""}${Tt.tx_gain - Tt.hits}</b><span class="delta muted">after ${Tt.hits} pts of hits; Wildcard ${Tt.wc_gain >= 0 ? "+" : ""}${Tt.wc_gain}</span></div>
      </div><p class="note">Transfer net = points the new player scored minus what the old player would have scored, while you kept him.</p></div>
  </div>
  <div class="panel"><h3>Week by week</h3><div class="tablebox"><table><thead><tr><th>GW</th><th class="n">Pts</th><th class="n">Avg</th><th class="n">Rank</th><th>Captain</th><th class="n">Cap lost</th><th class="n">Bench</th><th class="n">Best possible</th><th class="n">Model XI</th><th>Chip</th></tr></thead>
    <tbody>${R.weeks.slice().reverse().map(x => `<tr><td>${x.gw}</td><td class="n"><b>${x.pts}</b>${x.hits ? ` <span class="down">−${x.hits}</span>` : ""}</td><td class="n">${x.avg ?? "–"}</td><td class="n">${rankFmt(x.rank)}</td><td>${nm(x.captain)} <span class="muted">${x.cap_pts}</span></td><td class="n ${x.cap_lost ? "down" : ""}">${x.cap_lost ? "−" + x.cap_lost : "0"}</td><td class="n">${x.bench_pts}</td><td class="n">${x.best_possible}</td><td class="n">${x.xi_proj != null ? `${f1(x.xi_proj)} → ${x.xi_actual}` : "–"}</td><td>${x.chip ? `<span class="tag">${({ "3xc": "TC", bboost: "BB", freehit: "FH", wildcard: "WC" })[x.chip] || x.chip}</span>` : ""}</td></tr>`).join("")}</tbody></table></div></div>
  <div class="statgrid"><div class="panel"><h3>Best transfers</h3>${txl(best)}</div><div class="panel"><h3>Worst transfers</h3>${txl(worst)}</div></div>
  <div class="grid2"><div class="panel"><h3>Overall rank</h3>${rankChart(h)}</div>
    <div class="panel"><h3>Points per gameweek</h3><div class="gwbars">${h.map(x => `<div title="GW${x.gw}: ${x.pts} pts"><span class="num" style="color:var(--fg);font-weight:600">${x.pts}</span><i style="height:${x.pts / mx * 60}px;${x.chip ? "background:var(--armband)" : ""}"></i>${x.gw}</div>`).join("")}</div>
    <p class="note">Gold bars = chip weeks.</p></div></div>`;
}
