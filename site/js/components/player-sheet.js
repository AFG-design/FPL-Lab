// Player detail: a bottom sheet on phones, a centred panel on larger screens.
/* ---------- player dialog ---------- */

// season points as bars; hauls (10+) in armband yellow, blanks (≤2) muted
function pointsHistory(p) {
  const vals = p.s_pts || [];
  if (!vals.length) return `<p class="note">No minutes this season yet.</p>`;
  const mx = Math.max(10, ...vals), avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  return `<div class="ptsbars" role="img" aria-label="Points by gameweek: ${vals.map((v, i) => `GW${i + 1} ${v}`).join(", ")}. Average ${avg.toFixed(1)}.">
    <span class="pb-avg" style="bottom:${(17 + avg / mx * 96).toFixed(1)}px" aria-hidden="true"><span>avg ${avg.toFixed(1)}</span></span>
    ${vals.map((v, i) => `<div aria-hidden="true"><b>${v}</b><i class="${v >= 10 ? "haul" : v <= 2 ? "blank" : ""}" style="height:${Math.max(2, Math.max(0, v) / mx * 96).toFixed(1)}px"></i><span>${i + 1}</span></div>`).join("")}
  </div>`;
}

// how close the price is to changing (the FPL price-change estimate in the data)
function priceChange(p) {
  const pr = p.price_proj; if (!pr || pr[0] == null) return "";
  const v = pr[0], dir = v < 0 ? "fall" : "rise", pct = Math.min(100, Math.abs(v));
  const when = pr.findIndex(x => Math.abs(x) >= 100);
  const outlook = when === 0 ? `Likely to ${dir} tonight.` : when > 0 ? `On course to ${dir} in about ${when + 1} days.` : `Not expected to ${dir} in the next few days.`;
  return `<div class="price-move">
    <div class="pm-top"><span>${pct.toFixed(0)}% of the way to a price ${dir}</span><span class="${v < 0 ? "down" : "up"}">${v < 0 ? "▼" : "▲"}</span></div>
    <div class="pm-track ${v < 0 ? "neg" : ""}"><i style="width:${pct}%"></i></div>
    <p class="note">${outlook} ${(p.tin ?? 0).toLocaleString("en-GB")} transfers in and ${(p.tout ?? 0).toLocaleString("en-GB")} out this gameweek.</p>
  </div>`;
}

function upcomingFixtures(p, id) {
  const mx = Math.max(...GWS.map(x => xpg(id, x)), 1);
  return `<ol class="upnext">${GWS.map(g => {
    const fx = fxFor(p.team, g);
    return `<li><span class="un-gw">GW${g}</span>
      <span class="un-fx">${fx.length ? fx.map(x => fdrChip(x, { gw: g })).join("") : blankChip(g)}</span>
      <span class="un-opp">${fx.map(x => `${esc(T[x.opp].name)} ${x.home ? "(H)" : "(A)"}`).join(", ") || "No fixture"}</span>
      <span class="un-bar"><i style="width:${(xpg(id, g) / mx * 100).toFixed(0)}%"></i></span>
      <b>${xpCell(id, g)}</b></li>`;
  }).join("")}</ol>`;
}

// real starts in his club's last 5 gameweeks (st5 = [starts, games]), not the model's start chance
function startsText(p) {
  const [n, of] = p.st5 || [];
  return of ? `He started ${n} of his club's last ${of} games.` : "";
}

