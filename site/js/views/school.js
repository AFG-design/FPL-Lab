// FPL School (FL-147): any team ID in, a squad rating and one suggested move out. Read-only: nothing is saved.
//
// FPL's API doesn't answer other websites' pages, so the team and its picks come through the relay in fpl_school.json
// (a Cloudflare Worker, docs/fpl-school-relay.md), shipped as D.school.relay. Everything else is this build's data.
// Scored like the Squad rating on Home (rating.js): best XI + captain each rating gameweek from the team's 15, no
// transfers, on rating.js's ratingScore scale: 30% under the top-10k average (0), the top-10k average (50) and the
// best 15 for the team's own money (100), the best 15 worked out
// by the browser optimiser (plan-solver.js, rebuild in week 1 then hold, as build.py's rating solve). One move: the
// single transfer (same position, affordable, at most 3 from a club) that adds most to that best XI + captain.
// Missing / late / ambiguous (each said in the tab, never filled in):
//   no relay set up -> says so, with the guide; the relay or FPL not answering, an unknown team, no picks yet -> says
//   which; selling prices are private -> the team's money is its bank plus current prices, marked assumed; a player
//   with no projection -> 0 xP and listed; the best-15 solve failing -> rated against the top-10k only, said; no
//   rating weeks (season over) -> says so; no move adds points -> "keep the squad".
// Squad view (manager card + pitch), from the same two relay answers, no new paths:
//   card: each fact is kept only when FPL sent it (null or missing -> left off the card, never 0 or "—"); a
//   favourite_team id this build doesn't know is left off too; no chip played (active_chip null) -> no chip line.
//   pitch: positions 1-11 start, 12-15 are the bench in FPL's order, captain and vice as picked for that gameweek.
//   Numbers are xP for the first rating gameweek. A player outside the projections still gets a card ("No
//   projection", not tappable). Picks without 15 positions 1-15 -> no pitch, and the tab says why.
const SCHOOL = { id: "", busy: false, msg: "", err: "", res: null };
const SCHOOL_MIN = { GKP: 1, DEF: 3, MID: 2, FWD: 1 }, SCHOOL_MAX = { GKP: 1, DEF: 5, MID: 5, FWD: 3 };

