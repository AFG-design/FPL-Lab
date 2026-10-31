// Player explorer.
/* ---------- Players ---------- */
// [key, header, numeric, shown by default]
const COLS = [["team", "Team", 0, 1], ["pos", "Pos", 0, 1], ["price", "£m", 1, 1], ["form", "Form", 1, 1], ["pts", "Pts", 1, 1],
  ["xg", "xG", 1, 1], ["xa", "xA", 1, 1], ["xgi90_4", "xGI/90 L4", 1, 1], ["own", "Own %", 1, 1], ["t10k", "Top 10k", 1, 0],
  ["nailed", "Nailed", 1, 1], ["xmin", "xMins", 1, 0], ["xp1", "xP next", 1, 1], ["xp5", "xP 5", 1, 1], ["val", "xP5/£m", 1, 0], ["pc", "Price change", 1, 1]];
// FPL Review columns exist only on a device that has imported an export (data/fplr.js)
const playerCols = () => frOn() ? COLS.concat(FR_COLS) : COLS;
const colsOn = () => { const v = store.get("fpl.cols"); return Array.isArray(v) ? v : COLS.filter(c => c[3]).map(c => c[0]); };
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
  const t10 = p => D.crowd?.top10k.own[p.id] || 0;
  let rows = D.players.slice();
  if (S.pos !== "ALL") rows = rows.filter(p => p.pos === S.pos);
  if (S.team !== "ALL") rows = rows.filter(p => String(p.team) === String(S.team));
  if (S.minp) rows = rows.filter(p => p.price >= +S.minp);
  if (S.maxp) rows = rows.filter(p => p.price <= +S.maxp);
  if (S.minform) rows = rows.filter(p => +p.form >= +S.minform);
  if (S.own === "diff") rows = rows.filter(p => p.own < 5);
  else if (S.own === "mid") rows = rows.filter(p => p.own >= 5 && p.own < 20);
  else if (S.own === "template") rows = rows.filter(p => p.own >= 20);
  if (S.q) { const q = S.q.toLowerCase(); rows = rows.filter(p => (p.name + " " + p.full).toLowerCase().includes(q)); }
  const g5 = GWS.slice(0, 5), lab5 = p => g5.reduce((a, g) => a + xpg(p.id, g), 0);
  const fr = { fr1: p => frXp(p.id, D.meta.next_gw), fr5: p => frFrom(p.id, g5), frd: p => { const t = frFrom(p.id, g5); return t == null ? null : lab5(p) - t; } };
  // players missing from the FPL Review file sort last either way, never as if they were 0
  const val = p => fr[S.sort] ? (fr[S.sort](p) ?? (S.dir < 0 ? -1e9 : 1e9)) : S.sort === "t10k" ? t10(p) : S.sort === "val" ? p.xp5 / p.price : S.sort === "team" ? T[p.team].short
    : S.sort === "pc" ? (p.price_proj?.[0] ?? 0) : ["name", "pos"].includes(S.sort) ? p[S.sort] : +p[S.sort] || 0;
  rows.sort((a, b) => { const x = val(a), y = val(b); return (x > y ? 1 : x < y ? -1 : 0) * S.dir; });
  const shown = rows.slice(0, 150), on = new Set(colsOn()), cols = playerCols().filter(c => on.has(c[0]));
  const cell = {
    team: p => T[p.team].short, pos: p => p.pos, price: p => p.price.toFixed(1), form: p => f1(p.form), pts: p => p.pts,
    xg: p => (p.xg ?? 0).toFixed(1), xa: p => (p.xa ?? 0).toFixed(1), xgi90_4: p => p.xgi90_4.toFixed(2), own: p => p.own.toFixed(1),
    t10k: p => D.crowd ? t10(p).toFixed(0) + "%" : "–", nailed: p => nailedPill(p), xmin: p => p.xmin, xp1: p => xpCell(p.id, D.meta.next_gw),
    xp5: p => `<b>${f1(p.xp5)}</b>`, val: p => (p.xp5 / p.price).toFixed(2), pc: p => priceCell(p),
    fr1: p => frCell(fr.fr1(p), p.id), fr5: p => frCell(fr.fr5(p), p.id),
    frd: p => { const d = fr.frd(p); return d == null ? frCell(null, p.id) : `<span class="${d >= 1 ? "up" : d <= -1 ? "down" : ""}">${frCell(d, p.id, true)}</span>`; },
  };
  const teamOpts = Object.values(T).sort((a, b) => a.name.localeCompare(b.name)).map(t => `<option value="${t.id}" ${String(S.team) === String(t.id) ? "selected" : ""}>${t.name}</option>`).join("");
  const prices = [4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 9, 10, 12, 15];
  const priceSel = (id, cur, any, op) => `<select id="${id}" aria-label="${any}"><option value="">${any}</option>${prices.map(x => `<option ${+cur === x ? "selected" : ""} value="${x}">${op} £${x.toFixed(1)}m</option>`).join("")}</select>`;
  const active = [S.pos !== "ALL", S.team !== "ALL", S.minp, S.maxp, S.minform, S.own && S.own !== "any", S.q].filter(Boolean).length;
  const head = `<th class="sort sticky-col" data-sort="name" ${S.sort === "name" ? `aria-sort="${S.dir < 0 ? "descending" : "ascending"}"` : ""}>Player${S.sort === "name" ? (S.dir < 0 ? " ↓" : " ↑") : ""}</th>` +
    cols.map(([k, l, n]) => `<th class="sort ${n ? "n" : ""}" data-sort="${k}" ${S.sort === k ? `aria-sort="${S.dir < 0 ? "descending" : "ascending"}"` : ""}>${COLTERM[k] ? term(COLTERM[k], l) : l}${S.sort === k ? (S.dir < 0 ? " ↓" : " ↑") : ""}</th>`).join("");
  const body = shown.map(p => `<tr class="${MINE.has(p.id) ? "mine" : ""}">
      <td class="sticky-col"><span class="pcell"><input type="checkbox" data-cmp="${p.id}" ${S.cmp.includes(p.id) ? "checked" : ""} aria-label="Compare ${esc(p.name)}">
        <button data-p="${p.id}" class="pname linkish">${esc(p.name)}</button>${p.status !== "a" ? `<span class="pill ${p.status === "d" ? "warn" : "bad"}" title="${esc(p.news)}">${p.chance ?? 0}%</span>` : ""}${playerTags(p, 2)}</span></td>
      ${cols.map(([k, , n]) => `<td class="${n ? "n" : ""}">${cell[k](p)}</td>`).join("")}</tr>`).join("");
  return `<div class="panel explorer">
    <div class="bar"><h2>Players</h2><span class="muted" aria-live="polite">${rows.length} player${rows.length === 1 ? "" : "s"}${rows.length > 150 ? ", top 150 shown" : ""}</span></div>
    <div class="filters">
      <input type="search" id="q" placeholder="Search players" value="${esc(S.q)}" aria-label="Search players">
      <div class="seg" role="group" aria-label="Position">${["ALL", "GKP", "DEF", "MID", "FWD"].map(x => `<button data-fpos="${x}" aria-pressed="${S.pos === x}">${x === "ALL" ? "All" : x}</button>`).join("")}</div>
    </div>
    <div class="filters">
      <select id="fteam" aria-label="Team"><option value="ALL">All teams</option>${teamOpts}</select>
      ${priceSel("fmin", S.minp, "Min price", "From")}${priceSel("fmax", S.maxp, "Max price", "Up to")}
      <select id="fform" aria-label="Minimum form"><option value="">Any form</option>${[2, 3, 4, 5, 6, 8].map(x => `<option ${+S.minform === x ? "selected" : ""} value="${x}">Form ${x}+</option>`).join("")}</select>
      <select id="fown" aria-label="Ownership"><option value="any">Any ownership</option>${[["diff", "Differentials (under 5%)"], ["mid", "5% to 20% owned"], ["template", "Template (20%+)"]].map(([v, l]) => `<option value="${v}" ${S.own === v ? "selected" : ""}>${l}</option>`).join("")}</select>
      ${active ? `<button class="btn ghost sm" data-fclear="1">Clear filters (${active})</button>` : ""}
      <details class="colpick"><summary>Columns</summary><div class="colpick-body" role="group" aria-label="Columns to show">
        ${playerCols().map(([k, l]) => `<label><input type="checkbox" data-col="${k}" ${on.has(k) ? "checked" : ""}> ${l}</label>`).join("")}
        <button class="btn ghost sm" data-colreset="1">Reset columns</button></div></details>
      ${fplrButton()}
    </div>
    ${compareHTML()}
    ${shown.length ? `<div class="tablebox"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`
      : stateView({ title: "No players match", body: "Loosen a filter, or clear them all to see every player.", action: `<button class="btn" data-fclear="1">Clear filters</button>` })}
    <p class="note">Yellow edge = in your squad. Tick players to compare them side by side. Nailed = how sure a player is to start and play most of the game (0–100). xGI/90 L4 = expected goal involvement per 90 over the last 4 gameweeks. <span class="asm">Grey italic</span> xP = assumed (no official return date or chance from FPL). ${frOn() ? `FPLR = your FPL Review export (this device only); LAB − FPLR = FPL LAB's ${g5.length}-GW total minus FPL Review's, so green means FPL LAB rates him higher. ` : ""}Price change = progress towards a change at the next update${(D.meta.price_deadlines || []).find(d => new Date(d) > new Date()) ? ` (around ${ukTime(D.meta.price_deadlines.find(d => new Date(d) > new Date()))})` : ""}.</p></div>`;
}
function compareHTML() {
  if (!S.cmp.length) return "";
  const ps = S.cmp.map(i => P[i]).filter(Boolean), g = D.meta.next_gw, gws = GWS.slice(0, 5);
  const t10 = p => D.crowd?.top10k?.own?.[p.id] ?? null;
  const pct = x => x == null ? "–" : Math.round(x) + "%";
  // [label, value fn, better: 1 higher / -1 lower / 0 neither, format, glossary key]
  const groups = [
    ["Projections", [["xP GW" + g, p => p.xp1, 1, f1, "xp"], [`xP next ${gws.length}`, p => p.xp5, 1, f1, "xp"],
      ["Chance of 10+", p => (p.dist?.[g]?.[0] ?? 0) * 100, 1, pct], ["Chance of 2 or fewer", p => (p.dist?.[g]?.[2] ?? 0) * 100, -1, pct]]],
    ["Minutes", [["Nailed", p => p.nailed, 1, x => x, "nailed"], ["Expected minutes", p => p.xmin, 1, x => x, "xmins"], [`Mins ${"L4"}`, p => p.mins4, 1, x => x, "l4"]]],
    ["Attack", [["xGI/90 L4", p => p.xgi90_4, 1, x => x.toFixed(2), "xgi"], ["xGI/90 model", p => p.xgi90, 1, x => x.toFixed(2), "xgi"],
      ["In box/90", p => p.us?.sib90 ?? 0, 1, x => x.toFixed(1), "inbox"], ["Big chances/90", p => p.us?.bc90 ?? 0, 1, x => x.toFixed(2), "bigchance"],
      ["Created/90", p => p.us?.cc90 ?? 0, 1, x => x.toFixed(1), "created"], ["Goals − xG", p => p.g_xg, 0, x => (x > 0 ? "+" : "") + x.toFixed(1)]]],
    ["Defence and bonus", [["DC chance", p => p.dc_rate * 100, 1, pct, "dc"], ["BPS/90 L4", p => p.bf4?.bps90 ?? 0, 1, x => x.toFixed(0), "bps"]]],
    ["Season", [["Points", p => p.pts, 1, x => x], ["Goals, assists", p => p.goals + p.assists, 1, (x, p) => `${p.goals}, ${p.assists}`], ["Form", p => p.form, 1, f1]]],
    ["Price and ownership", [["Price", p => p.price, -1, money], ["Price change tonight", p => p.price_proj?.[0] ?? 0, 0, x => (x > 0 ? "+" : "") + x.toFixed(0) + "%"],
      ["Owned (all)", p => p.own, 0, x => x.toFixed(1) + "%"], ["Owned (top 10k)", p => t10(p) ?? -1, 0, x => x < 0 ? "–" : x.toFixed(0) + "%", "eo"]]],
  ];
  const cell = (fn, dir, fmt) => { const vals = ps.map(fn), best = dir === 1 ? Math.max(...vals) : dir === -1 ? Math.min(...vals) : null;
    return ps.map((p, k) => `<td class="n ${ps.length > 1 && dir && vals[k] === best && vals.some(v => v !== best) ? "best" : ""}">${fmt(vals[k], p)}</td>`).join(""); };
  const fxRow = `<tr><th scope="row">Next ${gws.length} fixtures</th>${ps.map(p => `<td><div class="cmp-fx">${gws.map(x => { const f = fxFor(p.team, x);
      return `<span title="GW${x}">${f.length ? f.map(y => fdrChip(y, { gw: x })).join("") : blankChip(x)}<small>${xpCell(p.id, x)}</small></span>`; }).join("")}</div></td>`).join("")}</tr>`;
  const news = ps.some(p => p.status !== "a") ? `<tr><th scope="row">News</th>${ps.map(p => `<td>${p.status !== "a" ? `<span class="pill ${p.status === "d" ? "warn" : "bad"}">${esc(p.news || "Flagged")}</span>` : '<span class="muted">Fit</span>'}</td>`).join("")}</tr>` : "";
  return `<div class="panel cmp-table" id="cmpPanel"><div class="bar"><h3>Comparing ${ps.length} player${ps.length > 1 ? "s" : ""}</h3><span class="muted">${ps.length < 4 ? "Tick up to 4 in the list, or press Compare in any player's panel" : "Up to 4 at a time"}</span></div>
    <div class="tablebox"><table><thead><tr><th></th>${ps.map(p => `<th scope="col"><button data-p="${p.id}" class="pname linkish">${esc(p.name)}</button><br><span class="muted">${T[p.team].short} · ${p.pos}${MINE.has(p.id) ? " · yours" : ""}</span><br>${playerTags(p, 4)} <button class="btn ghost sm" data-uncmp="${p.id}" aria-label="Remove ${esc(p.name)}">✕</button></th>`).join("")}</tr></thead>
    <tbody>${news}${fxRow}${groups.map(([h, rows]) => `<tr class="cmp-h"><th colspan="${ps.length + 1}">${h}</th></tr>${rows.map(([l, fn, dir, fmt, gk]) => `<tr><th scope="row">${gk ? term(gk, l) : l}</th>${cell(fn, dir, fmt)}</tr>`).join("")}`).join("")}</tbody></table></div>
    <p class="note">Highlighted = best of the group. Fixture chips show FPL difficulty with projected points underneath.</p></div>`;
}