/* ---------- why this projection: the xP for next gameweek explained in plain English ---------- */
function whyXP(p, g) {
  const d = p.xp_detail || {}, fx = fxFor(p.team, g), out = [];
  if (!fx.length) return `<section class="ph-sec"><h3>Why ${f1(p.xp1)}?</h3><p class="note">${esc(T[p.team].name)} have no fixture in GW${g}.</p></section>`;
  const v = k => d[k] || 0, opp = fx.map(x => `${T[x.opp].short} (${x.home ? "H" : "A"})`).join(" and ");
  // minutes
  const last = (p.s_min || []).slice(-4), played = last.filter(m => m > 0).length;
  const mins = [`<b>${p.xmin} expected minutes</b>${fx.length > 1 ? " across his two games" : ""}.`];
  if (p.status !== "a" || (p.chance != null && p.chance < 100)) mins.push(`FPL lists him ${p.chance == null ? "as flagged, with no chance given" : `at ${fplChance(p.chance)}`}${p.news ? `: ${esc(p.news)}` : ""}.`);
  if ((p.assumed || []).length) mins.push(`<span class="asm" title="${ASM_TIP}">Projections for GW${p.assumed.join(", GW")} are assumed: FPL gives no return date or chance, so a gradual return is pencilled in.</span>`);
  // FL-093: kept in the list because FPL's data says he is close to a return (returning: back / chance / date). He has no
  // minutes this season, so the model's start chance comes from its default for that, not from games he played.
  // FL-030: new to the Premier League (no minutes in the last two seasons): the start chance is partly our price-band guess
  if (p.arrival) mins.push(`<span class="asm" title="${ASM_TIP}">New to the Premier League, so his ${Math.round((p.start_next ?? p.p_start) * 100)}% start chance is ${p.arrival >= 0.99 ? "assumed" : "partly assumed"}: a guess from his price (what arrivals at that price have started) that fades out over his first 5 games.</span>`);
  else if (p.start_assumed) mins.push(`<span class="asm" title="${ASM_TIP}">${p.returning === "back" ? "FPL has him available again after injury news earlier this season" : p.returning === "date" ? "FPL gives a return date inside the next 5 gameweeks" : "FPL gives him a chance of playing"}, but he has no minutes this season, so his ${Math.round((p.start_next ?? p.p_start) * 100)}% start chance is assumed: it is the model's default for a player with no minutes, not a measure of his place.</span>`);
  if (p.ret) mins.push(`${last.length && last[last.length - 1] > 0 ? `He played only ${last[last.length - 1]} minutes in his club's last game, with injury news since, so it's treated as a knock, not being dropped` : `He missed his club's last game${p.status === "a" ? " but FPL now has him available, so it's treated as a knock, not being dropped" : ""}`}. Players coming back start less often in their first game back, so his start chance is reduced.`);
  else if (last.length && last[last.length - 1] === 0 && played >= 2) {
    if (p.status === "a" && !p.news) mins.push("He didn't play in his club's last game with no injury news, which the model reads as a sign he may have lost his place.");
    else mins.push(`He missed his club's last game (FPL news since: ${p.news ? esc(p.news) : p.chance == null ? "flagged, no chance given" : `flagged at ${fplChance(p.chance)}`}).`);
  }
  else if (p.p_start < 0.6 && played) mins.push(`${startsText(p)}${p.psub > 0.15 ? " He often comes off the bench." : ""} The model gives him a ${Math.round(p.p_start * 100)}% chance to start next game, weighting the latest games most.`);
  else if (p.p_start >= 0.85) mins.push(`A regular starter: minutes in his last ${last.length} were ${last.join(", ")}.`);
  if (fx.some(x => x.eu)) mins.push(`${T[p.team].short} also play ${esc(fx.find(x => x.eu).eu)}, so some rotation is allowed for.`);
  out.push(["Minutes", mins.join(" "), v("mins")]);
  // attack
  const xgf = fx.reduce((a, x) => a + x.xgf, 0), xga = fx.reduce((a, x) => a + x.xga, 0);
  const atk = v("goals") + v("assists");
  if (p.pos !== "GKP") out.push(["Attack", `He gets <b>${p.xgi90.toFixed(2)} expected goals + assists per 90</b> (${p.xg90.toFixed(2)} xG, ${p.xa90.toFixed(2)} xA, this season blended with last). ${T[p.team].short} are expected to score <b>${xgf.toFixed(1)}</b> against ${opp}.${p.sp?.pen === 1 ? " He's on penalties, which is included." : ""}`, atk]);
  // defence
  if (p.pos !== "FWD") {
    const cs = fx.reduce((a, x) => a + csChance(x.xga), 0) / fx.length;
    const def = v("cs") + v("gc") + v("saves");
    out.push(["Defence", `${T[p.team].short} are expected to concede <b>${xga.toFixed(1)}</b>, about a <b>${Math.round(cs * 100)}%</b> clean-sheet chance${fx.length > 1 ? " per game" : ""}.${p.pos === "GKP" && v("saves") ? ` Saves add ${v("saves").toFixed(2)}.` : ""}`, def]);
  }
  if (p.pos !== "GKP" && v("dc") >= 0.05) out.push(["Defensive contribution", `About a <b>${Math.round(p.dc_rate * 100)}%</b> chance per start of the defensive contribution target (2 points), any length of game.`, v("dc")]);
  if (v("bonus") >= 0.05) out.push(["Bonus", `From his BPS record${p.bf4 ? ` (${p.bf4.bps90.toFixed(0)} BPS per 90 lately)` : ""} and the returns above.`, v("bonus")]);
  if (v("cards") <= -0.05) out.push(["Cards", "Allowance for yellow and red cards.", v("cards")]);
  const rest = (p.xp1 || 0) - out.reduce((a, r) => a + r[2], 0);
  return `<section class="ph-sec"><h3>Why ${f1(p.xp1)} in GW${g}?</h3>
    <ul class="why">${out.map(([k, t, pts]) => `<li><span class="why-k">${k}</span><span class="why-t">${t}</span><b class="why-v">${pts >= 0 ? "+" : "−"}${Math.abs(pts).toFixed(1)}</b></li>`).join("")}</ul>
    <p class="note">Points from each part add up to his projection${Math.abs(rest) >= 0.15 ? ` (with ${rest > 0 ? "+" : "−"}${Math.abs(rest).toFixed(1)} from the model's overall calibration)` : ""}. Minutes points are the 1 or 2 for playing.</p></section>`;
}
function openPlayer(id) {
  if (!EXTRA.ready && !EXTRA.failed) { withExtra(() => openPlayer(id)); return; }   // failed: open without the detail
  const p = P[id]; if (!p) return;
  const d = p.xp_detail || {}, g = D.meta.next_gw;
  const labels = { mins: "Appearance", goals: "Goals", assists: "Assists", cs: "Clean sheet", gc: "Conceded", saves: "Saves", dc: "Def. contrib.", bonus: "Bonus", cards: "Cards", appear_adj: "Appearance adj." };
  const sq = D.squad.find(s => s.id === id);
  const POS = { GKP: "Goalkeeper", DEF: "Defender", MID: "Midfielder", FWD: "Forward" };
  const tile = (l, v) => `<div><span>${l}</span><b>${v}</b></div>`;
  const eu = fxFor(p.team, g).find(x => x.eu);
  const pills = [
    p.status !== "a" ? `<span class="pill ${p.status === "d" ? "warn" : "bad"}">${esc(p.news || "Flagged")}</span>` : "",
    p.mflag ? `<span class="pill warn">${esc(p.mflag)}</span>` : "",
    eu ? `<span class="pill mut">Also plays ${esc(eu.eu)}</span>` : "",
  ].join("") + playerTags(p, 6);

  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" id="dlgX">×</button>
    <div class="phead">
      <img class="photo" src="${photoURL(p)}" alt="" onerror="if(!this.dataset.f){this.dataset.f=1;this.src=PHOTO_BASE+'/placeholder.png'}else this.remove()">
      <div class="ph-main">
        <p class="ph-club"><button data-team="${p.team}" class="linkish">${esc(T[p.team].name)}</button>, ${POS[p.pos] || p.pos}${MINE.has(id) ? ' <span class="tag">In your squad</span>' : ""}</p>
        <h2 id="dlgTitle">${esc(p.full)}</h2>
        <div class="ph-pills">${nailedPill(p)}<span class="note">${term("nailed", "nailed on")}</span>${pills}</div>
      </div>
    </div>
    ${EXTRA.failed ? `<p class="note" role="status">Shots, bonus, defence, history and the points breakdown didn't load (${esc(EXTRA.failed.replace(/^The detail file /, ""))}). <button type="button" class="linkish" id="dlgExtraRetry">Try again</button></p>` : ""}

    <dl class="ph-stats">
      ${statBadge("Price", money(p.price), { sub: sq ? `you sell at ${money(sq.sell)}` : `${p.own.toFixed(1)}% owned` })}
      ${statBadge("Form", f1(p.form), { sub: "points per game, last 30 days" })}
      ${statBadge(`xP GW${g}`, f1(p.xp1), { sub: fxText(p, g), tone: "accent" })}
      ${S.xh > 1 ? statBadge(`xP ${fcLabel()}`, fcTxt(p), { sub: `${p.xmin} expected mins` }) : statBadge("Expected minutes", String(p.xmin), { sub: `GW${g}` })}
    </dl>

    ${whyXP(p, g)}
    ${newsTimeline(p)}
    <section class="ph-sec"><h3>Points this season</h3>${pointsHistory(p)}
      <p class="note">Points per gameweek. Yellow bars are 10 or more.</p></section>

    <section class="ph-sec"><h3>Upcoming fixtures</h3>${upcomingFixtures(p, id)}
      <p class="note">The chip shows FPL's fixture difficulty, 1 easiest to 5 hardest. The number on the right is projected points.</p></section>

    ${p.price_proj?.[0] != null ? `<section class="ph-sec"><h3>Price change</h3>${priceChange(p)}</section>` : ""}
    ${p.pos !== "GKP" ? `<section class="ph-sec" id="shotmap" data-pid="${id}"><h3>Shot map</h3><p class="note">Loading…</p></section>` : ""}

    <section class="ph-sec"><h3>Key stats</h3>
      <div class="brk">${tile("Season pts", p.pts)}${tile("Goals, assists", `${p.goals}, ${p.assists}`)}${tile("xG, xA", `${p.xg.toFixed(1)}, ${p.xa.toFixed(1)}`)}${tile("xGI/90 L4", p.xgi90_4.toFixed(2))}${p.st5?.[1] ? tile(`Starts, last ${p.st5[1]}`, `${p.st5[0]} of ${p.st5[1]}`) : ""}${tile("Chance to start next game", `${Math.round(p.p_start * 100)}%`)}${tile("Owned", `${p.own.toFixed(1)}%`)}${p.last ? tile(`${p.last.season} pts`, p.last.pts) : ""}${sq ? tile("Bought at", money(sq.buy)) : ""}</div>
      ${outcomeTiles(p, g, tile)}
      <details><summary>GW${g} projection breakdown</summary>
        <div class="brk dbody">${Object.entries(d).filter(([, v]) => Math.abs(v) >= 0.01).map(([k, v]) => tile(labels[k] || k, v.toFixed(2))).join("")}</div></details>
      ${p.us ? `<details><summary>Shots and chances per 90 (last 4 GWs)</summary><div class="brk dbody">
        ${tile("Shots", p.us.shots90.toFixed(1))}
        ${tile("In the box", `${p.us.sib90.toFixed(1)} <small class="muted">(${p.us.sib90_4.toFixed(1)})</small>`)}
        ${tile("Big chances", `${p.us.bc90.toFixed(2)} <small class="muted">(${p.us.bc_4} in L4)</small>`)}
        ${tile("Big ch. scored", `${p.us.bc_scored}/${p.us.bc}`)}
        ${tile("Chances created", p.us.cc90.toFixed(1))}
        ${tile("BPS/90 L4", p.bf4.bps90.toFixed(0))}
        ${tile("Top-3 BPS L6", `${p.bf6.top3}/${p.bf6.apps}`)}</div></details>` : ""}
    </section>

    <div class="ph-acts"><button class="btn ${isStarred(id) ? "primary" : ""}" id="dlgStar" aria-pressed="${isStarred(id)}">${isStarred(id) ? "★ On your watchlist" : "☆ Add to watchlist"}</button>${MINE.has(id) ? `<button class="btn primary" data-plan-replace="${id}">Plan a replacement</button>` : `<button class="btn primary" data-try="${id}">Try in my plan</button>`}
      <button class="btn" id="dlgCmp">${S.cmp.includes(id) ? "In comparison ✓" : "Compare"}</button>
      <button class="btn" id="dlgLock">${SB.rules.locked.includes(id) ? "Unlock in plans" : "Lock in plans"}</button>
      <button class="btn" id="dlgBan">${SB.rules.banned.includes(id) ? "Allow in plans" : "Never pick in plans"}</button></div>`;
  const dlg = $("#dlg"); dlg.setAttribute("aria-labelledby", "dlgTitle"); if (!dlg.open) dlg.showModal();
  $("#dlgX").onclick = () => dlg.close();
  const rx = $("#dlgExtraRetry");
  if (rx) rx.onclick = () => { EXTRA.failed = null; rx.textContent = "Loading…"; rx.disabled = true; withExtra(() => openPlayer(id)); };
  if (p.pos !== "GKP") fillShotMap(id);
  $("#dlgCmp").onclick = () => { if (!S.cmp.includes(id)) { if (S.cmp.length >= 4) S.cmp.shift(); S.cmp.push(id); } $("#dlg").close(); setView("players"); setTimeout(() => $("#cmpPanel")?.scrollIntoView({ behavior: "smooth", block: "start" }), 60); };
  $("#dlgStar").onclick = () => { toggleStar(id); const b = $("#dlgStar"), on = isStarred(id); b.classList.toggle("primary", on); b.setAttribute("aria-pressed", on); b.textContent = on ? "★ On your watchlist" : "☆ Add to watchlist"; render(); };
  $("#dlgLock").onclick = () => { SB.rules.locked = SB.rules.locked.includes(id) ? SB.rules.locked.filter(x => x !== id) : [...SB.rules.locked, id]; SB.rules.banned = SB.rules.banned.filter(x => x !== id); saveSandbox(); dlg.close(); render(); };
  $("#dlgBan").onclick = () => { SB.rules.banned = SB.rules.banned.includes(id) ? SB.rules.banned.filter(x => x !== id) : [...SB.rules.banned, id]; SB.rules.locked = SB.rules.locked.filter(x => x !== id); saveSandbox(); dlg.close(); render(); };
  const pr = $("[data-plan-replace]"); if (pr) pr.onclick = () => { dlg.close(); SB.sel = id; SB.gw = PG[0]; SB.q = ""; S.pview = "edit"; setView("planner"); };
  const tb = $("#dlgBody [data-try]"); if (tb) tb.onclick = () => openTry(id);
}

/* ---------- Try in my plan (FL-156 idea 7) ----------
   For a player you don't own: a preview of signing him in your current plan (the one the Planner shows, a saved path
   you're editing included), then Apply through the Planner's own edit and undo. The preview works on a copy of the
   plan and never changes it; Cancel or closing leaves the plan, saved paths and undo as they were. Scored with the
   Planner's own functions on that copy (scoreMoves, ftTable, bankAt, squadAt, cleanMoves), with your chip pins, so the
   figures are the ones the Planner shows after Apply. Choices: the gameweek (the plan's weeks) and who goes out (same
   position, in that week's squad with its planned moves, affordable: bank that week plus his selling price, and at
   most 3 from a club). Missing or ambiguous, said rather than guessed: he's already in that week's squad; no one in the
   position can afford him or the club limit blocks it (says which); a later planned move that the new one makes
   impossible (e.g. it sells the same player) is listed and dropped on Apply; FPL lists him as unavailable (said, but
   allowed, as in the Planner). */
const TRY = { id: null, gw: null, out: null };
function tryOptions(id, g) {
  const ch = SB.chips || {}, sq = squadAt(g, SB.moves, ch), bank = bankAt(g, SB.moves, ch), p = P[id];
  const bought = new Set(SB.moves.filter(m => m.gw <= g).map(m => m.in));
  const sellOf = o => (D.squad.some(s => s.id === o) && !bought.has(o) ? sellPrice(o) : P[o].price);
  const clubs = {}; sq.forEach(i => { clubs[P[i].team] = (clubs[P[i].team] || 0) + 1; });
  const all = sq.filter(o => P[o].pos === p.pos).map(o => {
    const sell = sellOf(o), afford = bank + sell >= p.price - 1e-9, club = (clubs[p.team] || 0) - (P[o].team === p.team ? 1 : 0) < 3;
    return { id: o, sell, ok: afford && club, why: !afford ? `short by ${money(p.price - bank - sell)}` : !club ? `3 from ${T[p.team].short} already` : "" };
  });
  return { inSquad: sq.includes(id), bank, all, ok: all.filter(o => o.ok) };
}
function tryPreview(id, g, out) {
  const ch = SB.chips || {}, cand = cleanMoves([...SB.moves, { gw: g, out, in: id }], ch);
  const added = cand.some(m => m.gw === g && m.out === out && m.in === id);
  const dropped = SB.moves.filter(m => !cand.some(c => c.gw === m.gw && c.out === m.out && c.in === m.in));
  const before = scoreMoves(SB.moves), after = scoreMoves(cand, null, ch);
  const ftB = before.weeks.find(w => w.gw === g), ftA = after.weeks.find(w => w.gw === g);
  const hitsB = before.weeks.reduce((a, w) => a + w.hits, 0), hitsA = after.weeks.reduce((a, w) => a + w.hits, 0);
  const span = PG.filter(x => x >= g), xp = i => span.reduce((a, x) => a + xpg(i, x), 0);
  const opt = tryOptions(id, g).all.find(o => o.id === out);
  return { cand, added, dropped, sell: opt ? opt.sell : null, buy: P[id].price, bankBefore: bankAt(g, SB.moves, ch), bankAfter: bankAt(g, cand, ch),
    ftBefore: ftB.ft, movesBefore: ftB.n, movesAfter: ftA.n, chip: ftA.chip, extraHits: hitsA - hitsB, hereHits: ftA.hits - ftB.hits,
    playerDiff: xp(id) - xp(out), span, planBefore: before.tot + ftValue() * before.ftLeft, planAfter: after.tot + ftValue() * after.ftLeft, after };
}
function openTry(id) {
  const p = P[id]; if (!p) return;
  if (TRY.id !== id) { TRY.id = id; TRY.gw = PG[0]; TRY.out = null; }
  if (!PG.includes(TRY.gw)) TRY.gw = PG[0];
  const g = TRY.gw, opt = tryOptions(id, g);
  // the default player out: one whose sale leaves your later planned moves possible, then the lowest xP that week
  const breaks = o => cleanMoves([...SB.moves, { gw: g, out: o, in: id }], SB.chips || {}).length < SB.moves.length + 1;
  if (!opt.ok.some(o => o.id === TRY.out)) TRY.out = opt.ok.length ? opt.ok.slice().sort((a, b) => breaks(a.id) - breaks(b.id) || xpg(a.id, g) - xpg(b.id, g))[0].id : null;
  const edit = typeof tpEditInfo === "function" ? tpEditInfo() : null;
  const head = `<button class="x" aria-label="Close" id="dlgX">×</button><h2 id="dlgTitle">Try ${esc(p.name)} in my plan</h2>
    <p class="note" style="margin-top:0">${edit ? `In saved path “${esc(edit.d.name)}”, which you're editing` : `In your plan (${esc(planName())})`}. A preview: nothing changes until you press Apply.${p.ok === false ? ` <span class="pill bad">FPL lists him as unavailable</span>` : ""}</p>
    <div class="filters"><label class="pv-lbl" for="tryGw">Transfer in</label><select id="tryGw">${PG.map(x => `<option value="${x}" ${x === g ? "selected" : ""}>GW${x}${chipAt(x, SB.chips || {}) ? ` (${CHIP_NAME[chipAt(x, SB.chips)]})` : ""}</option>`).join("")}</select>
      <label class="pv-lbl" for="tryOut">Sell</label><select id="tryOut" ${opt.ok.length ? "" : "disabled"}>${opt.all.map(o => `<option value="${o.id}" ${o.id === TRY.out ? "selected" : ""} ${o.ok ? "" : "disabled"}>${esc(P[o.id].name)} · sell ${money(o.sell)}${o.ok ? "" : ` (${o.why})`}</option>`).join("")}</select></div>`;
  let body;
  if (opt.inSquad) body = `<p class="verdict">${esc(p.name)} is already in your plan's GW${g} squad.</p>`;
  else if (!TRY.out) body = `<p class="verdict">No ${p.pos} in your GW${g} squad can go out for him: ${opt.all.map(o => `${esc(P[o.id].name)} (${o.why})`).join(", ") || "none in that position"}. Bank that week: ${money(opt.bank)}.</p>`;
  else {
    const r = tryPreview(id, g, TRY.out), o = P[TRY.out], span = `GW${r.span[0]}${r.span.length > 1 ? `–${r.span[r.span.length - 1]}` : ""}`;
    const free = r.chip === "wildcard" || r.chip === "freehit";
    const ftUse = free ? `free (${CHIP_NAME[r.chip]})` : r.movesAfter <= r.ftBefore ? `uses 1 of ${r.ftBefore - r.movesBefore} free transfer${r.ftBefore - r.movesBefore === 1 ? "" : "s"} left` : "no free transfer left";
    body = `<div class="kpis try-kpis">
        <div class="kpi"><span class="lbl">Out → in, GW${g}</span><b style="font-size:var(--fs-lg)">${esc(o.name)} → ${esc(p.name)}</b><span class="delta muted">sell ${money(r.sell)} · buy ${money(r.buy)}</span></div>
        <div class="kpi"><span class="lbl">GW${g} bank</span><b>${money(r.bankBefore)} → ${money(r.bankAfter)}</b><span class="delta muted">after that week's moves</span></div>
        <div class="kpi"><span class="lbl">Extra hits, whole plan</span><b class="${r.extraHits ? "down" : ""}">${r.extraHits ? `−${4 * r.extraHits} pts` : "None"}</b><span class="delta muted">GW${g}: ${r.hereHits ? `a −${4 * r.hereHits} hit (no free transfer left)` : ftUse}${r.extraHits > r.hereHits ? `; ${r.extraHits - r.hereHits === 1 ? "a −4" : `${r.extraHits - r.hereHits} hits`} later, as fewer free transfers are left for your planned moves` : ""}</span></div>
      </div>
      <div class="kpis try-kpis">
        <div class="kpi"><span class="lbl">The two players, ${span}</span><b class="${r.playerDiff >= 0 ? "up" : "down"}">${sgn(r.playerDiff)}</b><span class="delta muted">${esc(p.name)}'s xP minus ${esc(o.name)}'s</span></div>
        <div class="kpi"><span class="lbl">Your whole plan, ${PG.length} GWs</span><b class="${r.planAfter - r.planBefore >= 0 ? "up" : "down"}">${sgn(r.planAfter - r.planBefore)}</b><span class="delta muted">${f1(r.planBefore)} → ${f1(r.planAfter)}: best XI and captain, minus hits, banked FTs at ${f1(ftValue())}</span></div>
      </div>
      ${r.dropped.length ? `<p class="verdict bad" role="alert">This makes ${r.dropped.length === 1 ? "a later planned move" : `${r.dropped.length} later planned moves`} impossible, so ${r.dropped.length === 1 ? "it is" : "they are"} dropped on Apply: ${r.dropped.map(m => `GW${m.gw} ${esc(P[m.out].name)} → ${esc(P[m.in].name)}`).join("; ")}.</p>` : ""}
      ${r.chip === "freehit" ? `<p class="note">GW${g} is your Free Hit week: this move lasts that week only.</p>` : ""}`;
  }
  const can = !opt.inSquad && TRY.out;
  $("#dlgBody").innerHTML = `${head}${body}
    <div class="ph-acts"><button class="btn primary" id="tryApply" ${can ? "" : "disabled"}>Apply to plan</button><button class="btn" id="tryBack">Back to ${esc(p.name)}</button><button class="btn" id="tryCancel">Cancel</button></div>
    <p class="note">Apply adds the move to ${edit ? `the path you're editing; press Save changes to path in the Planner to keep it there` : "your plan"}, and Undo in the Planner takes it back.</p>`;
  const dlg = $("#dlg"); dlg.setAttribute("aria-labelledby", "dlgTitle"); if (!dlg.open) dlg.showModal();
  $("#dlgX").onclick = () => dlg.close();
  $("#tryCancel").onclick = () => dlg.close();
  $("#tryBack").onclick = () => openPlayer(id);
  $("#tryGw").onchange = e => { TRY.gw = +e.target.value; TRY.out = null; openTry(id); $("#tryGw")?.focus(); };
  const ts = $("#tryOut"); if (ts) ts.onchange = e => { TRY.out = +e.target.value; openTry(id); $("#tryOut")?.focus(); };
  $("#tryApply").onclick = () => {
    if (!can) return;
    const r = tryPreview(id, g, TRY.out);
    editPlan(() => { SB.moves = r.cand; });
    dlg.close(); TRY.id = null;
    toast(`${P[r.cand.find(m => m.gw === g && m.in === id)?.out]?.name || "Move"} → ${p.name} added to GW${g}${edit ? `; save it to “${edit.d.name}” in the Planner` : ""}. Undo is in the Planner.`);
    render();
  };
}
$("#dlg").addEventListener("click", e => { if (e.target.id === "dlg") e.target.close(); });
$("#dlg").addEventListener("close", () => $("#dlg").removeAttribute("aria-labelledby"));

// simulated outcomes for one gameweek: chance of a haul (10+) and a blank (2 or fewer), and the likely range
function outcomeTiles(p, g, tile) {
  const d = p.dist?.[g];
  if (!d) return "";
  const pc = x => x < 0.01 ? "<1%" : Math.round(x * 100) + "%";
  return `<h3 class="ph-sub">GW${g} ${term("outcomes", "outcomes")}</h3>
      <div class="brk">${tile("10+ pts", pc(d[0]))}${tile("6+ pts", pc(d[1]))}${tile("2 or fewer", pc(d[2]))}${tile("Likely range", `${Math.round(d[3])}–${Math.round(d[4])}`)}</div>`;
}