function schoolInfo(id) {
  if (P[id]) return { name: P[id].name, pos: P[id].pos, team: P[id].team, price: P[id].price, xp: P[id].xp || {}, projected: true };
  const o = (D.school?.others || []).find(r => r[0] === id);
  return o ? { name: o[1], pos: o[2], team: o[3], price: o[4], xp: {}, projected: false } : null;
}
// best XI + captain for one gameweek from these players, by FPL's formation rules (as tools' and rating.js's best XI)
function schoolBestPts(ids, g, info) {
  const xp = i => info[i]?.xp[g] || 0, pos = i => info[i].pos;
  const order = ids.filter(i => info[i]).sort((a, b) => xp(b) - xp(a));
  const xi = [], cnt = { GKP: 0, DEF: 0, MID: 0, FWD: 0 };
  const need = () => Object.keys(SCHOOL_MIN).reduce((a, k) => a + Math.max(0, SCHOOL_MIN[k] - cnt[k]), 0);
  const add = i => {
    const p = pos(i); if (xi.includes(i) || xi.length >= 11 || cnt[p] >= SCHOOL_MAX[p]) return;
    cnt[p]++; if (xi.length + 1 + need() > 11) { cnt[p]--; return; }
    xi.push(i);
  };
  Object.keys(SCHOOL_MIN).forEach(p => order.filter(i => pos(i) === p).forEach(i => { if (cnt[p] < SCHOOL_MIN[p]) add(i); }));
  order.forEach(add);
  return xi.reduce((a, i) => a + xp(i), 0) + (xi.length ? Math.max(...xi.map(xp)) : 0);
}
async function schoolGet(path) {
  let r;
  try { r = await fetch(D.school.relay.replace(/\/$/, "") + path, { cache: "no-store" }); }
  catch (e) { throw new Error("The relay didn't answer. Is it deployed, and is the address in fpl_school.json right? (docs/fpl-school-relay.md)"); }
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`FPL didn't answer (${r.status}). Try again in a moment.`);
  return r.json();
}
// the review, from FPL's answers (entry, picks) and this build's data; the best 15 (best) is filled in afterwards
function schoolReview(teamId, entry, picks) {
  const R = D.rating || {}, gws = R.gws || [];
  if (!gws.length) throw new Error("This build has no rating gameweeks (season over, or no plan this time).");
  const ids = picks.picks.map(p => p.element), info = {};
  ids.forEach(i => { info[i] = schoolInfo(i); });
  const unknown = ids.filter(i => !info[i]);
  if (unknown.length) throw new Error(`This build doesn't know ${unknown.length} of the team's players; try again after the next refresh.`);
  const bank = (picks.entry_history?.bank || 0) / 10;
  const budget = bank + ids.reduce((a, i) => a + info[i].price, 0);
  const pts = sq => gws.reduce((a, g) => a + schoolBestPts(sq, g, info), 0);
  const mine = pts(ids), field = R.field ? R.field.reduce((a, b) => a + b, 0) : null;
  const clubs = {}; ids.forEach(i => { clubs[info[i].team] = (clubs[info[i].team] || 0) + 1; });
  const x5 = p => gws.reduce((a, g) => a + (p.xp?.[g] || 0), 0);
  let move = null;
  ids.forEach(out => {
    const o = info[out], money = bank + o.price;
    D.players.filter(p => p.pos === o.pos && !ids.includes(p.id) && p.ok !== false && p.price <= money + 1e-9
      && (clubs[p.team] || 0) - (o.team === p.team ? 1 : 0) < 3)
      .sort((a, b) => x5(b) - x5(a)).slice(0, 12).forEach(p => {
        const sq = ids.map(i => i === out ? p.id : i), inf = { ...info, [p.id]: schoolInfo(p.id) };
        const gain = gws.reduce((a, g) => a + schoolBestPts(sq, g, inf), 0) - mine;
        if (gain > 0.05 && (!move || gain > move.gain)) move = { out, in: p.id, gain, outInfo: o, inInfo: inf[p.id] };
      });
  });
  return { teamId, team: entry.name, manager: `${entry.player_first_name || ""} ${entry.player_last_name || ""}`.trim(),
    gw: picks.entry_history?.event || entry.current_event, gws, mine, field, best: null, bestNote: "working",
    budget, bank, move, notProjected: ids.filter(i => !info[i].projected).map(i => info[i].name),
    card: schoolCard(entry, picks), squad: schoolSquad(picks),
    unprojected: Object.fromEntries(ids.filter(i => !info[i].projected).map(i => [i, { name: info[i].name, pos: info[i].pos, team: info[i].team }])) };
}
const SCHOOL_CHIP = { wildcard: "Wildcard", freehit: "Free Hit", bboost: "Bench Boost", "3xc": "Triple Captain", manager: "Assistant Manager" };
// the manager card's facts, each only when FPL sent it (finite numbers, non-empty text)
function schoolCard(entry, picks) {
  const eh = picks.entry_history || {}, c = {};
  const n = v => typeof v === "number" && Number.isFinite(v);
  if (typeof entry.player_region_name === "string" && entry.player_region_name) c.region = entry.player_region_name;
  if (entry.favourite_team != null && T[entry.favourite_team]) c.club = T[entry.favourite_team].name;
  if (n(entry.summary_overall_points)) c.overallPts = entry.summary_overall_points;
  if (n(entry.summary_overall_rank)) c.overallRank = entry.summary_overall_rank;
  if (n(entry.summary_event_points)) c.gwPts = entry.summary_event_points;
  if (n(entry.summary_event_rank)) c.gwRank = entry.summary_event_rank;
  if (n(eh.value)) c.value = eh.value / 10;
  if (n(eh.bank)) c.bankNow = eh.bank / 10;
  if (n(eh.event_transfers)) c.transfers = eh.event_transfers;
  if (n(eh.event_transfers_cost)) c.hits = eh.event_transfers_cost;
  if (n(eh.points_on_bench)) c.benchPts = eh.points_on_bench;
  if (picks.active_chip) c.chip = SCHOOL_CHIP[picks.active_chip] || picks.active_chip;   // an unknown code is shown as FPL sends it
  return c;
}
// the XI and bench in FPL's order; null when the picks don't hold positions 1-15 once each
function schoolSquad(picks) {
  const ps = [...picks.picks].sort((a, b) => a.position - b.position);
  if (ps.length !== 15 || ps.some((p, k) => p.position !== k + 1)) return null;
  return { xi: ps.slice(0, 11).map(p => p.element), bench: ps.slice(11).map(p => p.element),
    cap: ps.find(p => p.is_captain)?.element ?? null, vice: ps.find(p => p.is_vice_captain)?.element ?? null };
}
function schoolScore(r) {
  // the same scale as Home's Squad rating (ratingScore in rating.js)
  return ratingScore(r.mine, r.field, r.best);
}
async function schoolBest(r) {
  try {
    const highs = await getHighs();
    const settings = window.FPLSolver.settingsFrom(D.plan_rules);
    if (!settings) throw new Error("no planner settings");
    const players = {};
    D.players.forEach(p => { players[p.id] = { pos: p.pos, team: p.team, price: p.price, xp: p.xp || {}, ok: p.ok !== false }; });
    const sol = await window.FPLSolver.solve(highs, { ...settings, players, squad: [], sell: {}, bank: r.budget, ft0: 5, gws: r.gws,
      hit: 0, ftValue: 0, maxMovesWeek: 15, freezeAfter: 1, maxHits: null, locked: [], banned: [] }, () => { SOLVE.highs = null; return getHighs(); });
    r.best = sol.value; r.bestNote = null;
  } catch (e) {
    r.best = null; r.bestNote = `the best 15 for this money couldn't be worked out (${e.message || e}), so the rating is against the top-10k only`;
  }
}
async function schoolRun(id) {
  SCHOOL.id = String(id); SCHOOL.err = ""; SCHOOL.res = null; SCHOOL.busy = true; SCHOOL.msg = "Fetching the team…"; render();
  try {
    const entry = await schoolGet(`/entry/${id}/`);
    if (!entry) throw new Error(`FPL has no team ${id}.`);
    if (!entry.current_event) throw new Error(`Team ${id} hasn't picked a team for a gameweek yet.`);
    const picks = await schoolGet(`/entry/${id}/event/${entry.current_event}/picks/`);
    if (!picks) throw new Error(`FPL has no GW${entry.current_event} picks for team ${id}.`);
    SCHOOL.res = schoolReview(id, entry, picks);
    SCHOOL.msg = "Working out the best 15 for this money…"; render();
    await schoolBest(SCHOOL.res);
    SCHOOL.msg = "";
  } catch (e) { SCHOOL.err = e.message || String(e); SCHOOL.msg = ""; SCHOOL.res = null; }
  SCHOOL.busy = false; render();
}

