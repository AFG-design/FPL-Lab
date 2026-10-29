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
  if (p.status !== "a" || (p.chance != null && p.chance < 100)) mins.push(`FPL lists him at ${p.chance ?? 0}%${p.news ? `: ${esc(p.news)}` : ""}.`);
  if ((p.assumed || []).length) mins.push(`<span class="asm" title="${ASM_TIP}">Projections for GW${p.assumed.join(", GW")} are assumed: FPL gives no return date or chance, so a gradual return is pencilled in.</span>`);
  if (p.ret) mins.push(`${last.length && last[last.length - 1] > 0 ? `He played only ${last[last.length - 1]} minutes in his club's last game, with injury news since, so it's treated as a knock, not being dropped` : `He missed his club's last game${p.status === "a" ? " but FPL now has him available, so it's treated as a knock, not being dropped" : ""}`}. Players coming back start less often in their first game back, so his start chance is reduced.`);
  else if (last.length && last[last.length - 1] === 0 && played >= 2) {
    if (p.status === "a" && !p.news) mins.push("He didn't play in his club's last game with no injury news, which the model reads as a sign he may have lost his place.");
    else mins.push(`He missed his club's last game (FPL news since: ${p.news ? esc(p.news) : `flagged at ${p.chance ?? 0}%`}).`);
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
    const cs = fx.reduce((a, x) => a + Math.exp(-x.xga), 0) / fx.length;
    const def = v("cs") + v("gc") + v("saves");
    out.push(["Defence", `${T[p.team].short} are expected to concede <b>${xga.toFixed(1)}</b>, about a <b>${Math.round(cs * 100)}%</b> clean-sheet chance${fx.length > 1 ? " per game" : ""}.${p.pos === "GKP" && v("saves") ? ` Saves add ${v("saves").toFixed(2)}.` : ""}`, def]);
  }
  if (p.pos !== "GKP" && v("dc") >= 0.05) out.push(["Defensive contribution", `About a <b>${Math.round(p.dc_rate * 100)}%</b> chance per game of the defensive contribution target (2 points).`, v("dc")]);
  if (v("bonus") >= 0.05) out.push(["Bonus", `From his BPS record${p.bf4 ? ` (${p.bf4.bps90.toFixed(0)} BPS per 90 lately)` : ""} and the returns above.`, v("bonus")]);
  if (v("cards") <= -0.05) out.push(["Cards", "Allowance for yellow and red cards.", v("cards")]);
  const rest = (p.xp1 || 0) - out.reduce((a, r) => a + r[2], 0);
  return `<section class="ph-sec"><h3>Why ${f1(p.xp1)} in GW${g}?</h3>
    <ul class="why">${out.map(([k, t, pts]) => `<li><span class="why-k">${k}</span><span class="why-t">${t}</span><b class="why-v">${pts >= 0 ? "+" : "−"}${Math.abs(pts).toFixed(1)}</b></li>`).join("")}</ul>
    <p class="note">Points from each part add up to his projection${Math.abs(rest) >= 0.15 ? ` (with ${rest > 0 ? "+" : "−"}${Math.abs(rest).toFixed(1)} from the model's overall calibration)` : ""}. Minutes points are the 1 or 2 for playing.</p></section>`;
}
function openPlayer(id) {
  if (!EXTRA.ready) { withExtra(() => openPlayer(id)); return; }
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
    p.sp?.cor === 1 ? '<span class="pill good">Corners</span>' : "",
    p.sp?.fk === 1 ? '<span class="pill good">Free kicks</span>' : "",
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

    <dl class="ph-stats">
      ${statBadge("Price", money(p.price), { sub: sq ? `you sell at ${money(sq.sell)}` : `${p.own.toFixed(1)}% owned` })}
      ${statBadge("Form", f1(p.form), { sub: "points per game, last 30 days" })}
      ${statBadge(`xP GW${g}`, f1(p.xp1), { sub: fxText(p, g), tone: "accent" })}
      ${statBadge(`xP next ${Math.min(5, GWS.length)}`, f1(p.xp5), { sub: `${p.xmin} expected mins` })}
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

    <div class="ph-acts"><button class="btn ${isStarred(id) ? "primary" : ""}" id="dlgStar" aria-pressed="${isStarred(id)}">${isStarred(id) ? "★ On your watchlist" : "☆ Add to watchlist"}</button>${MINE.has(id) ? `<button class="btn primary" data-plan-replace="${id}">Plan a replacement</button>` : ""}
      <button class="btn" id="dlgCmp">${S.cmp.includes(id) ? "In comparison ✓" : "Compare"}</button>
      <button class="btn" id="dlgLock">${SB.rules.locked.includes(id) ? "Unlock in plans" : "Lock in plans"}</button>
      <button class="btn" id="dlgBan">${SB.rules.banned.includes(id) ? "Allow in plans" : "Never pick in plans"}</button></div>`;
  const dlg = $("#dlg"); dlg.setAttribute("aria-labelledby", "dlgTitle"); dlg.showModal();
  $("#dlgX").onclick = () => dlg.close();
  if (p.pos !== "GKP") fillShotMap(id);
  $("#dlgCmp").onclick = () => { if (!S.cmp.includes(id)) { if (S.cmp.length >= 4) S.cmp.shift(); S.cmp.push(id); } $("#dlg").close(); setView("players"); setTimeout(() => $("#cmpPanel")?.scrollIntoView({ behavior: "smooth", block: "start" }), 60); };
  $("#dlgStar").onclick = () => { toggleStar(id); const b = $("#dlgStar"), on = isStarred(id); b.classList.toggle("primary", on); b.setAttribute("aria-pressed", on); b.textContent = on ? "★ On your watchlist" : "☆ Add to watchlist"; render(); };
  $("#dlgLock").onclick = () => { SB.rules.locked = SB.rules.locked.includes(id) ? SB.rules.locked.filter(x => x !== id) : [...SB.rules.locked, id]; SB.rules.banned = SB.rules.banned.filter(x => x !== id); saveSandbox(); dlg.close(); render(); };
  $("#dlgBan").onclick = () => { SB.rules.banned = SB.rules.banned.includes(id) ? SB.rules.banned.filter(x => x !== id) : [...SB.rules.banned, id]; SB.rules.locked = SB.rules.locked.filter(x => x !== id); saveSandbox(); dlg.close(); render(); };
  const pr = $("[data-plan-replace]"); if (pr) pr.onclick = () => { dlg.close(); SB.sel = id; SB.gw = PG[0]; SB.q = ""; setView("planner"); };
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
