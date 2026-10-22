// Player detail.
/* ---------- player dialog ---------- */
function openPlayer(id) {
  const p = P[id]; if (!p) return;
  const d = p.xp_detail || {}, g = D.meta.next_gw;
  const labels = { mins: "Appearance", goals: "Goals", assists: "Assists", cs: "Clean sheet", gc: "Conceded", saves: "Saves", dc: "Def. contrib.", bonus: "Bonus", cards: "Cards" };
  const mx = Math.max(...GWS.map(x => xpg(id, x)), 1);
  const sq = D.squad.find(s => s.id === id);
  const gwl = Array.from({ length: D.meta.cur_gw }, (_, i) => String(i + 1));
  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" id="dlgX">×</button>
    <div class="phead"><img class="photo" src="${photoURL(p)}" alt="" onerror="if(!this.dataset.f){this.dataset.f=1;this.src=PHOTO_BASE+'/placeholder.png'}else this.remove()"><div><span class="lbl">${T[p.team].name} · ${p.pos} · ${money(p.price)} · ${p.own.toFixed(1)}% owned</span><h2>${esc(p.full)}</h2>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">${nailedPill(p)} <span class="muted" style="font-size:13px">${term("nailed", "nailed")}</span>${p.mflag ? ` <span class="pill warn">${esc(p.mflag)}</span>` : ""}${p.sp?.pen === 1 ? ' <span class="pill good">Penalties</span>' : ""}${p.sp?.cor === 1 ? ' <span class="pill good">Corners</span>' : ""}${p.sp?.fk === 1 ? ' <span class="pill good">Free kicks</span>' : ""}${fxFor(p.team, g).some(x => x.eu) ? ` <span class="pill mut">${esc(fxFor(p.team, g).find(x => x.eu).eu)}</span>` : ""}</div></div></div>
    ${p.status !== "a" ? `<p class="pill ${p.status === "d" ? "warn" : "bad"}" style="margin-top:6px">${esc(p.news || "Flagged")}</p>` : ""}
    <div class="kpis"><div class="kpi"><span class="lbl">xP next</span><b>${f1(p.xp1)}</b></div><div class="kpi"><span class="lbl">xP 5 GWs</span><b>${f1(p.xp5)}</b></div><div class="kpi"><span class="lbl">xMins</span><b>${p.xmin}</b></div></div>
    <div><span class="lbl">GW${g} breakdown · ${fxText(p, g)}</span><div class="brk" style="margin-top:6px">${Object.entries(d).filter(([, v]) => Math.abs(v) >= 0.01).map(([k, v]) => `<div><span class="muted" style="font-size:12px">${labels[k] || k}</span><b>${v.toFixed(2)}</b></div>`).join("")}</div></div>
    <div><span class="lbl">Projected points by gameweek</span><div class="gwbars" style="margin-top:6px">${GWS.map(x => `<div><span class="num" style="color:var(--fg);font-weight:600">${f1(xpg(id, x))}</span><i style="height:${xpg(id, x) / mx * 50}px"></i>${fxFor(p.team, x).map(oppTxt).join("+") || "–"}</div>`).join("")}</div></div>
    <div><span class="lbl">This season, by gameweek</span><div class="legend" style="margin-top:4px"><span><i class="s1"></i>Points</span><span><i class="s2"></i>xGI × 10</span></div>${lineChart([{ cls: "s1", vals: p.s_pts }, { cls: "s2", vals: p.s_xgi.map(v => v * 10) }], gwl, { h: 150 })}</div>
    ${p.us ? `<div><span class="lbl">Shots and chances · per 90 (last 4 GWs)</span><div class="brk" style="margin-top:6px">
      <div><span class="muted" style="font-size:12px">Shots</span><b>${p.us.shots90.toFixed(1)}</b></div>
      <div><span class="muted" style="font-size:12px">In the box</span><b>${p.us.sib90.toFixed(1)} <small class="muted">(${p.us.sib90_4.toFixed(1)})</small></b></div>
      <div><span class="muted" style="font-size:12px">Big chances</span><b>${p.us.bc90.toFixed(2)} <small class="muted">(${p.us.bc_4} in L4)</small></b></div>
      <div><span class="muted" style="font-size:12px">Big ch. scored</span><b>${p.us.bc_scored}/${p.us.bc}</b></div>
      <div><span class="muted" style="font-size:12px">Chances created</span><b>${p.us.cc90.toFixed(1)}</b></div>
      <div><span class="muted" style="font-size:12px">BPS/90 L4</span><b>${p.bf4.bps90.toFixed(0)}</b></div>
      <div><span class="muted" style="font-size:12px">Top-3 BPS L6</span><b>${p.bf6.top3}/${p.bf6.apps}</b></div></div></div>` : ""}
    <div class="brk"><div><span class="muted" style="font-size:12px">Season pts</span><b>${p.pts}</b></div><div><span class="muted" style="font-size:12px">G / A</span><b>${p.goals} / ${p.assists}</b></div><div><span class="muted" style="font-size:12px">xG / xA</span><b>${p.xg.toFixed(1)} / ${p.xa.toFixed(1)}</b></div><div><span class="muted" style="font-size:12px">xGI/90 L4</span><b>${p.xgi90_4.toFixed(2)}</b></div><div><span class="muted" style="font-size:12px">Starts</span><b>${Math.round(p.p_start * 100)}%</b></div>${p.last ? `<div><span class="muted" style="font-size:12px">${p.last.season} pts</span><b>${p.last.pts}</b></div>` : ""}${sq ? `<div><span class="muted" style="font-size:12px">Bought / sell</span><b>${sq.buy.toFixed(1)} / ${sq.sell.toFixed(1)}</b></div>` : ""}</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">${MINE.has(id) ? `<button class="btn primary" data-plan-replace="${id}">Plan a replacement</button>` : ""}
      <button class="btn" id="dlgLock">${SB.rules.locked.includes(id) ? "Unlock in plans" : "Lock in plans"}</button>
      <button class="btn" id="dlgBan">${SB.rules.banned.includes(id) ? "Allow in plans" : "Never pick in plans"}</button></div>`;
  const dlg = $("#dlg"); dlg.showModal();
  $("#dlgX").onclick = () => dlg.close();
  $("#dlgLock").onclick = () => { SB.rules.locked = SB.rules.locked.includes(id) ? SB.rules.locked.filter(x => x !== id) : [...SB.rules.locked, id]; SB.rules.banned = SB.rules.banned.filter(x => x !== id); saveSandbox(); dlg.close(); render(); };
  $("#dlgBan").onclick = () => { SB.rules.banned = SB.rules.banned.includes(id) ? SB.rules.banned.filter(x => x !== id) : [...SB.rules.banned, id]; SB.rules.locked = SB.rules.locked.filter(x => x !== id); saveSandbox(); dlg.close(); render(); };
  const pr = $("[data-plan-replace]"); if (pr) pr.onclick = () => { dlg.close(); SB.sel = id; SB.gw = PG[0]; SB.q = ""; setView("planner"); };
}
$("#dlg").addEventListener("click", e => { if (e.target.id === "dlg") e.target.close(); });