// the manager card: only the facts FPL sent (r.card holds nothing else)
function schoolCardHtml(r) {
  const c = r.card || {}, n = v => Number(v).toLocaleString("en-GB"), g = r.gw;
  const items = [
    ["Overall points", c.overallPts != null && n(c.overallPts)], ["Overall rank", c.overallRank != null && n(c.overallRank)],
    [`GW${g} points`, c.gwPts != null && n(c.gwPts)], [`GW${g} rank`, c.gwRank != null && n(c.gwRank)],
    [`GW${g} chip`, c.chip && esc(c.chip)],
    [`GW${g} transfers`, c.transfers != null && String(c.transfers)], [`GW${g} hits`, c.hits != null && (c.hits ? `−${c.hits} pts` : "None")],
    [`GW${g} bench points`, c.benchPts != null && String(c.benchPts)],
    ["Team value", c.value != null && `${money(c.value)} <small class="muted">incl. bank</small>`], ["In the bank", c.bankNow != null && money(c.bankNow)],
    ["Favourite club", c.club && esc(c.club)], ["Region", c.region && esc(c.region)],
  ].filter(([, v]) => v);
  return items.length ? `<dl class="sch-card" aria-label="Manager card">${items.map(([l, v]) => `<div><dt>${l}</dt><dd>${v}</dd></div>`).join("")}</dl>` : "";
}
// their team on the pitch: xP for the first rating gameweek, the One move's player out outlined and labelled
function schoolPitch(r) {
  const sq = r.squad, g = r.gws[0], out = r.move?.out;
  if (!sq) return `<p class="note">FPL's picks for this team don't list 15 players in positions 1–15, so the pitch isn't drawn.</p>`;
  const o = { cap: sq.cap, vice: sq.vice, sel: out };
  const item = id => {
    const u = r.unprojected?.[id];
    const role = sq.cap === id ? "cap" : sq.vice === id ? "vice" : "";
    const it = u ? { id, np: u, big: "–", sub: "No xP", role, sel: out === id,
      label: `${u.name}, ${u.pos}, not in the projections${role === "cap" ? ", captain" : role === "vice" ? ", vice-captain" : ""}`,
      c: { big: "–", sub: "No projection", foot: [] } } : projItem(id, g, o);
    if (it && id === out) {
      it.label += ", the suggested move's player out";
      it.c = { ...it.c, foot: [...(it.c?.foot || []), '<span class="sch-out">Out: the one move</span>'] };
      it.ex = `${it.ex || ""}<span class="sch-out">OUT</span>`;
    }
    return it;
  };
  return luPitch(sq.xi.map(item).filter(Boolean), sq.bench.map(item).filter(Boolean), {
    label: `${r.team || "Their"} GW${r.gw} XI`,
    key: `<span>Their GW${r.gw} team, captain, vice and bench order as they picked it</span><span>Big number: projected points for GW${g}; the captain's ×2 is marked, not added</span>${S.lineup !== "kits" ? "<span>Assumed: no official return date or chance, so the projection rests on our defaults</span>" : ""}<span>C captain · V vice · % chance of playing${out ? " · outlined: the one move's player out" : ""} · – no projection</span>${fdrKey()}`,
  });
}

