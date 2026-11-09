// Home: two views behind one switch.
//   Next deadline  preparing for the coming deadline: your plan (or the model's), the three calls, the pitch.
//   Current GW     the squad you actually submitted for the gameweek under way (or just finished), with its points.
// The two never share a squad: Next deadline reads the plan (core/plan.js), Current GW reads FPL's picks in D.live.
//
// Missing, late or ambiguous data, and what each part does:
//   - Which view opens: the one you last picked (localStorage "fpl.home"). On a first visit, Current GW while FPL says a
//     gameweek is under way (meta.cur_gw set and meta.cur_finished false: FPL's own flag, not "no live matches"),
//     otherwise Next deadline. That first choice is fixed for the visit, so a data refresh never flips the view.
//   - No live data for the current gameweek (D.live missing, or for another GW): Current GW says so and shows nothing
//     made up. Before GW1's deadline there's no current gameweek and it says that instead.
//   - Points: FPL's own gameweek points once FPL marks the gameweek finished; before that, the live total from
//     liveState (provisional bonus, auto-subs only once a starter's matches are all over), labelled provisional.
//   - Live rank: only liveState's estimate (needs FPL's rank sample), only while matches are on, marked provisional.
//     Without it the card says it's unavailable; after the gameweek it shows FPL's official overall rank.
//   - Expected points for Current GW: the forecast saved before that deadline (history/proj_gwN.json, joined in
//     build.py), never re-worked with later data. No saved forecast: "Unavailable", not zero.
//   - Money: team value is today's market prices (the only prices we have) and says so with the update time; bank is
//     FPL's figure for the gameweek's picks. In a Free Hit week FPL's bank is the restored one, so Current GW shows
//     the bank as unavailable rather than the wrong week's cash. Next deadline's bank is after planned moves, using
//     your real selling prices (plan.js bankAt).
//   - Double gameweeks: a player's state counts all his matches ("1 of 2 played"), so someone who has played can
//     still have points to come.
//   - Rival differences: field ownership (crowd data) for this gameweek only; any other gameweek's file is not used.

let WEEK_INTRO_DONE = false;   // the hero's entrance motion plays on the first draw only
const HOME_VIEWS = [["next", "Next deadline"], ["current", "Current GW"]];
{ const v = store.get("fpl.home"); S.home = HOME_VIEWS.some(([k]) => k === v) ? v : null; }
const gwInProgress = () => D.meta.cur_gw != null && !D.meta.cur_finished;
function homeView() {
  if (!S.home) S.home = gwInProgress() ? "current" : "next";   // first visit: fixed for the visit, not stored
  return S.home;
}
const hm = iso => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
const whenTxt = iso => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
const intSgn = n => (n > 0 ? "+" : n < 0 ? "−" : "±") + Math.abs(n);

function vHome() {
  const v = homeView(), cg = D.meta.cur_gw, ng = D.meta.next_gw;
  const tabs = HOME_VIEWS.map(([k, l]) => {
    const gw = k === "next" ? ng : cg, on = k === v;
    return `<button type="button" role="tab" id="hometab-${k}" data-home="${k}" aria-selected="${on}" aria-controls="homepanel" tabindex="${on ? 0 : -1}">
      ${l}<span class="ht-gw">${gw ? "GW" + gw : "–"}</span></button>`;
  }).join("");
  const hint = v === "next" && gwInProgress() ? `<span class="home-hint"><span class="live-dot" aria-hidden="true"></span>GW${cg} is under way: its points are in Current GW.</span>`
    : v === "current" && ng ? `<span class="home-hint">Plan changes apply to the GW${ng} deadline.</span>` : "";
  let body;
  try { body = v === "current" ? vCurrent() : vNext(); } catch (e) {
    console.error(e);
    body = stateView({ kind: "error", title: "This view couldn't be drawn", body: "Something in the latest data didn't match what this page expects. The other view should still work." });
  }
  return `<div class="homeswitch"><div class="seg hometabs" role="tablist" aria-label="Homepage view">${tabs}</div>${hint}</div>
    <div id="homepanel" role="tabpanel" aria-labelledby="hometab-${v}" class="home home-${v}">${body}</div>`;
}

/* ---------- shared pieces ---------- */
// team value, bank and expected points, one row above the pitch on both views. A value of null shows "Unavailable"
function moneyRow(items) {
  return `<dl class="mrow">${items.map(x => `<div class="mr"><dt>${x.lbl}</dt><dd class="mr-v${x.cls ? " " + x.cls : ""}">${x.val == null ? '<span class="mr-na">Unavailable</span>' : x.val}</dd><dd class="mr-s">${x.sub}</dd></div>`).join("")}</dl>`;
}
const squadValue = ids => ids.every(i => P[i] && P[i].price != null) ? Math.round(ids.reduce((a, i) => a + P[i].price, 0) * 10) / 10 : null;
function sidePanel(title, body, act = "", extra = "") {
  return `<section class="panel side"><div class="side-h"><h3>${title}</h3>${extra}</div>${body}${act ? `<div class="side-act">${act}</div>` : ""}</section>`;
}
// plan origin: the optimiser's plan untouched, your re-plan, or your own draft (any edit, lineup or captain choice)
function planKind() {
  const ov = Object.values(SB.ov || {}).some(o => o && (o.start?.length || o.bench?.length || o.cap || o.vice || o.order?.length));
  if (SB.source.startsWith("plan:") && !ov) {
    const k = SB.source.slice(5);
    if (D.plans?.[k] && sameMoves(planMoves(D.plans[k]), SB.moves))
      return { kind: "model", label: k === recommendedPlan() ? "Model recommendation" : "Model plan", plan: planLabel(k) };
  }
  if (SB.source.startsWith("replan:") && !ov) return { kind: "replan", label: "Optimiser re-plan" };
  return { kind: "draft", label: "Your active draft" };
}

