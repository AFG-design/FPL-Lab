// AFG suggestion: a fan's-eye punt layer on top of the model, kept apart from the rest of the app.
/* ---------- AFG ---------- */
const AFG_KIND = { matchup: "Record v opponent", split: "Home / away", club: "Head-to-head", hot: "Hot run",
  former: "Former club", derby: "Derby", euro: "Europe", mgr: "New manager" };
const afgOf = i => D.afg?.p?.[i];
const afgX = (i, g) => afgOf(i)?.x ?? xpg(i, g);
const afgN = i => afgOf(i)?.n || 0;

function afgXI(ids, g) {
  const MIN = { GKP: 1, DEF: 3, MID: 2, FWD: 1 }, MAX = { GKP: 1, DEF: 5, MID: 5, FWD: 3 };
  const ps = ids.filter(i => P[i]).slice().sort((a, b) => afgX(b, g) - afgX(a, g));
  const xi = [], cnt = { GKP: 0, DEF: 0, MID: 0, FWD: 0 };
  Object.keys(MIN).forEach(k => ps.filter(i => P[i].pos === k).slice(0, MIN[k]).forEach(i => { xi.push(i); cnt[k]++; }));
  ps.forEach(i => { if (xi.length < 11 && !xi.includes(i) && cnt[P[i].pos] < MAX[P[i].pos]) { xi.push(i); cnt[P[i].pos]++; } });
  const order = xi.slice().sort((a, b) => afgX(b, g) - afgX(a, g));
  return { xi, cap: order[0], vice: order[1], bench: ps.filter(i => !xi.includes(i)) };
}

// punts: one-for-one swaps that the fan factors (not just the model) push up, for the squad in your plan
function afgPunts(squad, g) {
  const bank = bankAt(g), clubs = clubCounts(squad), out = [];
  const owned = id => D.squad.some(s => s.id === id);
  squad.forEach(o => {
    const budget = bank + (owned(o) ? sellPrice(o) : P[o].price) + 1e-9;
    const fits = i => P[i] && P[i].ok && !squad.includes(i) && P[i].pos === P[o].pos && P[i].price <= budget
      && (clubs[P[i].team] || 0) - (P[o].team === P[i].team ? 1 : 0) < 3;
    let best = null;
    Object.keys(D.afg.p).map(Number).forEach(i => {
      if (!fits(i)) return;
      const gain = afgX(i, g) - afgX(o, g);
      if (afgN(i) >= 0.3 && gain >= 0.5 && (!best || gain > best.gain)) best = { out: o, in: i, gain };
    });
    if (!best) return;
    best.alt = D.players.filter(p => fits(p.id)).reduce((a, p) => !a || xpg(p.id, g) > xpg(a, g) ? p.id : a, null);
    out.push(best);
  });
  const seen = new Set();
  return out.sort((a, b) => b.gain - a.gain).filter(m => !seen.has(m.in) && seen.add(m.in)).slice(0, 3);
}

function afgWhy(a, { limit = 9, compact = false } = {}) {
  if (!a || !a.why.length) return `<p class="note" style="margin:0">No fan factors: the AFG number is the model's.</p>`;
  const list = a.why.slice().sort((x, y) => Math.abs(y[1]) - Math.abs(x[1])).slice(0, limit);
  return `<ul class="afg-why${compact ? " compact" : ""}">${list.map(([k, v, t]) => `<li>
    <span class="afg-k">${AFG_KIND[k] || k}${v ? ` <b class="${v > 0 ? "up" : "down"}">${sgn(v)}</b>` : ' <span class="muted">shown only</span>'}</span>
    <span class="afg-t">${esc(t)}</span></li>`).join("")}</ul>`;
}
const afgFx = (i, g) => fxFor(P[i].team, g).map(x => fdrChip(x, { gw: g, size: "xs" })).join("") || blankChip(g);
const afgMove = (m, g) => `${f1(m)} <span class="muted">→</span> <b>${f1(g)}</b>`;

