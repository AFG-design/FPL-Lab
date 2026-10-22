// Rivals and mini-leagues.
/* ---------- Rivals: the field and mini-leagues ---------- */
const CHIP_SHORT = { wildcard: "WC", freehit: "FH", bboost: "BB", "3xc": "TC" };
const CHIP_NAME = { wildcard: "Wildcard", freehit: "Free Hit", bboost: "Bench Boost", "3xc": "Triple Captain" };
function chipHalf() { const g = D.meta.next_gw || 1; return g <= 19 ? [1, 19] : [20, 38]; }
function chipState(chips) {
  if (!chips) return null;
  const [a, b] = chipHalf();
  return ["wildcard", "freehit", "bboost", "3xc"].map(k => { const u = chips.find(c => c.name === k && c.event >= a && c.event <= b); return { k, used: u ? u.event : null }; });
}
function chipBadges(chips) {
  const st = chipState(chips); if (!st) return '<span class="muted">–</span>';
  return `<span class="chipset">${st.map(c => `<span class="cbadge ${c.used ? "used" : ""}" title="${CHIP_NAME[c.k]}: ${c.used ? "used GW" + c.used : "still available"}">${CHIP_SHORT[c.k]}</span>`).join("")}</span>`;
}
const recTeam = () => myTeam();
const field = () => D.crowd ? D.crowd[S.field === "near" ? "near" : "top10k"] : null;
function fieldRows(F, mult, g) {
  const ids = new Set([...Object.keys(F.eo).map(Number), ...Object.keys(mult).map(Number)]);
  return [...ids].filter(i => P[i]).map(i => {
    const eo = (F.eo[i] || 0) / 100, mine = mult[i] || 0, x = xpg(i, g);
    return { id: i, eo, own: F.own[i] || 0, cap: F.cap[i] || 0, mine, x, impact: (mine - eo) * x };
  });
}
function threats(n = 3) {
  const F = D.crowd?.top10k, t = recTeam(); if (!F || !t) return [];
  return fieldRows(F, t.mult, D.meta.next_gw).filter(r => r.impact < -1 && r.mine === 0).sort((a, b) => a.impact - b.impact).slice(0, n);
}
function vRivals() {
  const C = D.crowd;
  if (!C) return `<div class="panel"><h2>Rivals</h2><p class="muted">Ownership data appears after the next gameweek deadline, once managers' teams become public.</p></div>`;
  const g = D.meta.next_gw, t = recTeam(), F = field();
  const rows = fieldRows(F, t.mult, g);
  const thr = rows.filter(r => r.impact < -0.3).sort((a, b) => a.impact - b.impact).slice(0, 8);
  const edge = rows.filter(r => r.impact > 0.3).sort((a, b) => b.impact - a.impact).slice(0, 8);
  const xiOwn = t.xi.reduce((a, i) => a + (F.own[i] || 0), 0) / t.xi.length;
  const capTop = Object.entries(F.cap).filter(([, v]) => v >= 1).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const chipTxt = Object.entries(F.chips || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${({ "3xc": "Triple Captain", bboost: "Bench Boost", freehit: "Free Hit", wildcard: "Wildcard" })[k] || k} ${v.toFixed(0)}%`).join(" · ") || "none";
  const label = S.field === "near" ? `managers around your rank (${rankFmt(F.rank_from)}–${rankFmt(F.rank_to)})` : "the top 10,000";
  const multTxt = m => m === 2 ? `<span class="pill warn">C</span>` : m === 1 ? "XI" : `<span class="muted">—</span>`;
  const tbl = (list, head) => `<div class="tablebox"><table><thead><tr><th>${head}</th><th class="n">${term("xp", "xP")}</th><th class="n">${term("eo", "EO")}</th><th class="n">You</th><th class="n">${term("swing", "Swing")}</th></tr></thead><tbody>${list.map(r => `<tr class="${MINE.has(r.id) ? "mine" : ""}"><td><button data-p="${r.id}" style="all:unset;cursor:pointer" class="pname">${esc(P[r.id].name)}</button> <span class="muted">${T[P[r.id].team].short}</span></td><td class="n">${f1(r.x)}</td><td class="n">${Math.round(r.eo * 100)}%</td><td class="n">${multTxt(r.mine)}</td><td class="n ${r.impact > 0 ? "up" : "down"}">${sgn(r.impact)}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">None</td></tr>`}</tbody></table></div>`;

  // mini-leagues
  const L = C.leagues || [];
  if (S.league == null || !L.find(l => l.id === S.league)) S.league = (L.slice().sort((a, b) => a.size - b.size).find(l => l.size <= 70) || L[0])?.id;
  const lg = L.find(l => l.id === S.league);
  const me = lg?.rows.find(r => r.me);
  const live = C.in_play;
  const gwOf = r => live && r.live != null ? r.live : r.gw_pts;
  const bestGw = lg ? Math.max(...lg.rows.map(r => gwOf(r) ?? -1)) : null;
  const lgTable = lg ? `<div class="tablebox league"><table><thead><tr><th class="n">Rank</th><th>Manager</th><th class="n">GW${C.gw}${live ? " live" : ""}</th><th class="n">Total</th><th class="n">${term("gap", "Gap")}</th><th>${term("chipsleft", "Chips left")}</th></tr></thead><tbody>${lg.rows.map(r => {
      const mv = r.last_rank && r.rank ? r.last_rank - r.rank : 0;
      const gap = me && r.total != null ? r.total - me.total : null;
      const arrow = mv > 0 ? `<span class="mv up" aria-label="up ${mv}">▲${mv}</span>` : mv < 0 ? `<span class="mv down" aria-label="down ${-mv}">▼${-mv}</span>` : `<span class="mv same" aria-label="no change">–</span>`;
      const gw = gwOf(r);
      return `<tr class="${r.me ? "mine" : ""} ${r.entry === S.rival ? "is-rival" : ""}"><td class="n"><span class="lg-rank"><b>${r.rank ?? "–"}</b>${arrow}</span></td>
        <td>${r.me ? `<span class="pname">${esc(r.player)}</span> <span class="pill good">You</span>` : `<button class="pname linkish" data-rival="${r.entry}" aria-pressed="${r.entry === S.rival}">${esc(r.player)}</button>`}${r.chip ? ` <span class="tag">${esc(r.chip)}</span>` : ""}<br><span class="muted lg-team">${esc(r.team)}</span></td>
        <td class="n ${gw === bestGw && gw != null ? "lg-best" : ""}">${gw ?? "–"}</td><td class="n"><b>${r.total ?? "–"}</b></td><td class="n ${gap > 0 ? "down" : gap < 0 ? "up" : ""}">${gap == null || r.me ? "" : (gap > 0 ? "+" : "") + gap}</td><td>${chipBadges(r.chips)}</td></tr>`;
    }).join("")}</tbody></table></div>
    ${lg.size > lg.rows.length ? `<p class="note">Big league: showing the top 10 and the managers around you.</p>` : ""}
    ${(() => { const st = lg.rows.filter(r => !r.me && r.chips).map(r => chipState(r.chips)); if (!st.length) return ""; const [a, b] = chipHalf();
      return `<p class="note">Rivals with each chip still to play (GW${a}–${b}): ${["wildcard", "freehit", "bboost", "3xc"].map(k => `<b>${CHIP_NAME[k]}</b> ${st.filter(x => !x.find(c => c.k === k).used).length}/${st.length}`).join(" · ")}. Greyed badges are used.</p>`; })()}` : "";

  // rival comparison
  const rv = lg?.rows.find(r => r.entry === S.rival);
  const cmp = rv && rv.picks ? teamCompare(rv, { gw: C.gw, close: 'data-rival="0"' }) : "";

  return `
  <div class="panel"><div class="bar"><h2>The field</h2>
      <div class="seg" role="group" aria-label="Compare with"><button data-field="top10k" aria-pressed="${S.field !== "near"}">Top 10k</button><button data-field="near" aria-pressed="${S.field === "near"}">Around your rank</button></div></div>
    <p class="note" style="margin-top:0">What ${label} owned and captained in GW${C.gw} (${F.n.toLocaleString("en-GB")} teams sampled), against your planned GW${g} team. ${term("eo", "EO")} (effective ownership) counts captains twice. ${term("swing", "Swing")} = how much a player's projected points move your rank: negative means the field gains on you if he delivers.</p>
    <div class="kpis" style="margin-bottom:14px">
      <div class="kpi"><span class="lbl">Your XI's average ownership</span><b>${xiOwn.toFixed(0)}%</b><span class="delta muted">${xiOwn > 60 ? "very template" : xiOwn > 40 ? "fairly template" : "plenty of differentials"}</span></div>
      <div class="kpi"><span class="lbl">Their captain</span><b>${esc(P[capTop[0]?.[0]]?.name || "–")}</b><span class="delta muted">${capTop[0] ? capTop[0][1].toFixed(0) + "% of teams" : ""}</span></div>
      <div class="kpi"><span class="lbl">Chips played GW${C.gw}</span><b style="font-size:18px">${chipTxt}</b><span class="delta muted">avg ${F.avg_pts} pts · hits ${F.hits}</span></div>
    </div>
    <div class="statgrid"><div><h3 style="margin-bottom:8px">Threats</h3>${tbl(thr, "Owned by the field")}</div><div><h3 style="margin-bottom:8px">Your edges</h3>${tbl(edge, "Your differentials")}</div></div>
    <div style="margin-top:14px"><span class="lbl">Captaincy split</span><div class="capbars" style="margin-top:6px">${capTop.map(([id, v], k) => `<div class="cb ${k === 0 ? "top" : ""}"><span class="pname">${esc(P[id]?.name || id)}</span><div class="track"><div class="fill" style="width:${v}%"></div></div><span class="val">${v.toFixed(0)}%</span></div>`).join("")}</div></div>
  </div>
  <div class="grid2">
    <div class="panel"><div class="bar"><h2>Mini-leagues</h2><select id="leagueSel" class="sel" aria-label="League">${L.map(l => `<option value="${l.id}" ${l.id === S.league ? "selected" : ""}>${esc(l.name)} (${l.my_rank ?? "–"}/${l.size})</option>`).join("")}</select></div>
      ${lgTable || stateView({ title: "No mini-leagues yet", body: "Your classic mini-leagues appear here after the next gameweek sample." })}<p class="note">Tap a manager to compare teams. Arrows show places moved since last gameweek; the highlighted score is the best this gameweek.${live ? " Live points are summed from the latest match data, without automatic substitutions." : ""}</p></div>
    <div style="min-width:0">${cmp || `<div class="panel"><h3>Compare with a rival</h3><p class="muted">Pick someone from the league table to see where your teams differ and who the differences favour next gameweek.</p></div>`}</div>
  </div>
  ${watchPanel()}`;
}

/* ---------- compare two teams: where your squads differ and who that favours next gameweek ---------- */
function teamCompare(rv, { gw, close }) {
  const t = recTeam(), g = D.meta.next_gw;
  const theirs = {}; rv.picks.forEach(([el, m]) => theirs[el] = m);
  const all = new Set([...Object.keys(theirs).map(Number), ...Object.keys(t.mult).map(Number)]);
  const diffs = [...all].filter(i => P[i]).map(i => ({ id: i, me: t.mult[i] || 0, them: theirs[i] || 0, x: xpg(i, g) })).filter(r => r.me !== r.them).map(r => ({ ...r, sw: (r.me - r.them) * r.x }));
  const swing = diffs.reduce((a, r) => a + r.sw, 0);
  const capT = rv.picks.find(([, m]) => m >= 2)?.[0];
  const shared = rv.picks.filter(([el]) => MINE.has(el)).length;
  const mineOnly = diffs.filter(r => r.sw > 0).sort((a, b) => b.sw - a.sw), theirsOnly = diffs.filter(r => r.sw < 0).sort((a, b) => a.sw - b.sw);
  const li = r => `<li class="${r.sw > 0 ? "good" : "bad"}"><span><button data-p="${r.id}" class="pname linkish">${esc(P[r.id].name)}</button> ${r.me === 2 ? "(your C)" : r.them === 2 ? "(their C)" : ""} · ${f1(r.x)} xP · ${sgn(r.sw)}</span></li>`;
  return `<div class="panel cmp-panel"><div class="bar"><h3>You vs ${esc(rv.player)}</h3>${close ? `<button class="btn" ${close}>Close</button>` : ""}</div>
    <p class="verdict">Their GW${gw} team${capT ? ` captained <b>${esc(P[capT]?.name || "?")}</b>` : ""}${rv.chip ? ` with ${esc(CHIP_NAME[rv.chip] || rv.chip)} active` : ""}. You share <b>${shared} of 15</b> players.${rv.chips ? ` Chips used: ${rv.chips.length ? rv.chips.map(c => `${CHIP_NAME[c.name] || c.name} GW${c.event}`).join(", ") : "none"}. Still to play this half: ${chipState(rv.chips).filter(c => !c.used).map(c => CHIP_NAME[c.k]).join(", ") || "none"}.` : ""} Against your planned GW${g} team, the differences are worth <b class="${swing >= 0 ? "up" : "down"}">${sgn(swing)}</b> projected points to you next gameweek.</p>
    <div class="statgrid" style="margin-top:12px"><div><span class="lbl">Where you gain</span><ul class="alerts" style="margin-top:6px">${mineOnly.map(li).join("") || "<li><span class='muted'>Nothing</span></li>"}</ul></div>
    <div><span class="lbl">Where they gain</span><ul class="alerts" style="margin-top:6px">${theirsOnly.map(li).join("") || "<li><span class='muted'>Nothing</span></li>"}</ul></div></div>
    <p class="note">Based on their GW${gw} team, the latest that FPL shows. Changes they make before the deadline appear afterwards.</p></div>`;
}

/* ---------- compare any team: the overall leader, your watch list, or any team ID ---------- */
const WATCH = { msg: "", busy: false };
function watchTeams() {
  const seen = new Set(), out = [];
  (D.watch || []).filter(w => w.picks).forEach(w => { seen.add(w.entry); out.push({ ...w, src: w.auto ? "Overall leader" : (w.label || "Watch list") }); });
  (D.crowd?.leagues || []).forEach(l => l.rows.forEach(r => { if (!r.me && r.picks && !seen.has(r.entry)) { seen.add(r.entry); out.push({ ...r, src: l.name }); } }));
  return out;
}
function watchPanel() {
  const list = watchTeams(), mine = D.history;
  const sel = list.find(w => w.entry === S.cmpTeam);
  const pending = S.cmpTeam && !sel ? S.cmpTeam : null;
  const chip = w => `<button class="chipbtn" data-cmpteam="${w.entry}" aria-pressed="${w.entry === S.cmpTeam}">${esc(w.player)}<span>${esc(w.src)}</span></button>`;
  const watched = list.filter(w => D.watch?.some(x => x.entry === w.entry)), leaguers = list.filter(w => !watched.includes(w));
  const chips = watched.map(chip).join("") + (leaguers.length ? `<details class="morechips" ${leaguers.some(w => w.entry === S.cmpTeam) ? "open" : ""}><summary>Mini-league rivals (${leaguers.length})</summary><div class="chiprow">${leaguers.map(chip).join("")}</div></details>` : "");
  let body = "";
  if (sel) {
    const mi = {}; mine.forEach(h => mi[h.gw] = h);
    const rows = (sel.hist || []).slice(-6).reverse().map(([gw, pts, rank]) => { const m = mi[gw]; const d = m ? m.pts - pts : null;
      return `<tr><td>${gw}</td><td class="n">${m ? m.pts : "–"}</td><td class="n">${pts}</td><td class="n ${d > 0 ? "up" : d < 0 ? "down" : ""}">${d == null ? "" : (d > 0 ? "+" : "") + d}</td><td class="n">${rankFmt(m?.rank)}</td><td class="n">${rankFmt(rank)}</td></tr>`; }).join("");
    const gap = sel.total != null ? D.manager.points - sel.total : null;
    body = `<div class="kpis" style="margin:12px 0">
        <div class="kpi"><span class="lbl">Their rank</span><b>${rankFmt(sel.rank)}</b><span class="delta muted">yours ${rankFmt(D.manager.rank)}</span></div>
        <div class="kpi"><span class="lbl">Points gap</span><b class="${gap >= 0 ? "up" : "down"}">${gap == null ? "–" : (gap > 0 ? "+" : gap < 0 ? "−" : "") + Math.abs(gap)}</b><span class="delta muted">${sel.total ?? "–"} total</span></div>
        ${sel.value != null ? `<div class="kpi"><span class="lbl">Team value</span><b>${money(sel.value)}</b><span class="delta muted">bank ${money(sel.bank)} · yours ${money(D.manager.value)}</span></div>` : ""}
      </div>
      ${teamCompare(sel, { gw: sel.gw || D.crowd?.gw || D.meta.cur_gw })}
      ${rows ? `<div class="tablebox" style="margin-top:12px"><table><thead><tr><th>GW</th><th class="n">You</th><th class="n">Them</th><th class="n">Diff</th><th class="n">Your rank</th><th class="n">Their rank</th></tr></thead><tbody>${rows}</tbody></table></div>` : ""}
      ${sel.src !== "Overall leader" && !(D.crowd?.leagues || []).some(l => l.rows.some(r => r.entry === sel.entry)) ? `<button class="btn ghost sm" data-unwatch="${sel.entry}" style="margin-top:10px">Remove from watch list</button>` : ""}`;
  } else if (pending) {
    body = `<p class="verdict" style="margin-top:12px">Team ${pending} isn't in the data yet. ${syncToken() ? `<button class="btn primary sm" data-watchadd="${pending}">Add to watch list</button> The site rebuilds with their team in about 5 minutes.` : `Add it to <a href="https://github.com/${REPO}/edit/main/watch.json" target="_blank" rel="noopener">watch.json on GitHub</a> as <code>{"teams": [{"id": ${pending}}]}</code>, or set up Sync (top of the page) to add teams in one tap.`}</p>`;
  }
  return `<div class="panel"><div class="bar"><h2>Compare any team</h2></div>
    <p class="note" style="margin-top:0">Pick a team, or enter any FPL team ID: it's the number in the address of their Points page on the FPL site (fantasy.premierleague.com/entry/<b>123456</b>/event/…).</p>
    <form class="filters" id="cmpForm" style="margin:8px 0"><input id="cmpId" inputmode="numeric" pattern="[0-9]*" placeholder="Team ID" aria-label="FPL team ID" value="${pending || ""}" style="max-width:160px"><button class="btn" type="submit">Compare</button></form>
    <div class="chiprow">${chips || '<span class="muted">No teams yet.</span>'}</div>
    <p class="st-msg" id="watchMsg">${esc(WATCH.msg)}</p>
    ${body}</div>`;
}
async function watchEdit(id, add) {
  if (!syncToken() || WATCH.busy) return;
  WATCH.busy = true; WATCH.msg = add ? "Adding…" : "Removing…"; render();
  try {
    const url = `https://api.github.com/repos/${REPO}/contents/watch.json`;
    const r = await fetch(url + "?ref=main&t=" + Date.now(), { headers: syncHeaders(true), cache: "no-store" });
    let doc = { teams: [] }, sha;
    if (r.ok) { const j = await r.json(); doc = JSON.parse(b64d(j.content)); sha = j.sha; }
    doc.teams = (doc.teams || []).filter(t => +t.id !== id);
    if (add) doc.teams.push({ id });
    const body = { message: (add ? "Watch team " : "Unwatch team ") + id, content: b64e(JSON.stringify(doc, null, 1) + "\n"), branch: "main" };
    if (sha) body.sha = sha;
    const w = await fetch(url, { method: "PUT", headers: { ...syncHeaders(true), "Content-Type": "application/json" }, body: JSON.stringify(body) });
    WATCH.msg = w.ok ? (add ? `Team ${id} added. It appears here after the rebuild, in about 5 minutes.` : `Team ${id} removed.`) : w.status === 401 || w.status === 403 ? "Your token can't edit the repository. It needs Contents: Read and write." : "GitHub said " + w.status + ".";
  } catch (e) { WATCH.msg = "Couldn't reach GitHub."; }
  WATCH.busy = false; render();
}
