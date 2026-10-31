// Stats: Goals & assists leaders, the DefCon table and the Season race chart.
// All three read per-player detail from data-extra.json (us, dcs, ga6, s_pts). When a player's detail is missing
// (the file didn't load, or he isn't in it) he is left out and the panel says how many were left out: never a 0.

/* ---------- small shared controls ---------- */
// max-price filter: "" = any price
const PRICE_CAPS = ["", 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 10.0];
function priceSel(key, label = "Max price") {
  const v = S[key] ?? "";
  return `<select class="sel" data-sset="${key}" aria-label="${label}">${PRICE_CAPS.map(c => `<option value="${c}" ${String(v) === String(c) ? "selected" : ""}>${c === "" ? "Any price" : `≤ £${c.toFixed(1)}m`}</option>`).join("")}</select>`;
}
const underCap = (p, key) => S[key] === "" || S[key] == null || p.price <= +S[key];
// sortable header; the column sorts high to low
function sortTh(key, col, label, title = "") {
  const on = (S[key] || "") === col;
  return `<th class="sort n" data-ssort="${key}:${col}" ${on ? 'aria-sort="descending"' : ""} ${title ? `title="${esc(title)}"` : ""}>${label}${on ? " ↓" : ""}</th>`;
}
const pcell = p => `<td><button data-p="${p.id}" class="pname linkish">${esc(p.name)}</button> <span class="muted">${T[p.team].short} ${p.pos}</span></td>`;
const leftOut = (n, what) => n ? `<p class="note">${n} player${n === 1 ? "" : "s"} left out: no ${what} in this build.</p>` : "";