function afgRow(i, g, open = false) {
  const a = afgOf(i), n = afgN(i);
  const top = a?.why?.slice().sort((x, y) => Math.abs(y[1]) - Math.abs(x[1]))[0];
  return `<details class="afg-row"${open ? " open" : ""}><summary>
      <span class="afg-name"><button type="button" class="pname linkish" data-p="${i}">${esc(P[i].name)}</button><span class="afg-fx">${afgFx(i, g)}</span></span>
      <span class="afg-nums">${afgMove(xpg(i, g), afgX(i, g))} <span class="tag afg-d ${n > 0.05 ? "up" : n < -0.05 ? "down" : ""}">${n ? sgn(n) : "±0.0"}</span></span>
      <span class="afg-sub">${top ? esc(top[2]) : "No fan factors this week"}</span>
    </summary>${afgWhy(a)}</details>`;
}

function afgScoreboard() {
  const B = D.afg.board || [], bt = D.afg.backtest;
  const nm = i => i && P[i] ? esc(P[i].name) : "–";
  const sum = (k) => B.reduce((s, w) => s + (w[k] || 0), 0);
  const punts = B.flatMap(w => w.punts.map(m => ({ ...m, gw: w.gw })));
  const pIn = punts.reduce((s, m) => s + m.in_pts, 0), pAlt = punts.reduce((s, m) => s + (m.alt_pts ?? 0), 0);
  const calls = sum("calls"), right = sum("calls_right");
  const lead = (a, b) => a === b ? `<span class="muted">Level</span>` : `<span class="${a > b ? "up" : "down"}">${a > b ? "AFG" : "Model"} +${Math.abs(a - b)}</span>`;
  const btTiles = bt ? `<h3 style="margin:16px 0 6px">Tested on ${bt.season.replace("-", "/")} first</h3>
    <p class="note" style="margin-top:0">Every gameweek of last season re-run with only the records available at the time.</p>
    <div class="kpis">
      <div class="kpi"><span class="lbl">Captain points, ${bt.gws} GWs</span><b>${bt.cap_afg} <span class="muted afg-v">v ${bt.cap_model}</span></b><span class="delta muted">AFG v model, different pick in ${bt.cap_diff_weeks} weeks</span></div>
      <div class="kpi"><span class="lbl">Nudges in the right direction</span><b>${Math.round(bt.calls_right / bt.calls * 100)}%</b><span class="delta muted">${bt.calls.toLocaleString("en-GB")} calls; 50% is a coin flip</span></div>
      <div class="kpi"><span class="lbl">Average miss per player</span><b>${bt.mae_afg.toFixed(2)} <span class="muted afg-v">v ${bt.mae_model.toFixed(2)}</span></b><span class="delta muted">AFG v model, lower is better</span></div>
    </div>` : "";
  if (!B.length) {
    return `<div class="panel"><h2>Scoreboard: AFG v the model</h2>
      <p>Each week AFG's captain, best XI and punts are saved before the deadline next to the model's, then marked once the gameweek finishes. The first results appear after GW${D.afg.gw}.</p>${btTiles}</div>`;
  }
  return `<div class="panel"><div class="bar"><h2>Scoreboard: AFG v the model</h2><span class="tag">${B.length} GW${B.length > 1 ? "s" : ""}</span></div>
    <div class="kpis">
      <div class="kpi"><span class="lbl">Captain points</span><b>${sum("afg_cap_pts")} <span class="muted afg-v">v ${sum("model_cap_pts")}</span></b><span class="delta">${lead(sum("afg_cap_pts"), sum("model_cap_pts"))}</span></div>
      <div class="kpi"><span class="lbl">Best XI points (with captain)</span><b>${sum("afg_xi_pts")} <span class="muted afg-v">v ${sum("model_xi_pts")}</span></b><span class="delta">${lead(sum("afg_xi_pts"), sum("model_xi_pts"))}</span></div>
      <div class="kpi"><span class="lbl">Punts v the model's swap</span><b>${pIn} <span class="muted afg-v">v ${pAlt}</span></b><span class="delta">${punts.length ? lead(pIn, pAlt) : '<span class="muted">No punts yet</span>'}</span></div>
      <div class="kpi"><span class="lbl">Nudges right</span><b>${calls ? Math.round(right / calls * 100) + "%" : "–"}</b><span class="delta muted">${right} of ${calls}; 50% is a coin flip</span></div>
    </div>
    <div class="tablebox" style="margin-top:12px"><table><thead><tr><th>GW</th><th>AFG captain</th><th>Model captain</th><th class="n">XI pts</th><th>Punts (AFG v model)</th><th class="n">Nudges right</th><th class="n">Avg miss</th></tr></thead>
    <tbody>${B.slice().reverse().map(w => `<tr><td>GW${w.gw}</td>
      <td>${nm(w.afg_cap)} <b>${w.afg_cap_pts}</b></td><td>${nm(w.model_cap)} <b>${w.model_cap_pts}</b></td>
      <td class="n">${w.afg_xi_pts} v ${w.model_xi_pts}</td>
      <td>${w.punts.length ? w.punts.map(m => `${nm(m.in)} ${m.in_pts} v ${nm(m.alt)} ${m.alt_pts ?? "–"}`).join("<br>") : '<span class="muted">None</span>'}</td>
      <td class="n">${w.calls ? `${w.calls_right}/${w.calls}` : "–"}</td>
      <td class="n">${w.mae_afg != null ? `${w.mae_afg.toFixed(2)} v ${w.mae_model.toFixed(2)}` : "–"}</td></tr>`).join("")}</tbody></table></div>
    <p class="note">Captain points are doubled. Punts are scored on the week they were suggested, against the model's best like-for-like swap for the same player. Avg miss: AFG v model across every player who played in the three weeks before.</p>
    ${btTiles}</div>`;
}

