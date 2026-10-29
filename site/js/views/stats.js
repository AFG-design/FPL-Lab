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
  const tabs = [["form", "Form"], ["shots", "Shots"], ["sp", "Set pieces"], ["defence", "Defence"], ["bonus", "Bonus"], ["value", "Value"], ["prices", "Prices"], ["teams", "Teams"]];
  const tab = S.stab || "form";
  const nav = `<div class="stats-nav"><div class="seg ptabs" role="group" aria-label="Stats sections">${tabs.map(([k, l]) => `<button data-stab="${k}" aria-pressed="${tab === k}">${l}</button>`).join("")}</div>
    <button class="btn ghost sm" data-statlabels="${tab}" aria-haspopup="dialog">What the labels mean</button></div>`;
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
  else if (tab === "prices") body = pricesHTML();
  else body = `<div class="grid2">
    <div class="panel"><div class="bar"><h3>Team trend</h3><select id="trendTeam" aria-label="Team" style="background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 9px">${teamOpts}</select></div>
      <div class="legend"><span><i class="s1"></i>xG for</span><span><i class="s4"></i>xG against</span></div>
      ${trendChart}
      <p class="note">Real scores: ${tr.map(x => `${oppTxt(x)} ${x.gf}–${x.ga}`).join(" · ")}</p></div>
    <div class="panel"><h3>${term("strength", "Team strength")}</h3><p class="note" style="margin-top:0">From the model's predictions, adjusted for the opponents each team has faced. Strength = expected share of points against an average team; Attack and Defence are against the league average (100%).</p>
      <div class="tablebox" style="max-height:460px"><table><thead><tr><th>Team</th><th class="n">Strength</th><th class="n">Win vs avg</th><th class="n">Attack</th><th class="n">Defence</th><th class="n">Next ${Math.min(6, GWS.length)} win %</th></tr></thead><tbody>${Object.values(T).map(t => ({ t, s: teamStrength(t), nx: GWS.slice(0, 6).flatMap(g => (t.fx[g] || []).map(x => wdl(x.xgf, x.xga).w)) })).sort((a, b) => b.s.pts - a.s.pts).map(({ t, s: st, nx }) => `<tr><td><button data-team="${t.id}" class="linkish">${t.name}</button></td><td class="n"><span class="minibar" style="width:${st.pts * 0.8}px"></span> <b>${Math.round(st.pts)}%</b></td><td class="n">${Math.round(st.win)}%</td><td class="n">${Math.round(st.att)}%</td><td class="n">${Math.round(st.def)}%</td><td class="n">${nx.length ? Math.round(100 * nx.reduce((a, b) => a + b, 0) / nx.length) + "%" : "–"}</td></tr>`).join("")}</tbody></table></div></div>
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
  return `<div class="panel"><h3>Budget enablers</h3><p class="note" style="margin-top:0">The best cheap players who actually start (Nailed 70+), by projected points over ${H} GWs. Filling these spots well frees money for premiums.</p>
      <div class="statgrid">${enab}</div></div>
    ${rotationHTML()}${oopHTML()}`;
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

/* ---------- prices: tonight's likely changes and how reliable FPL's projection has been ---------- */
// our record for this projection band, once there's enough of it; otherwise null
function priceRecord(pr) {
  const B = D.prices?.bands; if (!B || pr == null) return null;
  const dir = pr >= 0 ? "rise" : "fall", a = Math.abs(pr);
  const b = B.filter(x => x.dir === dir).find(x => a >= x.lo); if (!b || b.n < 15) return null;
  return { pct: Math.round(100 * b.hit / b.n), n: b.n, band: b.band };
}
function pricesHTML() {
  const PR = D.prices, g0 = PG[0];
  const when = PR?.pending_night ? new Date(new Date(PR.pending_night).getTime() + 90 * 6e4).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" }) : "tonight";
  const pr = p => p.price_proj?.[0];
  const recNote = v => { const r = priceRecord(v); return r ? `: ${r.pct}% of players this close changed price that night (${r.n} cases)` : ""; };
  const chance = p => { const r = priceRecord(pr(p)); return r ? `<b>${r.pct}%</b> <span class="muted">(${r.n})</span>` : '<span class="muted">–</span>'; };
  const row = p => `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td><button data-p="${p.id}" class="pname linkish">${esc(p.name)}</button> <span class="muted">${T[p.team].short} ${p.pos}</span></td><td class="n">${p.price.toFixed(1)}</td><td>${priceCell(p)}</td><td class="n">${chance(p)}</td><td class="n">${(p.tin - p.tout).toLocaleString("en-GB")}</td></tr>`;
  const tbl = list => `<div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th><th>FPL projection</th><th class="n">Our record</th><th class="n">Net transfers</th></tr></thead><tbody>${list.map(row).join("") || '<tr><td colspan="5" class="muted">None close</td></tr>'}</tbody></table></div>`;
  const risers = D.players.filter(p => pr(p) >= 75).sort((a, b) => pr(b) - pr(a)).slice(0, 12);
  const fallers = D.players.filter(p => pr(p) <= -75).sort((a, b) => pr(a) - pr(b)).slice(0, 12);
  // what matters to you: players you own that may fall, players you plan to buy that may rise
  const buys = (SB?.moves || []).filter(m => m.gw === g0).map(m => P[m.in]).filter(Boolean);
  const alerts = [
    ...buys.filter(p => pr(p) >= 75).map(p => priceTonight(pr(p))
      ? ["warn", `<b>${esc(p.name)}</b> is in your plan and is projected to rise at the next update (${when}). Making the transfer before then saves £0.1m.`]
      : ["info", `<b>${esc(p.name)}</b> is in your plan and is ${priceMove(pr(p))}${recNote(pr(p))}.`]),
    ...D.squad.map(s => P[s.id]).filter(p => p && pr(p) <= -75).map(p => priceTonight(pr(p))
      ? ["bad", `<b>${esc(p.name)}</b> is projected to fall at the next update (${when}). If you're selling him anyway, sell before then.`]
      : ["info", `<b>${esc(p.name)}</b> is ${priceMove(pr(p))}${recNote(pr(p))}.`]),
  ];
  const last = PR?.last;
  const lastHTML = last && last.rows.length ? `<ul class="alerts">${last.rows.slice().sort((a, b) => b[2] - a[2]).slice(0, 16).map(([id, p0, ch]) => `<li class="${ch > 0 ? "good" : "bad"}"><span><b>${esc(P[id]?.name || id)}</b> ${ch > 0 ? "▲" : "▼"} £${(Math.abs(ch) / 10).toFixed(1)}m <span class="muted">· FPL had ${p0.toFixed(0)}%${Math.abs(p0) < 50 ? " (a surprise)" : ""}</span></span></li>`).join("")}</ul>`
    : `<p class="muted">${PR?.nights ? "No price changes at the last update." : "The first night of tracking finishes after the next update."}</p>`;
  const B = PR?.bands || [];
  const rec = ["100%+", "90–100%", "75–90%", "50–75%"].map(lab => { const r = B.find(x => x.dir === "rise" && x.band === lab), f = B.find(x => x.dir === "fall" && x.band === lab);
    const c = x => x && x.n ? `${Math.round(100 * x.hit / x.n)}% <span class="muted">(${x.hit}/${x.n})</span>` : '<span class="muted">–</span>';
    return `<tr><td>${lab}</td><td class="n">${c(r)}</td><td class="n">${c(f)}</td></tr>`; }).join("");
  return `${alerts.length ? `<div class="panel"><h3>Before the next price update</h3><ul class="alerts">${alerts.map(([c, t]) => `<li class="${c}"><span>${t}</span></li>`).join("")}</ul></div>` : ""}
  <div class="statgrid">
    <div class="panel"><h3>Closest to a rise</h3><p class="note" style="margin-top:0">FPL's projection for the next update (${when}). 100% means the threshold is reached; below that a change tonight is unlikely (see the track record).</p>${tbl(risers)}</div>
    <div class="panel"><h3>Closest to a fall</h3><p class="note" style="margin-top:0">Same projection, for falls. Your players are highlighted.</p>${tbl(fallers)}</div>
  </div>
  <div class="grid2">
    <div class="panel"><h3>Last update</h3>${lastHTML}</div>
    <div class="panel"><h3>Track record</h3><p class="note" style="margin-top:0">How often a player at each FPL projection actually changed price that night, over the last ${PR?.nights || 0} night${PR?.nights === 1 ? "" : "s"}. "Our record" above appears once a band has 15+ cases.${PR?.changes ? ` ${PR.unpredicted} of ${PR.changes} changes weren't projected above 50%.` : ""}</p>
      <div class="tablebox"><table><thead><tr><th>FPL projection</th><th class="n">Rose</th><th class="n">Fell</th></tr></thead><tbody>${rec}</tbody></table></div></div>
  </div>`;
}

/* ---------- what the labels mean, per Stats tab ---------- */
const STAT_LABELS = {
  general: ["Across Stats", [
    ["L4 / L6", "Over the last 4 or 6 gameweeks. Recent form reacts faster to a change of role or team than whole-season numbers."],
    ["/90", "Per 90 minutes, so players who play less can be compared fairly with regulars."],
    ["£m", "Current FPL price."],
    ["Highlighted row", "A player in your squad."],
    ["xG / xA / xGI", "Expected goals, expected assists, and the two added together (expected goal involvement): how good his chances were, whether or not they went in."],
    ["xP", "Projected FPL points from the model."],
  ]],
  form: ["Form", [
    ["Mins L4", "Minutes played over the last 4 gameweeks (360 is every minute)."],
    ["xGI/90 L4 and L6", "Expected goal involvement per 90 over the last 4 and 6 gameweeks."],
    ["Model", "The model's long-run xGI per 90 for him, blending this season with last season. This is what his projections are based on."],
    ["Trend", "xGI/90 over the last 4 minus the Model figure. ▲ means he's getting better chances than usual, often a sign he's coming into form before the points arrive."],
    ["Pts L4", "FPL points over the last 4 gameweeks."],
    ["DC %", "The model's chance he reaches the defensive contribution target (worth 2 points) in a game."],
    ["Running hot / Due a goal", "Goals compared with xG this season. Diff = goals minus xG. Big positive gaps usually shrink, and big negative ones usually close."],
  ]],
  shots: ["Shots", [
    ["Shots/90", "All shots per 90, including long-range efforts."],
    ["In box/90 (and L4)", "Shots from inside the penalty area per 90, where most goals come from. More reliable than total shots."],
    ["Big ch/90, Big ch L4", "Big chances: shots worth 0.3 xG or more, such as one-on-ones or close-range headers. Per 90, and the count over the last 4 gameweeks."],
    ["Big ch scored", "Big chances scored out of big chances taken."],
    ["Created/90", "Shots he set up with a pass (key passes) per 90."],
    ["Big ch created/90", "Big chances he set up per 90."],
  ]],
  sp: ["Set pieces", [
    ["Set-piece xG/90", "Expected goals from corners and free kicks per 90 (penalties not included)."],
    ["Set-piece shots / headers", "Shots, and headed shots, from set pieces this season."],
    ["Open-play xG/90", "Expected goals from open play per 90."],
    ["Pen xG", "Expected goals from penalties taken this season (about 0.76 each)."],
    ["Takes", "The set pieces FPL lists him as first choice for."],
    ["Set-piece xG for / against", "Per game: how dangerous a team is from set pieces, and how much it concedes from them."],
    ["Penalties, Corners, Free kicks", "First-choice taker on top, back-up underneath, from FPL's own data."],
  ]],
  defence: ["Defence", [
    ["Per 90 (need X)", "Clearances, blocks, interceptions and tackles per 90 (plus recoveries for midfielders and forwards). X is the target for 2 points in a match: 10 for defenders, 12 for others."],
    ["Hit rate", "How often he reached the target in games where he played 60+ minutes."],
    ["Chance next", "The model's chance he reaches it next game, allowing for small samples."],
    ["DC points", "Points he has earned from defensive contributions this season."],
    ["Last 6", "Games he hit the target out of his games in the last 6 gameweeks."],
    ["Nailed", "How sure he is to start, from 0 to 100. 85+ is nailed on; under 60 is a rotation risk."],
    ["xP N GWs", "Projected points over the plan length you've chosen."],
  ]],
  bonus: ["Bonus", [
    ["BPS/90 L4", "Bonus Point System score per 90 over the last 4 gameweeks. The top 3 BPS in each match get 3, 2 and 1 bonus points."],
    ["Top 3 in match L6", "Games in the last 6 where he finished in the top 3 for BPS in his match."],
    ["Bonus L6", "Bonus points over the last 6 gameweeks."],
    ["Season BPS", "Total BPS this season."],
  ]],
  value: ["Value", [
    ["Budget enablers", "The best regular starters at or under each price, by projected points over your plan length."],
    ["Nailed", "How sure he is to start (85+ nailed on)."],
    ["Rotation planner", "Pick a position and a price limit. Each pair is two regular starters from different clubs: you start whichever has the better fixture each week."],
    ["xP rotating", "What the pair projects over your plan length, with (+) the gain over just starting the better one every week."],
    ["GW columns", "Who you'd start that week and his projection."],
    ["A partner for your…", "For each of your own players at that position, the best player to rotate him with, and how much that adds."],
    ["Plays as", "Out of position tables: where Understat records him playing (D, M, F). Two letters means both."],
    ["In box/90", "Shots from inside the penalty area per 90."],
  ]],
  prices: ["Prices", [
    ["FPL projection", "FPL's own estimate of how close a player is to a price change at the next update (around 01:30 UK). 100% means the threshold is reached; negative means a fall."],
    ["Our record", "How often players at that projection actually changed price, from our nightly log. Appears once there are 15+ cases."],
    ["Net transfers", "Transfers in minus out this gameweek, which is what moves prices."],
    ["Rose / Fell", "In the track record: the share of players at each projection level that actually rose or fell that night."],
  ]],
  teams: ["Teams", [
    ["Strength", "The share of available points (3 a game) a team would expect against an average side on a neutral ground. 50% is mid-table; 70%+ is title form."],
    ["Win vs avg", "Their chance of beating an average team."],
    ["Attack", "Goals they'd expect to score against average, versus the league average (120% = 20% more)."],
    ["Defence", "How few they'd expect to concede versus average (120% = concede about a sixth less)."],
    ["Next N win %", "Average chance of winning their next fixtures, from the model."],
    ["xG for and against", "The team-trend chart: expected goals created and conceded in each recent match."],
  ]],
};
function openStatLabels(tab) {
  const sec = ([t, rows]) => `<section><h3>${t}</h3><dl class="labels">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></section>`;
  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" id="dlgX">×</button>
    <h2>What the labels mean</h2>
    ${sec(STAT_LABELS[tab] || STAT_LABELS.form)}${sec(STAT_LABELS.general)}
    <p class="note">Tap any dotted-underlined word on the site for a quick explanation too.</p>`;
  const dlg = $("#dlg"); dlg.showModal(); $("#dlgX").onclick = () => dlg.close();
}