/* ---------- Goals & assists ---------- */
// window: whole season (FPL totals, include live matches) or the last 6 gameweeks (ga6, finished matches only)
function gaRows() {
  const l6 = S.gaWin === "l6";
  const pool = D.players.filter(p => posMatch(p, S.gaPos || "ALL") && p.pos !== "GKP" && underCap(p, "gaMax"));
  let missing = 0;
  const rows = pool.map(p => {
    if (l6 && !p.ga6) { missing++; return null; }
    const w = l6 ? p.ga6 : { g: p.goals, a: p.assists, xg: p.xg, xa: p.xa, mins: p.mins };
    return { p, ...w, gi: w.g + w.a, xgi: w.xg + w.xa };
  }).filter(Boolean);
  return { rows, missing };
}
function gaWindowText() {
  const cur = D.meta.cur_gw, from = Math.max(1, cur - 5);
  if (S.gaWin !== "l6") return "Season so far";
  return `GW${from}–${cur}${D.meta.cur_finished ? "" : ` (GW${cur}: finished matches only)`}`;
}
function gaBars(rows, metric) {
  const val = { gi: r => r.gi, g: r => r.g, a: r => r.a }[metric];
  const exp = { gi: r => r.xgi, g: r => r.xg, a: r => r.xa }[metric];
  const lab = { gi: ["G+A", "xGI"], g: ["Goals", "xG"], a: ["Assists", "xA"] }[metric];
  const top = rows.filter(r => val(r) > 0).sort((a, b) => val(b) - val(a) || exp(b) - exp(a)).slice(0, 12);
  if (!top.length) return `<p class="muted">Nobody has a ${lab[0].toLowerCase()} with these filters yet.</p>`;
  const mx = Math.max(...top.map(r => Math.max(val(r), exp(r))), 1);
  const pc = v => (100 * v / mx).toFixed(1) + "%";
  return `<div class="legend ga-legend"><span><i class="ga-key-act"></i>${lab[0]} (actual)</span><span><i class="ga-key-exp"></i>${lab[1]} (expected)</span></div>
    <ol class="gabars" aria-label="${lab[0]} leaders, actual against expected">${top.map(r => {
      const d = val(r) - exp(r);
      return `<li class="${MINE.has(r.p.id) ? "mine" : ""}" title="${esc(`${r.p.name}: ${val(r)} ${lab[0]}, ${exp(r).toFixed(1)} ${lab[1]} (${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(1)})`)}">
        <button data-p="${r.p.id}" class="ga-name linkish">${esc(r.p.name)} <span class="muted">${T[r.p.team].short}</span></button>
        <span class="ga-track"><span class="ga-act" style="width:${pc(val(r))}"></span><span class="ga-exp" style="left:${pc(exp(r))}"></span></span>
        <span class="ga-val"><b>${val(r)}</b> <span class="muted">${exp(r).toFixed(1)}</span></span></li>`;
    }).join("")}</ol>`;
}
function gaHTML() {
  if (!S.gaWin) S.gaWin = "season";
  if (!S.gaMetric) S.gaMetric = "gi";
  if (!S.gaSort) S.gaSort = "gi";
  const { rows, missing } = gaRows();
  const l6 = S.gaWin === "l6", minM = l6 ? 180 : 270;
  const k = S.gaSort;
  const v = r => k === "gi90" ? (r.mins >= minM ? r.gi / r.mins * 90 : -1) : k === "diff" ? r.gi - r.xgi : r[k];
  const tbl = rows.slice().sort((a, b) => v(b) - v(a) || b.xgi - a.xgi).slice(0, 25);
  const num = (x, dp = 0) => dp ? x.toFixed(dp) : x;
  return `<div class="panel"><div class="bar"><h3>Goals and assists</h3>
      <div class="fx-controls">${posSeg("gaWin", [["season", "Season"], ["l6", "Last 6 GWs"]])}${posSeg("gaPos", [["ALL", "All"], ["DEF", "DEF"], ["MID", "MID"], ["FWD", "FWD"]])}${priceSel("gaMax")}</div></div>
    <p class="note" style="margin-top:0">${gaWindowText()}. Bars are what he actually scored or set up; the tick is what his chances were worth. A bar well past its tick is finishing above the chances, which rarely lasts. xG and xA are FPL's own expected stats (from Opta).</p>
    <div class="bar" style="margin-bottom:8px">${posSeg("gaMetric", [["gi", "G+A"], ["g", "Goals"], ["a", "Assists"]])}</div>
    ${gaBars(rows, S.gaMetric)}
    ${leftOut(missing, "last-6 data")}</div>
  <div class="panel"><h3>Leaders table</h3>
    <p class="note" style="margin-top:0">${gaWindowText()}. Tap a column to sort. Per 90 only counts players with ${minM}+ minutes in the window. +/− is goals plus assists minus xGI.</p>
    <div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th>${sortTh("gaSort", "mins", "Mins")}${sortTh("gaSort", "g", "G")}${sortTh("gaSort", "xg", "xG")}${sortTh("gaSort", "a", "A")}${sortTh("gaSort", "xa", "xA")}${sortTh("gaSort", "gi", "G+A")}${sortTh("gaSort", "xgi", "xGI")}${sortTh("gaSort", "diff", "+/−")}${sortTh("gaSort", "gi90", "G+A/90")}</tr></thead>
    <tbody>${tbl.map(r => { const d = r.gi - r.xgi; return `<tr class="${MINE.has(r.p.id) ? "mine" : ""}">${pcell(r.p)}<td class="n">${r.p.price.toFixed(1)}</td><td class="n">${r.mins}</td><td class="n">${r.g}</td><td class="n">${num(r.xg, 1)}</td><td class="n">${r.a}</td><td class="n">${num(r.xa, 1)}</td><td class="n"><b>${r.gi}</b></td><td class="n">${num(r.xgi, 1)}</td><td class="n ${d > 0.5 ? "up" : d < -0.5 ? "down" : ""}">${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(1)}</td><td class="n">${r.mins >= minM ? (r.gi / r.mins * 90).toFixed(2) : '<span class="muted" title="Fewer than ' + minM + ' minutes">–</span>'}</td></tr>`; }).join("") || '<tr><td colspan="11" class="muted">No players match these filters.</td></tr>'}</tbody></table></div></div>`;
}

