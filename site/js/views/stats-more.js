// Stats: Goals & assists leaders, the DefCon table and the Points leaders table.
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
function sortTh(key, col, label, title = "", cls = "") {
  const on = (S[key] || "") === col;
  return `<th class="sort n ${cls}" data-ssort="${key}:${col}" ${on ? 'aria-sort="descending"' : ""} ${title ? `title="${esc(title)}"` : ""}>${label}${on ? " ↓" : ""}</th>`;
}
// Filter and sort choices are remembered on this device. A saved value that isn't one of the current options (an
// older build, a renamed column) is dropped, so the tab falls back to its normal default rather than a broken view.
const STATS_PREFS = {
  gaWin: ["season", "l6"], gaPos: ["ALL", "DEF", "MID", "FWD"], gaMetric: ["gi", "g", "a"],
  gaSort: ["mins", "g", "xg", "a", "xa", "gi", "xgi", "diff", "gi90"],
  dcPos: ["DEF", "MID", "FWD"], dcSort: ["next", "per90", "rate", "pts", "l6", "mins", "nailed", "xp"],
  ldPos: ["ALL", "GKP", "DEF", "MID", "FWD"], ldSort: ["price", "starts", "mins", "own", "pts", "goals", "assists", "gi", "dd", "bonus"],
  gaMax: PRICE_CAPS.map(String), dcMax: PRICE_CAPS.map(String), ldMax: PRICE_CAPS.map(String),
};
{ const saved = store.get("fpl.statsf") || {};
  for (const [k, ok] of Object.entries(STATS_PREFS)) if (saved[k] != null && ok.includes(String(saved[k]))) S[k] = String(saved[k]); }
