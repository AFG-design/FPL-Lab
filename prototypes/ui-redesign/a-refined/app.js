// Concept A: Refined. Prototype only; reads the sample snapshot through window.PROTO, writes nothing.
(function () {
  const X = window.PROTO, { S, P, G, esc, money, num, rank, icon } = X;
  X.theme();
  const $ = s => document.querySelector(s);
  const NAV = [["Matchday", [["home", "This week"], ["planner", "Planner"], ["rivals", "Rivals"]]], ["Analysis", [["players", "Players"], ["fixtures", "Fixtures"]]], ["Season", [["chips", "Chips"], ["model", "Model"]]]];
  const BOTTOM = [["home", "Home"], ["planner", "Plan"], ["rivals", "Rivals"], ["players", "Players"], ["more", "More"]];
  const fdr = f => `<span class="fdr fdr-${f.fdr}">${esc(f.opp)}${f.home ? "" : ""} (${f.home ? "H" : "A"})</span>`;
  const fdrs = (team, gw) => { const l = X.fx(team, gw); return l.length ? l.map(fdr).join(" ") : `<span class="fdr fdr-3">Blank</span>`; };
  let strat = "balanced";

  function header() {
    const m = S.manager, h = S.history, mv = h[h.length - 2].rank - h[h.length - 1].rank, cd = X.countdown();
    $("#topbar").innerHTML = `
      <div class="team"><h1>${esc(m.team)}</h1><div class="sub">GW${S.meta.picks_gw} squad · ${m.free_transfers} free transfers</div></div>
      <dl class="kpis">
        <div class="kpi"><dt>Overall rank</dt><dd class="num">${rank(m.rank)}</dd><span class="sub up">▲ ${rank(mv)}</span></div>
        <div class="kpi"><dt>Points</dt><dd class="num">${m.points}</dd><span class="sub">GW${S.meta.picks_gw}: ${m.gw_points}</span></div>
        <div class="kpi"><dt>Bank</dt><dd class="num">${money(m.bank)}</dd><span class="sub">Value ${money(m.value)}</span></div>
      </dl>
      <div class="deadline-pill" title="Deadline countdown"><b class="num">${cd.text}</b><span><strong>GW${G} deadline</strong><span class="when">${X.deadlineText()}</span></span></div>
      <div class="updated desk"><span class="dot"></span>Updated 09:02<button class="iconbtn" aria-label="Refresh data">${icon("refresh")}</button></div>`;
  }

  /* ---------- home ---------- */
  function pitch(sq, gw = G) {
    const card = p => `<button class="pl" data-p="${p.id}" aria-label="${esc(p.name)}, ${num(X.xp(p.id, gw))} xP">
        ${p.cap ? `<span class="cap">C</span>` : p.vice ? `<span class="cap v">V</span>` : ""}
        <img src="${X.badge(p.team)}" alt=""><span class="nm">${esc(p.name)}</span>
        <span class="x num">${num(X.xp(p.id, gw))}<small>xP</small></span>${fdrs(p.team, gw)}</button>`;
    return `<div class="pitch">${sq.lines.map(l => `<div class="line">${l.map(card).join("")}</div>`).join("")}</div>
      <div class="benchrow"><span class="eyebrow">Bench</span>${sq.bench.map((p, i) => `<span class="b"><span class="muted">${i ? i : "GK"}</span><b>${esc(p.name)}</b><span class="muted num">${num(X.xp(p.id, gw))}</span></span>`).join("")}</div>`;
  }
  function home() {
    const sq = X.squad(), caps = X.captains(), st = X.strategies()[0], max = caps[0].cxp;
    const close = sq.bench[1];
    return `<div class="home">
      <section class="verdict" aria-label="This week's recommendation">
        <div><div class="eyebrow">GW${G} · Balanced strategy</div>
          <h2>Roll the transfer. <em>${esc(sq.captain.name)}</em> captain.</h2>
          <p>Banking takes you into GW${G + 1} with 4 free transfers, where the plan makes ${st.moves[0]?.pairs.length || 0} moves (+${num(st.gain)} xP over 5 GWs vs no transfers).</p></div>
        <div class="acts"><button class="btn">Open planner ${icon("arrow")}</button><button class="btn quiet">Compare</button></div>
      </section>
      <section class="card pitchcard" aria-label="Your GW${G} team">
        <div class="pc-head"><h2>GW${G} team</h2><div class="seg" role="group"><button aria-pressed="true">Cards</button><button aria-pressed="false">Kits</button></div>
          <span class="xp num">${num(sq.xp)}<small>team xP next GW, captain ×2</small></span></div>
        ${pitch(sq)}
      </section>
      <div class="rail">
        <section class="card decision"><div class="top"><span class="eyebrow">Captain</span><span class="call">Close call · 0.5 xP</span></div>
          <div class="capbars">${caps.map((c, i) => `<div class="capbar ${i ? "" : "c"}"><span class="nm">${esc(c.name)} <span class="muted">${esc(X.fx(c.team, G).map(f => f.opp).join(""))}</span></span><span class="track"><i style="width:${c.cxp / max * 100}%"></i></span><span class="v num">${num(c.cxp)}</span></div>`).join("")}</div>
          <p>Captain xP for GW${G} (xP × 2). 81% of managers near your rank captained Haaland last week.</p></section>
        <section class="card decision"><div class="top"><span class="eyebrow">Lineup</span><span class="call">Close call · 0.1 xP</span></div>
          <h3>Start Gibbs-White over ${esc(close.name)}</h3><p>Gibbs-White 3.6 xP vs ${esc(close.name)} ${num(X.xp(close.id))} xP. Bench order set by xP.</p>
          <button class="link">Edit lineup ${icon("arrow")}</button></section>
        <section class="card decision"><div class="top"><span class="eyebrow">Next 5 gameweeks</span></div>
          <div class="timeline">${st.weeks.map(w => `<div class="tl"><span class="gw">GW${w.gw}</span><span>${w.in.length ? `${w.in.length} moves · ${w.in.map(i => esc(P[i].name)).slice(0, 2).join(", ")}${w.in.length > 2 ? "…" : ""}` : `<span class="muted">Roll · ${w.ft} FT</span>`}</span><span class="x num">${num(w.xp)}</span></div>`).join("")}</div>
          <button class="link">See the plan ${icon("arrow")}</button></section>
      </div></div>`;
  }

  /* ---------- planner ---------- */
  function planner() {
    const ss = X.strategies(), cur = ss.find(s => s.key === strat);
    return `<h1 class="h-page">Planner</h1><p class="lede">What each strategy would do over the next 5 gameweeks. Gains are projected points vs making no transfers, after hits, with banked free transfers counted.</p>
      <div class="strats" role="group" aria-label="Strategy">${ss.map(s => `<button class="strat" data-strat="${s.key}" aria-pressed="${s.key === strat}"><span class="gain num">+${num(s.gain)}<small>xP vs no moves</small></span><b>${s.name}</b><span>${s.blurb}. GW${G}: ${s.nowAction}.</span></button>`).join("")}</div>
      <div class="gwrow">${cur.weeks.map((w, i) => `<div class="gwc" aria-current="${i === 1}"><div class="g">GW${w.gw}</div><div class="x num">${num(w.xp)} xP · ${w.ft} FT</div><div class="mv">${w.in.length ? `<b>${w.in.length} moves</b>` : `<span class="muted">Roll</span>`}</div></div>`).join("")}</div>
      <div class="two"><section class="card pitchcard"><div class="pc-head"><h2>GW${G + 1} team · ${cur.name}</h2><span class="xp num">${num(cur.weeks[1].xp)}<small>xP</small></span></div>${pitch(planSquad(cur.weeks[1]), cur.weeks[1].gw)}</section>
      <section class="card"><h2>Moves in this plan</h2><div class="moves" style="margin-top:12px">${cur.moves.flatMap(m => m.pairs.map(([o, i]) => `<div class="move"><span class="o">Out <b>${esc(o.name)}</b><br><span class="muted">${o.pos} · ${money(o.price)}</span></span><span class="muted">GW${m.gw}</span><span class="i">In <b>${esc(i.name)}</b><br><span class="muted">${i.pos} · ${money(i.price)}</span></span></div>`)).join("")}</div></section></div>`;
  }
  function planSquad(w) {
    const row = id => ({ ...P[id], cap: id === w.captain, vice: id === w.vice });
    const xi = w.xi.map(row);
    return { lines: ["GKP", "DEF", "MID", "FWD"].map(pos => xi.filter(p => p.pos === pos)), bench: w.bench.map(row) };
  }

  /* ---------- players ---------- */
  function players() {
    const list = X.players({ limit: 24 }), max = list[0].xp5;
    return `<h1 class="h-page">Players</h1><p class="lede">Projected points (xP) from the model. Tap a player for their gameweek-by-gameweek projection.</p>
      <div class="toolbar"><div class="search">${icon("search")}Search players</div>
        <div class="seg" role="group" aria-label="Position">${["All", "GKP", "DEF", "MID", "FWD"].map((p, i) => `<button aria-pressed="${!i}">${p}</button>`).join("")}</div>
        <div class="seg" role="group" aria-label="Horizon">${["Next GW", "3 GWs", "5 GWs"].map((p, i) => `<button aria-pressed="${i === 2}">${p}</button>`).join("")}</div>
        <button class="ghostbtn">${icon("filter")}Filters</button></div>
      <div class="chiprow"><span class="fchip">Top 150 by xP</span><span class="fchip">Any price</span><span class="muted" style="font-size:12px;align-self:center">472 players</span></div>
      <div class="tablewrap"><table><thead><tr><th>Player</th><th>£m</th><th class="hide-sm">Form</th><th class="hide-sm">Own %</th><th class="hide-sm">Start</th><th>Next GW</th><th>xP next 5</th></tr></thead><tbody>
      ${list.map(p => `<tr data-p="${p.id}" class="${X.inSquad(p.id) ? "mine" : ""}"><td><div class="who"><img src="${X.badge(p.team)}" alt=""><span><b>${esc(p.name)}</b>${p.status !== "a" ? `<span class="tag warn">${p.chance ?? "?"}%</span>` : p.sp.includes("pen") ? `<span class="tag">Pens</span>` : ""}<small>${X.teamShort(p.team)} · <span class="pos">${p.pos}</span> · ${X.fxLabel(p.team, G)}</small></span></div></td>
        <td class="num">${num(p.price)}</td><td class="num hide-sm">${num(p.form)}</td><td class="num hide-sm">${num(p.own)}</td><td class="num hide-sm">${X.pct(p.start)}</td><td class="num">${num(p.xp1)}</td>
        <td><span class="xpcell num"><i style="--w:${p.xp5 / max * 100}%"></i>${num(p.xp5)}</span></td></tr>`).join("")}
      </tbody></table></div>`;
  }

  /* ---------- fixtures ---------- */
  function fixtures() {
    const g = X.fixtureGrid();
    return `<h1 class="h-page">Fixtures</h1><p class="lede">Fixture difficulty (FDR 1 easiest to 5 hardest) for the next 5 gameweeks, easiest run first.</p>
      <div class="tablewrap"><table class="fgrid"><thead><tr><th>Team</th>${S.gws.map(w => `<th>GW${w}</th>`).join("")}<th>Avg</th></tr></thead><tbody>
      ${g.map(t => `<tr><td><div class="who"><img src="../../../site/badges/${t.code}.png" alt=""><b>${t.short}</b></div></td>${t.cells.map(c => `<td>${c.list.length ? c.list.map(f => `<span class="fdr fdr-${f.fdr}">${f.opp} ${f.home ? "H" : "A"}</span>`).join("") : `<span class="fdr fdr-3">–</span>`}</td>`).join("")}<td class="num"><b>${num(t.avg)}</b></td></tr>`).join("")}
      </tbody></table></div>`;
  }

  /* ---------- rivals ---------- */
  function rivals() {
    const L = S.league;
    return `<h1 class="h-page">Rivals</h1><p class="lede">${esc(L.name)} · ${rank(L.size)} teams. Names are anonymised in this prototype.</p>
      <div class="tablewrap"><table><thead><tr><th>Manager</th><th>Rank</th><th>GW${S.meta.picks_gw}</th><th>Total</th><th class="hide-sm">Captain</th></tr></thead><tbody>
      ${L.rows.map(r => { const d = r.last - r.rank; return `<tr class="${r.me ? "me" : ""}"><td><div class="who"><span><b>${esc(r.name)}</b><small>${esc(r.team)}</small></span></div></td><td><span class="rk num">${r.rank}</span> ${d ? `<span class="${d > 0 ? "mv-up" : "mv-dn"}">${d > 0 ? "▲" : "▼"}${Math.abs(d)}</span>` : ""}</td><td class="num">${r.gw}</td><td class="num"><b>${r.total}</b></td><td class="hide-sm">${r.cap ? esc(P[r.cap]?.name || "–") : "–"}</td></tr>`; }).join("")}
      </tbody></table></div>`;
  }

  /* ---------- player sheet ---------- */
  function sheet(id) {
    const p = P[id]; if (!p) return;
    const vals = S.gws.map(g => p.xp[g] ?? 0), max = Math.max(...vals, 1);
    const [p10, p6, blank] = p.dist || [];
    $("#sheet").innerHTML = `<div class="hd"><img src="${X.badge(p.team)}" alt=""><div><div class="eyebrow">${X.T[p.team].name} · ${p.pos} · ${money(p.price)}</div><h2>${esc(p.name)}</h2></div><button class="iconbtn close" data-close aria-label="Close">${icon("close")}</button></div>
      <div class="stats4"><div><span class="eyebrow">xP next GW</span><b class="num">${num(p.xp1)}</b></div><div><span class="eyebrow">xP 5 GWs</span><b class="num">${num(p.xp5)}</b></div><div><span class="eyebrow">Start</span><b class="num">${X.pct(p.start)}</b></div><div><span class="eyebrow">Owned</span><b class="num">${num(p.own)}%</b></div></div>
      <div class="eyebrow">Projected points by gameweek</div>
      <div class="gwbars">${S.gws.map((g, i) => `<div class="gwbar"><b class="num">${num(vals[i])}</b><i style="height:${vals[i] / max * 100}px"></i>${fdrs(p.team, g)}<span class="muted">GW${g}</span></div>`).join("")}</div>
      <div class="chance"><div class="eyebrow">GW${G} outcome chances</div>
        <div><span>10+ points</span><i style="--w:${(p10 || 0) * 100}%"></i><b class="num">${X.pct(p10)}</b></div>
        <div><span>6+ points</span><i style="--w:${(p6 || 0) * 100}%"></i><b class="num">${X.pct(p6)}</b></div>
        <div><span>2 or fewer</span><i style="--w:${(blank || 0) * 100}%"></i><b class="num">${X.pct(blank)}</b></div></div>
      <p class="muted" style="font-size:13px;margin-top:20px">Season: ${p.pts} pts · ${p.goals} G · ${p.assists} A · xG ${num(p.xg)} · xA ${num(p.xa)}</p>`;
    $("#sheet").hidden = $("#scrim").hidden = false;
  }
  const closeSheet = () => { $("#sheet").hidden = $("#scrim").hidden = true; };

  const VIEWS = { home, planner, players, fixtures, rivals };
  function render() {
    const { view, arg } = X.route(), v = VIEWS[view] ? view : "home";
    $("#sidenav").innerHTML = NAV.map(([g, items]) => `<div class="navhead">${g}</div>${items.map(([k, l]) => `<button class="navbtn" data-v="${k}" aria-current="${k === v ? "page" : "false"}">${icon(k === "home" ? "home" : k)}${l}</button>`).join("")}`).join("");
    $("#bottomnav").innerHTML = BOTTOM.map(([k, l]) => `<button data-v="${k}" aria-current="${k === v ? "page" : "false"}">${icon(k)}<span>${l}</span></button>`).join("");
    $("[data-theme-toggle]").innerHTML = `${icon("moon")}${document.documentElement.dataset.theme === "light" ? "Light" : "Dark"} mode`;
    header();
    $("#app").innerHTML = VIEWS[v]();
    if (arg) sheet(+arg); else closeSheet();
  }
  document.addEventListener("click", e => {
    const t = e.target.closest("[data-v],[data-p],[data-strat],[data-close],#scrim,[data-theme-toggle]"); if (!t) return;
    if (t.dataset.v && VIEWS[t.dataset.v]) location.hash = t.dataset.v;
    else if (t.dataset.p) sheet(+t.dataset.p);
    else if (t.dataset.strat) { strat = t.dataset.strat; render(); }
    else if (t.hasAttribute("data-theme-toggle")) { const r = document.documentElement; r.dataset.theme = r.dataset.theme === "light" ? "dark" : "light"; render(); }
    else closeSheet();
  });
  addEventListener("keydown", e => { if (e.key === "Escape") closeSheet(); });
  addEventListener("hashchange", render);
  render();
})();