function vSchool() {
  const relay = D.school?.relay;
  const form = `<form class="filters" id="schoolForm" style="margin:8px 0"><input id="schoolId" inputmode="numeric" pattern="[0-9]*" placeholder="FPL team ID" aria-label="FPL team ID" value="${esc(SCHOOL.id)}" style="max-width:180px" ${relay ? "" : "disabled"}><button class="btn primary" type="submit" ${relay && !SCHOOL.busy ? "" : "disabled"}>${SCHOOL.busy ? "Reviewing…" : "Review"}</button></form>`;
  const intro = `<p class="note" style="margin-top:0">Type any team ID (the number in the address of their Points page on the FPL site) for a rating and one suggested move. Read-only: nothing is saved, and the rest of the app stays on your team.</p>`;
  if (!relay) return `<div class="panel"><h2>FPL School</h2>${intro}${form}<p class="verdict">The relay isn't set up yet, so teams can't be fetched. It's a one-time, 5-minute job: see <code>docs/fpl-school-relay.md</code>, then put its address in <code>fpl_school.json</code>.</p></div>`;
  let body = "";
  if (SCHOOL.err) body = `<p class="verdict bad" role="alert">${esc(SCHOOL.err)}</p>`;
  else if (SCHOOL.res) {
    const r = SCHOOL.res, score = r.bestNote === "working" ? null : schoolScore(r);
    const word = score == null ? "" : ratingWord(score);
    const m = r.move;
    const notes = [`Money: ${money(r.budget)} (${money(r.bank)} in the bank), with players at their current prices: their real selling prices are private and can be lower (assumed).`];
    if (r.bestNote && r.bestNote !== "working") notes.push(r.bestNote.charAt(0).toUpperCase() + r.bestNote.slice(1) + ".");
    if (r.notProjected.length) notes.push(`Not in the projections, counted as 0: ${r.notProjected.map(esc).join(", ")}.`);
    body = `<h3 style="margin-top:12px">${esc(r.team || "")} <span class="muted">(${esc(r.manager)})</span></h3>
      <p class="muted">Their GW${r.gw} team, projected over GW${r.gws[0]}–${r.gws[r.gws.length - 1]} with no transfers.</p>
      ${schoolCardHtml(r)}
      <div class="bar lu-bar"><h3>GW${r.gws[0]} projection</h3>${lineupToggle()}</div>
      ${schoolPitch(r)}
      <div class="kpis" style="margin:10px 0">
        <div class="kpi"><span class="lbl">Rating</span><b>${score == null ? "…" : score}<small>/100</small></b><span class="delta muted">${score == null ? "working out the best 15" : word}</span></div>
        <div class="kpi"><span class="lbl">Their squad</span><b>${f1(r.mine)}</b><span class="delta muted">projected points</span></div>
        ${r.field != null ? `<div class="kpi"><span class="lbl">Top-10k average</span><b>${f1(r.field)}</b><span class="delta ${r.mine >= r.field ? "up" : "down"}">${f1(Math.abs(r.mine - r.field))} ${r.mine >= r.field ? "ahead" : "behind"}</span></div>` : ""}
        ${r.best != null ? `<div class="kpi"><span class="lbl">Best for ${money(r.budget)}</span><b>${f1(r.best)}</b><span class="delta muted">${f1(r.best - r.mine)} more than theirs</span></div>` : ""}
      </div>
      <h3>One move</h3>
      <p class="verdict">${m ? `${esc(m.outInfo.name)} (${money(m.outInfo.price)}) → <b>${esc(m.inInfo.name)}</b> (${money(m.inInfo.price)}): <b class="up">${sgn(m.gain)}</b> projected points over those weeks.` : "No single transfer adds points: keep the squad."}</p>
      <p class="note">${notes.join("<br>")}</p>`;
  }
  return `<div class="panel"><h2>FPL School</h2>${intro}${form}<p class="st-msg" aria-live="polite">${esc(SCHOOL.msg)}</p>${body}</div>`;
}