function saveStatsPrefs() {
  const o = {}; for (const k of Object.keys(STATS_PREFS)) if (S[k] != null) o[k] = S[k];
  store.set("fpl.statsf", o);
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

/* ---------- Points leaders: top 10 for any column ---------- */
// Season totals from FPL (they include matches being played now), apart from DD hauls, which count gameweeks of 10+
// points from s_pts (finished matches only, so a live gameweek can still add one). Starts comes from FPL's season
// figure; a build without it shows "–" in that column, never 0. A player with no s_pts shows "–" for DD hauls and
// sorts last on it.
const LEAD_COLS = [
  ["price", "Price", p => p.price, false], ["starts", "Starts", p => p.starts ?? null, false],
  ["mins", "Mins", p => p.mins, true], ["own", "Own %", p => p.own, true], ["pts", "Pts", p => p.pts, true],
  ["goals", "Gls", p => p.goals, true], ["assists", "Ast", p => p.assists, true], ["gi", "G+A", p => p.goals + p.assists, true],
  ["dd", "DD hauls", p => Array.isArray(p.s_pts) ? p.s_pts.filter(v => v >= 10).length : null, true],
  ["bonus", "Bonus", p => p.bonus, true],
];
function leadersHTML() {
  if (!S.ldSort || !LEAD_COLS.some(c => c[0] === S.ldSort)) S.ldSort = "pts";
  const col = LEAD_COLS.find(c => c[0] === S.ldSort), val = col[2];
  const pts = LEAD_COLS.find(c => c[0] === "pts")[2];
  const pool = D.players.filter(p => posMatch(p, S.ldPos || "ALL") && underCap(p, "ldMax"));
  const rows = pool.slice().sort((a, b) => (val(b) ?? -1) - (val(a) ?? -1) || pts(b) - pts(a) || b.mins - a.mins).slice(0, 10);
  // shading: each column against its own best among the ten shown (0 = no shade)
  const top = Object.fromEntries(LEAD_COLS.map(([k, , f]) => [k, Math.max(0, ...rows.map(p => f(p) ?? 0))]));
  const fmt = (k, v) => v == null ? '<span class="muted" title="Not in this build">–</span>' : k === "price" ? money(v) : k === "own" ? v.toFixed(1) : v;
  const td = (p, [k, , f, heat], cls = "") => {
    const v = f(p);
    if (!heat || v == null) return `<td class="n ${cls}">${fmt(k, v)}</td>`;
    const lvl = top[k] > 0 && v > 0 ? Math.max(1, Math.round(5 * v / top[k])) : 0;
    return `<td class="n ${cls}"><span class="hpill h${lvl}">${fmt(k, v)}</span></td>`;
  };
  const ptsCol = LEAD_COLS.find(c => c[0] === "pts");
  const live = !D.meta.cur_finished;
  const posTxt = { ALL: "players", GKP: "goalkeepers", DEF: "defenders", MID: "midfielders", FWD: "forwards" }[S.ldPos || "ALL"];
  return `<div class="panel"><div class="bar"><h3>Points leaders</h3><div class="fx-controls">${posSeg("ldPos", [["ALL", "All"], ["GKP", "GKP"], ["DEF", "DEF"], ["MID", "MID"], ["FWD", "FWD"]])}${priceSel("ldMax")}</div></div>
    <p class="note" style="margin-top:0">Top 10 ${posTxt} by ${col[1] === "Pts" ? "FPL points" : col[1]} this season. Tap any column to rank by it. Shading compares each column within the ten shown. DD hauls = gameweeks of 10+ points${live ? `; GW${D.meta.cur_gw} counts finished matches only so far` : ""}.</p>
    <div class="tablebox leaders"><table><thead><tr><th class="sticky-col">Player</th>${sortTh("ldSort", "pts", "Pts", "", "ph-only")}${LEAD_COLS.map(([k, l]) => sortTh("ldSort", k, l, "", k === "pts" ? "desk-only" : "")).join("")}</tr></thead>
    <tbody>${rows.map(p => { const star = isStarred(p.id); return `<tr class="${MINE.has(p.id) ? "mine" : ""}"><td class="sticky-col"><div class="ld-player">
      <button type="button" class="xstar" data-xstar="${p.id}" aria-pressed="${star}" aria-label="${star ? "Remove" : "Add"} ${esc(p.name)} ${star ? "from" : "to"} starred players">${star ? "★" : "☆"}</button>
      <img class="ld-photo" src="${photoURL(p)}" alt="" loading="lazy" onerror="if(!this.dataset.f){this.dataset.f=1;this.src=PHOTO_BASE+'/placeholder.png'}else this.style.visibility='hidden'">
      <span class="ld-nm"><button data-p="${p.id}" class="pname linkish"><span class="nm-full">${esc(p.full.length > 22 ? p.name : p.full)}</span><span class="nm-short">${esc(p.name)}</span></button><span class="muted">${T[p.team].short} <span class="pill">${p.pos}</span>${MINE.has(p.id) ? ' <span class="pill good ld-yours">Yours</span>' : ""}</span></span></div></td>${td(p, ptsCol, "ph-only")}${LEAD_COLS.map(c => td(p, c, c[0] === "pts" ? "desk-only" : "")).join("")}</tr>`; }).join("") || `<tr><td colspan="${LEAD_COLS.length + 2}" class="muted">No players match these filters.</td></tr>`}</tbody></table></div></div>`;
}

/* ---------- controls shared by these tabs ---------- */
function statsTabsRow() {
  const row = $("#app .stats-nav .ptabs"); if (!row) return;
  const edge = () => { row.classList.toggle("more-r", row.scrollLeft + row.clientWidth < row.scrollWidth - 4); row.classList.toggle("more-l", row.scrollLeft > 4); };
  const on = row.querySelector('[aria-pressed="true"]');
  if (on && row.scrollWidth > row.clientWidth) row.scrollLeft = Math.max(0, on.offsetLeft - (row.clientWidth - on.offsetWidth) / 2);
  row.addEventListener("scroll", edge, { passive: true }); edge();
}
function bindStatsMore() {
  if (S.view === "stats") { saveStatsPrefs(); statsTabsRow(); }
  document.querySelectorAll("#app [data-ssort]").forEach(th => th.onclick = e => {
    if (e.target.closest(".term")) return;   // the "Nailed" header's explainer, not a sort
    const [k, v] = th.dataset.ssort.split(":"); S[k] = v; render();
  });
  document.querySelectorAll("#app [data-sset]").forEach(el => el.onchange = () => { S[el.dataset.sset] = el.value; render(); });
}
