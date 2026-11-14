// Rivals and mini-leagues.
/* ---------- Rivals: the field and mini-leagues ---------- */
// chip names (CHIP_SHORT, CHIP_NAME) live in core/plan.js, shared with the Planner's chip pins (FL-005)
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
const recTeam = () => seasonOver() ? null : myTeam();   // season over: no planned team, so no field or rival swing
const field = () => {
  const f = D.crowd?.[S.field === "near" ? "near" : "top10k"];
  return f?.n > 0 && f.eo && f.cap && f.own ? f : null;
};
function fieldRows(F, mult, g) {
  const ids = new Set([...Object.keys(F.eo).map(Number), ...Object.keys(mult).map(Number)]);
  return [...ids].filter(i => P[i]).map(i => {
    const eo = (F.eo[i] || 0) / 100, mine = mult[i] || 0, x = xpg(i, g);
    return { id: i, eo, own: F.own[i] || 0, cap: F.cap[i] || 0, mine, x, impact: (mine - eo) * x };
  });
}
/* Sub-line of the "Chips played" tile. `hits` is the sample's average event_transfers_cost per team, in points.
   The sample is taken soon after the deadline, before any match, so the teams' points are all 0: no points
   average is shown. Missing or non-numeric hits (old or partial sample): print nothing, never "undefined". */
function fieldHitsTxt(F) {
  const h = F?.hits;
  if (typeof h !== "number" || !Number.isFinite(h)) return "";
  return `avg hit cost ${h > 0 ? "−" : ""}${Math.abs(h)} pts a team`;
}
function threats(n = 3) {
  const F = D.crowd?.top10k, t = recTeam(); if (!F?.n || !t) return [];
  return fieldRows(F, t.mult, D.meta.next_gw).filter(r => r.impact < -1 && r.mine === 0).sort((a, b) => a.impact - b.impact).slice(0, n);
}
/* ---------- Rivals page: My league (Standings, Weekly honours, head-to-head) and The field ----------
   Opens on My league every visit. The league you pick is remembered (fpl.league); if it isn't in the latest data (you
   left it, or it isn't sampled) the page falls back to the smallest league of up to 70 and says so. A pinned rival is
   remembered per league (fpl.rivalPins); without one, or if that manager has left, the closest manager by official
   season total leads, and a big league (only the top 10 and your neighbours sampled) says "closest tracked rival". */
const RV_TABS = [["league", "My league"], ["field", "The field"]];
const LT_TABS = [["standings", "Standings"], ["honours", "Weekly honours"]];
const rvPins = () => store.get("fpl.rivalPins") || {};
const ukStamp = iso => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
const ukClock = x => new Date(x).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
const ordn = n => n == null ? "–" : n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");
const ptsW = n => `${n} pt${Math.abs(n) === 1 ? "" : "s"}`;
const signed = n => (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n);
function tabsHtml(list, cur, { label, idp, data, panel }) {
  return `<div class="seg rv-tabs" role="tablist" aria-label="${label}">${list.map(([k, l]) => `<button type="button" role="tab" id="${idp}-${k}" data-${data}="${k}" aria-selected="${cur === k}" aria-controls="${panel}" tabindex="${cur === k ? 0 : -1}">${l}</button>`).join("")}</div>`;
}
function rvLeague(L) {
  if (!L.length) return { lg: null, note: "" };
  const want = store.get("fpl.league");
  const lg = L.find(l => l.id === want);
  if (lg) return { lg, note: "" };
  const fb = L.slice().sort((a, b) => a.size - b.size).find(l => l.size <= 70) || L[0];
  return { lg: fb, note: want != null ? `Your saved league isn't in this update (you may have left it), so this shows ${esc(fb.name)}.` : "" };
}
function vRivals() {
  const C = D.crowd;
  if (!C) return `<div class="panel"><h2>Rivals</h2><p class="muted">Ownership data appears after the next gameweek deadline, once managers' teams become public.</p></div>`;
  const L = C.leagues || [], { lg, note } = rvLeague(L), tab = S.rtab === "field" ? "field" : "league";
  const sel = tab === "league" && L.length ? `<select id="leagueSel" class="sel rv-lsel" aria-label="League">${L.map(l => `<option value="${l.id}" ${l.id === lg.id ? "selected" : ""}>${esc(l.name)} (${l.my_rank ?? "–"}/${l.size.toLocaleString("en-GB")})</option>`).join("")}</select>` : "";
  return `<div class="rv-head"><h2 class="rv-title">Rivals</h2>${sel}</div>
    ${tabsHtml(RV_TABS, tab, { label: "Rivals", idp: "rvtab", data: "rtab", panel: "rvpanel" })}
    <div id="rvpanel" role="tabpanel" aria-labelledby="rvtab-${tab}" class="rv-body">${tab === "field" ? vField(C) : vLeague(C, lg, note)}</div>`;
}
function vLeague(C, lg, note) {
  if (!lg) return stateView({ title: "No mini-leagues yet", body: "Your classic mini-leagues appear here after the next gameweek sample." });
  const sub = S.ltab === "honours" ? "honours" : "standings";
  const inner = S.ltab === "honours" ? vHonours(C, lg) : S.ltab === "h2h" ? vH2H(C, lg) : vStandings(C, lg);
  return `${tabsHtml(LT_TABS, sub, { label: "My league", idp: "lttab", data: "ltab", panel: "ltpanel" })}
    <div id="ltpanel" role="tabpanel" aria-labelledby="lttab-${sub}" class="rv-body">${note ? `<p class="note rv-flag">${note}</p>` : ""}${inner}</div>`;
}

/* Scores on one basis for every row (FL-078): GW points BEFORE hits, as FPL shows them, with the hit in its own column.
   Final: FPL's event_total. Live: your liveState() (same GW only) and the build's live points for rivals (automatic subs,
   provisional bonus, captain/vice: fpl_score.live_team_points). A rival with no sampled picks falls back to FPL's league
   table figure, marked *. Unknown (no figure at all) is a dash; a real 0 is 0. Hit unknown without picks: dash. */