/* ---------- rotation planner: two players who share a slot, any position and budget ---------- */
const ROT_CAPS = { GKP: [4.5, 5.0, 5.5], DEF: [4.5, 5.0, 5.5, 6.0], MID: [5.5, 6.5, 7.5], FWD: [6.0, 7.0, 8.0] };
function rotationHTML() {
  const pos = ROT_CAPS[S.rotPos] ? S.rotPos : "GKP", caps = ROT_CAPS[pos], cap = caps.includes(S.rotCap) ? S.rotCap : caps[1];
  const g0 = PG[0], xf = id => xpFrom(id, g0, PG.length), starter = p => p.ok !== false && p.nailed >= 70 && p.status === "a";
  const both = (a, b) => PG.reduce((t, g) => t + Math.max(xpg(a.id, g), xpg(b.id, g)), 0);
  const ps = D.players.filter(p => p.pos === pos && p.price <= cap && starter(p)).sort((a, b) => xf(b.id) - xf(a.id)).slice(0, 30);
  const pairs = [];
  for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) {
    const a = ps[i], b = ps[j]; if (a.team === b.team) continue;
    pairs.push({ a, b, tot: both(a, b), cost: a.price + b.price, best1: Math.max(xf(a.id), xf(b.id)) });
  }
  pairs.sort((x, y) => y.tot - x.tot);
  // a partner for each of your own players at this position
  const mine = D.squad.map(s2 => P[s2.id]).filter(p => p && p.pos === pos);
  const partners = mine.map(m => { const c = ps.filter(p => p.team !== m.team && !MINE.has(p.id)).map(p => ({ p, tot: both(m, p) })).sort((x, y) => y.tot - x.tot)[0];
    return c ? { m, ...c, gain: c.tot - xf(m.id) } : null; }).filter(Boolean).sort((x, y) => y.gain - x.gain);
  const who = (r, g) => (xpg(r.a.id, g) >= xpg(r.b.id, g) ? r.a : r.b);
  const tbl = list => list.length ? `<div class="tablebox"><table><thead><tr><th>Pair</th><th class="n">£m</th><th class="n">xP rotating</th>${PG.map(g => `<th>GW${g}</th>`).join("")}</tr></thead><tbody>${list.map(r => `<tr class="${MINE.has(r.a.id) || MINE.has(r.b.id) ? "mine" : ""}"><td><button data-p="${r.a.id}" class="pname linkish">${esc(r.a.name)}</button> <span class="muted">${T[r.a.team].short}</span> + <button data-p="${r.b.id}" class="pname linkish">${esc(r.b.name)}</button> <span class="muted">${T[r.b.team].short}</span></td><td class="n">${r.cost.toFixed(1)}</td><td class="n"><b>${f1(r.tot)}</b> <span class="muted">(+${f1(r.tot - r.best1)})</span></td>${PG.map(g => { const w = who(r, g); return `<td>${esc(w.name)} <span class="muted">${f1(xpg(w.id, g))}</span></td>`; }).join("")}</tr>`).join("")}</tbody></table></div>` : `<p class="muted">No regular starters at this price.</p>`;
  return `<div class="panel"><div class="bar"><h3>Rotation planner</h3>
      <div class="fx-controls"><div class="seg" role="group" aria-label="Position">${Object.keys(ROT_CAPS).map(k => `<button data-rotpos="${k}" aria-pressed="${pos === k}">${k}</button>`).join("")}</div>
      <div class="seg" role="group" aria-label="Price each">${caps.map(c => `<button data-rotcap="${c}" aria-pressed="${cap === c}">≤ £${c.toFixed(1)}m</button>`).join("")}</div></div></div>
    <p class="note" style="margin-top:0">Two players from different clubs sharing one slot: start whichever has the better fixture each week. "xP rotating" is what the pair projects over ${PG.length} GWs, with how much that beats just starting the better one every week. Regular starters (nailed 70+) only.</p>
    ${tbl(pairs.slice(0, 6))}
    ${partners.length ? `<h3 style="margin:14px 0 6px">A partner for your ${pos === "GKP" ? "keepers" : pos === "DEF" ? "defenders" : pos === "MID" ? "midfielders" : "forwards"}</h3>
      <ul class="alerts">${partners.map(r => `<li class="${r.gain >= 1 ? "good" : ""}"><span><b>${esc(r.m.name)}</b> + <button data-p="${r.p.id}" class="linkish">${esc(r.p.name)}</button> <span class="muted">${T[r.p.team].short} · ${money(r.p.price)}</span> · rotating projects <b>${f1(r.tot)}</b>, <span class="${r.gain > 0 ? "up" : ""}">${sgn(r.gain)}</span> vs starting ${esc(r.m.name)} every week</span></li>`).join("")}</ul>` : ""}</div>`;
}