/* ---------- Next deadline ---------- */
function vNext() {
  const c = weekCalls();
  if (!c) return stateView({ title: "No gameweek to plan", body: "The next deadline appears here once FPL publishes it." });
  const { g, me, w0, ft, moves0 } = c, k = planKind(), n = moves0.length;
  const intro = !WEEK_INTRO_DONE; WEEK_INTRO_DONE = true;   // entrance motion on the first draw only
  const why = k.kind === "model" ? `The ${MODES[S.mode]} strategy's plan (${esc(k.plan)}), as the optimiser made it. Any change you make turns it into your draft.`
    : k.kind === "replan" ? "The optimiser re-planned around your locks and rules. Any change you make turns it into your draft."
    : "Your draft is separate from the model's recommendation. Compare them before you commit.";
  const hero = `<section class="hero compact${intro ? " intro" : ""}" aria-label="Your plan for GW${g}">
    <p class="eyebrow">GW${g} · <span class="hero-kind">${k.label}</span> · Deadline ${ukTime(D.meta.deadline)} · <em>${countdown(D.meta.deadline)} left</em></p>
    <h1>${n ? `${n} move${n > 1 ? "s" : ""} planned.` : "No moves planned."} <span class="cap">${esc(P[me.cap].name)}</span> captain.</h1>
    <p class="hero-why">${why}${c.later.length ? ` ${c.later.length} more move${c.later.length > 1 ? "s" : ""} later in the plan.` : ""}</p>
    <div class="hero-acts"><button class="btn primary" data-plgo="compare">Compare with model</button><button class="btn" data-plgo="edit">Open planner</button></div>
  </section>`;

  // transfers
  const horizon = `GW${PG[0]}–${PG[PG.length - 1]}`;
  // one-line reason per move (U2): the two players' own xP over the plan length and the money it frees or costs, using
  // your real selling price. It's the player swap alone; the card's totals below include lineup, captain and hits.
  // A player with no projection counts as 0 xP.
  const why1 = m => { const d = xpFrom(m.in, g, PG.length) - xpFrom(m.out, g, PG.length), cash = Math.round((sellPrice(m.out) - P[m.in].price) * 10) / 10;
    return `${esc(P[m.in].name)}: ${sgn(d)} xP over ${PG.length} GW${PG.length === 1 ? "" : "s"} vs ${esc(P[m.out].name)}${cash > 0 ? `, frees ${money(cash)}` : cash < 0 ? `, costs ${money(-cash)}` : ", same money"}`; };
  const mvList = n ? `<ul class="dc-moves">${moves0.map(m => `<li><span class="out"><span class="sr">Out: </span>${esc(P[m.out].name)}</span><span class="arr" aria-hidden="true">→</span><span class="in"><span class="sr">In: </span>${esc(P[m.in].name)}</span><span class="muted mono">${money(P[m.in].price)}</span><small class="dc-why">${why1(m)}</small>${reasonBtn(m.gw, m.out, m.in, "why")}</li>`).join("")}</ul>`
    : `<p class="dc-do">Roll: no transfers planned</p>`;
  const tBody = `${mvList}
    <dl class="dc-nums">
      <div><dt>Hits</dt><dd>${w0.hits ? `<span class="down">−${4 * w0.hits}</span>` : "None"}</dd></div>
      <div><dt>Projected vs rolling</dt><dd class="${c.ptsVsRoll > 0.05 ? "up" : c.ptsVsRoll < -0.05 ? "down" : ""}">${sgn(c.ptsVsRoll)}</dd></div>
      <div><dt>Banked FTs (assumed)</dt><dd>${sgn(c.ftValue)}</dd></div>
    </dl>
    <p class="dc-sub">${n ? `Projected points over ${horizon} (${PG.length} GWs), after hits. Banked free transfers are assumed to be worth 1.5 pts each; the verdict adds the two.` : `You'll have ${Math.min(5, ft + 1)} free transfers next week. Compare against the model's moves in the planner.`}</p>`;
  const tAct = `<button class="btn primary sm" data-plgo="edit:suggest">Compare transfers →</button>${n ? `<button class="btn sm" data-howto="${g}">Make these moves on FPL</button>` : ""}`;

  // captain: your captain and the best other starter, both as captain (xP × 2)
  const capRows = [me.cap, c.alt].filter(i => i != null);
  const cmax = Math.max(...capRows.map(i => xpg(i, g))) || 1;
  const cBody = `<div class="dc-caps">${capRows.map((i, j) => `<button type="button" class="dcc${j ? "" : " top"}" data-p="${i}">
      <span class="dcc-n">${j ? '<span class="dcc-alt">Alt</span>' : '<span class="badge inline" aria-label="Captain">C</span>'}${esc(P[i].name)}<span class="muted dcc-fx">${fxText(P[i], g)}</span></span>
      <span class="dcc-bar"><i style="width:${(xpg(i, g) / cmax * 100).toFixed(0)}%"></i></span><b>${f1(xpg(i, g) * 2)}</b></button>`).join("")}</div>
    <p class="dc-sub">Projected captain points for GW${g} (xP × 2).${me.capMine ? ` Your choice; the model's pick is ${esc(P[capPick(me.xi, g).cap].name)}.` : ""} Vice: ${esc(P[me.vice].name)}.${c.capEO != null ? ` ${c.capEO.toFixed(0)}% of ${c.capSample.label} captained ${esc(P[me.cap].name)} in GW${c.capSample.gw}.` : " Captaincy sample unavailable: neither managers near your rank nor the top 10k has a usable sample."}</p>`;
  const cAct = `<button class="btn primary sm" data-plgo="edit:captains">Compare captains →</button>`;

  // lineup
  const lTxt = c.starts.length || c.benches.length
    ? `${c.starts.length ? `Start ${c.starts.map(i => esc(P[i].name)).join(", ")}` : ""}${c.starts.length && c.benches.length ? "; " : ""}${c.benches.length ? `bench ${c.benches.map(i => esc(P[i].name)).join(", ")}` : ""}`
    : "Keep last week's starting XI";
  const lBody = `<p class="dc-do">${lTxt}</p>
    <p class="dc-sub">${c.benchFirst && c.weakest ? `Closest call: ${esc(P[c.weakest].name)} (${f1(xpg(c.weakest, g))} xP) starts over first sub ${esc(P[c.benchFirst].name)} (${f1(xpg(c.benchFirst, g))} xP), a gap of ${f1(c.benchGap)}.` : ""} Bench order: ${me.bench.map(i => esc(P[i].name)).join(", ")}.</p>`;
  const lAct = `<button class="btn primary sm" data-plgo="edit">Edit lineup →</button>`;
  const dcard = (t, v, body, act) => `<article class="dcard"><h3>${t}<span class="pillwrap">${vPill(v)}</span></h3><div class="dc-body">${body}</div><div class="dc-acts">${act}</div></article>`;
  const cards = `<div class="dcards">${dcard("Transfers", c.tV, tBody, tAct)}${dcard("Captain", c.cV, cBody, cAct)}${dcard("Lineup", c.lV, lBody, lAct)}</div>`;

  // money and xP above the pitch
  const tv = squadValue(w0.sq);
  const mrow = moneyRow([
    { lbl: "Team value", val: tv != null ? money(tv) : null, sub: tv != null ? "Squad at today's prices, excluding cash" : "A player in your plan has no price" },
    { lbl: "In the bank", val: money(w0.bank), cls: w0.bank < 0 ? "down" : "", sub: n ? `After your GW${g} moves, at your selling prices` : `FPL's figure since the GW${D.meta.squad_gw} deadline` },
    { lbl: "Expected points", val: `${f1(me.pts)} <small>xP</small>`, sub: `GW${g}, captain ×2${w0.hits ? `, before the −${4 * w0.hits} hit (${f1(me.pts - 4 * w0.hits)} net)` : ""}` },
  ]);
  const left = `<div class="home-pitch">
    <div class="bar"><h2>GW${g} team · ${esc(planName())}</h2><span class="lu-head"><span class="tag">${f1(me.pts)} ${term("xp", "xP")}</span>${lineupToggle()}</span></div>
    ${mrow}${pitch(me.xi, me.bench, g, { cap: me.cap, vice: me.vice, fresh: new Set(moves0.map(m => m.in)) })}</div>`;

  // quick research: straight into the right section, with useful filters set
  const out5 = w0.sq.filter(i => P[i].pos !== "GKP").sort((a, b) => xpFrom(a, g, PG.length) - xpFrom(b, g, PG.length))[0];
  const owned = new Set(D.squad.map(s => s.id)), saleOf = i => owned.has(i) ? sellPrice(i) : P[i].price;
  const budget = out5 != null ? Math.round((w0.bank + saleOf(out5)) * 10) / 10 : null;
  const qr = sidePanel("Quick research", `<div class="qr">
      <button type="button" class="qrb" data-v-go="xptable">${icon("stats")}<span>Expected points<small>Every player by GW</small></span></button>
      <button type="button" class="qrb" data-qcmp="1">${icon("players")}<span>Player comparison<small>${n ? `${esc(P[moves0[0].out].name)} v ${esc(P[moves0[0].in].name)}` : "Your top two picks"}</small></span></button>
      ${budget != null ? `<button type="button" class="qrb" data-qbudget="${P[out5].pos}:${budget}" title="Your bank after planned moves plus ${esc(P[out5].name)}'s selling price">${icon("search")}<span>Budget options<small>${P[out5].pos} up to ${money(budget)}</small></span></button>` : ""}
      <button type="button" class="qrb" data-v-go="fixtures">${icon("fixtures")}<span>Fixture outlook<small>Next ${S.horizon} gameweeks</small></span></button></div>`);

  // watchlist and changes
  const stars = Object.keys(STARS.ids).map(Number).filter(i => P[i]).sort((a, b) => xpFrom(b, g, PG.length) - xpFrom(a, g, PG.length));
  const news = newsFor(7);
  const wl = sidePanel("Watchlist & changes", stars.length || news.length ? `<ul class="side-list">
      ${stars.slice(0, 3).map(i => { const s = STARS.ids[i], dp = s.price != null ? Math.round((P[i].price - s.price) * 10) / 10 : 0;
        return `<li><button class="linkish pname" data-p="${i}">${esc(P[i].name)}</button> · ${money(P[i].price)}${dp ? ` <span class="${dp > 0 ? "up" : "down"}">${dp > 0 ? "▲" : "▼"}${Math.abs(dp).toFixed(1)}</span>` : ""} · ${f1(xpFrom(i, g, PG.length))} xP over ${PG.length} GWs</li>`; }).join("")}
      ${news.slice(0, 3).map(([t, id, , cur]) => `<li class="${newsCls(cur[0])}"><button class="linkish pname" data-p="${id}">${esc(P[id].name)}</button>: ${newsLine(cur)} <span class="muted">· ${agoTxt(t)}</span></li>`).join("")}</ul>`
    : `<p class="muted side-empty">Nobody on your watchlist and no news on your players this week. Star a player from his info panel to follow him.</p>`,
    `<button class="btn sm" data-scrollto="watchlist">Open watchlist →</button>`, `<span class="muted">${stars.length} starred</span>`);

  // needs attention: availability, minutes, money and plan validity
  const att = c.risks.filter(r => r[0] === "bad" || r[0] === "warn");
  if (c.chipNow) att.push(["info", `Consider Triple Captain on <b>${esc(P[c.bestTc.id].name)}</b> (${f1(c.bestTc.x)} xP). It expires after GW${c.tc.to}.`]);
  const na = sidePanel("Needs attention", att.length ? `<ul class="alerts side-alerts">${att.map((r, i) => `<li class="${r[0]}"${i >= 3 ? " hidden" : ""}><span>${r[1]}</span></li>`).join("")}</ul>`
    : `<p class="muted side-empty">Nothing to fix: no injury flags, minutes worries, budget or club-limit problems in your plan.</p>`,
    att.length > 3 ? `<button class="btn sm" data-showall="1" aria-expanded="false">Show all ${att.length}</button>` : "",
    att.length ? `<span class="pill warn">${att.length} to check</span>` : `<span class="pill good">Clear</span>`);

  return `${hero}${cards}<div class="home-main">${left}<div class="home-side">${qr}${wl}${na}</div></div>${prevGwStrip()}
    <div class="grid2">${squadRatingPanel()}<div id="watchlist" tabindex="-1">${starsPanel()}</div></div>`;
}
// last finished gameweek in one line, with Review and Rivals
function prevGwStrip() {
  const fin = D.meta.cur_finished ? D.meta.cur_gw : (D.meta.cur_gw || 1) - 1;
  const h = D.history.find(x => x.gw === fin); if (!h) return "";
  const p = D.history.find(x => x.gw === fin - 1), mv = p && h.rank && p.rank ? p.rank - h.rank : 0;
  const avg = D.live && D.live.gw === fin && D.live.finished && D.live.average ? D.live.average : null;
  return `<p class="prevgw"><span><b>GW${fin}: ${h.pts} pts</b>${h.hit ? ` (−${h.hit} hit)` : ""}${avg != null ? ` · ${intSgn(h.pts - avg)} vs average (${avg})` : ""}</span>
    <span>Overall rank <b>${rankFmt(h.rank)}</b>${mv ? ` <span class="${mv > 0 ? "up" : "down"}">${mv > 0 ? "▲" : "▼"} ${rankFmt(Math.abs(mv))}</span>` : ""}</span>
    <span class="prevgw-go"><button class="linkish" data-v-go="review">Open review →</button><button class="linkish" data-v-go="rivals">Rivals →</button></span></p>`;
}

