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
/* ---------- decision score: your choices judged on what the model knew before the deadline ---------- */
function decisionPanel(R) {
  const W = R.weeks.filter(w => w.decision);
  if (!W.length) return "";
  const nm = id => esc(P[id]?.name || "?");
  const tot = W.reduce((a, w) => { const d = w.decision; a.cap += d.cap_loss; a.xi += d.lineup_loss; a.tx += d.tx_gain || 0; a.luck += d.luck; return a; }, { cap: 0, xi: 0, tx: 0, luck: 0 });
  const gp = { A: 4, B: 3, C: 2, D: 1 }, avg = W.reduce((a, w) => a + gp[w.decision.grade], 0) / W.length;
  const overall = avg >= 3.5 ? "A" : avg >= 2.5 ? "B" : avg >= 1.5 ? "C" : "D";
  const cls = g => g === "A" ? "good" : g === "B" ? "info" : g === "C" ? "warn" : "bad";
  const rows = W.slice().reverse().map(w => {
    const d = w.decision, capOk = d.cap_loss < 0.05;
    return `<tr><td>${w.gw}</td><td><span class="grade g-${d.grade}">${d.grade}</span></td>
      <td>${capOk ? `<span class="up">✓</span> ${nm(w.captain)}` : `${nm(w.captain)} <span class="muted">→ ${nm(d.model_cap)}</span>`}</td>
      <td class="n ${d.cap_loss > 0.05 ? "down" : ""}">${d.cap_loss > 0.05 ? "−" + f1(d.cap_loss) : "0"}</td>
      <td class="n ${d.lineup_loss > 0.05 ? "down" : ""}">${d.lineup_loss > 0.05 ? "−" + f1(d.lineup_loss) : "0"}</td>
      <td class="n ${d.tx_gain == null ? "" : d.tx_gain >= 0 ? "up" : "down"}">${d.tx_gain == null ? '<span class="muted">–</span>' : sgn(d.tx_gain)}</td>
      <td class="n">${f1(d.proj)}${d.src === "rerun" ? '<sup class="muted" title="Re-run with the current model">*</sup>' : ""} → <b>${w.pts}</b></td><td class="n ${d.luck >= 0 ? "up" : "down"}">${sgn(d.luck)}</td></tr>`;
  }).join("");
  return `<div class="panel"><div class="bar"><h3>${term("decision", "Decision score")}</h3><span class="grade big g-${overall}" aria-label="Season grade ${overall}">${overall}</span></div>
    <p class="note" style="margin-top:0">Each gameweek's choices judged on the projections available <i>before</i> the deadline, not on what happened. A bad week can still be a good decision.</p>
    <div class="kpis" style="margin-bottom:12px">
      <div class="kpi"><span class="lbl">Captain choices</span><b class="${tot.cap > 0.05 ? "down" : ""}">${tot.cap > 0.05 ? "−" + f1(tot.cap) : "0.0"}</b><span class="delta muted">xP given up vs the model's captain</span></div>
      <div class="kpi"><span class="lbl">Starting XI</span><b class="${tot.xi > 0.05 ? "down" : ""}">${tot.xi > 0.05 ? "−" + f1(tot.xi) : "0.0"}</b><span class="delta muted">xP left on the bench by your picks</span></div>
      <div class="kpi"><span class="lbl">Transfers</span><b class="${tot.tx >= 0 ? "up" : "down"}">${sgn(tot.tx)}</b><span class="delta muted">projected gain over 3 GWs, after hits</span></div>
      <div class="kpi"><span class="lbl">${term("luck", "Luck")}</span><b class="${tot.luck >= 0 ? "up" : "down"}">${sgn(tot.luck)}</b><span class="delta muted">points scored vs projected</span></div>
    </div>
    <div class="tablebox"><table><thead><tr><th>GW</th><th>Grade</th><th>Captain <span class="muted">→ model</span></th><th class="n">Cap</th><th class="n">XI</th><th class="n">Moves</th><th class="n">Proj → actual</th><th class="n">Luck</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="note">A = within half a point of the model's best choices; B within 1.5; C within 3; D more. Starts from GW3, when the model has enough data.${W.some(w => w.decision.src === "rerun") ? " * No projection was saved before this deadline, so the week is re-run with the current model." : ""}</p></div>`;
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
  if (w.xi_proj != null) lines.push(["info", `Model: your starting XI was ${w.proj_src === "rerun" ? "projected (re-run with the current model)" : "projected before the deadline"} ${f1(w.xi_proj)} (before captain) and scored ${w.xi_actual}.`]);
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
  ${pastTeamPanel(R)}
  ${decisionPanel(R)}
  ${templatePanel()}
  <div class="panel"><h3>Week by week</h3><div class="tablebox"><table><thead><tr><th>GW</th><th class="n">Pts</th><th class="n">Avg</th><th class="n">Rank</th><th>Captain</th><th class="n">Cap lost</th><th class="n">Bench</th><th class="n">Best possible</th><th class="n">Model XI</th><th>Chip</th></tr></thead>
    <tbody>${R.weeks.slice().reverse().map(x => `<tr><td>${x.gw}</td><td class="n"><b>${x.pts}</b>${x.hits ? ` <span class="down">−${x.hits}</span>` : ""}</td><td class="n">${x.avg ?? "–"}</td><td class="n">${rankFmt(x.rank)}</td><td>${nm(x.captain)} <span class="muted">${x.cap_pts}</span></td><td class="n ${x.cap_lost ? "down" : ""}">${x.cap_lost ? "−" + x.cap_lost : "0"}</td><td class="n">${x.bench_pts}</td><td class="n">${x.best_possible}</td><td class="n">${x.xi_proj != null ? `${f1(x.xi_proj)} → ${x.xi_actual}` : "–"}</td><td>${x.chip ? `<span class="tag">${({ "3xc": "TC", bboost: "BB", freehit: "FH", wildcard: "WC" })[x.chip] || x.chip}</span>` : ""}</td></tr>`).join("")}</tbody></table></div></div>
  <div class="statgrid"><div class="panel"><h3>Best transfers</h3>${txl(best)}</div><div class="panel"><h3>Worst transfers</h3>${txl(worst)}</div></div>
  <div class="grid2"><div class="panel"><h3>Overall rank</h3>${rankChart(h)}</div>
    <div class="panel"><h3>Points per gameweek</h3><div class="gwbars">${h.map(x => `<div title="GW${x.gw}: ${x.pts} pts"><span class="num" style="color:var(--fg);font-weight:600">${x.pts}</span><i style="height:${x.pts / mx * 60}px;${x.chip ? "background:var(--armband)" : ""}"></i>${x.gw}</div>`).join("")}</div>
    <p class="note">Gold bars = chip weeks.</p></div></div>`;
}

/* ---------- your team in any past gameweek: real points on the pitch, with the projection made before it ---------- */
function pastTeamPanel(R) {
  const W = R.weeks.filter(w => w.team); if (!W.length) return "";
  if (!W.some(w => w.gw === S.revGw)) S.revGw = W[W.length - 1].gw;
  const w = W.find(x => x.gw === S.revGw);
  const subIn = new Set(w.autosubs.map(a => a[0])), subOut = new Set(w.autosubs.map(a => a[1]));
  const pre = w.proj_src !== "rerun", projLbl = pre ? "Projected before the deadline" : "Re-run with the current model";
  const card = ([id, slot, mult, pts, mins, xp]) => { const p = P[id]; if (!p) return "";
    const capB = mult >= 2 ? `<span class="badge" aria-hidden="true">${mult === 3 ? "TC" : "C"}</span>` : "";
    const sc = mult ? pts * mult : pts, tag = subIn.has(id) ? '<span class="subtag in">▲ sub on</span>' : subOut.has(id) ? '<span class="subtag out">▼ sub off</span>' : "";
    const label = `${p.name}: ${pts} points${mult >= 2 ? ` (×${mult} as captain)` : ""}, ${mins} minutes${xp != null ? `, ${pre ? "projected" : "re-run projection"} ${xp}` : ""}`;
    return `<button class="pc past ${sc >= 10 ? "haul" : ""}" data-p="${id}" aria-label="${esc(label)}">${capB}
      <img class="shirt" src="${shirtURL(p)}" srcset="${shirtSet(p)}" sizes="30px" alt="" loading="lazy" onerror="this.remove()">
      <span class="nm">${esc(p.name)}</span><span class="xp">${sc}</span>
      <span class="pc-meta"><span>${mins}'</span>${xp != null ? `<span title="${projLbl}">xP ${xp.toFixed(1)}</span>` : ""}</span>${tag}</button>`; };
  const xi = w.team.filter(t => t[1] <= 11), bench = w.team.filter(t => t[1] > 11);
  const rows = ["GKP", "DEF", "MID", "FWD"].map(pos => `<div class="row">${xi.filter(t => P[t[0]]?.pos === pos).map(card).join("")}</div>`).join("");
  const proj = w.team.every(t => t[5] != null) ? xi.reduce((a, t) => a + t[5] * Math.max(1, t[2]), 0) : null;
  const chip = w.chip ? ({ "3xc": "Triple Captain", bboost: "Bench Boost", freehit: "Free Hit", wildcard: "Wildcard" })[w.chip] || w.chip : "";
  return `<div class="panel"><div class="bar"><h3>Your team by gameweek</h3>
      <div class="seg" role="group" aria-label="Gameweek">${W.map(x => `<button data-revgw="${x.gw}" aria-pressed="${x.gw === w.gw}">GW${x.gw}</button>`).join("")}</div></div>
    <p class="note" style="margin-top:0"><b>${w.pts} pts</b>${w.hits ? ` (−${w.hits} hit)` : ""} · average ${w.avg ?? "–"} · rank ${rankFmt(w.rank)}${chip ? ` · ${chip}` : ""}${proj != null ? ` · ${projLbl.toLowerCase()}: ${f1(proj)}` : ""}${w.decision ? ` · decision grade <span class="grade g-${w.decision.grade}">${w.decision.grade}</span>` : ""}</p>
    <div class="pitchwrap"><div class="pitch" role="group" aria-label="Starting XI, GW${w.gw}">${rows}</div><div class="bench" role="group" aria-label="Bench"><span class="lbl">Bench</span>${bench.map(card).join("")}</div>
      <div class="pitch-key"><span>Big number: points scored (doubled for the captain)</span><span>Then minutes and ${pre ? "the projection made before that deadline" : "the projection re-run with the current model (none was saved before this deadline)"}</span></div></div>
    ${w.moves.length ? `<p class="note">Transfers that week: ${w.moves.map(m => `${esc(P[m.out]?.name || "?")} → ${esc(P[m.in]?.name || "?")}`).join(", ")}.</p>` : ""}</div>`;
}