/* ---------- out of position: FPL position vs where they actually play ---------- */
function oopHTML() {
  const g0 = PG[0], xf = id => xpFrom(id, g0, PG.length);
  const play = u => (u || "").replace(/S/g, "").trim();
  const role = u => ({ D: "defender", M: "midfielder", F: "forward", GK: "keeper" })[play(u).split(" ").filter(Boolean)[0]] || "–";
  const roles = u => play(u).split(" ").filter(Boolean).map(x => ({ D: "D", M: "M", F: "F" })[x] || x).join("/");
  const defs = D.players.filter(p => p.pos === "DEF" && /[MF]/.test(play(p.upos)) && p.mins > 0).sort((a, b) => xf(b.id) - xf(a.id)).slice(0, 10);
  const mids = D.players.filter(p => p.pos === "MID" && /F/.test(play(p.upos)) && p.mins > 0).sort((a, b) => xf(b.id) - xf(a.id)).slice(0, 10);
  // and simply the defenders who attack most, whatever Understat calls them
  const atk = D.players.filter(p => p.pos === "DEF" && p.nailed >= 60 && p.mins >= 270).sort((a, b) => b.xgi90 - a.xgi90).slice(0, 8);
  const avgDef = (() => { const ds = D.players.filter(p => p.pos === "DEF" && p.mins >= 270); return ds.reduce((s2, p) => s2 + p.xgi90, 0) / Math.max(1, ds.length); })();
  const row = p => `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td><button data-p="${p.id}" class="pname linkish">${esc(p.name)}</button> <span class="muted">${T[p.team].short}</span></td><td class="n">${p.price.toFixed(1)}</td><td>${roles(p.upos) || "–"}</td><td class="n"><b>${p.xgi90.toFixed(2)}</b></td><td class="n">${p.xgi90_4.toFixed(2)}</td><td class="n">${(p.us?.sib90 ?? 0).toFixed(1)}</td><td class="n">${nailedPill(p)}</td><td class="n">${f1(xf(p.id))}</td></tr>`;
  const tbl = list => list.length ? `<div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th><th>${term("oop", "Plays as")}</th><th class="n">xGI/90</th><th class="n">L4</th><th class="n">In box/90</th><th class="n">Nailed</th><th class="n">xP ${PG.length}</th></tr></thead><tbody>${list.map(row).join("")}</tbody></table></div>` : '<p class="muted">None this season so far.</p>';
  return `<div class="panel"><h3>Out of position</h3>
    <p class="note" style="margin-top:0">Players FPL lists in one position who also play further forward. Defenders who play in midfield score attacking returns but still get 4 points for a clean sheet and 6 per goal, which makes them some of the best value in the game. Positions are from Understat (D defender, M midfielder, F forward).</p>
    <div class="statgrid"><div><h3 style="font-size:16px;margin:4px 0 6px">Defenders who play further forward</h3>${tbl(defs)}</div>
      <div><h3 style="font-size:16px;margin:4px 0 6px">Midfielders who play up front</h3>${tbl(mids)}</div></div>
    <h3 style="font-size:16px;margin:14px 0 6px">Most attacking defenders</h3><p class="note" style="margin-top:0">Ranked by expected goals + assists per 90 (regular starters). The average defender gets ${avgDef.toFixed(2)}.</p>${tbl(atk)}</div>`;
}