/* ---------- Defensive contributions (DefCon) ---------- */
function dcHTML() {
  const f = S.dcPos || "DEF";
  const thr = f === "DEF" ? 10 : 12;
  if (!S.dcSort) S.dcSort = "next";
  // expected DC points next game: the model's (shrunk) chance of hitting the threshold x how nailed he is
  const exp = p => p.dc_rate * Math.min(1, p.nailed / 100);
  const pool = D.players.filter(p => posMatch(p, f) && p.pos !== "GKP" && underCap(p, "dcMax"));
  const missing = pool.filter(p => !p.dcs).length;
  const k = S.dcSort;
  const val = {
    next: exp, per90: p => p.dcs.per90, rate: p => p.dcs.hits / p.dcs.apps, pts: p => p.dcs.pts ?? -1,
    l6: p => p.dc6 ? p.dc6.hits / Math.max(1, p.dc6.apps) : -1, mins: p => p.dcs.mins ?? p.mins, nailed: p => p.nailed,
    xp: p => xpFrom(p.id, PG[0], PG.length),
  }[k] || exp;
  const rows = pool.filter(p => p.dcs && p.dcs.apps >= 4).sort((a, b) => val(b) - val(a) || exp(b) - exp(a)).slice(0, 25);
  const ptsCell = p => p.dcs.pts == null ? '<span class="muted" title="Not in this build">–</span>' : p.dcs.pts;
  return `<div class="panel"><div class="bar"><h3>Defensive contribution leaders</h3><div class="fx-controls">${posSeg("dcPos", [["DEF", "DEF"], ["MID", "MID"], ["FWD", "FWD"]])}${priceSel("dcMax")}</div></div>
    <p class="note" style="margin-top:0">A ${term("dc", "defensive contribution")} is worth 2 points: ${f === "DEF" ? "10 clearances, blocks, interceptions and tackles" : "12 clearances, blocks, interceptions, tackles and recoveries"} in a match. Hit rate = how often he reached it in games of 60+ minutes. Chance next = the model's estimate for his next game, allowing for small samples and how likely he is to start. DC points = what FPL actually gave him, including hits in shorter games. At least 4 games of 60+ minutes; tap a column to sort.</p>
    <div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th>${sortTh("dcSort", "mins", "Mins")}${sortTh("dcSort", "per90", `Per 90 (need ${thr})`)}${sortTh("dcSort", "rate", "Hit rate")}${sortTh("dcSort", "next", "Chance next")}${sortTh("dcSort", "pts", "DC points")}${sortTh("dcSort", "l6", "Last 6")}${sortTh("dcSort", "nailed", term("nailed", "Nailed"))}${sortTh("dcSort", "xp", `xP ${PG.length} GWs`)}</tr></thead>
    <tbody>${rows.map(p => `<tr class="${MINE.has(p.id) ? "mine" : ""}">${pcell(p)}<td class="n">${p.price.toFixed(1)}</td><td class="n">${p.dcs.mins ?? p.mins}</td><td class="n">${p.dcs.per90.toFixed(1)}</td><td class="n">${Math.round(100 * p.dcs.hits / p.dcs.apps)}% <span class="muted">(${p.dcs.hits}/${p.dcs.apps})</span></td><td class="n"><b>${Math.round(100 * exp(p))}%</b></td><td class="n">${ptsCell(p)}</td><td class="n">${p.dc6 ? `${p.dc6.hits}/${p.dc6.apps}` : "–"}</td><td class="n">${nailedPill(p)}</td><td class="n">${f1(xpFrom(p.id, PG[0], PG.length))}</td></tr>`).join("") || '<tr><td colspan="10" class="muted">No players with 4+ games of 60 minutes match these filters.</td></tr>'}</tbody></table></div>
    ${leftOut(missing, "defensive record")}</div>`;
}