function rvPhase(C) {
  if (!C.in_play) return "final";
  const L = D.live;
  if (!L || L.gw !== C.gw || !L.fixtures) return "nolive";
  return L.fixtures.some(f => f.started) ? "live" : "pre";
}
function rvScores(C) {
  const ls = C.in_play && D.live?.gw === C.gw ? liveState() : null;
  const gwOf = r => !C.in_play ? r.gw_pts ?? null : r.me && ls ? ls.gross : r.live != null ? r.live : r.gw_pts ?? null;
  const srcOf = r => !C.in_play ? "final" : (r.me && ls) || r.live != null ? "live" : r.gw_pts != null ? "fpl" : null;
  const hitOf = r => r.me && ls ? ls.hits : r.picks ? (r.hits ?? 0) : null;
  return { phase: rvPhase(C), ls, gwOf, srcOf, hitOf };
}
// What the status bar says is wrong, if anything: a failed check keeps the last scores and says when they're from.
function rvStale(ph) {
  const age = Date.now() - new Date(D.meta.built);
  if (POLL.err && (!POLL.ok || POLL.err > POLL.ok)) return `Couldn't check for new scores at ${ukClock(POLL.err)}. Showing the last scores that loaded, from ${ukClock(D.meta.built)} UK.`;
  if (ph === "live" && age > 30 * 6e4) return `Scores may be behind: the last update was ${Math.round(age / 6e4)} minutes ago. During matches they normally update every 10 minutes.`;
  if (ph === "nolive") return "Live player scores for this gameweek aren't in the latest data, so the scores are FPL's league-table figures.";
  return "";
}
function rvStatus(C, sc) {
  const g = C.gw, ph = sc.phase, stale = rvStale(ph);
  const label = { final: `GW${g} · Final scores`, live: `GW${g} live`, pre: `GW${g} · Before kick-off`, nolive: `GW${g} in progress` }[ph];
  return `<div class="rv-status${ph === "live" ? " is-live" : ""}${stale ? " is-stale" : ""}">
    <b class="rv-phase">${ph === "live" ? '<span class="live-dot" aria-hidden="true"></span>' : ""}${label}</b>
    <span class="rv-upd">Updated ${ukStamp(D.meta.built)} UK</span>
    <span class="rv-poll muted" role="status">${POLL.busy ? "Checking for new scores…" : "Checks every 5 min"}</span>
    <button type="button" class="btn sm" data-rvrefresh="1"${POLL.busy ? ' aria-busy="true"' : ""}>${icon("refresh")}Refresh scores</button>
    ${stale ? `<p class="rv-stale" role="alert">${stale}</p>` : ""}</div>`;
}
const firstName = (r, rows) => { const f = String(r.player || "").trim().split(/\s+/)[0]; return rows.some(x => x !== r && String(x.player || "").trim().split(/\s+/)[0] === f) ? r.player : f; };
function rvRival(lg, me) {
  const pin = rvPins()[lg.id], others = lg.rows.filter(r => !r.me);
  const pinned = others.find(r => r.entry === pin);
  if (pinned) return { r: pinned, kind: "Pinned rival" };
  const cand = others.filter(r => r.total != null);
  if (!me || me.total == null || !cand.length) return null;
  const r = cand.sort((a, b) => Math.abs(a.total - me.total) - Math.abs(b.total - me.total) || b.total - a.total || (a.rank ?? 1e9) - (b.rank ?? 1e9))[0];
  return { r, kind: lg.size > lg.rows.length ? "Closest tracked rival" : "Closest rival", pinLost: pin != null };
}
// The one factual line: a change of lead is only claimed when both managers have official ranks before and after.
function rvMoment(C, lg, me, R, sc) {
  const rv = R.r, fn = esc(firstName(rv, lg.rows)), g = C.gw;
  if (me?.total == null || rv.total == null) return "";
  const gap = me.total - rv.total;
  const pw = n => `${n} point${n === 1 ? "" : "s"}`;
  const head = gap > 0 ? `You lead by ${pw(gap)}` : gap < 0 ? `${fn} leads by ${pw(-gap)}` : `Level on ${me.total} points`;
  const sm = sc.gwOf(me), sr = sc.gwOf(rv), hm = sc.hitOf(me), hr = sc.hitOf(rv);
  const scoring = sm != null && sr != null ? `scoring ${sm} to ${fn}'s ${sr}` : "";
  const ranks = me.rank && rv.rank && me.last_rank && rv.last_rank && me.rank !== rv.rank && me.last_rank !== rv.last_rank;
  let line = "";
  if (scoring && ranks) {
    const was = me.last_rank < rv.last_rank, now = me.rank < rv.rank;
    line = !was && now ? `You overtook ${fn} in GW${g}, ${scoring}.` : was && !now ? `${fn} overtook you in GW${g}, ${scoring}.` : `${now ? "You stayed ahead" : `${fn} stayed ahead`} in GW${g}, ${scoring}.`;
  } else if (scoring) line = `In GW${g} you scored ${sm} and ${fn} scored ${sr}.${me.last_rank && rv.last_rank ? "" : " Earlier league ranks aren't available, so no change of lead is claimed."}`;
  const hits = [hm > 0 ? `your −${hm} hit` : "", hr > 0 ? `${fn}'s −${hr} hit` : ""].filter(Boolean);
  if (line && hits.length) line += ` Scores are before ${hits.join(" and ")}, which the totals include.`;
  return `<section class="panel rv-moment" aria-labelledby="rvm-h"><span class="rv-eyebrow">Rivalry moment · after GW${g} · ${R.kind}</span>
    <h3 id="rvm-h" class="rv-headline">${head}</h3>${line ? `<p>${line}</p>` : ""}
    <div class="rv-pair"><div><span>${ordn(me.rank)} · ${esc(me.player)}</span><b>${me.total}</b></div><div><span>${ordn(rv.rank)} · ${esc(rv.player)}</span><b>${rv.total}</b></div></div>
    ${R.pinLost ? `<p class="note">Your pinned rival isn't in this league's latest data, so this is the closest manager instead.</p>` : ""}</section>`;
}
/* Where your planned team and a rival's differ: your ACTIVE Planner plan for the next GW (myTeam(): its XI, captain and
   chip) against the rival's latest public picks. Points are projected (xP) for the next GW. */
