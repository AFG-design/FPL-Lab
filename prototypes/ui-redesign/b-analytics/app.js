// Concept B: Premium Analytics. Prototype only; reads the sample snapshot through window.PROTO, writes nothing.
(function () {
  const X = window.PROTO, { S, P, G, esc, money, num, rank, icon } = X;
  X.theme();
  const $ = s => document.querySelector(s);
  const TABS = [["home", "Matchday"], ["planner", "Planner"], ["players", "Players"], ["fixtures", "Fixtures"], ["rivals", "Rivals"], ["chips", "Chips"], ["model", "Model"]];
  const SER = { balanced: "var(--s1)", safe: "var(--s2)", chase: "var(--s3)" };
  const fdrChip = (team, gw) => { const l = X.fx(team, gw); return l.length ? l.map(f => `<span class="fdr fdr-${f.fdr}">${f.opp} ${f.home ? "H" : "A"}</span>`).join(" ") : `<span class="fdr fdr-3">Blank</span>`; };
  const heat = v => `h${Math.max(1, Math.min(5, Math.round((v - 2) / 0.7)))}`;
  const pn = p => `<span class="pn"><img src="${X.badge(p.team)}" alt=""><b>${esc(p.name)}</b></span>`;
  let sel = 411;

  /* ---------- chrome ---------- */
  function chrome(v) {
    $("#tabs").innerHTML = TABS.map(([k, l]) => `<button data-v="${k}" aria-current="${k === v ? "page" : "false"}">${l}</button>`).join("");
    const cd = X.countdown();
    $("#appbarR").innerHTML = `<div class="cmdk">${icon("search")}<span>Search players, teams…</span><kbd>/</kbd></div><div class="dl"><b>${cd.text}</b><span>GW${G} deadline</span></div>`;
    const m = S.manager, h = S.history, mv = h[h.length - 2].rank - h[h.length - 1].rank;
    $("#ribbon").innerHTML = `
      <div class="kpi"><div class="lbl">Team · GW${S.meta.picks_gw} squad</div><div class="team">${esc(m.team)}</div></div>
      <div class="kpi"><div class="lbl">Overall rank</div><div class="v">${rank(m.rank)} <small class="up">▲ ${X.short(mv)}</small></div></div>
      <div class="kpi"><div class="lbl">Points</div><div class="v">${m.points} <small>GW${S.meta.picks_gw} ${m.gw_points}</small></div></div>
      <div class="kpi"><div class="lbl">Bank · FT</div><div class="v">${money(m.bank)} <small>${m.free_transfers} FT</small></div></div>
      <div class="kpi hide-sm"><div class="lbl">Squad value</div><div class="v">${money(m.value)}</div></div>
      <div class="kpi wide"><div class="lbl">Overall rank by gameweek (log scale, higher is better)</div>${rankSpark()}</div>`;
  }
  function rankSpark() {
    const h = S.history, W = 300, H = 40, lo = Math.log10(Math.min(...h.map(x => x.rank))), hi = Math.log10(Math.max(...h.map(x => x.rank)));
    const pts = h.map((x, i) => [i / (h.length - 1) * W, 4 + (Math.log10(x.rank) - lo) / (hi - lo) * (H - 8)]);
    const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join("");
    const last = pts[pts.length - 1];
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Overall rank from ${rank(h[0].rank)} in GW1 to ${rank(h[h.length - 1].rank)} in GW${h.length}">
      <path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
      ${h.map((x, i) => `<circle cx="${pts[i][0]}" cy="${pts[i][1]}" r="${i === h.length - 1 ? 3 : 0}" fill="var(--accent)"><title>GW${x.gw}: ${rank(x.rank)}</title></circle>`).join("")}
      <circle cx="${last[0]}" cy="${last[1]}" r="3" fill="var(--accent)"/></svg>`;
  }

  /* ---------- matchday ---------- */
  function home() {
    const sq = X.squad(), caps = X.captains(), ss = X.strategies(), bal = ss[0];
    const margin = (gap, max) => `<span class="margin"><i style="--w:${Math.min(100, gap / max * 100)}%"></i>${gap < 1 ? "Close call" : "Clear"} · ${num(gap)}</span>`;
    const board = `<table class="board"><tbody>
      <tr><td class="k lbl">Transfers</td><td><div class="lbl kin">Transfers</div><div class="call">Roll · start GW${G + 1} with 4 FT</div><div class="why">No GW${G} move clears the 1-point profit rule; banking funds ${bal.moves[0].pairs.length} moves next week.</div></td><td class="ev"><b>+${num(bal.gain)}</b><span class="muted">xP · 5 GWs</span></td></tr>
      <tr><td class="k lbl">Captain</td><td><div class="lbl kin">Captain</div><div class="call"><em>${esc(caps[0].name)}</em> <span class="muted" style="font-weight:500">vs ${X.fxLabel(caps[0].team, G)}</span></div><div class="why">Vice ${esc(caps[1].name)} ${num(caps[1].cxp)}. ${margin(caps[0].cxp - caps[1].cxp, 3)}</div></td><td class="ev"><b>${num(caps[0].cxp)}</b><span class="muted">captain xP</span></td></tr>
      <tr><td class="k lbl">Lineup</td><td><div class="lbl kin">Lineup</div><div class="call">Gibbs-White in, Calvert-Lewin benched</div><div class="why">${margin(0.1, 3)} xP between them</div></td><td class="ev"><b>${num(sq.xp)}</b><span class="muted">team xP</span></td></tr>
      <tr><td class="k lbl">Chips</td><td><div class="lbl kin">Chips</div><div class="call">Hold all chips</div><div class="why">Triple Captain best value GW${S.gws[3]}; Wildcard 2 from GW20.</div></td><td class="ev"><b>3</b><span class="muted">left this half</span></td></tr>
    </tbody></table>`;
    const xi = [...sq.xi, ...sq.bench.map(p => ({ ...p, bench: true }))];
    const squadT = `<div class="scroll"><table class="tbl"><thead><tr><th class="l">Player</th><th class="l">GW${G}</th><th>Start</th><th>xP GW${G}</th>${S.gws.slice(1).map(g => `<th class="hide-sm">GW${g}</th>`).join("")}<th>5 GW</th></tr></thead><tbody>
      ${xi.map(p => `<tr data-p="${p.id}" ${p.bench ? 'style="opacity:.62"' : ""}><td class="l"><span class="pos">${p.bench ? "SUB" : p.pos}</span>${pn(p)}${p.cap ? '<span class="cap">C</span>' : p.vice ? '<span class="cap v">V</span>' : ""}</td><td class="l">${fdrChip(p.team, G)}</td><td>${X.pct(p.start)}</td><td><span class="bar"><i style="--w:${X.xp(p.id) / 6 * 100}%"></i><b>${num(X.xp(p.id))}</b></span></td>${S.gws.slice(1).map(g => `<td class="hide-sm heat ${heat(p.xp[g])}">${num(p.xp[g])}</td>`).join("")}<td><b>${num(p.xp5)}</b></td></tr>`).join("")}
    </tbody></table></div>`;
    return `<div class="grid">
      <section class="panel c7"><div class="ph"><h2>Decision board · GW${G}</h2><div class="r"><span class="lbl">Balanced strategy</span></div></div>${board}</section>
      <section class="panel c5"><div class="ph"><h2>Strategy outlook</h2><div class="r"><span class="lbl">Team xP per GW</span></div></div><div class="pb">${stratChart(ss)}
        <div class="legend" style="margin-top:10px">${ss.map(s => `<span><i style="background:${SER[s.key]}"></i>${s.name} <b>+${num(s.gain)}</b></span>`).join("")}<span class="muted">xP vs no moves, 5 GWs</span></div></div></section>
      <section class="panel c12"><div class="ph"><h2>Squad projection</h2><div class="r"><div class="seg"><button aria-pressed="true">Table</button><button aria-pressed="false">Pitch</button></div></div></div>${squadT}</section>
    </div>`;
  }
  function stratChart(ss, W = 520) {
    const H = W > 600 ? 240 : 190, L = 34, R = 80, T = 10, B = 24, all = ss.flatMap(s => s.weeks.map(w => w.xp)), lo = Math.floor(Math.min(...all) - 1), hi = Math.ceil(Math.max(...all) + 1);
    const x = i => L + i * (W - L - R) / 4, y = v => T + (hi - v) / (hi - lo) * (H - T - B);
    const ticks = [lo, Math.round((lo + hi) / 2), hi];
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Projected team xP per gameweek for each strategy">
      <g class="grid">${ticks.map(t => `<line x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/><text x="${L - 8}" y="${y(t) + 3}" text-anchor="end">${t}</text>`).join("")}</g>
      ${S.gws.map((g, i) => `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">GW${g}</text>`).join("")}
      ${ss.map(s => `<path d="${s.weeks.map((w, i) => `${i ? "L" : "M"}${x(i)} ${y(w.xp)}`).join("")}" fill="none" stroke="${SER[s.key]}" stroke-width="2" stroke-linejoin="round"/>
        ${s.weeks.map((w, i) => `<circle cx="${x(i)}" cy="${y(w.xp)}" r="4" fill="${SER[s.key]}" stroke="var(--panel)" stroke-width="2"><title>${s.name}, GW${w.gw}: ${num(w.xp)} xP${w.in.length ? `, ${w.in.length} moves` : ""}</title></circle>`).join("")}`).join("")}
      ${endLabels(ss.map(s => ({ t: s.name, y: y(s.weeks[4].xp) + 4 }))).map(l => `<text class="lbl-d" x="${x(4) + 10}" y="${l.y}">${l.t}</text>`).join("")}
    </svg>`;
  }

  // direct labels at the line ends, nudged apart so they never overlap (min 13px between baselines)
  function endLabels(ls) {
    ls.sort((a, b) => a.y - b.y);
    for (let i = 1; i < ls.length; i++) if (ls[i].y - ls[i - 1].y < 13) ls[i].y = ls[i - 1].y + 13;
    return ls;
  }

  /* ---------- players: master-detail ---------- */
  function players() {
    const list = X.players({ limit: 30 });
    const tbl = `<div class="scroll"><table class="tbl"><thead><tr><th class="l">Player</th><th>£m</th><th class="hide-sm">Own</th><th class="hide-sm">Start</th><th class="hide-sm">xGI/90 L4</th>${S.gws.map((g, i) => `<th class="${i > 1 ? "hide-sm" : ""}">GW${g}</th>`).join("")}<th>5 GW ↓</th></tr></thead><tbody>
      ${list.map(p => `<tr data-p="${p.id}" class="${p.id === sel ? "sel" : ""}"><td class="l"><span class="pos">${p.pos}</span>${pn(p)}${X.inSquad(p.id) ? '<span class="cap v" title="In your squad">✓</span>' : ""}${p.status !== "a" ? `<span class="flag">⚑ ${p.chance ?? "?"}%</span>` : ""}</td><td>${num(p.price)}</td><td class="hide-sm">${num(p.own)}%</td><td class="hide-sm">${X.pct(p.start)}</td><td class="hide-sm">${num(p.xgi90_4, 2)}</td>${S.gws.map((g, i) => `<td class="heat ${heat(p.xp[g])} ${i > 1 ? "hide-sm" : ""}">${num(p.xp[g])}</td>`).join("")}<td><b>${num(p.xp5)}</b></td></tr>`).join("")}
    </tbody></table></div>`;
    return `<div class="grid">
      <section class="panel c8"><div class="ph"><h2>Players</h2><div class="r"><div class="seg">${["All", "GKP", "DEF", "MID", "FWD"].map((p, i) => `<button aria-pressed="${!i}">${p}</button>`).join("")}</div><button class="btn">${icon("filter")}Filters · 0</button></div></div>
        <div class="pb" style="padding-bottom:0"><span class="muted">472 players · cells are xP per gameweek, shaded low → high · ✓ in your squad</span></div>${tbl}</section>
      <section class="panel c4 detail" id="detail">${detail(sel)}</section></div>`;
  }
  function detail(id) {
    const p = P[id], [p10, p6, blank, q10, q90] = p.dist || [], max = 15;
    const vals = S.gws.map(g => p.xp[g] ?? 0), vmax = Math.max(...vals) * 1.15;
    const W = 300, H = 120;
    const bars = `<svg class="chart" viewBox="0 0 ${W} ${H + 36}" role="img" aria-label="xP by gameweek">${vals.map((v, i) => { const bw = 40, x = 10 + i * 58, h = v / vmax * H; const f = X.fx(p.team, S.gws[i])[0];
      return `<rect x="${x}" y="${H - h}" width="${bw}" height="${h}" rx="4" fill="var(--accent)"><title>GW${S.gws[i]}: ${num(v)} xP</title></rect><text class="lbl-d" x="${x + bw / 2}" y="${H - h - 6}" text-anchor="middle">${num(v)}</text><text x="${x + bw / 2}" y="${H + 14}" text-anchor="middle">GW${S.gws[i]}</text><text x="${x + bw / 2}" y="${H + 28}" text-anchor="middle">${f ? `${f.opp} ${f.home ? "H" : "A"}` : "–"}</text>`; }).join("")}</svg>`;
    return `<div class="ph"><h2>Player</h2><div class="r"><button class="btn">Compare</button><button class="btn primary">Add to plan</button></div></div><div class="pb">
      <div class="hero"><img src="${X.badge(p.team)}" alt=""><div><div class="lbl">${X.T[p.team].name} · ${p.pos} · ${money(p.price)}</div><h3>${esc(p.name)}</h3></div></div>
      <div class="mstats"><div><span class="lbl">xP GW${G}</span><b>${num(p.xp1)}</b></div><div><span class="lbl">xP 5 GW</span><b>${num(p.xp5)}</b></div><div><span class="lbl">Start</span><b>${X.pct(p.start)}</b></div><div><span class="lbl">Own</span><b>${num(p.own)}%</b></div></div>
      <div class="lbl">xP by gameweek</div>${bars}
      <div class="lbl" style="margin-top:12px">GW${G} likely range (10th–90th percentile)</div>
      <div class="range"><span class="axis"></span><span class="band" style="left:${q10 / max * 100}%;width:${(q90 - q10) / max * 100}%"></span><span class="mid" style="left:${p.xp1 / max * 100}%"></span></div>
      <div class="kv" style="margin-bottom:12px"><span>Range</span><b>${num(q10, 0)}–${num(q90, 0)} pts · xP ${num(p.xp1)}</b></div>
      <div class="kv"><span>Chance of 10+</span><b>${X.pct(p10)}</b><span>Chance of 6+</span><b>${X.pct(p6)}</b><span>Chance of 2 or fewer</span><b>${X.pct(blank)}</b>
        <span>Season pts · last 4</span><b>${p.pts} · ${p.pts4}</b><span>xG · xA (season)</span><b>${num(p.xg)} · ${num(p.xa)}</b><span>Transfers in · out (GW)</span><b>${rank(p.tin)} · ${rank(p.tout)}</b></div></div>`;
  }

  /* ---------- planner matrix ---------- */
  function planner() {
    const ss = X.strategies();
    const cell = (s, w) => w.in.length ? s.moves.find(m => m.gw === w.gw).pairs.map(([o, i]) => `<span class="mv"><span class="o">− ${esc(o.name)}</span> <span class="i">+ ${esc(i.name)}</span></span>`).join("") + (w.hits ? `<span class="mv dn">−${w.hits * 4} hit</span>` : "") : `<span class="muted">Roll · ${w.ft} FT</span>`;
    return `<div class="grid">
      ${ss.map(s => `<section class="panel c4"><div class="pb"><div class="lbl"><span class="sw" style="background:${SER[s.key]}"></span>${s.name}</div><div class="sgain ${s.key === "balanced" ? "up" : ""}">+${num(s.gain)} <small class="muted" style="font-size:12px;font-weight:500">xP vs no moves</small></div><div class="muted">${s.blurb} · ${num(s.total)} xP over 5 GWs</div></div></section>`).join("")}
      <section class="panel c12"><div class="ph"><h2>Plan matrix</h2><div class="r"><div class="seg"><button>3 GWs</button><button aria-pressed="true">5 GWs</button><button>6 GWs</button></div></div></div>
        <div class="scroll"><table class="tbl matrix"><thead><tr><th class="l">GW</th>${ss.map(s => `<th class="l"><span class="sw" style="background:${SER[s.key]}"></span>${s.name}</th>`).join("")}</tr></thead><tbody>
        ${S.gws.map((g, i) => `<tr><td class="l"><b>GW${g}</b></td>${ss.map(s => `<td class="l">${cell(s, s.weeks[i])}<span class="mv muted">${num(s.weeks[i].xp)} xP · C ${esc(P[s.weeks[i].captain].name)}</span></td>`).join("")}</tr>`).join("")}
        </tbody></table></div></section>
      <section class="panel c12"><div class="ph"><h2>Projected team xP</h2></div><div class="pb">${stratChart(ss, 1240)}</div></section></div>`;
  }

  /* ---------- fixtures heatmap ---------- */
  function fixtures() {
    const g = X.fixtureGrid();
    return `<section class="panel"><div class="ph"><h2>Fixture difficulty</h2><div class="r"><span class="muted">FDR 1 easiest → 5 hardest · sorted by average</span></div></div><div class="scroll"><table class="tbl"><thead><tr><th class="l">Team</th>${S.gws.map(w => `<th class="l">GW${w}</th>`).join("")}<th>Avg FDR</th></tr></thead><tbody>
      ${g.map(t => `<tr><td class="l"><span class="pn"><img src="../../../site/badges/${t.code}.png" alt=""><b>${t.short}</b> <span class="muted hide-sm">${t.name}</span></span></td>${t.cells.map(c => `<td class="l">${c.list.length ? c.list.map(f => `<span class="fdr fdr-${f.fdr}">${f.opp} ${f.home ? "H" : "A"}</span>`).join(" ") : `<span class="fdr fdr-3">Blank</span>`}</td>`).join("")}<td><span class="bar"><i style="--w:${(5 - t.avg) / 4 * 100}%"></i><b>${num(t.avg)}</b></span></td></tr>`).join("")}
      </tbody></table></div></section>`;
  }

  /* ---------- rivals ---------- */
  function rivals() {
    const L = S.league, me = L.rows.find(r => r.me);
    return `<div class="grid"><section class="panel c12"><div class="ph"><h2>${esc(L.name)}</h2><div class="r"><span class="muted">${rank(L.size)} teams · anonymised sample</span></div></div><div class="scroll"><table class="tbl"><thead><tr><th class="l">#</th><th class="l">Manager</th><th>Move</th><th>GW${S.meta.picks_gw}</th><th>Total</th><th>Gap to you</th><th class="l hide-sm">Captain</th><th class="l hide-sm">Chip</th></tr></thead><tbody>
      ${L.rows.map(r => { const d = r.last - r.rank, gap = r.total - me.total; return `<tr class="${r.me ? "me" : ""}"><td class="l"><b>${r.rank}</b></td><td class="l"><b>${esc(r.name)}</b> <span class="muted hide-sm">${esc(r.team)}</span></td><td class="${d > 0 ? "up" : d < 0 ? "dn" : "muted"}">${d ? (d > 0 ? "▲" : "▼") + Math.abs(d) : "–"}</td><td>${r.gw}</td><td><b>${r.total}</b></td><td class="${gap > 0 ? "dn" : gap < 0 ? "up" : "muted"}">${r.me ? "–" : (gap > 0 ? "+" : "") + gap}</td><td class="l hide-sm">${r.cap ? esc(P[r.cap]?.name || "–") : "–"}</td><td class="l hide-sm">${r.chip || "–"}</td></tr>`; }).join("")}
      </tbody></table></div></section></div>`;
  }

  const VIEWS = { home, planner, players, fixtures, rivals };
  function render() {
    const { view, arg } = X.route(), v = VIEWS[view] ? view : "home";
    if (arg) sel = +arg;
    chrome(v);
    $("#app").innerHTML = VIEWS[v]();
    if (arg && matchMedia("(max-width: 860px)").matches) $("#detail")?.scrollIntoView();
  }
  document.addEventListener("click", e => {
    const t = e.target.closest("[data-v],[data-p]"); if (!t) return;
    if (t.dataset.v && VIEWS[t.dataset.v]) location.hash = t.dataset.v;
    else if (t.dataset.p) location.hash = "players/" + t.dataset.p;
  });
  addEventListener("hashchange", render);
  render();
})();
