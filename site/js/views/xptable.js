// Expected points table: every player's projected points per gameweek (players[].xp), like the FPL Review grid.
/* ---------- xP table ----------
   Missing data, shown rather than filled in:
   - a gameweek with a fixture but no xP for the player: "–" with a tooltip, left out of Σ / Avg / xP per £m, and the
     total is marked "*" with how many gameweeks it covers;
   - a blank gameweek (no fixture): the blank chip and "–"; it counts as 0 because he can't score;
   - xP resting on our defaults (no official return date or chance): italic with the "assumed" tooltip, as elsewhere;
   - live column with no pre-deadline snapshot (meta.xp_cur.status): "–" with the reason. A player absent from an
     existing snapshot (xp_cur_absent) was projected 0 (the snapshot keeps only players above 0): 0.0, saying so. */
S.xsort = store.get("fpl.xsort") || "sum";
S.xdir = store.get("fpl.xdir") === 1 ? 1 : -1;
S.xh = [3, 5, 6].includes(store.get("fpl.xh")) ? store.get("fpl.xh") : 5;
S.xagg = store.get("fpl.xagg") === "avg" ? "avg" : "sum";
S.xquick = ["all", "mine", "star"].includes(store.get("fpl.xquick")) ? store.get("fpl.xquick") : "all";
const xLiveShown = () => { const v = store.get("fpl.xlive"); return v == null ? !matchMedia("(max-width: 560px)").matches : !!v; };