/* ---------- template tracker: your team against the top-10k template ---------- */
function templatePanel() {
  const TT = D.template; if (!TT || !TT.length) return "";
  const nm = id => `<button data-p="${id}" class="linkish">${esc(P[id]?.name || "?")}</button>`;
  const tot = TT.reduce((a, t) => a + t.net, 0), back = TT.filter(t => t.source === "backfill").map(t => t.gw);
  const rows = TT.slice().reverse().map(t => `<tr><td>GW${t.gw}${t.source === "backfill" ? '<sup title="Rebuilt from managers in the top 10k now">*</sup>' : ""}</td>
    <td class="n"><span class="minibar" style="width:${(t.overlap * 0.5).toFixed(0)}px"></span> ${Math.round(t.overlap)}%</td><td class="n">${t.shared}/${t.tpl_size}</td>
    <td>${t.missing.length ? t.missing.slice(0, 3).map(([i, o, pt]) => `${nm(i)} <span class="muted">${o}% · ${pt} pts</span>`).join(", ") : '<span class="muted">none</span>'}</td>
    <td>${t.diffs.length ? t.diffs.slice(0, 3).map(([i, o, pt]) => `${nm(i)} <span class="muted">${o}% · ${pt} pts</span>`).join(", ") : '<span class="muted">none</span>'}</td>
    <td class="n ${t.net >= 0 ? "up" : "down"}"><b>${sgn(t.net)}</b></td></tr>`).join("");
  const lastT = TT[TT.length - 1];
  return `<div class="panel"><div class="bar"><h3>Template tracker</h3><span class="${tot >= 0 ? "up" : "down"}"><b>${sgn(tot)}</b> vs the top 10k so far</span></div>
    <p class="note" style="margin-top:0">How your team lined up against what the top 10,000 owned each week. <b>Overlap</b> = average top-10k ownership of your starting XI. <b>Template</b> = how many of the players owned by 40%+ of them you had. The last column is the points your ownership differences won or lost you against the top-10k average that week (captains counted twice, hits and transfers not included).</p>
    <div class="kpis" style="margin-bottom:12px">
      <div class="kpi"><span class="lbl">Overlap GW${lastT.gw}</span><b>${Math.round(lastT.overlap)}%</b><span class="delta muted">${lastT.overlap > 60 ? "very template" : lastT.overlap > 45 ? "fairly template" : "lots of differentials"}</span></div>
      <div class="kpi"><span class="lbl">Won where you owned more</span><b class="up">${sgn(TT.reduce((a, t) => a + t.gain, 0))}</b><span class="delta muted">incl. captaining players they didn't</span></div>
      <div class="kpi"><span class="lbl">Lost where they owned more</span><b class="down">${sgn(TT.reduce((a, t) => a + t.loss, 0))}</b><span class="delta muted">incl. their popular captains</span></div>
    </div>
    <div class="tablebox"><table><thead><tr><th>GW</th><th class="n">Overlap</th><th class="n">Template</th><th>Template players you didn't have</th><th>Your differentials (&lt;15% owned)</th><th class="n">vs top 10k</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${back.length ? `<p class="note">* GW${back[0]}${back.length > 1 ? `–${back[back.length - 1]}` : ""} rebuilt from 500 managers who are in the top 10k now, so they flatter the picks that worked. Later weeks use the real sample of 2,000 taken after each deadline.</p>` : ""}</div>`;
}