/* ---------- Current GW ---------- */
// a player's matches this gameweek, counting every fixture of a double gameweek
function rowMatch(r, L) {
  const fx = L.fixtures.filter(f => f.h === r.team || f.a === r.team), n = fx.length;
  const done = fx.filter(f => f.done).length, now = fx.some(f => f.started && !f.done);
  if (!n) return { key: "dnp", label: "No match", left: 0 };
  if (now) return { key: "playing", label: n > 1 ? `Playing (game ${done + 1} of ${n})` : "Playing", left: n - done };
  if (done === n) return r.mins > 0 ? { key: "done", label: "Finished", left: 0 } : { key: "dnp", label: "Did not play", left: 0 };
  if (done) return { key: "toplay", label: `${done} of ${n} played`, left: n - done, played: true };
  return { key: "toplay", label: n > 1 ? `To play (${n} games)` : "To play", left: n };
}
function vCurrent() {
  const cg = D.meta.cur_gw, ng = D.meta.next_gw, L = D.live;
  const planBtn = `<button class="btn primary" data-plgo="edit">Continue planning${ng ? ` for GW${ng}` : ""}</button>`;
  if (cg == null) return stateView({ title: "No gameweek has started yet", body: `Your submitted squad and its points appear here after the GW${ng || 1} deadline.`, action: planBtn });
  const s = L && L.gw === cg ? liveState() : null;
  if (!s) return stateView({ title: `GW${cg} scores aren't available`, body: `The latest data has no live scores for GW${cg}${L ? ` (it has GW${L.gw})` : ""}. They usually return with the next refresh, every 30 minutes and every 10 during matches.`, action: planBtn });

  const allDone = L.fixtures.length > 0 && L.fixtures.every(f => f.done);
  const phase = D.meta.cur_finished ? "final" : allDone ? "awaiting" : L.fixtures.some(f => f.started) ? "live" : "pre";
  const provisional = phase !== "final";
  const hits = L.hits || 0, chip = L.chip ? CHIP_NAME[L.chip] || L.chip : null, capX = L.chip === "3xc" ? 3 : 2;
  // FPL's own points once the gameweek is finished; until then the live total (before hits, as FPL shows it)
  const gross = !provisional && L.points != null ? L.points : s.total + hits;
  const counted = s.counted, st = new Map(s.rows.map(r => [r, rowMatch(r, L)]));
  const left = s.xi.filter(r => st.get(r).left > 0);
  const nPlaying = left.filter(r => st.get(r).key === "playing").length, nToPlay = left.length - nPlaying;
  const leftTxt = [nToPlay ? `${nToPlay} still to play` : "", nPlaying ? `${nPlaying} playing` : ""].filter(Boolean).join(", ");
  const myFx = L.fixtures.filter(f => s.xi.some(r => r.team === f.h || r.team === f.a));
  const myFxLeft = myFx.filter(f => !f.done).length;
  const ko1 = L.fixtures.filter(f => !f.started).map(f => f.ko).filter(Boolean).sort()[0];

  const phaseTxt = { final: "Completed", awaiting: "All matches played · provisional", live: "Live", pre: "Deadline passed" }[phase];
  const head = phase === "final" ? `${gross} points. <span class="cap">GW${cg} complete.</span>`
    : phase === "awaiting" ? `${gross} points. <span class="cap">All matches played.</span>`
    : phase === "live" ? `${gross} points. <span class="cap">${left.length ? `${leftTxt}.` : "All your players have played."}</span>`
    : `GW${cg} is locked. <span class="cap">${left.length} players to play.</span>`;
  const why = phase === "final" ? `Final points from FPL${hits ? `, before the −${hits} hit` : ""}${chip ? `, with ${chip} played` : ""}.`
    : phase === "pre" ? `No matches have started.${ko1 ? ` First kick-off ${ukTime(ko1)}.` : ""} Points appear as games kick off.`
    : `Live points are provisional: bonus as it stands, auto-subs once a player's matches are over.${left.length ? ` ${myFxLeft} of your ${myFx.length} matches left.` : ""}`;
  const acts = phase === "final"
    ? `<button class="btn primary" data-v-go="review">Open full review →</button><button class="btn" data-v-go="rivals">Compare with rivals</button>`
    : `<button class="btn primary" data-scrollto="gwScores">View live scores</button><button class="btn" data-v-go="rivals">Compare with rivals</button>`;
  const hero = `<section class="hero compact" aria-label="GW${cg} so far">
    <p class="eyebrow">GW${cg} · ${phase === "live" ? `<em><span class="live-dot" aria-hidden="true"></span>${phaseTxt}</em>` : phaseTxt} · Your submitted squad · updated ${hm(D.meta.built)}</p>
    <h1>${head}</h1><p class="hero-why">${why}</p><div class="hero-acts">${acts}</div></section>`;

  // gameweek points, rank, captain
  const avg = L.average || null;
  const ptsTile = `<div class="dash-tile"><h3>Gameweek points${provisional ? " · provisional" : ""}</h3><div class="dash-big"><b>${gross}</b><span>pts</span></div>
    <p class="dash-sub">${avg != null ? `<span class="${gross >= avg ? "up" : "down"}">${intSgn(gross - avg)} vs average</span> (${avg}${provisional ? " so far" : ""})` : "Gameweek average not published yet"}${hits ? `. Net after −${hits} hit: <b>${gross - hits}</b>` : ""}.</p></div>`;
  const hc = D.history.find(h => h.gw === cg), hp = D.history.find(h => h.gw === cg - 1);
  let rankTile;
  if ((phase === "live" || phase === "awaiting") && s.rank) {
    const b = L.rank_before, mv = b ? b - s.rank.r : 0;
    rankTile = `<h3>${term("liverank", "Live rank estimate")}</h3><div class="dash-big"><b>${s.rank.edge === "above" ? "Top " : s.rank.edge === "below" ? "Below " : "~"}${rankShort(s.rank.r)}</b></div>
      <p class="dash-sub">Provisional, from a sample of ${rankFmt(L.sample_n || 0)} managers${b ? ` · <span class="${mv > 0 ? "up" : mv < 0 ? "down" : ""}">${mv > 0 ? "▲" : mv < 0 ? "▼" : ""} ${rankShort(Math.abs(mv))}</span> from ${rankShort(b)}` : ""}. Updated ${hm(D.meta.built)}.</p>`;
  } else if (phase === "final" && hc?.rank) {
    const mv = hp?.rank ? hp.rank - hc.rank : 0;
    rankTile = `<h3>Overall rank · official</h3><div class="dash-big"><b>${rankFmt(hc.rank)}</b></div>
      <p class="dash-sub">${mv ? `<span class="${mv > 0 ? "up" : "down"}">${mv > 0 ? "▲" : "▼"} ${rankFmt(Math.abs(mv))}</span> since GW${cg - 1}. ` : ""}${hc.gw_rank ? `Gameweek rank ${rankFmt(hc.gw_rank)}.` : ""}</p>`;
  } else {
    rankTile = `<h3>Live rank estimate</h3><div class="dash-big"><b class="mr-na">Unavailable</b></div>
      <p class="dash-sub">${phase === "pre" ? "Appears once matches are under way." : "FPL's rank sample isn't in this update, so there's no estimate."}</p>`;
  }
  const capR = s.capOut ? (s.vice && s.vice.mins > 0 ? s.vice : null) : s.cap;
  let capTile;
  if (capR) {
    const m = s.mult(capR), rs = st.get(capR);
    capTile = `<h3>Captain${s.capOut ? " · vice took over" : ""}</h3><div class="dash-big"><b>${esc(P[capR.id]?.name)}</b><span>${rs.key === "toplay" && !rs.played ? "yet to play" : `${capR.live * m} pts`}</span></div>
      <p class="dash-sub">${capR.live} pts × ${m}${L.chip === "3xc" ? " (Triple Captain)" : ""} = his contribution${provisional ? ", provisional" : ""}.${s.capOut ? ` ${esc(P[s.cap.id]?.name)} didn't play.` : ""}</p>`;
  } else {
    capTile = `<h3>Captain</h3><div class="dash-big"><b>${esc(P[s.cap?.id]?.name || "–")}</b></div>
      <p class="dash-sub">${s.capOut ? `Didn't play. The armband passes to ${esc(P[s.vice?.id]?.name || "your vice")} if he plays.` : `${capX === 3 ? "Triple Captain: points ×3" : "Points ×2"} once he plays.`}</p>`;
  }
  const tiles = `<div class="dash gwtiles">${ptsTile}<div class="dash-tile">${rankTile}</div><div class="dash-tile">${capTile}</div></div>`;

  // money and the saved forecast, above the pitch
  const tv = squadValue(s.rows.map(r => r.id));
  const mrow = moneyRow([
    { lbl: "Team value", val: tv != null ? money(tv) : null, sub: tv != null ? `Today's prices, not deadline prices · ${whenTxt(D.meta.built)}` : "A player in this squad has no price" },
    { lbl: "In the bank", val: D.meta.fh_restored ? null : money(D.manager.bank), sub: D.meta.fh_restored ? "Free Hit week: FPL shows the restored bank, not this week's" : `FPL's figure for your GW${cg} squad` },
    { lbl: "Expected points", val: s.hasXp ? `${f1(s.proj)} <small>xP</small>` : null,
      sub: s.hasXp ? `Pre-deadline forecast${L.xp_built ? `, saved ${whenTxt(L.xp_built)}` : ""} · captain ×${capX}${chip ? `, ${chip}` : ""}${hits ? `, after −${hits} hit` : ""}` : `No forecast was saved before the GW${cg} deadline` },
  ]);

  // pitch: the XI as submitted, actual points with the armband applied; the bench says whether it counts
  const subOff = new Set(s.subs.map(x => x.out)), subOn = new Map(s.subs.map(x => [x.in, x]));
  const item = r => {
    const cnt = counted.includes(r), m = cnt ? s.mult(r) : 1;
    const role = r.cap ? "cap" : r.vice && s.capOut && r.mins > 0 ? "capvice" : r.vice ? "vice" : "";
    const note = subOff.has(r) ? "Auto-subbed off" : subOn.has(r) ? (subOn.get(r).sure ? "Auto-sub: counts" : "Auto-sub if he plays") : r.cap && s.capOut ? "Armband to vice" : "";
    const rs = st.get(r);
    return { r, st: rs, played: rs.played || r.mins > 0 || rs.key === "done", pts: r.live * m, mult: m, counts: cnt, role, note };
  };
  const xi = s.rows.filter(r => r.pos <= 11).map(item), bench = s.rows.filter(r => r.pos > 11).sort((a, b) => a.pos - b.pos).map(item);
  const benchNote = L.chip === "bboost" ? "Bench Boost: your bench points count."
    : s.subs.length ? `Auto-sub${s.subs.length > 1 ? "s" : ""}: ${s.subs.map(x => `${esc(P[x.in.id]?.name)} for ${esc(P[x.out.id]?.name)}${x.sure ? "" : " (if he plays)"}`).join(", ")}. Only confirmed substitutes' points count.`
    : `Bench points don't count unless an auto-sub applies.${!provisional && L.bench_pts != null ? ` Your bench scored ${L.bench_pts}.` : ""}`;
  const key = `<span>Big number: actual points, ${capX === 3 ? "Triple Captain ×3" : "captain ×2"} already included (never doubled again)</span><span>${provisional ? "Provisional until FPL confirms" : "Final from FPL"}</span><span>Under it: match state; a double gameweek counts both matches</span>`;
  const pitchCol = `<div class="home-pitch">
    <div class="bar"><h2>GW${cg} team · submitted squad</h2><span class="lu-head"><span class="tag">${gross} pts${provisional ? " so far" : ""}</span>${lineupToggle()}</span></div>
    ${mrow}${livePitch(xi, bench, benchNote, key)}</div>`;

  // live matches with your players
  const order = f => f.started && !f.done ? 0 : !f.started ? 1 : 2;
  const fxs = myFx.slice().sort((a, b) => order(a) - order(b) || (a.ko || "").localeCompare(b.ko || "")).slice(0, 5);
  const fxLine = f => {
    const stt = f.done ? "FT" : f.started ? `<span class="mc-live"><i aria-hidden="true"></i>${f.mins ? f.mins + "'" : "LIVE"}</span>` : `${new Date(f.ko).toLocaleDateString("en-GB", { weekday: "short", timeZone: "Europe/London" })} ${hm(f.ko)}`;
    const mine = counted.filter(r => r.team === f.h || r.team === f.a).map(r => `${esc(P[r.id]?.name)} ${f.started ? r.live * s.mult(r) : "–"}`).join(", ");
    return `<li><span class="lm-st">${stt}</span><span class="lm-sc">${T[f.h].short} ${f.started ? `${f.hs ?? 0}–${f.as ?? 0}` : "v"} ${T[f.a].short}</span><span class="lm-mine">${mine}</span></li>`;
  };
  const lm = sidePanel(phase === "final" ? "Your matches" : "Live matches", fxs.length ? `<ul class="lm">${fxs.map(fxLine).join("")}</ul>` : `<p class="muted side-empty">None of your players has a match this gameweek.</p>`,
    `<button class="btn sm" data-scrollto="gwScores">All scores →</button>`, `<span class="muted">${provisional ? "Provisional points" : "Final points"}</span>`);

  // rival differences: effective ownership around your rank against what you have, this gameweek's file only
  const sample = fieldSample(D.crowd?.gw === cg ? D.crowd : null), F = sample?.data;
  let rv;
  if (F) {
    const all = L.pts_all || {}, mine = {};
    counted.forEach(r => { mine[r.id] = s.mult(r); });
    const ids = new Set([...Object.keys(F.eo).map(Number), ...Object.keys(mine).map(Number)]);
    const rows = [...ids].filter(i => P[i]).map(i => { const eo = (F.eo[i] || 0) / 100, m = mine[i] || 0, pts = all[i] || 0; return { i, eo, m, pts, d: m - eo, imp: (m - eo) * pts }; });
    const started = phase !== "pre";
    const hurt = rows.filter(r => r.d < -0.3).sort((a, b) => started ? a.imp - b.imp : a.d - b.d).slice(0, 2);
    const help = rows.filter(r => r.d > 0.3).sort((a, b) => started ? b.imp - a.imp : b.d - a.d).slice(0, 2);
    const who = sample.label, avg = sample.key === "near" ? s.near : s.top10k;
    const line = (r, cls) => `<li class="${cls}"><span><button class="linkish pname" data-p="${r.i}">${esc(P[r.i].name)}</button>: ${Math.round(r.eo * 100)}% owned by them, ${r.m ? `yours${r.m > 1 ? ` ×${r.m}` : ""}` : "not yours"}${started ? ` · ${r.pts} pts, ${sgn(r.imp)} for you` : ""}</span></li>`;
    const fCap = Object.entries(F.cap || {}).sort((a, b) => b[1] - a[1])[0];
    rv = sidePanel("Your rival differences", `<ul class="alerts side-alerts">${hurt.map(r => line(r, "warn")).join("")}${help.map(r => line(r, "good")).join("")}</ul>
      <p class="dc-sub">Effective ownership among ${who}${started ? "; points are live" : ""}.${fCap && P[fCap[0]] ? ` Their most-captained: ${esc(P[fCap[0]].name)} (${Math.round(fCap[1])}%).` : ""}${avg != null ? ` They average about ${f1(avg)} so far.` : ""}</p>`,
      `<button class="btn sm" data-v-go="rivals">Open rivals →</button>`);
  } else {
    rv = sidePanel("Your rival differences", `<p class="muted side-empty">Ownership sample unavailable for GW${cg}: neither managers near your rank nor the top 10k has a usable sample. It's sampled after each deadline.</p>`, `<button class="btn sm" data-v-go="rivals">Open rivals →</button>`);
  }

  // next deadline: the saved plan
  let nd;
  if (ng && D.meta.deadline) {
    const mine = SB.moves.filter(m => m.gw === ng), bank = bankAt(ng);
    nd = sidePanel("Next deadline", `<ul class="side-list">
        <li><b>${esc(planName())}</b>: ${mine.length ? `${mine.length} move${mine.length > 1 ? "s" : ""} for GW${ng}` : `no moves for GW${ng}`}</li>
        <li>${D.manager.free_transfers} free transfer${D.manager.free_transfers === 1 ? "" : "s"} · ${money(bank)} in the bank after planned moves</li>
        <li>Deadline ${ukTime(D.meta.deadline)} · ${countdown(D.meta.deadline)}</li></ul>`, `<button class="btn primary sm" data-plgo="edit">Continue planning →</button>`);
  } else nd = sidePanel("Next deadline", `<p class="muted side-empty">No further deadline this season.</p>`);

  // outlook
  const fc = s.hasXp ? s.proj : null, net = gross - hits;
  const ol = sidePanel("Gameweek outlook", `<ul class="side-list">
      <li>${provisional ? "Points so far" : "Final points"}: <b>${gross}</b>${hits ? ` (${net} after the hit)` : ""}</li>
      <li>${phase === "final" ? "All matches played" : `Starters: ${leftTxt || "none left to play"} · ${myFxLeft} of your ${myFx.length} matches left`}</li>
      <li>Pre-deadline forecast: ${fc != null ? `<b>${f1(fc)} xP</b> (after hits)${phase === "final" ? ` · <span class="${net >= fc ? "up" : "down"}">${sgn(net - fc)}</span> against it` : ""}` : '<span class="mr-na">Unavailable</span>'}</li></ul>
    <p class="dc-sub">The forecast is the estimate saved before the deadline, not a guaranteed final score.</p>`);

  const scores = scoresStrip() + livePanel();
  return `${hero}${tiles}<div class="home-main">${pitchCol}<div class="home-side">${lm}${rv}${nd}${ol}</div></div>
    <div id="gwScores" tabindex="-1" class="gwscores">${scores || `<p class="note">Match cards for GW${cg} are shown until the GW${ng || ""} deadline.${phase === "final" ? ' Full breakdown in <button class="linkish" data-v-go="review">Review</button>.' : ""}</p>`}</div>
    <p class="prevgw"><span>GW${cg} squad is locked. Plan changes apply to the ${ng ? `GW${ng} ` : "next "}deadline.</span><span class="prevgw-go"><button class="linkish" data-plgo="edit">Continue planning →</button></span></p>`;
}