/* ---------- Season race: running points total for the top 10 ---------- */
function raceData() {
  const pool = D.players.filter(p => posMatch(p, S.racePos || "ALL"));
  const missing = pool.filter(p => !Array.isArray(p.s_pts)).length;
  const top = pool.filter(p => Array.isArray(p.s_pts)).sort((a, b) => b.pts - a.pts || b.mins - a.mins).slice(0, 10);
  const ser = top.map(p => { let c = 0; return { p, cum: p.s_pts.map(v => (c += v)) }; });
  return { ser, missing };
}
// drawn at the width it will be shown, so its text stays at its real size on a phone (a fixed 640-wide drawing
// scaled down to a 390px screen makes 14px labels about 7px)
function raceGeom() {
  const box = $("#app")?.clientWidth || 640, W = Math.round(Math.max(300, Math.min(900, box - 40)));
  const narrow = W < 480;
  return { W, H: narrow ? 240 : 300, pad: { l: 34, r: narrow ? 92 : 112, t: 14, b: 28 }, narrow };
}
function raceChart(ser, sel) {
  const cur = D.meta.cur_gw, live = !D.meta.cur_finished;
  const { W, H, pad, narrow } = raceGeom();
  const mx = Math.max(10, ...ser.flatMap(s => s.cum));
  const step = mx <= 50 ? 10 : mx <= 120 ? 20 : mx <= 250 ? 50 : 100, top = Math.ceil(mx / step) * step;
  const x = i => pad.l + (cur <= 1 ? 0 : i / (cur - 1)) * (W - pad.l - pad.r);
  const y = v => pad.t + (1 - v / top) * (H - pad.t - pad.b);
  const ticks = []; for (let v = 0; v <= top; v += step) ticks.push(v);
  const every = cur > 19 ? 4 : cur > 12 ? 2 : 1;
  const pts = (cum, from, to) => cum.slice(from, to).map((v, i) => `${x(from + i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const done = live ? cur - 1 : cur;   // last fully counted GW (index + 1)
  // draw order: others, then yours, then the selected line on top
  const order = ser.slice().sort((a, b) => (a.p.id === sel) - (b.p.id === sel) || MINE.has(a.p.id) - MINE.has(b.p.id));
  const line = s => {
    const c = s.p.id === sel ? "race-sel" : MINE.has(s.p.id) ? "race-mine" : "race-other";
    return `<g class="race-line ${c}" data-race="${s.p.id}">
      <polyline points="${pts(s.cum, 0, done)}"/>${live && cur > 1 ? `<polyline class="race-live" points="${pts(s.cum, done - 1, cur)}"/>` : ""}
      <polyline class="race-hit" points="${pts(s.cum, 0, cur)}" data-racesel="${s.p.id}"><title>${esc(s.p.name)}</title></polyline>
      <circle cx="${x(cur - 1)}" cy="${y(s.cum[cur - 1])}" r="${s.p.id === sel ? 4.5 : 3}"/></g>`;
  };
  // end labels: the selected player and your players, nudged apart so they don't overlap
  const labs = order.filter(s => s.p.id === sel || MINE.has(s.p.id)).map(s => ({ s, yy: y(s.cum[cur - 1]) })).sort((a, b) => a.yy - b.yy);
  for (let i = 1; i < labs.length; i++) labs[i].yy = Math.max(labs[i].yy, labs[i - 1].yy + (narrow ? 14 : 16));
  return `<div class="race-wrap"><svg class="chart race${narrow ? " narrow" : ""}" data-w="${W}" data-pl="${pad.l}" data-pr="${pad.r}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Running points total by gameweek for the top ${ser.length} players. The table below lists the same totals.">
    ${ticks.map(v => `<line class="grid" x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${pad.l - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`).join("")}
    ${Array.from({ length: cur }, (_, i) => (i % every === 0 || i === cur - 1) ? `<text x="${x(i)}" y="${H - 9}" text-anchor="middle">${i + 1}${live && i === cur - 1 ? "*" : ""}</text>` : "").join("")}
    <line class="race-cross" x1="0" x2="0" y1="${pad.t}" y2="${H - pad.b}" visibility="hidden"/>
    ${order.map(line).join("")}
    ${labs.map(({ s, yy }) => `<text class="race-lab ${s.p.id === sel ? "on" : ""}" x="${x(cur - 1) + 9}" y="${yy + 4}">${esc(s.p.name)} ${s.cum[cur - 1]}</text>`).join("")}
  </svg><div class="race-tip" hidden></div></div>`;
}
function raceHTML() {
  const { ser, missing } = raceData();
  const cur = D.meta.cur_gw, live = !D.meta.cur_finished;
  if (!ser.length) return `<div class="panel"><h3>Season race</h3><p class="muted">No gameweek points in this build yet${missing ? ` (${missing} players have no per-gameweek data)` : ""}.</p></div>`;
  if (!ser.some(s => s.p.id === S.raceSel)) S.raceSel = (ser.find(s => MINE.has(s.p.id)) || ser[0]).p.id;
  const sel = ser.find(s => s.p.id === S.raceSel);
  const gw = sel.p.s_pts, gmx = Math.max(1, ...gw);
  return `<div class="panel"><div class="bar"><h3>Season race</h3>${posSeg("racePos", [["ALL", "All"], ["GKP", "GKP"], ["DEF", "DEF"], ["MID", "MID"], ["FWD", "FWD"]])}</div>
    <p class="note" style="margin-top:0">Running FPL points total for the top ${ser.length} ${S.racePos && S.racePos !== "ALL" ? S.racePos : "players"}, gameweek by gameweek. Tap a name or a line to follow one player; hover or tap the chart to see everyone at that gameweek.${live ? ` *GW${cur} is in progress: the chart counts finished matches only, while FPL total includes live points.` : ""}</p>
    <div class="legend"><span><i class="race-key-sel"></i>Selected</span><span><i class="race-key-mine"></i>Your players</span><span><i class="race-key-other"></i>Others</span></div>
    ${raceChart(ser, S.raceSel)}
    <div class="race-grid">
      <ol class="race-list" aria-label="Top ${ser.length} by FPL total">${ser.map((s, i) => `<li><button type="button" data-racesel="${s.p.id}" aria-pressed="${s.p.id === S.raceSel}">
        <span class="race-rank">${i + 1}</span><i class="race-sw ${s.p.id === S.raceSel ? "race-key-sel" : MINE.has(s.p.id) ? "race-key-mine" : "race-key-other"}"></i>
        <span class="race-nm">${esc(s.p.name)} <span class="muted">${T[s.p.team].short} ${s.p.pos}</span>${MINE.has(s.p.id) ? ' <span class="pill good">Yours</span>' : ""}</span>
        <span class="race-tot"><b>${s.p.pts}</b>${s.cum[cur - 1] !== s.p.pts ? ` <span class="muted" title="Chart total, finished matches only">(${s.cum[cur - 1]})</span>` : ""}</span></button></li>`).join("")}</ol>
      <div><span class="lbl">${esc(sel.p.name)}: points per gameweek</span>
        <div class="gwbars race-bars">${gw.map((v, i) => `<div title="GW${i + 1}: ${v} pts">${v}<i style="height:${Math.max(2, 70 * Math.max(0, v) / gmx)}px"></i>${i + 1}${live && i === cur - 1 ? "*" : ""}</div>`).join("")}</div>
        <p class="note">${esc(sel.p.full)} · ${money(sel.p.price)} · ${sel.p.mins} minutes · <button class="linkish" data-p="${sel.p.id}">Player details</button></p></div>
    </div>
    <p class="note">Ranked by FPL total${live ? "; a number in brackets is the chart's total so far" : ""}.</p>
    ${leftOut(missing, "per-gameweek points")}</div>`;
}
// crosshair + tooltip on the race chart (pointer and touch), and line taps to select
function bindRace() {
  const svg = $("#app svg.race"); if (!svg) return;
  const tip = $("#app .race-tip"), cross = svg.querySelector(".race-cross");
  const { ser } = raceData(), cur = D.meta.cur_gw;
  const W = +svg.dataset.w, pad = { l: +svg.dataset.pl, r: +svg.dataset.pr };
  const show = e => {
    const r = svg.getBoundingClientRect(), sx = (e.clientX - r.left) / r.width * W;
    const i = Math.max(0, Math.min(cur - 1, Math.round((sx - pad.l) / Math.max(1, W - pad.l - pad.r) * (cur - 1))));
    const xx = pad.l + (cur <= 1 ? 0 : i / (cur - 1)) * (W - pad.l - pad.r);
    cross.setAttribute("x1", xx); cross.setAttribute("x2", xx); cross.setAttribute("visibility", "visible");
    const rows = ser.map(s => ({ s, v: s.cum[i], g: s.p.s_pts[i] })).sort((a, b) => b.v - a.v);
    tip.innerHTML = `<b>After GW${i + 1}${!D.meta.cur_finished && i === cur - 1 ? " (so far)" : ""}</b>${rows.map(({ s, v, g }) => `<div class="${s.p.id === S.raceSel ? "on" : MINE.has(s.p.id) ? "mine" : ""}"><span>${esc(s.p.name)}</span><span>${v} <span class="muted">(${g >= 0 ? "+" : ""}${g})</span></span></div>`).join("")}`;
    tip.hidden = false;
    const wrap = tip.parentElement.getBoundingClientRect(), px = xx / W * r.width;
    tip.style.left = (px > wrap.width / 2 ? Math.max(0, px - tip.offsetWidth - 12) : Math.min(wrap.width - tip.offsetWidth, px + 12)) + "px";
  };
  const hide = () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); };
  svg.addEventListener("pointermove", show);
  svg.addEventListener("pointerdown", show);
  svg.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") hide(); });
  document.querySelectorAll("#app [data-racesel]").forEach(el => el.addEventListener("click", () => { S.raceSel = +el.dataset.racesel; render(); }));
}

/* ---------- controls shared by these tabs ---------- */
function bindStatsMore() {
  document.querySelectorAll("#app [data-ssort]").forEach(th => th.onclick = e => {
    if (e.target.closest(".term")) return;   // the "Nailed" header's explainer, not a sort
    const [k, v] = th.dataset.ssort.split(":"); S[k] = v; render();
  });
  document.querySelectorAll("#app [data-sset]").forEach(el => el.onchange = () => { S[el.dataset.sset] = el.value; render(); });
  bindRace();
}
// redraw the race chart when the screen width changes enough to matter (phone rotated, window resized)
{ let lastW = 0, t;
  addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => {
    const svg = $("#app svg.race"); if (!svg) return;
    const w = raceGeom().W; if (Math.abs(w - (lastW || +svg.dataset.w)) > 40) { lastW = w; render(); }
  }, 200); });
}