function vAfg() {
  const A = D.afg, g = D.meta.next_gw;
  if (!A || !A.p) return stateView({ kind: "empty", title: "No AFG suggestion yet", body: "It appears after the next data refresh." });
  if (A.gw !== g) return stateView({ kind: "empty", title: `AFG is still on GW${A.gw}`, body: "It catches up on the next data refresh." });
  const me = myTeam(), squad = me.week.sq, af = afgXI(squad, g);
  const capSame = af.cap === me.cap, capGap = afgX(af.cap, g) - afgX(af.vice, g);
  const capV = verdict(capGap, 1, 0.4);
  const ins = af.xi.filter(i => !me.xi.includes(i)), outs = me.xi.filter(i => !af.xi.includes(i));
  const punts = afgPunts(squad, g);
  const pool = Object.keys(A.p).map(Number).filter(i => P[i] && A.p[i].m >= 2);
  const risers = pool.filter(i => A.p[i].n >= 0.3).sort((a, b) => A.p[b].n - A.p[a].n).slice(0, 6);
  const fallers = pool.filter(i => A.p[i].n <= -0.3).sort((a, b) => A.p[a].n - A.p[b].n).slice(0, 5);
  const step = (n, title, pill, doTxt, body) => `<div class="stepcard act"><span class="no">${n}</span><div class="sbody">
    <h3>${title} ${pill ? `<span class="pillwrap">${pill}</span>` : ""}</h3><div class="do">${doTxt}</div>${body || ""}</div></div>`;

  const capStep = step(1, "Captain", vPill(capV),
    `C ${esc(P[af.cap].name)} · V ${esc(P[af.vice].name)}`,
    `<p class="sub">${capSame ? `Same as the model's pick.` : `The model says <b>${esc(P[me.cap].name)}</b> (${f1(xpg(me.cap, g))} xP). AFG leans to ${esc(P[af.cap].name)}: ${afgMove(xpg(af.cap, g), afgX(af.cap, g))}.`} ${f1(capGap)} AFG pts clear of ${esc(P[af.vice].name)}.</p>
     ${afgWhy(afgOf(af.cap), { limit: 4 })}`);
  const xiStep = step(2, "Lineup", ins.length ? `<span class="pill warn">Differs</span>` : `<span class="pill good">Same</span>`,
    ins.length ? `Start <b>${ins.map(i => esc(P[i].name)).join(", ")}</b>; bench <b>${outs.map(i => esc(P[i].name)).join(", ")}</b>` : "Same XI as the model",
    ins.length ? `<p class="sub">${ins.map((i, k) => `${esc(P[i].name)} ${afgMove(xpg(i, g), afgX(i, g))} over ${esc(P[outs[k]]?.name || "")} ${afgMove(xpg(outs[k], g), afgX(outs[k], g))}`).join(". ")}.</p>` : `<p class="sub">The fan factors don't change who starts.</p>`);
  const puntStep = step(3, "Punts", punts.length ? vPill(verdict(punts[0].gain, 1.5, 0.8)) : `<span class="pill mut">None</span>`,
    punts.length ? `${punts.length} swap${punts.length > 1 ? "s" : ""} the fan factors like` : "No swap stands out this week",
    punts.length ? punts.map(m => `<div class="sugg">
        <div class="sg-top"><div class="move"><span class="out">▼ ${esc(P[m.out].name)}</span><span class="in">▲ <button type="button" class="linkish" data-p="${m.in}">${esc(P[m.in].name)}</button></span><span class="muted mono">${money(P[m.in].price)} · ${T[P[m.in].team].short}</span></div><span class="sg-gain up">+${f1(m.gain)}</span></div>
        <div class="sg-meta"><span class="sgfx">${afgFx(m.in, g)}</span><span class="note">AFG ${afgMove(xpg(m.in, g), afgX(m.in, g))}${m.alt ? ` · the model would bring in <button type="button" class="linkish" data-p="${m.alt}">${esc(P[m.alt].name)}</button> (${f1(xpg(m.alt, g))})` : ""}</span></div>
        ${afgWhy(afgOf(m.in), { limit: 3, compact: true })}
        <button class="btn sm sg-add" data-afgmove="${m.out}:${m.in}">Add to plan for GW${g}</button></div>`).join("")
      : `<p class="sub">A punt needs a player the fan factors push up by at least 0.3 and who beats yours by 0.5 AFG points, within budget.</p>`);

  return `<div class="panel afg-hero">
      <div class="bar" style="margin:0"><h2>AFG suggestion · GW${g}</h2><span class="tag">Punt layer</span></div>
      <p>The model's projections, nudged by what a fan would look at: record against this opponent and at this ground, home and away form, head-to-heads, hot runs, Europe and new managers. It's kept apart from the rest of the app, which still follows the model.</p>
      <p class="note">Built on your plan's squad (${esc(planName())}). Records cover ${(A.seasons[0] || "").replace("-", "/")} to now. The labels show how far AFG leans, not proof of an edge: see the scoreboard below.</p>
    </div>
    <div class="grid2">
      <div class="steps">${capStep}${xiStep}${puntStep}</div>
      <div class="panel" style="align-self:start"><div class="bar"><h3>Your squad, AFG view</h3><span class="tag">model → AFG</span></div>
        ${squad.slice().sort((a, b) => afgX(b, g) - afgX(a, g)).map(i => afgRow(i, g)).join("")}
      </div>
    </div>
    <div class="grid2 afg-movers">
      <div class="panel"><h3>Fan factors pushing up</h3>${risers.length ? risers.map(i => afgRow(i, g)).join("") : '<p class="note">Nobody this week.</p>'}</div>
      <div class="panel"><h3>Fan factors pulling down</h3>${fallers.length ? fallers.map(i => afgRow(i, g)).join("") : '<p class="note">Nobody this week.</p>'}</div>
    </div>
    ${afgScoreboard()}
    <div class="panel" style="max-width:800px"><details><summary><h3 style="display:inline">How AFG works</h3></summary><div class="dbody">
      <ul>
        <li><b>Start from the model.</b> Every player's projected points for GW${g}, unchanged.</li>
        <li><b>Records, beyond expectation.</b> For each past game: his points, minus his own average that season, minus what players in his position usually get against that opponent at that venue. That takes out the opponent's strength, which the model already has.</li>
        <li><b>Shrunk hard.</b> About 10 games against an opponent (or at a ground) before a record counts for half its face value; 15 for home and away.</li>
        <li><b>Head-to-head</b> for keepers and defenders: how the club's defence has done against this opponent.</li>
        <li><b>Hot run</b> (returns in each of the last 3 starts) ${sgn(A.set.hot)}; <b>European game</b> that week ${sgn(A.set.euro)}; <b>new manager</b> ${sgn(A.set.new_mgr)} (set by hand in afg_manual.json).</li>
        <li><b>Shown, not scored:</b> derbies and former clubs. Across seven seasons derbies made no difference, and players facing a former club scored slightly below par.</li>
        <li>Scaled by how sure he is to play, and capped at ±${f1(A.set.cap)} a game.</li>
      </ul>
      <p class="note">Honest bit: tested on seven seasons (about 55,000 starts), records against an opponent or at a ground didn't predict later games once opponent strength was taken out. That's why it's a punt layer with its own tab, and why the scoreboard is here.</p>
    </div></details></div>`;
}
