// Concept C: Modern & Interactive. Prototype only; reads the sample snapshot through window.PROTO, writes nothing.
// Interactions: strategy switch and gameweek scrubber re-draw the pitch for that plan week; tap a player for a
// drawer (side panel on desktop, bottom sheet on phones); Escape or the scrim closes it.
(function () {
  const X = window.PROTO, { S, P, G, esc, money, num, rank, icon } = X;
  X.theme();
  const $ = s => document.querySelector(s);
  const NAV = [["home", "Matchday"], ["planner", "Plan"], ["players", "Players"], ["fixtures", "Fixtures"], ["rivals", "Rivals"]];
  const st = { strat: "balanced", gw: 0 };
  const SS = X.strategies();
  const segCtl = (items, cur, attr, label) => { const i = items.findIndex(([k]) => k === cur); return `<div class="seg" role="group" aria-label="${label}" style="--n:${items.length};--i:${i}"><span class="thumb" aria-hidden="true"></span>${items.map(([k, l]) => `<button type="button" ${attr}="${k}" aria-pressed="${k === cur}">${l}</button>`).join("")}</div>`; };
  const fdrClass = (team, gw) => { const f = X.fx(team, gw)[0]; return f ? `d${f.fdr}` : "d3"; };

  function chrome(v) {
    $("#rail").innerHTML = `<div class="logo" aria-label="FPL LAB">FPL</div>${NAV.map(([k, l]) => `<button data-v="${k}" aria-label="${l}" aria-current="${k === v ? "page" : "false"}">${icon(k)}<span class="tip">${l}</span></button>`).join("")}<span class="spacer"></span><button data-theme aria-label="Theme">${icon("moon")}<span class="tip">Theme</span></button>`;
    $("#dock").innerHTML = NAV.map(([k, l]) => `<button data-v="${k}" aria-current="${k === v ? "page" : "false"}">${icon(k)}<span>${l}</span></button>`).join("");
    const m = S.manager, h = S.history, mv = h[h.length - 2].rank - h[h.length - 1].rank, cd = X.countdown();
    const frac = (cd.d * 24 + cd.h) / (7 * 24), C = 2 * Math.PI * 17;
    $("#top").innerHTML = `<div class="hello"><div class="k">GW${G} · ${m.free_transfers} free transfers · ${money(m.bank)} in the bank</div><h1>${esc(m.team)}</h1></div>
      <div class="pills"><div class="pill"><span>Overall rank</span><b class="num">${rank(m.rank)}<small>▲${X.short(mv)}</small></b></div><div class="pill"><span>Points</span><b class="num">${m.points}</b></div><div class="pill"><span>GW${S.meta.picks_gw}</span><b class="num">${m.gw_points}</b></div></div>
      <div class="ring" role="timer" aria-label="GW${G} deadline in ${cd.text}"><svg viewBox="0 0 42 42" aria-hidden="true"><circle cx="21" cy="21" r="17" fill="none" stroke="rgb(255 210 63 / 20%)" stroke-width="4"/><circle cx="21" cy="21" r="17" fill="none" stroke="var(--hi)" stroke-width="4" stroke-linecap="round" stroke-dasharray="${C * frac} ${C}"/></svg><div><b class="num">${cd.text}</b><span><span class="long">to the </span>GW${G} deadline</span></div></div>
      <button class="iconbtn press" aria-label="Search">${icon("search")}</button>`;
  }

  /* ---------- home: interactive pitch ---------- */
  function stage() {
    const s = SS.find(x => x.key === st.strat), w = s.weeks[st.gw], prev = st.gw ? s.weeks[st.gw - 1] : { xi: S.lineup.xi, bench: S.lineup.bench };
    const owned = new Set([...prev.xi, ...prev.bench]);
    const row = id => ({ ...P[id], cap: id === w.captain, vice: id === w.vice, isNew: !owned.has(id) });
    const xi = w.xi.map(row), lines = ["GKP", "DEF", "MID", "FWD"].map(pos => xi.filter(p => p.pos === pos));
    const tok = (p, i) => `<button class="tok swap-in" style="animation-delay:${i * 18}ms" data-p="${p.id}" aria-label="${esc(p.name)}, ${num(X.xp(p.id, w.gw))} xP in GW${w.gw}">
        <span class="disc"><img src="${X.badge(p.team)}" alt="">${p.cap ? `<span class="badge">C</span>` : p.vice ? `<span class="badge v">V</span>` : p.isNew ? `<span class="badge new">NEW</span>` : ""}</span>
        <span class="nm">${esc(p.name)}</span><span class="xp num">${num(X.xp(p.id, w.gw))}<small>xP</small></span><span class="opp">${X.fxLabel(p.team, w.gw)}</span></button>`;
    let k = 0;
    return `<div class="stage-top">${segCtl(SS.map(x => [x.key, x.name]), st.strat, "data-strat", "Strategy")}
        <div class="total"><b class="num fade" key="${st.strat}${st.gw}">${num(w.xp)}</b><span>team xP in GW${w.gw}, captain ×2</span></div></div>
      <div class="scrub" role="group" aria-label="Gameweek">${s.weeks.map((x, i) => `<button class="gwchip" data-gw="${i}" aria-pressed="${i === st.gw}"><b>GW${x.gw}${x.in.length ? '<span class="dotm" aria-label="moves"></span>' : ""}</b><span class="num">${x.in.length ? `${x.in.length} move${x.in.length > 1 ? "s" : ""}` : "Roll"} · ${num(x.xp)}</span></button>`).join("")}</div>
      <div class="pitch">${lines.map(l => `<div class="row">${l.map(p => tok(p, k++)).join("")}</div>`).join("")}</div>
      <div class="bench">${w.bench.map((id, i) => `<span class="b"><span class="muted">${i ? i : "GK"}</span><img src="${X.badge(P[id].team)}" alt=""><b>${esc(P[id].name)}</b><span class="muted num">${num(X.xp(id, w.gw))}</span></span>`).join("")}</div>`;
  }
  function home() {
    const caps = X.captains(), [a, b] = caps, bal = SS[0];
    const share = a.cxp / (a.cxp + b.cxp) * 100;
    return `<div class="home"><section class="card stage" id="stage" aria-label="Your team by plan week">${stage()}</section>
      <div class="calls">
        <section class="card call"><div class="hd"><span class="k">TRANSFERS · GW${G}</span><span class="tag">Strong</span></div>
          <h3>Roll it. Start GW${G + 1} with 4 free transfers.</h3>
          <div class="stepper" aria-label="Free transfers banked">${[1, 2, 3, 4, 5].map(i => `<i class="${i <= 4 ? "on" : ""}"></i>`).join("")}</div>
          <p>The ${bal.moves[0].pairs.length} moves in GW${G + 1} are worth +${num(bal.gain)} xP over 5 GWs against making none.</p>
          <div style="display:flex;gap:8px"><button class="cta" data-v="planner">See the moves ${icon("arrow", "ic")}</button><button class="cta ghost">Why roll?</button></div></section>
        <section class="card call"><div class="hd"><span class="k">CAPTAIN · GW${G}</span><span class="tag">Close · ${num(a.cxp - b.cxp)}</span></div>
          <div class="vs"><button class="side win press" data-p="${a.id}"><img src="${X.badge(a.team)}" alt=""><span>${esc(a.name)}</span><b class="num">${num(a.cxp)}</b><small>${X.fxLabel(a.team, G)}</small></button><span class="mid">VS</span>
            <button class="side press" data-p="${b.id}"><img src="${X.badge(b.team)}" alt=""><span>${esc(b.name)}</span><b class="num">${num(b.cxp)}</b><small>${X.fxLabel(b.team, G)}</small></button></div>
          <div class="tug" aria-hidden="true"><i style="width:${share}%"></i><i style="width:${100 - share}%"></i></div>
          <p>Captain xP (xP × 2). 81% of managers near your rank captained Haaland last week.</p></section>
        <section class="card call"><div class="hd"><span class="k">LINEUP</span><span class="tag">Close · 0.1</span></div>
          <h3>Gibbs-White starts, Calvert-Lewin first sub.</h3><p>3.6 xP vs 3.5 xP. Drag to swap on the pitch.</p></section>
      </div></div>`;
  }

  /* ---------- planner: timeline ---------- */
  function planner() {
    const s = SS.find(x => x.key === st.strat), best = Math.max(...SS.map(x => x.gain));
    return `<div class="plan"><div class="stratcards" role="group" aria-label="Strategy">${SS.map(x => `<button class="sc" data-strat="${x.key}" aria-pressed="${x.key === st.strat}"><span class="g num">+${num(x.gain)}<small>xP vs no moves</small></span><b>${x.name}</b><span>${x.blurb}</span><span class="meter"><i style="width:${x.gain / best * 100}%"></i></span></button>`).join("")}</div>
      <div class="tl">${s.weeks.map((w, i) => { const m = s.moves.find(mm => mm.gw === w.gw);
        return `<section class="card node ${m ? "act" : ""}"><div class="hd"><b>GW${w.gw}</b><span class="muted">${m ? `${m.pairs.length} transfer${m.pairs.length > 1 ? "s" : ""}${w.hits ? ` · −${w.hits * 4} hit` : " · no hit"}` : `Roll · ${w.ft} FT next`}</span><span class="x num">${num(w.xp)} xP</span></div>
          ${m ? `<div class="swaps">${m.pairs.map(([o, n]) => `<div class="swap"><span class="o">${esc(o.name)}<br><span class="muted" style="font-weight:500">${money(o.price)}</span></span>${icon("swap")}<span class="i">${esc(n.name)}<br><span class="muted" style="font-weight:500">${money(n.price)}</span></span></div>`).join("")}</div>` : `<p class="muted" style="margin:8px 0 0;font-size:13.5px">Captain ${esc(P[w.captain].name)} · bank ${money(w.bank)}</p>`}</section>`; }).join("")}</div></div>`;
  }

  /* ---------- players: cards ---------- */
  function players() {
    const list = X.players({ limit: 12 });
    return `<div class="bar-tools"><div class="search">${icon("search")}Search 472 players</div>
      <div class="chips" role="group" aria-label="Position">${["All", "Goalkeepers", "Defenders", "Midfielders", "Forwards", "My squad", "Under £6m"].map((c, i) => `<button class="chip press" aria-pressed="${!i}">${c}</button>`).join("")}</div></div>
      <div class="pgrid">${list.map(p => { const v = S.gws.map(g => p.xp[g] || 0), mx = 6;
        return `<button class="pc" data-p="${p.id}"><div class="t"><img src="${X.badge(p.team)}" alt=""><div><b>${esc(p.name)}${X.inSquad(p.id) ? '<span class="mine-dot" title="In your squad"></span>' : ""}</b><span>${X.teamShort(p.team)} · ${p.pos} · ${money(p.price)}</span></div><div class="x"><b class="num">${num(p.xp5)}</b><span class="muted">xP next 5</span></div></div>
          <div class="mini" aria-label="xP per gameweek">${v.map((x, i) => `<div><i style="height:${x / mx * 48}px"></i><span>${num(x)}</span></div>`).join("")}</div>
          <div class="fdrline" aria-label="Fixture difficulty, next 5">${S.gws.map(g => `<span class="${fdrClass(p.team, g)}" title="GW${g}: ${X.fxLabel(p.team, g)}"></span>`).join("")}</div>
          <div class="foot"><span>Start <b>${X.pct(p.start)}</b></span><span>Own <b>${num(p.own)}%</b></span><span>Form <b>${num(p.form)}</b></span></div></button>`; }).join("")}</div>`;
  }

  /* ---------- fixtures ---------- */
  function fixtures() {
    return `<div class="fhead"><span>Team</span>${S.gws.map(g => `<span>GW${g}</span>`).join("")}<span>Avg</span></div><div class="frows">${X.fixtureGrid().map(t => `<div class="frow"><div class="tm"><img src="../../../site/badges/${t.code}.png" alt=""><span>${t.short}</span></div>${t.cells.map(c => { const f = c.list[0]; return f ? `<div class="fcell d${f.fdr}" title="GW${c.gw}: ${f.opp} (${f.home ? "H" : "A"}), FDR ${f.fdr}">${f.opp}${f.home ? "" : "·a"}</div>` : `<div class="fcell d3">–</div>`; }).join("")}<div class="av num">${num(t.avg)}</div></div>`).join("")}</div>
      <p class="muted" style="font-size:13px">FDR 1 (easiest, green) to 5 (hardest, red). Lower-case “·a” = away. Easiest run first.</p>`;
  }

  /* ---------- rivals ---------- */
  function rivals() {
    const L = S.league, me = L.rows.find(r => r.me), top = L.rows[0].total;
    return `<h2 style="margin-bottom:6px">${esc(L.name)}</h2><p class="muted" style="margin:0 0 16px">${rank(L.size)} teams · names anonymised in this prototype</p>
      <div class="lb">${L.rows.map(r => { const d = r.last - r.rank; return `<div class="lr ${r.me ? "me" : ""}"><span class="pos num">${r.rank}</span><div class="who"><b>${esc(r.name)} ${d ? `<small class="${d > 0 ? "" : ""}" style="color:var(--${d > 0 ? "good" : "bad"})">${d > 0 ? "▲" : "▼"}${Math.abs(d)}</small>` : ""}</b><span>${esc(r.team)} · GW${S.meta.picks_gw} ${r.gw} pts${r.cap ? ` · C ${esc(P[r.cap]?.name || "–")}` : ""}</span></div>
        <div class="gap"><span>${r.me ? "You" : `${r.total - me.total > 0 ? "+" : ""}${r.total - me.total} vs you`}</span><i style="--w:${Math.max(2, (top - r.total) / 80 * 100)}%"></i></div><span class="tot num">${r.total}</span></div>`; }).join("")}</div>`;
  }

  /* ---------- drawer ---------- */
  function drawer(id) {
    const p = P[id]; if (!p) return;
    const v = S.gws.map(g => p.xp[g] || 0), mx = Math.max(...v) * 1.1, [p10, p6, blank] = p.dist || [];
    $("#drawer").innerHTML = `<div class="hd"><span class="crest"><img src="${X.badge(p.team)}" alt=""></span><div><div class="k">${X.T[p.team].name.toUpperCase()} · ${p.pos} · ${money(p.price)}</div><h2>${esc(p.name)}</h2></div><button class="iconbtn close press" data-close aria-label="Close">${icon("close")}</button></div>
      <div class="big3"><div><span>xP GW${G}</span><b class="num">${num(p.xp1)}</b></div><div><span>xP next 5</span><b class="num">${num(p.xp5)}</b></div><div><span>Start chance</span><b class="num">${X.pct(p.start)}</b></div></div>
      <div class="k">PROJECTED POINTS BY GAMEWEEK</div>
      <div class="dbars">${v.map((x, i) => `<div><b class="num">${num(x)}</b><i style="height:${x / mx * 120}px"></i><span>GW${S.gws[i]}<br>${X.fxLabel(p.team, S.gws[i])}</span></div>`).join("")}</div>
      <div class="k" style="margin-top:14px">GW${G} OUTCOMES</div>
      <div class="odds"><div class="odd" style="--w:${(p10 || 0) * 100}%"><span>10+ pts</span><b class="num">${X.pct(p10)}</b></div><div class="odd" style="--w:${(p6 || 0) * 100}%"><span>6+ pts</span><b class="num">${X.pct(p6)}</b></div><div class="odd" style="--w:${(blank || 0) * 100}%"><span>2 or fewer</span><b class="num">${X.pct(blank)}</b></div></div>
      <div class="acts"><button class="cta">${X.inSquad(id) ? "Plan a sale" : "Add to plan"}</button><button class="cta ghost">Compare</button></div>`;
    $("#drawer").hidden = $("#scrim").hidden = false;
  }
  const close = () => { $("#drawer").hidden = $("#scrim").hidden = true; };

  const VIEWS = { home, planner, players, fixtures, rivals };
  function render() {
    const { view, arg } = X.route(), v = VIEWS[view] ? view : "home";
    chrome(v);
    $("#app").innerHTML = VIEWS[v]();
    if (arg) drawer(+arg); else close();
  }
  document.addEventListener("click", e => {
    const t = e.target.closest("[data-v],[data-p],[data-strat],[data-gw],[data-close],#scrim,[data-theme]"); if (!t) return;
    if (t.dataset.v && VIEWS[t.dataset.v]) location.hash = t.dataset.v;
    else if (t.dataset.p) drawer(+t.dataset.p);
    else if (t.dataset.strat) { st.strat = t.dataset.strat; if ($("#stage")) $("#stage").innerHTML = stage(); else render(); }
    else if (t.dataset.gw) { st.gw = +t.dataset.gw; $("#stage").innerHTML = stage(); }
    else if (t.hasAttribute("data-theme")) { const r = document.documentElement; r.dataset.theme = r.dataset.theme === "light" ? "dark" : "light"; }
    else close();
  });
  addEventListener("keydown", e => { if (e.key === "Escape") close(); });
  addEventListener("hashchange", render);
  render();
})();