function cmpDiffs(rv, t) {
  const g = D.meta.next_gw, theirs = {}; rv.picks.forEach(([el, m]) => theirs[el] = m);
  const all = new Set([...Object.keys(theirs).map(Number), ...Object.keys(t.mult).map(Number)]);
  const diffs = [...all].filter(i => P[i]).map(i => ({ id: i, me: t.mult[i] || 0, them: theirs[i] || 0, x: xpg(i, g) })).filter(r => r.me !== r.them).map(r => ({ ...r, sw: (r.me - r.them) * r.x }));
  return { swing: diffs.reduce((a, r) => a + r.sw, 0), capT: rv.picks.find(([, m]) => m >= 2)?.[0], shared: rv.picks.filter(([el]) => MINE.has(el)).length,
    mineOnly: diffs.filter(r => r.sw > 0).sort((a, b) => b.sw - a.sw), theirsOnly: diffs.filter(r => r.sw < 0).sort((a, b) => a.sw - b.sw) };
}
function rvProjection(C, lg, R) {
  const rv = R.r, fn = esc(firstName(rv, lg.rows)), t = recTeam(), g = D.meta.next_gw;
  let body;
  if (!t) body = `<p class="note">Season over: there is no next gameweek to project.</p>`;
  else if (!rv.picks) body = `<p class="note">${fn}'s GW${C.gw} picks aren't in the sample, so there's no projection.</p>`;
  else {
    const c = cmpDiffs(rv, t), line = (r, who) => `<li><span><button type="button" data-p="${r.id}" class="pname linkish">${esc(P[r.id].name)}</button> · ${who}</span><b class="${r.sw > 0 ? "up" : "down"}">${sgn(r.sw)}</b></li>`;
    body = `<p class="rv-big ${c.swing >= 0 ? "up" : "down"}">${sgn(c.swing)} pts</p>
      <p class="note">Projected for GW${g}: your planned XI (active plan: ${esc(planName())}) against ${fn}'s last public picks, from GW${C.gw}.</p>
      <ul class="rv-lines">${c.mineOnly[0] ? line(c.mineOnly[0], "your edge") : ""}${c.theirsOnly[0] ? line(c.theirsOnly[0], `${fn}'s edge`) : ""}</ul>`;
  }
  return `<section class="panel rv-proj" aria-labelledby="rvp-h"><h3 id="rvp-h" class="rv-h">You vs ${fn}</h3><p class="muted">${R.kind} · GW${g ?? ""} projection</p>${body}
    <button type="button" class="linkish rv-go" data-rvh2h="${rv.entry}">Compare both teams <span aria-hidden="true">→</span></button></section>`;
}
function rvTable(C, lg, sc, me) {
  const g = C.gw, live = C.in_play, pin = rvPins()[lg.id];
  const best = Math.max(...lg.rows.map(r => sc.gwOf(r) ?? -1));
  const rows = lg.rows.map(r => {
    const mv = r.last_rank && r.rank ? r.last_rank - r.rank : null;
    const arrow = mv > 0 ? `<span class="mv up" aria-label="up ${mv}">▲${mv}</span>` : mv < 0 ? `<span class="mv down" aria-label="down ${-mv}">▼${-mv}</span>` : `<span class="mv same" aria-label="${mv == null ? "no previous rank" : "no change"}">–</span>`;
    const gw = sc.gwOf(r), hit = sc.hitOf(r), src = sc.srcOf(r);
    const gap = me && !r.me && r.total != null && me.total != null ? r.total - me.total : null;
    const who = r.me ? `<span class="pname">${esc(r.player)}</span> <span class="pill good">You</span>` : `<button type="button" class="pname linkish" data-rvh2h="${r.entry}">${esc(r.player)}</button>${r.entry === pin ? ' <span class="pill warn">Rival</span>' : ""}`;
    return `<tr class="${r.me ? "mine" : ""}${r.entry === pin ? " is-rival" : ""}"><td class="n"><span class="lg-rank"><b>${r.rank ?? "–"}</b>${arrow}</span></td>
      <td class="rv-mgr">${who}${r.chip ? ` <span class="tag">${esc(CHIP_NAME[r.chip] || r.chip)}</span>` : ""}<span class="muted lg-team">${esc(r.team)}</span></td>
      <td class="n${gw != null && gw > 0 && gw === best ? " lg-best" : ""}"${hitTip(hit, gw)}>${gw ?? "–"}${live && src === "fpl" ? '<sup class="rv-fb" title="FPL league-table figure: no live picks for this manager">*</sup>' : ""}</td>
      <td class="n rv-hit">${hit == null ? '<span class="muted" title="Not known: no picks for this manager">–</span>' : hit > 0 ? `<span class="down">−${hit}</span>` : '<span class="muted">0</span>'}</td>
      <td class="n"><b>${r.total ?? "–"}</b></td><td class="n rv-c-gap ${gap > 0 ? "down" : gap < 0 ? "up" : ""}">${gap == null ? "" : signed(gap)}</td><td class="rv-c-chips">${chipBadges(r.chips)}</td></tr>`;
  }).join("");
  const fb = live && lg.rows.some(r => sc.srcOf(r) === "fpl");
  const notes = [`Points are GW${g} points before hits, as FPL shows them; Hit is that manager's transfer cost (0 = none, – = not known). # and Total are FPL's official league rank and season total, which include hits. Arrows show places moved since the last gameweek.`];
  if (live) notes.push(`Live points include provisional bonus and automatic substitutions once a starter's matches are over and his replacement has played, with the same rule for every row.${(C.vice_unknown || []).some(e => lg.rows.some(r => r.entry === e)) ? " For managers sampled before the vice-captain was saved, the armband isn't passed to the vice if the captain doesn't play." : ""}`);
  if (fb) notes.push("* No live picks for this manager, so the figure is FPL's league table, which updates less often.");
  const st = lg.rows.filter(r => !r.me && r.chips).map(r => chipState(r.chips));
  if (st.length) { const [a, b] = chipHalf(); notes.push(`Rivals with each chip still to play (GW${a}–${b}): ${["wildcard", "freehit", "bboost", "3xc"].map(k => `<b>${CHIP_NAME[k]}</b> ${st.filter(x => !x.find(c => c.k === k).used).length}/${st.length}`).join(" · ")}.`); }
  const count = lg.size > lg.rows.length ? `${lg.rows.length} of ${lg.size.toLocaleString("en-GB")} managers: top 10 and around you` : `${lg.size} managers`;
  return `<section class="panel rv-standings" aria-labelledby="rvst-h"><div class="bar"><h3 id="rvst-h" class="rv-h">Season standings</h3><span class="muted">${count} · Official ranks</span></div>
    <div class="tablebox league rv-table"><table><thead><tr><th class="n" scope="col">#</th><th scope="col">Manager</th><th class="n" scope="col">GW${g}${live ? '<span class="rv-c-live"> live</span>' : ""}</th><th class="n" scope="col">Hit</th><th class="n" scope="col">Total</th><th class="n rv-c-gap" scope="col">${term("gap", "Gap")}</th><th class="rv-c-chips" scope="col">${term("chipsleft", "Chips left")}</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="note">Select a manager for team details, chips and a full comparison.</p>${notes.map(n => `<p class="note">${n}</p>`).join("")}</section>`;
}
function vStandings(C, lg) {
  const sc = rvScores(C), me = lg.rows.find(r => r.me), R = rvRival(lg, me);
  const hero = R ? `<div class="rv-hero${sc.phase === "final" ? "" : " one"}">${sc.phase === "final" ? rvMoment(C, lg, me, R, sc) : ""}${rvProjection(C, lg, R)}</div>` : "";
  const table = rvTable(C, lg, sc, me), any = `<p class="rv-anyteam"><button type="button" class="linkish rv-go" data-rvh2h="0">Compare any team or FPL entry ID <span aria-hidden="true">→</span></button></p>`;
  // after a settled gameweek the rivalry leads; during play (and before kick-off) the table comes first
  return rvStatus(C, sc) + (sc.phase === "final" ? hero + table : table + hero) + rvFeatured(C, lg) + any;
}

