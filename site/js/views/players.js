// Player explorer.
/* ---------- Players ---------- */
const COLS = [["name", "Player", 0], ["team", "Team", 0], ["pos", "Pos", 0], ["price", "£m", 1], ["own", "Own %", 1], ["pts", "Pts", 1],
  ["xgi90_4", "xGI/90 L4", 1], ["t10k", "Top 10k", 1], ["nailed", "Nailed", 1], ["xmin", "xMins", 1], ["xp1", "xP next", 1], ["xp5", "xP 5", 1], ["val", "xP5/£m", 1], ["pc", "Price", 1]];
function nailedPill(p) {
  const n = p.nailed ?? 0, c = n >= 85 ? "good" : n >= 60 ? "warn" : "bad";
  return `<span class="pill ${c}" title="${esc(p.mflag || (n >= 85 ? "Nailed on" : n >= 60 ? "Usually starts" : "Rotation or bench risk"))}">${n}</span>`;
}
const COLTERM = { xgi90_4: "xgi", nailed: "nailed", xmin: "xmins", xp1: "xp", xp5: "xp" };
function priceCell(p) {
  const v = p.price_proj?.[0]; if (v == null) return "–";
  const w = Math.min(100, Math.abs(v)) * 0.5;
  return `<span class="minibar ${v < 0 ? "neg" : ""}" style="width:${w}px" title="${v.toFixed(0)}% towards a ${v < 0 ? "fall" : "rise"}"></span> <span class="mono">${v.toFixed(0)}%</span>`;
}
function vPlayers() {
  let rows = D.players.slice();
  if (S.pos !== "ALL") rows = rows.filter(p => p.pos === S.pos);
  if (S.team !== "ALL") rows = rows.filter(p => String(p.team) === String(S.team));
  if (S.maxp) rows = rows.filter(p => p.price <= +S.maxp);
  if (S.q) { const q = S.q.toLowerCase(); rows = rows.filter(p => (p.name + " " + p.full).toLowerCase().includes(q)); }
  const t10 = p => D.crowd?.top10k.own[p.id] || 0;
  const val = p => S.sort === "t10k" ? t10(p) : S.sort === "val" ? p.xp5 / p.price : S.sort === "team" ? T[p.team].short : S.sort === "pc" ? (p.price_proj?.[0] ?? 0) : p[S.sort];
  rows.sort((a, b) => { const x = val(a), y = val(b); return (x > y ? 1 : x < y ? -1 : 0) * S.dir; });
  const shown = rows.slice(0, 150);
  const teamOpts = Object.values(T).sort((a, b) => a.name.localeCompare(b.name)).map(t => `<option value="${t.id}" ${String(S.team) === String(t.id) ? "selected" : ""}>${t.name}</option>`).join("");
  return `<div class="panel"><div class="bar"><h2>Players</h2><span class="muted">${rows.length} players${rows.length > 150 ? " · top 150 shown" : ""}</span></div>
    <div class="filters">
      <input type="search" id="q" placeholder="Search players" value="${esc(S.q)}" aria-label="Search players">
      <select id="fpos" aria-label="Position">${["ALL", "GKP", "DEF", "MID", "FWD"].map(x => `<option ${S.pos === x ? "selected" : ""} value="${x}">${x === "ALL" ? "All positions" : x}</option>`).join("")}</select>
      <select id="fteam" aria-label="Team"><option value="ALL">All teams</option>${teamOpts}</select>
      <select id="fmax" aria-label="Max price"><option value="">Any price</option>${[4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 9, 10, 12].map(x => `<option ${+S.maxp === x ? "selected" : ""} value="${x}">≤ £${x.toFixed(1)}m</option>`).join("")}</select>
    </div>
    ${compareHTML()}
    <div class="tablebox" style="max-height:70vh"><table><thead><tr><th>Cmp</th>${COLS.map(([k, l, n]) => `<th class="sort ${n ? "n" : ""}" data-sort="${k}" ${S.sort === k ? `aria-sort="${S.dir < 0 ? "descending" : "ascending"}"` : ""}>${COLTERM[k] ? term(COLTERM[k], l) : l}${S.sort === k ? (S.dir < 0 ? " ↓" : " ↑") : ""}</th>`).join("")}</tr></thead>
    <tbody>${shown.map(p => `<tr class="${MINE.has(p.id) ? "mine" : ""}">
      <td><input type="checkbox" data-cmp="${p.id}" ${S.cmp.includes(p.id) ? "checked" : ""} aria-label="Compare ${esc(p.name)}"></td>
      <td><button data-p="${p.id}" style="all:unset;cursor:pointer" class="pname">${esc(p.name)}</button>${p.status !== "a" ? ` <span class="pill ${p.status === "d" ? "warn" : "bad"}" title="${esc(p.news)}">${p.chance ?? 0}%</span>` : ""}</td>
      <td>${T[p.team].short}</td><td>${p.pos}</td><td class="n">${p.price.toFixed(1)}</td><td class="n">${p.own.toFixed(1)}</td><td class="n">${p.pts}</td>
      <td class="n">${p.xgi90_4.toFixed(2)}</td><td class="n">${D.crowd ? t10(p).toFixed(0) + "%" : "–"}</td><td class="n">${nailedPill(p)}</td><td class="n">${p.xmin}</td><td class="n">${f1(p.xp1)}</td><td class="n"><b>${f1(p.xp5)}</b></td><td class="n">${(p.xp5 / p.price).toFixed(2)}</td><td class="n">${priceCell(p)}</td></tr>`).join("")}</tbody></table></div>
    <p class="note">Gold edge = in your squad. Nailed = how sure a player is to start and play most of the game (0–100). xGI/90 L4 = expected goal involvement per 90 over the last 4 gameweeks. Price = progress towards a price change at the next update${(D.meta.price_deadlines || []).find(d => new Date(d) > new Date()) ? ` (around ${ukTime(D.meta.price_deadlines.find(d => new Date(d) > new Date()))})` : ""}. Tick up to 4 players to compare; charts appear in Stats.</p></div>`;
}
function compareHTML() {
  if (!S.cmp.length) return "";
  const ps = S.cmp.map(i => P[i]).filter(Boolean);
  const stats = [["Price", p => p.price, -1, money], ["xP next", p => p.xp1, 1, f1], ["xP next 5", p => p.xp5, 1, f1], ["xGI/90 L4", p => p.xgi90_4, 1, x => x.toFixed(2)], ["xGI/90 model", p => p.xgi90, 1, x => x.toFixed(2)], ["xMins", p => p.xmin, 1, x => x], ["Points", p => p.pts, 1, x => x], ["Goals − xG", p => p.g_xg, 0, x => (x > 0 ? "+" : "") + x.toFixed(1)], ["Owned", p => p.own, 0, x => x.toFixed(1) + "%"], ["DC chance", p => p.dc_rate * 100, 1, x => x.toFixed(0) + "%"], ["In box/90", p => p.us?.sib90 ?? 0, 1, x => x.toFixed(1)], ["Big ch/90", p => p.us?.bc90 ?? 0, 1, x => x.toFixed(2)], ["Created/90", p => p.us?.cc90 ?? 0, 1, x => x.toFixed(1)], ["BPS/90 L4", p => p.bf4?.bps90 ?? 0, 1, x => x.toFixed(0)]];
  return `<div class="compare" style="margin-bottom:12px">${ps.map(p => `<div class="cmp"><div class="bar" style="margin:0"><b>${esc(p.name)}</b><button class="btn" data-uncmp="${p.id}" aria-label="Remove">✕</button></div>
    <span class="muted">${T[p.team].short} · ${p.pos}</span>
    <dl>${stats.map(([l, fn, dir, fmt]) => { const vals = ps.map(fn), best = dir === 1 ? Math.max(...vals) : dir === -1 ? Math.min(...vals) : null, v = fn(p); return `<dt>${l}</dt><dd class="${ps.length > 1 && best === v ? "best" : ""}">${fmt(v)}</dd>`; }).join("")}</dl></div>`).join("")}</div>`;
}
