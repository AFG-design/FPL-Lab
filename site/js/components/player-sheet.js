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
      <b>${f1(xpg(id, g))}</b></li>`;
  }).join("")}</ol>`;
}

function openPlayer(id) {
  const p = P[id]; if (!p) return;
  const d = p.xp_detail || {}, g = D.meta.next_gw;
  const labels = { mins: "Appearance", goals: "Goals", assists: "Assists", cs: "Clean sheet", gc: "Conceded", saves: "Saves", dc: "Def. contrib.", bonus: "Bonus", cards: "Cards" };
  const sq = D.squad.find(s => s.id === id);
  const POS = { GKP: "Goalkeeper", DEF: "Defender", MID: "Midfielder", FWD: "Forward" };
  const tile = (l, v) => `<div><span>${l}</span><b>${v}</b></div>`;
  const eu = fxFor(p.team, g).find(x => x.eu);
  const pills = [
    p.status !== "a" ? `<span class="pill ${p.status === "d" ? "warn" : "bad"}">${esc(p.news || "Flagged")}</span>` : "",
    p.mflag ? `<span class="pill warn">${esc(p.mflag)}</span>` : "",
    p.sp?.pen === 1 ? '<span class="pill good">Penalties</span>' : "",
    p.sp?.cor === 1 ? '<span class="pill good">Corners</span>' : "",
    p.sp?.fk === 1 ? '<span class="pill good">Free kicks</span>' : "",
    eu ? `<span class="pill mut">Also plays ${esc(eu.eu)}</span>` : "",
  ].join("");

  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" id="dlgX">×</button>
    <div class="phead">
      <img class="photo" src="${photoURL(p)}" alt="" onerror="if(!this.dataset.f){this.dataset.f=1;this.src=PHOTO_BASE+'/placeholder.png'}else this.remove()">
      <div class="ph-main">
        <p class="ph-club">${esc(T[p.team].name)}, ${POS[p.pos] || p.pos}${MINE.has(id) ? ' <span class="tag">In your squad</span>' : ""}</p>
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

    <section class="ph-sec"><h3>Points this season</h3>${pointsHistory(p)}
      <p class="note">Points per gameweek. Yellow bars are 10 or more.</p></section>

    <section class="ph-sec"><h3>Upcoming fixtures</h3>${upcomingFixtures(p, id)}
      <p class="note">The chip shows FPL's fixture difficulty, 1 easiest to 5 hardest. The number on the right is projected points.</p></section>

    ${p.price_proj?.[0] != null ? `<section class="ph-sec"><h3>Price change</h3>${priceChange(p)}</section>` : ""}

    <section class="ph-sec"><h3>Key stats</h3>
      <div class="brk">${tile("Season pts", p.pts)}${tile("Goals, assists", `${p.goals}, ${p.assists}`)}${tile("xG, xA", `${p.xg.toFixed(1)}, ${p.xa.toFixed(1)}`)}${tile("xGI/90 L4", p.xgi90_4.toFixed(2))}${tile("Starts", `${Math.round(p.p_start * 100)}%`)}${tile("Owned", `${p.own.toFixed(1)}%`)}${p.last ? tile(`${p.last.season} pts`, p.last.pts) : ""}${sq ? tile("Bought at", money(sq.buy)) : ""}</div>
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

    <div class="ph-acts">${MINE.has(id) ? `<button class="btn primary" data-plan-replace="${id}">Plan a replacement</button>` : ""}
      <button class="btn" id="dlgLock">${SB.rules.locked.includes(id) ? "Unlock in plans" : "Lock in plans"}</button>
      <button class="btn" id="dlgBan">${SB.rules.banned.includes(id) ? "Allow in plans" : "Never pick in plans"}</button></div>`;
  const dlg = $("#dlg"); dlg.setAttribute("aria-labelledby", "dlgTitle"); dlg.showModal();
  $("#dlgX").onclick = () => dlg.close();
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