/* ---------- head-to-head with one manager: pin, replace or unpin, details, and where your teams differ ---------- */
function vH2H(C, lg) {
  const back = `<button type="button" class="linkish rv-back" data-ltab="standings"><span aria-hidden="true">‹</span> Back to standings</button>`;
  const rv = lg.rows.find(r => r.entry === S.rival && !r.me);
  if (!rv) return `${back}<h3 class="rv-h rv-sec" id="h2h-h" tabindex="-1">Compare another team</h3>${watchPanel()}`;
  const fn = esc(firstName(rv, lg.rows)), g = D.meta.next_gw, sc = rvScores(C), me = lg.rows.find(r => r.me);
  const pin = rvPins()[lg.id], pinned = pin === rv.entry, other = lg.rows.find(r => r.entry === pin && !r.me);
  const t = recTeam(), c = t && rv.picks ? cmpDiffs(rv, t) : null;
  const gw = sc.gwOf(rv), hit = sc.hitOf(rv), gap = me?.total != null && rv.total != null ? me.total - rv.total : null;
  const st = chipState(rv.chips), [ha, hb] = chipHalf(), capId = rv.picks?.find(([, m]) => m >= 2)?.[0];
  const dl = [["Team", esc(rv.team)], ["League rank", `${ordn(rv.rank)}${rv.last_rank && rv.rank ? ` (${ordn(rv.last_rank)} before GW${C.gw})` : ""}`],
    ["Official total", `${rv.total ?? "–"}${gap != null ? ` · you ${gap > 0 ? `lead by ${gap}` : gap < 0 ? `trail by ${-gap}` : "are level"}` : ""}`],
    [`GW${C.gw} points`, `${gw ?? "–"}${hit > 0 ? ` before a −${hit} hit` : hit === 0 ? " · no hit" : ""}`],
    ["Last captain", capId ? esc(P[capId]?.name || "?") : "Not known"],
    [`Chip in GW${C.gw}`, rv.chip ? esc(CHIP_NAME[rv.chip] || rv.chip) : rv.picks ? "None" : "Not known"],
    [`Chips left GW${ha}–${hb}`, st ? st.filter(x => !x.used).map(x => CHIP_NAME[x.k]).join(", ") || "None" : "Not known"]];
  const li = r => `<li><span><button type="button" data-p="${r.id}" class="pname linkish">${esc(P[r.id].name)}</button> <span class="muted">${T_TEAM(r.id)} · ${f1(r.x)} xP${r.me === 2 ? " · your C" : r.them === 2 ? " · their C" : ""}</span></span><b class="${r.sw > 0 ? "up" : "down"}">${sgn(r.sw)}</b></li>`;
  const lists = !t ? `<p class="note">Season over: there is no next gameweek to compare your teams for.</p>` : !c ? `<p class="note">${fn}'s GW${C.gw} picks aren't in the sample, so the teams can't be compared.</p>` :
    `<div class="rv-edges"><section class="panel"><h3 class="rv-h">Where you gain</h3><p class="muted">Projected GW${g} points from the differences in your XIs</p><ul class="rv-lines">${c.mineOnly.map(li).join("") || '<li class="muted">Nothing</li>'}</ul></section>
      <section class="panel"><h3 class="rv-h">Where ${fn} gains</h3><p class="muted">Projected cost to your team</p><ul class="rv-lines">${c.theirsOnly.map(li).join("") || '<li class="muted">Nothing</li>'}</ul></section></div>`;
  return `${back}<div class="bar rv-sec"><h3 class="rv-h" id="h2h-h" tabindex="-1">Head-to-head</h3><span class="muted">${esc(lg.name)}</span></div>
    <section class="panel rv-moment"><span class="rv-eyebrow">${pinned ? "Pinned rival" : "Selected manager"} · GW${g ?? C.gw} outlook</span><h4 class="rv-headline">You vs ${esc(rv.player)}</h4>
      <p>Your planned GW${g ?? ""} team${t ? ` (active plan: ${esc(planName())})` : ""} against ${fn}'s public GW${C.gw} team.</p>
      <div class="rv-pair"><div><span>Projected advantage</span><b class="${c && c.swing < 0 ? "down" : ""}">${c ? `${sgn(c.swing)} pts` : "–"}</b></div><div><span>Shared players</span><b>${c ? `${c.shared} / 15` : "–"}</b></div></div></section>
    <section class="panel"><h3 class="rv-h">Rival details</h3><dl class="rv-dl">${dl.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>
      <div class="rv-acts">${pinned ? `<button type="button" class="btn sm" data-rvpin="0">Unpin ${fn}</button>` : `<button type="button" class="btn primary sm" data-rvpin="${rv.entry}">${other ? `Pin ${fn} instead of ${esc(firstName(other, lg.rows))}` : `Pin ${fn} as your rival`}</button>`}
      <button type="button" class="btn ghost sm" data-ltab="standings">Choose another manager</button></div></section>
    ${lists}
    ${c ? `<p class="note">Based on ${fn}'s GW${C.gw} team, the latest FPL shows. Changes before the deadline appear afterwards.</p>` : ""}
    ${watchPanel()}`;
}

/* ---------- Weekly honours (awards.py, settled once a gameweek is final; history/awards.json) ----------
   The latest settled week of each league is in data.json; earlier weeks load from awards.json when asked for.
   Medals: competition ranking within each award (1, 2, 3, 3 or 1, 1, 3). Nothing here is ever recalculated. */
const AWARDS = {
  totw: ["Transfer of the Week", "Net points from the week's transfers, after hits."],
  climber: ["Biggest Climber", "Places gained in the official league table."],
  wall: ["The Wall", "Keeper and defenders in the final XI combined."],
  bench: ["Bench Rescue", "Best single automatic substitution."],
  blueprint: ["The Blueprint", "Starters shared with the league's template XI."],
  grain: ["Against the Grain", "Points from starters picked by under 20%."],
  hits: ["Hit Parade", "Points spent on transfer hits."],
  shuffler: ["Team Sheet Shuffler", "Transfers made, including chip weeks."],
};
const AW_NONE = { totw: "Nobody made a permanent transfer (Free Hit squads aren't counted).", climber: "Nobody moved up the table.", wall: "No final XIs were available.",
  bench: "No automatic substitution scored.", blueprint: "No starting XIs were available.", grain: "No starter picked by under 20% scored.", hits: "Nobody took a hit.", shuffler: "Nobody made a transfer." };
const AW = { data: null, busy: false, err: null };
function loadAwards() {
  if (AW.busy || AW.data) return;
  AW.busy = true; AW.err = null;
  fetch("awards.json?t=" + encodeURIComponent(D.meta.built), { cache: "no-store" })
    .then(r => r.ok ? r.json() : Promise.reject(new Error("awards.json returned " + r.status)))
    .then(j => { if (!j || !j.leagues) throw new Error("awards.json had no leagues"); AW.data = j; })
    .catch(e => { AW.err = e.message || String(e); })
    .finally(() => { AW.busy = false; if (S.view === "rivals" && S.ltab === "honours") render(); });
}
function awVal(k, p) {
  return { totw: `${signed(p.value)} ${Math.abs(p.value) === 1 ? "pt" : "pts"}`, climber: `${p.value} place${p.value === 1 ? "" : "s"}`, blueprint: `${p.value}/${p.of}`,
    shuffler: `${p.value}${p.chip ? ` · ${CHIP_SHORT[p.chip] || p.chip}` : ""}` }[k] ?? ptsW(p.value);
}
function awExplain(k, a) {
  const p = a.places[0]; if (!p) return "";
  const nm = esc(p.player), list = xs => xs.map(([n, v]) => `${esc(n)} ${v}`).join(", ");
  const txt = {
    totw: () => `${nm}: arrivals scored ${p.pin} (${list(p.ins) || "none"}); departures ${p.pout} (${list(p.outs) || "none"}); hits ${p.hit}. ${p.pin} − ${p.pout} − ${p.hit} = ${signed(p.value)}.`,
    climber: () => `${nm} moved from ${ordn(p.before)} to ${ordn(p.after)}.`,
    wall: () => `${nm}'s keeper scored ${p.gk} and defenders ${p.df}, in the final XI after automatic subs.`,
    bench: () => `${esc(p.sub_in)} came on for ${esc(p.sub_out)} in ${nm}'s team and scored ${p.value}.`,
    blueprint: () => `Template XI, the most-selected legal XI from ${a.ref_n} starting XIs: ${(a.ref || []).map(esc).join(", ")}.`,
    grain: () => `${nm}: ${p.players.map(([n, v, c]) => `${esc(n)} ${v} (in ${c} of ${a.base} XIs)`).join(", ")}.`,
    hits: () => p.gain == null ? `${nm} spent ${p.value} on hits. Transfer detail isn't available, so whether the arrivals covered it isn't known.` : `${nm} spent ${p.value} on hits; the arrivals scored ${signed(p.gain)} against the players sold, so they ${p.covered_cost ? "covered" : "didn't cover"} the cost.`,
    shuffler: () => `${nm} made ${p.value} transfer${p.value === 1 ? "" : "s"}${p.chip ? ` on a ${CHIP_NAME[p.chip]}` : ""}${p.changed !== p.value ? `, changing ${p.changed} player${p.changed === 1 ? "" : "s"}` : ""}.`,
  }[k]();
  const shared = ["gold", "silver", "bronze"].map(m => a.places.filter(x => x.medal === m)).filter(x => x.length > 1)
    .map(x => `${x.slice(0, -1).map(y => esc(y.player)).join(", ")} and ${esc(x[x.length - 1].player)} share ${x[0].medal}.`).join(" ");
  return txt + (shared ? " " + shared : "");
}
function awardCard(k, a, W) {
  const [title, sub] = AWARDS[k], me = D.meta.team_id, size = W.coverage?.size || W.size;
  const places = a?.places || [];
  const body = !a ? `<p class="note">Not in this week's results.</p>` : a.status === "unavailable" ? `<p class="note aw-why">Not available: ${esc(a.why || "the inputs couldn't be recovered.")}</p>` :
    !places.length ? `<p class="note">${AW_NONE[k]}</p>` :
    `<ol class="podium">${places.map(p => `<li class="${p.entry === me ? "mine" : ""}"><span class="medal m-${p.medal}">${p.medal}</span><span class="aw-who">${esc(p.player)}${p.entry === me ? " · You" : ""}</span><span class="aw-val">${awVal(k, p)}</span></li>`).join("")}</ol><p class="note">${awExplain(k, a)}</p>`;
  const cov = a && a.status !== "unavailable" && a.covered < size ? `<p class="aw-cov">${a.covered} of ${size.toLocaleString("en-GB")} managers covered${W.coverage && W.coverage.members < size ? " (tracked managers only)" : ""}</p>` : "";
  return `<section class="aw-card" aria-labelledby="aw-${k}"><h4 id="aw-${k}" class="rv-h">${title}</h4><p class="muted aw-sub">${sub}</p>${body}${k === "totw" && places.length ? '<p class="aw-cov">Free Hit squads aren\'t counted: they go back after a week.</p>' : ""}${cov}</section>`;
}
function awWho(W) {
  const c = W.coverage || {}, size = c.size || W.size, n = c.members ?? size;
  return n < size ? `Among ${n} tracked managers of ${size.toLocaleString("en-GB")}` : `${size} managers`;
}
function rvFeatured(C, lg) {
  const A = D.awards?.[lg.id], W = A?.latest;
  if (!W) return `<section class="rv-hon"><div class="bar"><h3 class="rv-h">Weekly honours</h3></div><p class="note">${D.awards ? "Awards are settled once a gameweek is final (bonus confirmed). None are saved for this league yet." : "Weekly honours aren't in this update."}</p></section>`;
  const ok = k => W.awards[k]?.places?.length;
  const keys = ["totw", "climber", "wall"].filter(ok);
  for (const k of Object.keys(AWARDS)) if (keys.length < 3 && !keys.includes(k) && ok(k)) keys.push(k);
  return `<section class="rv-hon" aria-labelledby="rvhon-h"><div class="bar"><h3 class="rv-h" id="rvhon-h">Weekly honours</h3><span class="muted">GW${W.gw} · Final${C.in_play ? ` · last settled week` : ""}</span></div>
    ${keys.length ? `<div class="aw-grid">${keys.map(k => awardCard(k, W.awards[k], W)).join("")}</div>` : `<p class="note">No award had a qualifier in GW${W.gw}.</p>`}
    <button type="button" class="linkish rv-go" data-ltab="honours">View all 8 award podiums <span aria-hidden="true">→</span></button></section>`;
}
function vHonours(C, lg) {
  const A = D.awards?.[lg.id];
  if (!A?.gws?.length) return `<section class="panel"><h3 class="rv-h">Weekly honours</h3><p class="note">${D.awards ? "Awards are settled for each league once a gameweek is final (bonus confirmed). None are saved for this league yet." : "Weekly honours aren't in this update."}</p></section>`;
  const gws = A.gws, latest = gws[gws.length - 1], g = gws.includes(S.hgw) ? S.hgw : latest, i = gws.indexOf(g);
  const W = g === latest ? A.latest : AW.data?.leagues?.[lg.id]?.gws?.[g];
  if (!AW.data && !AW.err) loadAwards();
  const sel = `<div class="rv-gwsel"><button type="button" class="btn sm" data-hgw="${gws[i - 1] ?? ""}" aria-label="Earlier gameweek"${i > 0 ? "" : " disabled"}>‹</button>
    <select id="hgwSel" class="sel" aria-label="Gameweek">${gws.slice().reverse().map(x => `<option value="${x}"${x === g ? " selected" : ""}>GW${x} · Final</option>`).join("")}</select>
    <button type="button" class="btn sm" data-hgw="${gws[i + 1] ?? ""}" aria-label="Later gameweek"${i < gws.length - 1 ? "" : " disabled"}>›</button></div>`;
  let body;
  if (!W) body = AW.err ? stateView({ kind: "error", title: `GW${g} awards didn't load`, body: esc(AW.err) + ". The latest week is still shown when you pick it.", action: '<button class="btn primary" data-awretry="1">Try again</button>' })
    : `<p class="note" role="status">Loading GW${g}…</p>`;
  else body = `<div class="aw-grid">${Object.keys(AWARDS).map(k => awardCard(k, W.awards[k], W)).join("")}</div>`;
  const notes = [];
  if (C.in_play && g === latest) notes.push(`GW${C.gw} is still being played, so these are the last settled awards, from GW${g}.`);
  if (W?.source === "backfill") notes.push(`Rebuilt on ${new Date(W.saved).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Europe/London" })} from the league's managers then: anyone who has left since is missing, and Biggest Climber can't be recovered because FPL doesn't keep earlier league ranks.`);
  return `<div class="bar rv-hon-bar"><div><h3 class="rv-h">Weekly honours</h3><p class="muted">${W ? awWho(W) + " · " : ""}Equal results share a medal.</p></div>${sel}</div>
    ${notes.map(n => `<p class="note rv-flag">${n}</p>`).join("")}${body}`;
}

