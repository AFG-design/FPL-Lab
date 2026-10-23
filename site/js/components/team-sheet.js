// Team profile: one club at a glance (form, xG, set pieces, likely XI, fixtures, best FPL picks).
function likelyXI(tid) {
  const ps = D.players.filter(p => p.team === tid && p.status !== "u").sort((a, b) => (b.p_start ?? 0) - (a.p_start ?? 0) || b.mins - a.mins);
  const gk = ps.filter(p => p.pos === "GKP").slice(0, 1), out = ps.filter(p => p.pos !== "GKP");
  const xi = [...gk], cnt = { DEF: 0, MID: 0, FWD: 0 }, MIN = { DEF: 3, MID: 2, FWD: 1 }, MAX = { DEF: 5, MID: 5, FWD: 3 };
  for (const pos of ["DEF", "MID", "FWD"]) out.filter(p => p.pos === pos).slice(0, MIN[pos]).forEach(p => { xi.push(p); cnt[pos]++; });
  for (const p of out) { if (xi.length >= 11) break; if (!xi.includes(p) && cnt[p.pos] < MAX[p.pos]) { xi.push(p); cnt[p.pos]++; } }
  return xi;
}
function openTeam(tid) {
  const t = T[tid]; if (!t) return;
  const st = teamStrength(t), tr = t.trend || [], last = tr.slice(-6);
  const res = x => x.gf > x.ga ? "W" : x.gf < x.ga ? "L" : "D";
  const rec = tr.reduce((a, x) => { a[res(x)]++; a.gf += x.gf; a.ga += x.ga; a.xgf += x.xgf; a.xga += x.xga; return a; }, { W: 0, D: 0, L: 0, gf: 0, ga: 0, xgf: 0, xga: 0 });
  const nm = p => `<button data-p="${p.id}" class="linkish">${esc(p.name)}</button>`;
  const xi = likelyXI(tid), rows = ["GKP", "DEF", "MID", "FWD"].map(pos => [pos, xi.filter(p => p.pos === pos)]);
  const sp = D.setpieces?.now?.[tid] || {}, taker = k => (sp[k] || []).filter(i => P[i]).map(i => esc(P[i].name)).join(", ") || "–";
  const fx = GWS.slice(0, 6).map(g => [g, t.fx[g] || []]);
  const picks = pos => D.players.filter(p => p.team === tid && pos.includes(p.pos) && p.ok !== false).sort((a, b) => b.xp5 - a.xp5).slice(0, 3);
  const mine = D.squad.map(s => P[s.id]).filter(p => p && p.team === tid);
  const sw = typeof swings === "function" ? swings().filter(r => r.t.id === tid && Math.abs(r.d) > (r.kind === "att" ? 0.12 : 0.04)) : [];
  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" id="dlgX">×</button>
    <div><p class="ph-club">Team profile${mine.length ? ` · you own ${mine.map(nm).join(", ")}` : ""}</p><h2>${esc(t.name)}</h2></div>
    <dl class="ph-stats">
      ${statBadge("Strength", Math.round(st.pts) + "%", { sub: `win vs average ${Math.round(st.win)}%` })}
      ${statBadge("Attack", Math.round(st.att) + "%", { sub: "goals vs league average" })}
      ${statBadge("Defence", Math.round(st.def) + "%", { sub: "100% = average" })}
      ${statBadge("Record", `${rec.W}-${rec.D}-${rec.L}`, { sub: `goals ${rec.gf}–${rec.ga} · xG ${rec.xgf.toFixed(1)}–${rec.xga.toFixed(1)}` })}
    </dl>
    <section class="ph-sec"><h3>Recent results</h3>
      <div class="tm-res">${last.slice().reverse().map(x => `<div class="r-${res(x)}"><b>${res(x)}</b><span>${x.home ? T[x.opp].short : T[x.opp].short.toLowerCase()} ${x.gf}–${x.ga}</span><small>xG ${x.xgf.toFixed(1)}–${x.xga.toFixed(1)}</small></div>`).join("") || '<p class="muted">No games yet.</p>'}</div>
      ${tr.length >= 3 ? `<div class="legend"><span><i class="s1"></i>xG for</span><span><i class="s4"></i>xG against</span></div>${lineChart([{ cls: "s1", vals: tr.map(x => x.xgf) }, { cls: "s4", vals: tr.map(x => x.xga) }], tr.map(x => x.home ? T[x.opp].short : T[x.opp].short.toLowerCase()), { h: 150, yfmt: v => v.toFixed(1) })}` : ""}</section>
    <section class="ph-sec"><h3>Next fixtures</h3>
      <div class="tablebox"><table><thead><tr><th>GW</th><th>Opponent</th><th class="n">Win</th><th class="n">xG for</th><th class="n">xG against</th><th class="n">Clean sheet</th></tr></thead><tbody>${fx.map(([g, l]) => l.length ? l.map(x => { const w = wdl(x.xgf, x.xga);
        return `<tr><td>GW${g}</td><td>${fdrChip(x, { gw: g })} ${esc(T[x.opp].name)}</td><td class="n">${Math.round(w.w * 100)}%</td><td class="n">${x.xgf.toFixed(1)}</td><td class="n">${x.xga.toFixed(1)}</td><td class="n">${Math.round(Math.exp(-x.xga) * 100)}%</td></tr>`; }).join("") : `<tr><td>GW${g}</td><td colspan="5" class="muted">No fixture</td></tr>`).join("")}</tbody></table></div>
      ${sw.length ? `<ul class="alerts" style="margin-top:8px">${sw.map(r => `<li class="${r.d > 0 ? "good" : "bad"}"><span>${r.kind === "att" ? "Attack" : "Defence"} fixtures turn ${r.d > 0 ? "easier" : "harder"} from GW${r.from}.</span></li>`).join("")}</ul>` : ""}</section>
    <section class="ph-sec"><h3>Likely XI</h3>
      <dl class="xi-lines">${rows.map(([pos, ps]) => `<dt>${pos}</dt><dd>${ps.map(p => `${nm(p)} <span class="muted">${Math.round((p.p_start ?? 0) * 100)}%</span>${p.status !== "a" ? ` <span class="pill ${p.status === "d" ? "warn" : "bad"}">${p.chance ?? 0}%</span>` : ""}`).join(", ")}</dd>`).join("")}</dl>
      <p class="note">From the model's start chances (recent starts, minutes and FPL flags), not press-conference news. The % is his chance of starting.</p></section>
    <section class="ph-sec"><h3>Set pieces</h3>
      <div class="brk"><div><span>Penalties</span><b style="font-size:var(--fs-sm)">${taker("pen")}</b></div><div><span>Corners</span><b style="font-size:var(--fs-sm)">${taker("cor")}</b></div><div><span>Free kicks</span><b style="font-size:var(--fs-sm)">${taker("fk")}</b></div>
      ${t.sp ? `<div><span>Set-piece xG for / against</span><b>${t.sp.for.toFixed(2)} / ${t.sp.against.toFixed(2)}</b></div>` : ""}</div></section>
    <section class="ph-sec"><h3>Best FPL picks</h3>
      <div class="statgrid">${[["Attack", ["MID", "FWD"]], ["Defence", ["GKP", "DEF"]]].map(([l, pos]) => `<div><span class="lbl">${l}</span><ul class="alerts" style="margin-top:6px">${picks(pos).map(p => `<li><span>${nm(p)} <span class="muted">${p.pos} · ${money(p.price)} · ${f1(p.xp5)} xP next 5</span>${playerTags(p, 2)}</span></li>`).join("")}</ul></div>`).join("")}</div></section>`;
  const dlg = $("#dlg"); if (!dlg.open) dlg.showModal(); $("#dlgBody").scrollTop = 0; $("#dlgX").onclick = () => dlg.close();
}
// team names and players inside dialogs open their profiles
document.addEventListener("click", e => {
  const tb = e.target.closest("[data-team]");
  if (tb) { e.preventDefault(); openTeam(+tb.dataset.team); return; }
  const pb = e.target.closest("#dlg [data-p]");
  if (pb) { e.preventDefault(); openPlayer(+pb.dataset.p); }
});