/* ---------- events ---------- */
function bindHome() {
  const tabs = [...document.querySelectorAll("[data-home]")];
  const pick = (k, focus) => {
    if (k !== S.home) { S.home = k; store.set("fpl.home", k); render(); }
    if (focus) $(`#hometab-${k}`)?.focus();
  };
  tabs.forEach(b => {
    b.onclick = () => pick(b.dataset.home, true);
    b.onkeydown = e => {
      const i = tabs.indexOf(b), n = tabs.length;
      const j = e.key === "ArrowRight" ? (i + 1) % n : e.key === "ArrowLeft" ? (i - 1 + n) % n : e.key === "Home" ? 0 : e.key === "End" ? n - 1 : -1;
      if (j >= 0) { e.preventDefault(); pick(tabs[j].dataset.home, true); }
    };
  });
  const on = (sel, fn) => document.querySelectorAll(sel).forEach(el => el.onclick = () => fn(el));
  // planner shortcuts: data-plgo="view[:tool]" opens that Planner tab (and tool) as the Planner remembers them
  on("[data-plgo]", b => {
    const [v, t] = b.dataset.plgo.split(":");
    S.pview = v; store.set("fpl.pview", v);
    if (t) { S.ptab = t; store.set("fpl.ptab", t); }
    setView("planner");
  });
  on("[data-qcmp]", () => {
    const g = D.meta.next_gw, m0 = SB.moves.find(m => m.gw === g);
    if (m0) S.cmp = [m0.out, m0.in];
    else if (!S.cmp.length) { const t = myTeam(); S.cmp = [t.cap, t.vice]; }
    setView("players");
  });
  on("[data-qbudget]", b => { const [pos, max] = b.dataset.qbudget.split(":"); Object.assign(S, { pos, maxp: max, team: "ALL", q: "" }); setView("players"); });
  on("[data-scrollto]", b => { const el = $("#" + b.dataset.scrollto); if (el) { el.scrollIntoView({ behavior: calm() ? "auto" : "smooth", block: "start" }); el.focus({ preventScroll: true }); } });
  on("[data-showall]", b => {
    const open = b.getAttribute("aria-expanded") === "true", list = b.closest(".side")?.querySelectorAll(".side-alerts li") || [];
    list.forEach((li, i) => { if (i >= 3) li.hidden = open; });
    b.setAttribute("aria-expanded", String(!open)); b.textContent = open ? `Show all ${list.length}` : "Show fewer";
  });
}