/* ---------- The field: Top 10k or around your rank, against your planned team ---------- */
function vField(C) {
  const g = D.meta.next_gw, t = recTeam(), F = field();
  const seg = `<div class="seg" role="group" aria-label="Compare with"><button type="button" data-field="top10k" aria-pressed="${S.field !== "near"}">Top 10k</button><button type="button" data-field="near" aria-pressed="${S.field === "near"}">Around your rank</button></div>`;
  const rows = F && t ? fieldRows(F, t.mult, g) : [];
  const thr = rows.filter(r => r.impact < -0.3).sort((a, b) => a.impact - b.impact).slice(0, 8);
  const edge = rows.filter(r => r.impact > 0.3).sort((a, b) => b.impact - a.impact).slice(0, 8);
  const xiOwn = F && t ? t.xi.reduce((a, i) => a + (F.own[i] || 0), 0) / t.xi.length : null;
  const capTop = Object.entries(F?.cap || {}).filter(([, v]) => v >= 1).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const chipTxt = Object.entries(F?.chips || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${CHIP_NAME[k] || k} ${v.toFixed(0)}%`).join(" · ") || "none";
  // FL-082: FPL gave no overall rank (before your first finished GW), so the band is centred on an assumed 100,000
  const label = S.field === "near" ? `managers near ${F?.rank_assumed ? "an assumed rank of 100,000 (FPL gave no overall rank)" : "your rank"} (${rankFmt(F?.rank_from)}–${rankFmt(F?.rank_to)})` : "the top 10k";
  const warn = [];
  if (C.gw !== D.meta.cur_gw) warn.push(`This sample is from GW${C.gw}; this week's is taken after the deadline.`);
  if (C.complete === false) warn.push(`Some requests failed when the sample was taken (${C.failed}), so it has fewer teams than planned.`);
  const multTxt = m => m === 2 ? `<span class="pill warn">C</span>` : m === 1 ? "XI" : `<span class="muted">—</span>`;
  const tbl = (list, head) => `<div class="tablebox"><table><thead><tr><th>${head}</th><th class="n">${term("xp", "xP")}</th><th class="n">${term("eo", "EO")}</th><th class="n">You</th><th class="n">${term("swing", "Swing")}</th></tr></thead><tbody>${list.map(r => `<tr class="${MINE.has(r.id) ? "mine" : ""}"><td><button data-p="${r.id}" class="pname linkish">${esc(P[r.id].name)}</button> <span class="muted">${T[P[r.id].team].short}</span></td><td class="n">${f1(r.x)}</td><td class="n">${Math.round(r.eo * 100)}%</td><td class="n">${multTxt(r.mine)}</td><td class="n ${r.impact > 0 ? "up" : "down"}">${sgn(r.impact)}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">None</td></tr>`}</tbody></table></div>`;
  const li = r => `<li><span><button type="button" data-p="${r.id}" class="pname linkish">${esc(P[r.id].name)}</button> <span class="muted">${T_TEAM(r.id)} · ${Math.round(r.eo * 100)}% EO</span></span><b class="${r.impact > 0 ? "up" : "down"}">${sgn(r.impact)}</b></li>`;
  let main;
  if (!t) main = `<p class="note">Season over: there is no next gameweek to set your team against the field.</p>`;
  else if (!F) main = `<p class="note">Ownership and captaincy sample unavailable for ${label}. Choose another sample or wait for the next update.</p>`;
  else main = `<p class="muted rv-fsub">GW${g} plan against ${F.n.toLocaleString("en-GB")} GW${C.gw} teams · ${label}</p>
    <div class="rv-edges"><section class="panel"><h4 class="rv-h">Your edges</h4><p class="muted">Top 3 by projected swing</p><ul class="rv-lines">${edge.slice(0, 3).map(li).join("") || '<li class="muted">None</li>'}</ul></section>
      <section class="panel"><h4 class="rv-h">Field threats</h4><p class="muted">Top 3 by projected swing</p><ul class="rv-lines">${thr.slice(0, 3).map(li).join("") || '<li class="muted">None</li>'}</ul></section></div>
    <details class="rv-more"><summary>Full player tables and swing definitions</summary>
      <p class="note">What ${label} owned and captained in GW${C.gw} (${F.n.toLocaleString("en-GB")} teams sampled), against your planned GW${g} team (active plan: ${esc(planName())}). ${term("eo", "EO")} (effective ownership) counts captains twice. ${term("swing", "Swing")} = how much a player's projected points move your rank: negative means the field gains on you if he delivers.</p>
      <div class="statgrid"><div><h4 style="margin-bottom:8px">Threats</h4>${tbl(thr, "Owned by the field")}</div><div><h4 style="margin-bottom:8px">Your edges</h4>${tbl(edge, "Your differentials")}</div></div></details>
    <details class="rv-more"><summary>Captaincy split, XI ownership and chips</summary>
      <div class="kpis" style="margin:10px 0 14px">
        <div class="kpi"><span class="lbl">Your XI's average ownership</span><b>${xiOwn.toFixed(0)}%</b><span class="delta muted">${xiOwn > 60 ? "very template" : xiOwn > 40 ? "fairly template" : "plenty of differentials"}</span></div>
        <div class="kpi"><span class="lbl">Their captain</span><b>${esc(P[capTop[0]?.[0]]?.name || "–")}</b><span class="delta muted">${capTop[0] ? capTop[0][1].toFixed(0) + "% of teams" : ""}</span></div>
        <div class="kpi"><span class="lbl">Chips played GW${C.gw}</span><b style="font-size:18px">${chipTxt}</b><span class="delta muted">${fieldHitsTxt(F)}</span></div>
      </div>
      <span class="lbl">Captaincy split</span><div class="capbars" style="margin-top:6px">${capTop.map(([id, v], k) => `<div class="cb ${k === 0 ? "top" : ""}"><span class="pname">${esc(P[id]?.name || id)}</span><div class="track"><div class="fill" style="width:${v}%"></div></div><span class="val">${v.toFixed(0)}%</span></div>`).join("")}</div></details>`;
  return `${seg}<section class="panel rv-field" aria-labelledby="rvf-h"><h3 class="rv-h" id="rvf-h">Where you gain and lose</h3>${warn.map(w => `<p class="note rv-flag">${w}</p>`).join("")}${main}</section>
  ${eliteGapPanel(C)}`;
}

/* ---------- compare two teams: where your squads differ and who that favours next gameweek ---------- */
function teamCompare(rv, { gw, close }) {
  const t = recTeam(), g = D.meta.next_gw;
  if (!t) return `<div class="panel cmp-panel"><div class="bar"><h3>You vs ${esc(rv.player)}</h3>${close ? `<button class="btn" ${close}>Close</button>` : ""}</div>
    <p class="note">Season over: there is no next gameweek to compare your teams for.</p></div>`;
  const { swing, capT, shared, mineOnly, theirsOnly } = cmpDiffs(rv, t);
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

/* FL-141: the top 10k against everyone, from the ownership sample (crowd.py, every 5th top-10k manager) and FPL's own
   figures. Overall ownership is FPL's selected_by_percent (P[i].own); "started" in the top 10k is effective ownership
   minus captaincy (a captain counts twice in EO; a Bench Boost bench counts as started); benched = owned - started.
   Chips: the sample's share against FPL's count of everyone who played each chip that GW. Hits: the sample's average;
   FPL publishes no overall figure, so none is shown. Missing / old / incomplete: no top-10k sample -> no panel; a
   sample from an earlier GW or with failed requests (FL-082) -> said in the note; a player not in this build's list
   (crowd sample slimmed to it) -> left out. */
function eliteGapPanel(C) {
  const TK = C?.top10k;
  if (!TK || !TK.n || !TK.own) return "";
  const ids = Object.keys(TK.own).map(Number).filter(i => P[i]);
  const gap = i => (TK.own[i] || 0) - (P[i].own || 0);
  const started = i => Math.max(0, (TK.eo?.[i] || 0) - (TK.cap?.[i] || 0));
  const benched = i => Math.max(0, (TK.own[i] || 0) - started(i));
  const byGap = ids.filter(i => (TK.own[i] || 0) >= 5 || (P[i].own || 0) >= 5).sort((a, b) => gap(b) - gap(a));
  const fav = byGap.slice(0, 6), avoid = byGap.slice(-6).reverse().filter(i => gap(i) < 0);
  const bench = ids.filter(i => (TK.own[i] || 0) >= 10).sort((a, b) => benched(b) - benched(a)).slice(0, 6).filter(i => benched(i) >= 1);
  const pc = x => `${x.toFixed(0)}%`;
  const nm = i => `<button data-p="${i}" class="pname linkish">${esc(P[i].name)}</button> <span class="muted">${T_TEAM(i)}</span>`;
  const tbl = (list, head, cells) => `<div class="tablebox"><table><thead><tr><th>${head}</th>${cells.map(c => `<th class="n">${c[0]}</th>`).join("")}</tr></thead><tbody>${list.map(i => `<tr class="${MINE.has(i) ? "mine" : ""}"><td>${nm(i)}</td>${cells.map(c => `<td class="n">${c[1](i)}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${cells.length + 1}" class="muted">None</td></tr>`}</tbody></table></div>`;
  const gapCells = [["Top 10k", i => pc(TK.own[i] || 0)], ["Everyone", i => pc(P[i].own || 0)], ["Gap", i => `<b class="${gap(i) > 0 ? "up" : "down"}">${gap(i) > 0 ? "+" : ""}${gap(i).toFixed(0)}</b>`]];
  const NAMES = { bboost: "Bench Boost", "3xc": "Triple Captain", freehit: "Free Hit", wildcard: "Wildcard" };
  const chips = Object.keys(NAMES).map(k => `<tr><td>${NAMES[k]}</td><td class="n">${TK.chips?.[k] != null ? `${TK.chips[k].toFixed(1)}%` : "0%"}</td><td class="n">${C.overall_chips?.[k] != null ? `${C.overall_chips[k].toFixed(1)}%` : "–"}</td></tr>`).join("");
  const notes = [];
  if (C.gw !== D.meta.cur_gw) notes.push(`This sample is from GW${C.gw}; this week's is taken after the deadline.`);
  if (C.complete === false) notes.push(`Some requests failed when it was taken (${C.failed}), so it's smaller than planned.`);
  return `<div class="panel rv-elite"><div class="bar"><h3 class="rv-h">Top 10k v everyone</h3><span class="muted">GW${C.gw} ownership and selection</span></div>
    <p class="note" style="margin-top:0">Where the top 10,000 managers (${TK.n.toLocaleString("en-GB")} teams sampled) differ from all ${C.total_players ? C.total_players.toLocaleString("en-GB") : "FPL"} managers. Ownership is the share of teams that own him.${notes.length ? " " + notes.join(" ") : ""}</p>
    <details class="rv-more"><summary>Ownership gaps in both directions</summary><div class="statgrid"><div><h4 style="margin-bottom:8px">The top 10k own more</h4>${tbl(fav, "Player", gapCells)}</div>
    <div><h4 style="margin-bottom:8px">Everyone owns more</h4>${tbl(avoid, "Player", gapCells)}</div></div></details>
    <details class="rv-more"><summary>Owned but benched by the top 10k</summary>${tbl(bench, "Player", [["Owned", i => pc(TK.own[i] || 0)], ["Started", i => pc(started(i))], ["Benched", i => pc(benched(i))]])}
      <p class="note">Started = in the XI (a Bench Boost bench counts as started).</p></details>
    <details class="rv-more"><summary>Chip use and average hit cost</summary><h4 style="margin:8px 0">Chips played GW${C.gw}</h4><div class="tablebox"><table><thead><tr><th>Chip</th><th class="n">Top 10k</th><th class="n">Everyone</th></tr></thead><tbody>${chips}</tbody></table></div>
      <p class="note">Hits: ${TK.hits != null ? `the top 10k took ${TK.hits.toFixed(2)} points of hits per manager on average` : "not in this sample"}; FPL doesn't publish a figure for everyone.</p></details></div>`;
}
const T_TEAM = i => (T[P[i]?.team]?.short || "");   // club short name (global T: teams)