const xLiveGW = () => {
  const m = D.meta;
  return m.cur_gw && !m.cur_finished && D.live && D.live.gw === m.cur_gw ? m.cur_gw : null;
};
// one player's numbers over the chosen horizon: {sum, avg, n (gameweeks with a number), of (gameweeks in horizon)}
function xTotals(p, gws) {
  let sum = 0, n = 0;
  gws.forEach(g => {
    const v = p.xp[g];
    if (v != null) { sum += v; n++; } else if (!fxFor(p.team, g).length) n++;   // blank: 0, and it is known
  });
  return { sum, avg: n ? sum / n : 0, n, of: gws.length };
}
function xLiveCell(p, lg) {
  const meta = D.meta.xp_cur;
  const started = (D.live.fixtures || []).some(f => (f.h === p.team || f.a === p.team) && f.started);
  const pts = started ? `<small class="xlive-pts" title="Live points so far, incl. provisional bonus">${D.live.pts_all?.[p.id] ?? 0} pts</small>` : "";
  let xp;
  if (p.xp_cur_absent) xp = `<span title="Projected 0 before the GW${lg} deadline (the snapshot only keeps players above 0; also the case for anyone signed after the deadline)">${f1(0)}</span>`;
  else if (p.xp_cur != null) xp = `<span title="Projected for GW${lg} before its deadline">${f1(p.xp_cur)}</span>`;
  else xp = `<span title="${esc(meta?.status || "No pre-deadline projections for this gameweek")}">–</span>`;
  return `<td class="n xlive">${xp}${pts}</td>`;
}
function vXpTable() {
  const gws = GWS, hz = gws.slice(0, S.xh), next = D.meta.next_gw, lg = xLiveGW(), showLive = lg && xLiveShown();
  let rows = D.players.slice();
  if (S.pos !== "ALL") rows = rows.filter(p => p.pos === S.pos);
  if (S.team !== "ALL") rows = rows.filter(p => String(p.team) === String(S.team));
  if (S.maxp) rows = rows.filter(p => p.price <= +S.maxp);
  if (S.q) { const q = S.q.toLowerCase(); rows = rows.filter(p => (p.name + " " + p.full).toLowerCase().includes(q)); }
  if (S.xquick === "mine") rows = rows.filter(p => MINE.has(p.id));
  if (S.xquick === "star") rows = rows.filter(p => isStarred(p.id));

  const tot = new Map(rows.map(p => [p.id, xTotals(p, hz)]));
  const key = p => {
    const t = tot.get(p.id);
    if (S.xsort === "name") return p.name;
    if (S.xsort === "price") return p.price;
    if (S.xsort === "val") return t.sum / p.price;
    if (S.xsort === "live") return p.xp_cur ?? -1;
    if (S.xsort.startsWith("g")) return p.xp[S.xsort.slice(1)] ?? -1;
    return S.xagg === "avg" ? t.avg : t.sum;
  };
  rows.sort((a, b) => { const x = key(a), y = key(b); return (x > y ? 1 : x < y ? -1 : 0) * S.xdir; });
  const shown = rows.slice(0, 150);

  // heat scale between the 5th and 95th percentile of the numbers on screen, so one player can't flatten it
  const vals = shown.flatMap(p => hz.map(g => p.xp[g]).filter(v => v != null)).sort((a, b) => a - b);
  const q = f => vals.length ? vals[Math.min(vals.length - 1, Math.floor(f * vals.length))] : 0;
  const lo = q(0.05), hi = q(0.95);
  const heat = v => hi > lo ? Math.max(0, Math.min(5, Math.round((v - lo) / (hi - lo) * 5))) : 0;
  const barMax = Math.max(1e-9, ...shown.map(p => S.xagg === "avg" ? tot.get(p.id).avg : tot.get(p.id).sum));

  const sortAttr = k => S.xsort === k ? ` aria-sort="${S.xdir < 0 ? "descending" : "ascending"}"` : "";
  const arrow = k => S.xsort === k ? (S.xdir < 0 ? " ↓" : " ↑") : "";
  const head = `<th class="sort sticky-col" data-xsort="name"${sortAttr("name")}>Player${arrow("name")}</th>
    <th class="sort n xwide" data-xsort="price"${sortAttr("price")}>£${arrow("price")}</th>
    <th class="sort n xwide" data-xsort="val"${sortAttr("val")}>${term("xpm", "xP/£m")}${arrow("val")}</th>
    ${lg ? (showLive
      ? `<th class="sort n xlive" data-xsort="live"${sortAttr("live")}>GW${lg}${arrow("live")}<small>Live</small><button type="button" class="btn ghost xs" data-xlive="0" aria-label="Hide the GW${lg} live column">Hide</button></th>`
      : `<th class="n xlive-off"><button type="button" class="btn ghost xs" data-xlive="1" aria-label="Show the GW${lg} live column">GW${lg}</button></th>`) : ""}
    ${gws.map(g => `<th class="sort n xg${g === next ? " xnext" : ""}${hz.includes(g) ? "" : " xout"}" data-xsort="g${g}"${sortAttr("g" + g)}>GW${g}${arrow("g" + g)}${g === next ? "<small>Next</small>" : ""}</th>`).join("")}
    <th class="sort n xsum" data-xsort="sum"${sortAttr("sum")}>${S.xagg === "avg" ? "Avg xP" : "Σ xP"}${arrow("sum")}
      <button type="button" class="btn ghost xs" data-xagg="${S.xagg === "avg" ? "sum" : "avg"}" aria-label="Show ${S.xagg === "avg" ? "the total" : "the average per gameweek"}">${S.xagg === "avg" ? "Σ" : "Avg"}</button></th>`;

  const body = shown.map(p => {
    const t = tot.get(p.id), part = t.n < t.of;
    const v = S.xagg === "avg" ? t.avg : t.sum;
    const star = isStarred(p.id);
    const gwCells = gws.map(g => {
      const fx = fxFor(p.team, g), x = p.xp[g], out = hz.includes(g) ? "" : " xout";
      const chips = fx.length ? fx.map(f => fdrChip(f, { gw: g, size: "xs" })).join("") : blankChip(g);
      const dgw = fx.length > 1 ? `<span class="xdgw" title="Double gameweek: the number is both matches together">DGW</span>` : "";
      if (!fx.length) return `<td class="n xc${out}"><span class="xfx">${chips}</span><b class="xv">–</b></td>`;
      if (x == null) return `<td class="n xc${out}"><span class="xfx">${chips}</span><b class="xv" title="No projection for this gameweek">–</b></td>`;
      const asm = isAsm(p.id, g);
      return `<td class="n xc h${heat(x)}${g === next ? " xnext" : ""}${out}"><span class="xfx">${chips}${dgw}</span><b class="xv${asm ? " asm" : ""}"${asm ? ` title="${ASM_TIP}"` : ""}>${f1(x)}</b></td>`;
    }).join("");
    return `<tr class="${MINE.has(p.id) ? "mine" : ""}">
      <td class="sticky-col"><span class="xplayer">
        <img class="shirt" src="${shirtURL(p)}" alt="" loading="lazy" onerror="this.remove()">
        <span class="xwho"><span class="xname"><button data-p="${p.id}" class="pname linkish">${esc(p.name)}</button>
          <button type="button" class="xstar" data-xstar="${p.id}" aria-pressed="${star}" aria-label="${star ? "Remove" : "Add"} ${esc(p.name)} ${star ? "from" : "to"} starred players">${star ? "★" : "☆"}</button>
          ${p.status !== "a" ? `<span class="pill ${p.status === "d" ? "warn" : "bad"}" title="${esc(p.news || "Flagged")}">${p.chance ?? 0}%</span>` : ""}</span>
          <span class="muted xmeta">${T[p.team].short} <span class="xpos">${p.pos}</span><span class="xprice"> · ${money(p.price)}</span></span></span></span></td>
      <td class="n xwide">${p.price.toFixed(1)}</td>
      <td class="n xwide">${(t.sum / p.price).toFixed(1)}${part ? "*" : ""}</td>
      ${showLive ? xLiveCell(p, lg) : lg ? `<td class="xlive-off"></td>` : ""}
      ${gwCells}
      <td class="n xsum"${part ? ` title="Covers ${t.n} of ${t.of} gameweeks: the rest have no projection"` : ""}><span class="xbar" style="width:${Math.round(v / barMax * 48)}px" aria-hidden="true"></span><b>${f1(v)}${part ? "*" : ""}</b></td></tr>`;
  }).join("");

  const teamOpts = Object.values(T).sort((a, b) => a.name.localeCompare(b.name)).map(t => `<option value="${t.id}" ${String(S.team) === String(t.id) ? "selected" : ""}>${t.name}</option>`).join("");
  const prices = [4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 9, 10, 12, 15];
  const active = [S.pos !== "ALL", S.team !== "ALL", S.maxp, S.q, S.xquick !== "all"].filter(Boolean).length;
  return `<div class="panel explorer xptable">
    <div class="bar"><h2>Expected points</h2><span class="muted" aria-live="polite">${rows.length} player${rows.length === 1 ? "" : "s"}${rows.length > 150 ? ", top 150 shown" : ""}</span></div>
    <div class="filters">
      <input type="search" id="q" placeholder="Search players" value="${esc(S.q)}" aria-label="Search players">
      <div class="seg" role="group" aria-label="Position">${["ALL", "GKP", "DEF", "MID", "FWD"].map(x => `<button data-fpos="${x}" aria-pressed="${S.pos === x}">${x === "ALL" ? "All" : x}</button>`).join("")}</div>
      <div class="seg" role="group" aria-label="Show">${[["all", "All"], ["mine", "My squad"], ["star", "Starred"]].map(([k, l]) => `<button data-xquick="${k}" aria-pressed="${S.xquick === k}">${l}</button>`).join("")}</div>
    </div>
    <div class="filters">
      <select id="fteam" aria-label="Team"><option value="ALL">All teams</option>${teamOpts}</select>
      <select id="fmax" aria-label="Max price"><option value="">Max price</option>${prices.map(x => `<option ${+S.maxp === x ? "selected" : ""} value="${x}">Up to £${x.toFixed(1)}m</option>`).join("")}</select>
      <div class="seg" role="group" aria-label="Gameweeks counted">${[3, 5, 6].filter(h => h <= gws.length).map(h => `<button data-xh="${h}" aria-pressed="${S.xh === h}">${h} GWs</button>`).join("")}</div>
      ${active ? `<button class="btn ghost sm" data-xclear="1">Clear filters (${active})</button>` : ""}
    </div>
    ${shown.length ? `<div class="tablebox"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`
      : stateView({ title: "No players match", body: S.xquick === "star" ? "You haven't starred anyone yet: tap ☆ next to a name." : "Loosen a filter, or clear them all to see every player.", action: `<button class="btn" data-xclear="1">Clear filters</button>` })}
    <p class="note">${term("xp", "xP")} = projected FPL points for that gameweek from FPL Lab's model (minutes, goals, assists, clean sheets, bonus).
      ${lg ? `Greyed column: projection made before the GW${lg} deadline, with live points. ` : ""}Flagged players' xP already includes their chance of playing.
      Σ, Avg and xP/£m count the next ${hz.length} gameweeks (GW${hz[0]}–${hz[hz.length - 1]}); faded columns are outside that.
      Blank gameweeks count as 0. * = some gameweeks have no projection and are left out. Shading compares the numbers on screen.</p>
    ${fdrKey()}
  </div>`;
}
function bindXp() {
  const set = (k, v, sk) => { S[k] = v; store.set(sk, v); render(); };
  document.querySelectorAll("th[data-xsort]").forEach(th => th.onclick = e => {
    if (e.target.closest("button")) return;   // the Hide / Avg buttons inside the header
    const k = th.dataset.xsort;
    if (S.xsort === k) S.xdir *= -1; else { S.xsort = k; S.xdir = k === "name" || k === "price" ? 1 : -1; }
    store.set("fpl.xsort", S.xsort); store.set("fpl.xdir", S.xdir); render();
  });
  document.querySelectorAll("[data-xh]").forEach(b => b.onclick = () => set("xh", +b.dataset.xh, "fpl.xh"));
  document.querySelectorAll("[data-xagg]").forEach(b => b.onclick = () => set("xagg", b.dataset.xagg, "fpl.xagg"));
  document.querySelectorAll("[data-xquick]").forEach(b => b.onclick = () => set("xquick", b.dataset.xquick, "fpl.xquick"));
  document.querySelectorAll("[data-xlive]").forEach(b => b.onclick = () => { store.set("fpl.xlive", b.dataset.xlive === "1"); render(); });
  document.querySelectorAll("[data-xstar]").forEach(b => b.onclick = () => { toggleStar(+b.dataset.xstar); render(); });
  document.querySelectorAll("[data-xclear]").forEach(b => b.onclick = () => {
    Object.assign(S, { pos: "ALL", team: "ALL", maxp: "", q: "", xquick: "all" }); store.set("fpl.xquick", "all"); render();
  });
}
