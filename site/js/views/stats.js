// Stats.
/* ---------- Stats ---------- */
function lineChart(series, labels, { h = 200, yfmt = x => x, title = "" } = {}) {
  const W = 600, pad = { l: 40, r: 12, t: 12, b: 26 };
  const all = series.flatMap(s => s.vals.filter(v => v != null));
  const mx = Math.max(1, ...all), mn = Math.min(0, ...all);
  const nice = mx <= 2 ? 0.5 : mx <= 5 ? 1 : mx <= 12 ? 2 : 5;
  const top = Math.ceil(mx / nice) * nice;
  const x = i => pad.l + (labels.length === 1 ? 0 : i / (labels.length - 1)) * (W - pad.l - pad.r);
  const y = v => pad.t + (1 - (v - mn) / (top - mn)) * (h - pad.t - pad.b);
  const ticks = []; for (let v = 0; v <= top + 1e-9; v += nice) ticks.push(v);
  return `<svg class="chart" viewBox="0 0 ${W} ${h}" role="img" aria-label="${esc(title || `Line chart across ${labels.length} gameweeks`)}">
    ${ticks.map(v => `<line class="grid" x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${pad.l - 6}" y="${y(v) + 4}" text-anchor="end">${yfmt(v)}</text>`).join("")}
    ${labels.map((l, i) => `<text x="${x(i)}" y="${h - 8}" text-anchor="middle">${l}</text>`).join("")}
    ${series.map(s => `<polyline class="${s.cls}" fill="none" stroke-width="2.5" stroke-linejoin="round" ${s.dash ? 'stroke-dasharray="5 4"' : ""} points="${s.vals.map((v, i) => v == null ? "" : `${x(i)},${y(v)}`).join(" ")}"/>${s.vals.map((v, i) => v == null ? "" : `<circle cx="${x(i)}" cy="${y(v)}" r="3" class="${s.cls}" fill="var(--surface)" stroke-width="2"/>`).join("")}`).join("")}
  </svg>`;
}
function vStats() {
  const cur = D.meta.cur_gw, gwl = Array.from({ length: cur }, (_, i) => "GW" + (i + 1));
  // form table
  const posF = S.stPos;
  let rows = D.players.filter(p => p.mins4 >= 180 && (posF === "ALL" || (posF === "ATT" ? (p.pos === "MID" || p.pos === "FWD") : p.pos === posF)));
  const k = S.stSort;
  rows.sort((a, b) => (k === "delta" ? (b.xgi90_4 - b.xgi90) - (a.xgi90_4 - a.xgi90) : (b[k] || 0) - (a[k] || 0)));
  rows = rows.slice(0, 25);
  const th = (key, l) => `<th class="sort n" data-stsort="${key}" ${S.stSort === key ? 'aria-sort="descending"' : ""}>${l}${S.stSort === key ? " ↓" : ""}</th>`;
  const form = `<div class="panel"><div class="bar"><h3>Form by underlying numbers</h3>
      <div class="seg" role="group" aria-label="Position">${[["ATT", "MID+FWD"], ["DEF", "DEF"], ["ALL", "All"]].map(([v, l]) => `<button data-stpos="${v}" aria-pressed="${posF === v}">${l}</button>`).join("")}</div></div>
    <p class="note" style="margin-top:0">Last 4 gameweeks, players with 180+ minutes. Rising xGI/90 is the best early sign of a player coming into form, before the points arrive.</p>
    <div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th><th class="n">Mins ${term("l4", "L4")}</th>${th("xgi90_4", "xGI/90 L4")}${th("xgi90_6", "L6")}<th class="n">Model</th>${th("delta", "Trend")}${th("pts4", "Pts L4")}${th("dc_rate", "DC %")}</tr></thead>
    <tbody>${rows.map(p => { const d = p.xgi90_4 - p.xgi90; return `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td><button data-p="${p.id}" style="all:unset;cursor:pointer" class="pname">${esc(p.name)}</button> <span class="muted">${T[p.team].short} ${p.pos}</span></td><td class="n">${p.price.toFixed(1)}</td><td class="n">${p.mins4}</td><td class="n"><b>${p.xgi90_4.toFixed(2)}</b></td><td class="n">${p.xgi90_6.toFixed(2)}</td><td class="n">${p.xgi90.toFixed(2)}</td><td class="n ${d > 0.05 ? "up" : d < -0.05 ? "down" : ""}">${d > 0 ? "▲" : d < 0 ? "▼" : ""} ${Math.abs(d).toFixed(2)}</td><td class="n">${p.pts4}</td><td class="n">${Math.round(p.dc_rate * 100)}%</td></tr>`; }).join("")}</tbody></table></div></div>`;
  // over/under
  const att = D.players.filter(p => (p.pos === "MID" || p.pos === "FWD") && p.xg >= 1.2);
  const hot = att.slice().sort((a, b) => b.g_xg - a.g_xg).slice(0, 8);
  const due = att.slice().sort((a, b) => a.g_xg - b.g_xg).slice(0, 8);
  const ou = list => `<div class="tablebox"><table><thead><tr><th>Player</th><th class="n">Goals</th><th class="n">xG</th><th class="n">Diff</th></tr></thead><tbody>${list.map(p => `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td><button data-p="${p.id}" style="all:unset;cursor:pointer" class="pname">${esc(p.name)}</button> <span class="muted">${T[p.team].short}</span></td><td class="n">${p.goals}</td><td class="n">${p.xg.toFixed(1)}</td><td class="n ${p.g_xg > 0 ? "up" : "down"}">${p.g_xg > 0 ? "+" : ""}${p.g_xg.toFixed(1)}</td></tr>`).join("")}</tbody></table></div>`;
  // team trend
  const tt = T[S.trendTeam];
  const tr = tt.trend;
  const trendChart = lineChart([{ cls: "s1", vals: tr.map(x => x.xgf) }, { cls: "s4", vals: tr.map(x => x.xga) }], tr.map(x => (x.home ? T[x.opp].short : T[x.opp].short.toLowerCase())), { title: "xG for and against" });
  const teamOpts = Object.values(T).sort((a, b) => a.name.localeCompare(b.name)).map(t => `<option value="${t.id}" ${String(S.trendTeam) === String(t.id) ? "selected" : ""}>${t.name}</option>`).join("");
  const ratings = Object.values(T).sort((a, b) => (b.att / b.def) - (a.att / a.def));
  // player charts
  const cps = S.cmp.map(i => P[i]).filter(Boolean).slice(0, 4);
  const cls = ["s1", "s2", "s3", "s4"];
  const pc = cps.length ? `<div class="legend">${cps.map((p, i) => `<span><i class="${cls[i]}"></i>${esc(p.name)}</span>`).join("")}</div>
      <span class="lbl">Points per gameweek</span>${lineChart(cps.map((p, i) => ({ cls: cls[i], vals: p.s_pts })), gwl, { h: 180 })}
      <span class="lbl">Expected goal involvement per gameweek</span>${lineChart(cps.map((p, i) => ({ cls: cls[i], vals: p.s_xgi })), gwl, { h: 180, yfmt: v => v.toFixed(1) })}`
    : `<p class="muted">Pick players to chart below, or tick them in the Players tab.</p>`;
  const tabs = [["form", "Form"], ["shots", "Shots"], ["sp", "Set pieces"], ["defence", "Defence"], ["bonus", "Bonus"], ["value", "Value"], ["teams", "Teams"]];
  const tab = S.stab || "form";
  const nav = `<div class="seg ptabs" role="group" aria-label="Stats sections">${tabs.map(([k, l]) => `<button data-stab="${k}" aria-pressed="${tab === k}">${l}</button>`).join("")}</div>`;
  let body = "";
  if (tab === "form") body = `${form}
  <div class="panel"><div class="bar"><h3>Player charts</h3><span class="muted">${cps.length}/4 selected</span></div>${pc}
    <div class="filters" style="margin-top:10px"><input type="search" id="chartq" list="plist" placeholder="Add a player to the chart" aria-label="Add a player to the chart"><datalist id="plist">${D.players.slice(0, 350).map(p => `<option value="${esc(p.name)} (${T[p.team].short})">`).join("")}</datalist>${cps.map(p => `<button class="btn" data-uncmp="${p.id}">✕ ${esc(p.name)}</button>`).join("")}</div></div>
  <div class="statgrid">
    <div class="panel"><h3>Running hot</h3><p class="note" style="margin-top:0">Scoring well above their xG. Finishing streaks rarely last, so expect fewer goals unless the chances rise.</p>${ou(hot)}</div>
    <div class="panel"><h3>Due a goal</h3><p class="note" style="margin-top:0">Getting chances but scoring less than their xG. Often good value before the goals come.</p>${ou(due)}</div>
  </div>`;
  else if (tab === "shots") body = shotsHTML();
  else if (tab === "sp") body = spThreatHTML() + setPiecesHTML();
  else if (tab === "defence") body = dcHTML();
  else if (tab === "bonus") body = bonusHTML();
  else if (tab === "value") body = valueHTML();
  else body = `<div class="grid2">
    <div class="panel"><div class="bar"><h3>Team trend</h3><select id="trendTeam" aria-label="Team" style="background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 9px">${teamOpts}</select></div>
      <div class="legend"><span><i class="s1"></i>xG for</span><span><i class="s4"></i>xG against</span></div>
      ${trendChart}
      <p class="note">Real scores: ${tr.map(x => `${oppTxt(x)} ${x.gf}–${x.ga}`).join(" · ")}</p></div>
    <div class="panel"><h3>${term("strength", "Team strength")}</h3><p class="note" style="margin-top:0">From the model's predictions, adjusted for the opponents each team has faced. Strength = expected share of points against an average team; Attack and Defence are against the league average (100%).</p>
      <div class="tablebox" style="max-height:460px"><table><thead><tr><th>Team</th><th class="n">Strength</th><th class="n">Win vs avg</th><th class="n">Attack</th><th class="n">Defence</th><th class="n">Next ${Math.min(6, GWS.length)} win %</th></tr></thead><tbody>${Object.values(T).map(t => ({ t, s: teamStrength(t), nx: GWS.slice(0, 6).flatMap(g => (t.fx[g] || []).map(x => wdl(x.xgf, x.xga).w)) })).sort((a, b) => b.s.pts - a.s.pts).map(({ t, s: st, nx }) => `<tr><td>${t.name}</td><td class="n"><span class="minibar" style="width:${st.pts * 0.8}px"></span> <b>${Math.round(st.pts)}%</b></td><td class="n">${Math.round(st.win)}%</td><td class="n">${Math.round(st.att)}%</td><td class="n">${Math.round(st.def)}%</td><td class="n">${nx.length ? Math.round(100 * nx.reduce((a, b) => a + b, 0) / nx.length) + "%" : "–"}</td></tr>`).join("")}</tbody></table></div></div>
  </div>${teamSPHTML()}`;
  return nav + body;
}

function posSeg(key, opts) {
  return `<div class="seg" role="group" aria-label="Position">${opts.map(([v, l]) => `<button data-posseg="${key}:${v}" aria-pressed="${(S[key] || opts[0][0]) === v}">${l}</button>`).join("")}</div>`;
}
const posMatch = (p, f) => f === "ALL" || (f === "ATT" ? (p.pos === "MID" || p.pos === "FWD") : p.pos === f);
function spThreatHTML() {
  const f = S.spPos || "DEF";
  const rows = D.players.filter(p => p.us && p.mins >= 270 && posMatch(p, f)).sort((a, b) => b.us.sp_xg90 - a.us.sp_xg90).slice(0, 20);
  return `<div class="panel"><div class="bar"><h3>Set-piece threat</h3>${posSeg("spPos", [["DEF", "DEF"], ["ATT", "MID+FWD"], ["ALL", "All"]])}</div>
    <p class="note" style="margin-top:0">xG from corners, free kicks and other set pieces, separate from open play and penalties. Defenders who are dangerous from set pieces score far more than their attacking stats suggest, and they're often cheap. Data from Understat.</p>
    <div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th><th class="n">Set-piece xG/90</th><th class="n">Set-piece shots</th><th class="n">Set-piece headers</th><th class="n">Open-play xG/90</th><th class="n">Pen xG</th><th>Takes</th></tr></thead>
    <tbody>${rows.map(p => `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td><button data-p="${p.id}" style="all:unset;cursor:pointer" class="pname">${esc(p.name)}</button> <span class="muted">${T[p.team].short} ${p.pos}</span></td><td class="n">${p.price.toFixed(1)}</td><td class="n"><b>${p.us.sp_xg90.toFixed(2)}</b></td><td class="n">${p.us.sp_shots}</td><td class="n">${p.us.sp_headers}</td><td class="n">${p.us.op_xg90.toFixed(2)}</td><td class="n">${p.us.pen_xg.toFixed(1)}</td><td>${[p.sp?.pen === 1 ? "Pens" : "", p.sp?.cor === 1 ? "Corners" : "", p.sp?.fk === 1 ? "FKs" : ""].filter(Boolean).join(", ") || '<span class="muted">–</span>'}</td></tr>`).join("")}</tbody></table></div></div>`;
}
function teamSPHTML() {
  const rows = Object.values(T).filter(t => t.sp).sort((a, b) => b.sp.for - a.sp.for);
  if (!rows.length) return "";
  return `<div class="panel"><h3>Set pieces by team</h3><p class="note" style="margin-top:0">Expected goals per game from set pieces, for and against. A team that concedes a lot from set pieces is a good opponent for set-piece-threat defenders; one that creates a lot makes its defenders worth more.</p>
    <div class="tablebox"><table><thead><tr><th>Team</th><th class="n">Set-piece xG for</th><th class="n">Set-piece xG against</th><th class="n">Open-play xG for</th><th class="n">Open-play xG against</th></tr></thead>
    <tbody>${rows.map(t => `<tr><td>${t.name}</td><td class="n"><span class="minibar" style="width:${t.sp.for * 80}px"></span> ${t.sp.for.toFixed(2)}</td><td class="n"><span class="minibar neg" style="width:${t.sp.against * 80}px"></span> ${t.sp.against.toFixed(2)}</td><td class="n">${t.sp.op_for.toFixed(2)}</td><td class="n">${t.sp.op_against.toFixed(2)}</td></tr>`).join("")}</tbody></table></div></div>`;
}
function dcHTML() {
  const f = S.dcPos || "DEF";
  const thr = f === "DEF" ? 10 : 12;
  // rank by expected DC points next game: the model's (shrunk) chance of hitting the threshold x how nailed he is
  const exp = p => p.dc_rate * Math.min(1, p.nailed / 100);
  const rows = D.players.filter(p => p.dcs && p.dcs.apps >= 4 && posMatch(p, f) && p.pos !== "GKP")
    .sort((a, b) => exp(b) - exp(a) || (b.dcs.per90 - a.dcs.per90)).slice(0, 25);
  return `<div class="panel"><div class="bar"><h3>Defensive contribution leaders</h3>${posSeg("dcPos", [["DEF", "DEF"], ["MID", "MID"], ["FWD", "FWD"]])}</div>
    <p class="note" style="margin-top:0">A ${term("dc", "defensive contribution")} is worth 2 points: ${f === "DEF" ? "10 clearances, blocks, interceptions and tackles" : "12 clearances, blocks, interceptions, tackles and recoveries"} in a match. Hit rate = how often he reached it in games of 60+ minutes. Chance next = the model's estimate for his next game, allowing for small samples and how likely he is to start. Ranked by chance next; at least 4 games of 60+ minutes.</p>
    <div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th><th class="n">Per 90 (need ${thr})</th><th class="n">Hit rate</th><th class="n">Chance next</th><th class="n">DC points</th><th class="n">Last 6</th><th class="n">${term("nailed", "Nailed")}</th><th class="n">xP ${PG.length} GWs</th></tr></thead>
    <tbody>${rows.map(p => `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td><button data-p="${p.id}" style="all:unset;cursor:pointer" class="pname">${esc(p.name)}</button> <span class="muted">${T[p.team].short}</span></td><td class="n">${p.price.toFixed(1)}</td><td class="n">${p.dcs.per90.toFixed(1)}</td><td class="n">${Math.round(100 * p.dcs.hits / p.dcs.apps)}% <span class="muted">(${p.dcs.hits}/${p.dcs.apps})</span></td><td class="n"><b>${Math.round(100 * exp(p))}%</b></td><td class="n">${2 * p.dcs.hits}</td><td class="n">${p.dc6.hits}/${p.dc6.apps}</td><td class="n">${nailedPill(p)}</td><td class="n">${f1(xpFrom(p.id, PG[0], PG.length))}</td></tr>`).join("")}</tbody></table></div></div>`;
}
function valueHTML() {
  const caps = { GKP: 4.5, DEF: 4.5, MID: 5.0, FWD: 5.5 }, g0 = PG[0], H = PG.length;
  const xf = id => xpFrom(id, g0, H);
  const starters = p => p.ok !== false && p.nailed >= 70 && p.status === "a";
  const enab = Object.keys(caps).map(pos => {
    const list = D.players.filter(p => p.pos === pos && p.price <= caps[pos] && starters(p)).sort((a, b) => xf(b.id) - xf(a.id)).slice(0, 5);
    return `<div><h3 style="font-size:16px;margin:10px 0 6px">${pos} ≤ £${caps[pos].toFixed(1)}m</h3>${list.length ? `<div class="tablebox"><table><tbody>${list.map(p => `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td><button data-p="${p.id}" style="all:unset;cursor:pointer" class="pname">${esc(p.name)}</button> <span class="muted">${T[p.team].short} · £${p.price.toFixed(1)}m</span></td><td class="n">${nailedPill(p)}</td><td class="n"><b>${f1(xf(p.id))}</b></td><td><span class="fx sgfx">${fxChips(p, g0, 4)}</span></td></tr>`).join("")}</tbody></table></div>` : '<p class="muted">No regular starters at this price.</p>'}</div>`;
  }).join("");
  // rotation pairs: two cheap players from different clubs; start whichever has the better fixture each week
  const pairsFor = (pos, cap, minEach) => {
    const ps = D.players.filter(p => p.pos === pos && p.price <= cap && starters(p) && xf(p.id) >= minEach).sort((a, b) => xf(b.id) - xf(a.id)).slice(0, 25);
    const out = [];
    for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) {
      const a = ps[i], b = ps[j]; if (a.team === b.team) continue;
      const tot = PG.reduce((s2, g) => s2 + Math.max(xpg(a.id, g), xpg(b.id, g)), 0);
      out.push({ a, b, tot, cost: a.price + b.price, best1: Math.max(xf(a.id), xf(b.id)) });
    }
    return out.sort((x, y) => y.tot - x.tot).slice(0, 4);
  };
  const pairTable = (list) => list.length ? `<div class="tablebox"><table><thead><tr><th>Pair</th><th class="n">£m</th><th class="n">xP rotating</th>${PG.map(g => `<th>GW${g}</th>`).join("")}</tr></thead><tbody>${list.map(r => `<tr><td><span class="pname">${esc(r.a.name)}</span> <span class="muted">${T[r.a.team].short}</span> + <span class="pname">${esc(r.b.name)}</span> <span class="muted">${T[r.b.team].short}</span></td><td class="n">${r.cost.toFixed(1)}</td><td class="n"><b>${f1(r.tot)}</b> <span class="muted">(+${f1(r.tot - r.best1)})</span></td>${PG.map(g => { const s2 = xpg(r.a.id, g) >= xpg(r.b.id, g) ? r.a : r.b; return `<td>${esc(s2.name)}</td>`; }).join("")}</tr>`).join("")}</tbody></table></div>` : '<p class="muted">No suitable pairs.</p>';
  return `<div class="panel"><h3>Budget enablers</h3><p class="note" style="margin-top:0">The best cheap players who actually start (Nailed 70+), by projected points over ${H} GWs. Filling these spots well frees money for premiums.</p>
      <div class="statgrid">${enab}</div></div>
    <div class="panel"><h3>Rotation pairs</h3><p class="note" style="margin-top:0">Two cheap players from different clubs: start whichever has the better fixture each week. The bracket shows how much the pair adds over just starting the better one every week.</p>
      <h3 style="font-size:16px;margin:6px 0">Goalkeepers ≤ £5.0m each</h3>${pairTable(pairsFor("GKP", 5.0, 0))}
      <h3 style="font-size:16px;margin:14px 0 6px">Defenders ≤ £5.0m each</h3>${pairTable(pairsFor("DEF", 5.0, 0))}</div>`;
}
function shotsHTML() {
  const posF = S.stPos, k = S.shSort || "sib90_4";
  let rows = D.players.filter(p => p.us && p.mins >= 270 && (posF === "ALL" || (posF === "ATT" ? (p.pos === "MID" || p.pos === "FWD") : p.pos === posF)));
  rows.sort((a, b) => (b.us[k] || 0) - (a.us[k] || 0));
  rows = rows.slice(0, 25);
  const th = (key, l, tip) => `<th class="sort n" data-shsort="${key}" ${k === key ? 'aria-sort="descending"' : ""}>${tip ? term(tip, l) : l}${k === key ? " ↓" : ""}</th>`;
  const U = D.meta.understat || {};
  return `<div class="panel"><div class="bar"><h3>Shots and big chances</h3>
      <div class="seg" role="group" aria-label="Position">${[["ATT", "MID+FWD"], ["DEF", "DEF"], ["ALL", "All"]].map(([v, l]) => `<button data-stpos="${v}" aria-pressed="${posF === v}">${l}</button>`).join("")}</div></div>
    <p class="note" style="margin-top:0">Who gets into scoring positions, often before the goals and xG add up. L4 = last 4 gameweeks (from GW${U.last4_from_gw ?? "–"}). Data from Understat (${U.matches ?? 0} matches), updated every 3 hours.</p>
    <div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th>${th("shots90", "Shots/90")}${th("sib90", "In box/90", "inbox")}${th("sib90_4", "In box/90 L4", "inbox")}${th("bc90", "Big ch/90", "bigchance")}${th("bc_4", "Big ch L4", "bigchance")}<th class="n">Big ch scored</th>${th("cc90", "Created/90", "created")}${th("bcc90", "Big ch created/90", "bigchance")}</tr></thead>
    <tbody>${rows.map(p => { const u = p.us; return `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td><button data-p="${p.id}" style="all:unset;cursor:pointer" class="pname">${esc(p.name)}</button> <span class="muted">${T[p.team].short} ${p.pos}</span></td><td class="n">${p.price.toFixed(1)}</td><td class="n">${u.shots90.toFixed(1)}</td><td class="n">${u.sib90.toFixed(1)}</td><td class="n"><b>${u.sib90_4.toFixed(1)}</b></td><td class="n">${u.bc90.toFixed(2)}</td><td class="n">${u.bc_4}</td><td class="n">${u.bc_scored}/${u.bc}</td><td class="n">${u.cc90.toFixed(1)}</td><td class="n">${u.bcc90.toFixed(2)}</td></tr>`; }).join("")}</tbody></table></div></div>`;
}
function bonusHTML() {
  const k = S.boSort || "bps90";
  let rows = D.players.filter(p => p.mins4 >= 180);
  const v = p => k === "bps90" ? p.bf4.bps90 : k === "top3" ? p.bf6.top3 / Math.max(1, p.bf6.apps) : k === "bonus6" ? p.bf6.bonus : p.bps_season;
  rows.sort((a, b) => v(b) - v(a)); rows = rows.slice(0, 20);
  const th = (key, l) => `<th class="sort n" data-bosort="${key}" ${k === key ? 'aria-sort="descending"' : ""}>${l}${k === key ? " ↓" : ""}</th>`;
  return `<div class="panel"><h3>Bonus point form</h3>
    <p class="note" style="margin-top:0">The top 3 ${term("bps", "BPS")} scores in each match earn 3, 2 and 1 bonus points. Players who keep finishing top 3 in their match pick up bonus even in quiet games.</p>
    <div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th>${th("bps90", "BPS/90 L4")}${th("top3", "Top 3 in match L6")}${th("bonus6", "Bonus L6")}${th("season", "Season BPS")}</tr></thead>
    <tbody>${rows.map(p => `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td><button data-p="${p.id}" style="all:unset;cursor:pointer" class="pname">${esc(p.name)}</button> <span class="muted">${T[p.team].short} ${p.pos}</span></td><td class="n">${p.price.toFixed(1)}</td><td class="n"><b>${p.bf4.bps90.toFixed(1)}</b></td><td class="n">${p.bf6.top3} of ${p.bf6.apps}</td><td class="n">${p.bf6.bonus}</td><td class="n">${p.bps_season}</td></tr>`).join("")}</tbody></table></div></div>`;
}
function setPiecesHTML() {
  const SP = D.setpieces; if (!SP) return "";
  const nm = id => id && P[id] ? `<button data-p="${id}" style="all:unset;cursor:pointer" class="${MINE.has(id) ? "pname" : ""}">${esc(P[id].name)}</button>${MINE.has(id) ? ' <span class="pill good">Yours</span>' : ""}` : '<span class="muted">–</span>';
  const second = id => id && P[id] ? `<span class="muted">${esc(P[id].name)}</span>` : "";
  const rows = Object.values(T).sort((a, b) => a.name.localeCompare(b.name)).map(t => { const r = SP.now[t.id] || {}; return `<tr><td>${t.name}</td>${["pen", "cor", "fk"].map(k => `<td>${nm((r[k] || [])[0])}<br>${second((r[k] || [])[1])}</td>`).join("")}</tr>`; }).join("");
  const label = { pen: "penalties", cor: "corners", fk: "direct free kicks" };
  const ch = (SP.changes || []).slice(0, 8);
  return `<div class="panel"><h3>Set pieces and penalties</h3><p class="note" style="margin-top:0">First choice on top, back-up underneath, from FPL's own data. Penalty takers already get a small boost in the projections.</p>
    ${ch.length ? `<ul class="alerts" style="margin-bottom:12px">${ch.map(c => `<li class="warn"><span>${c.date}: ${T[c.team]?.name} ${label[c.type]} now ${c.new && P[c.new] ? esc(P[c.new].name) : "unknown"}${c.old && P[c.old] ? ` (was ${esc(P[c.old].name)})` : ""}.</span></li>`).join("")}</ul>` : `<p class="note">Changes to first-choice takers will be listed here as FPL updates them.</p>`}
    <div class="tablebox" style="max-height:480px"><table><thead><tr><th>Team</th><th>Penalties</th><th>Corners</th><th>Free kicks</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}
