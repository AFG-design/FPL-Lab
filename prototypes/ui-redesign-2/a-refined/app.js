// A · Refined (round 2). Prototype only: static sample data, no network, no writes. Buttons that would act on the real
// app (Compare, Add to plan, Refresh) are visual only.
(function () {
  const X = window.PROTO; X.theme();
  const { S, P, G, icon, esc, money, num, rank, pct, sgn } = X;
  const $ = s => document.querySelector(s);
  const app = $("#app");
  const st = { strat: "balanced", gw: G, pos: "ALL", fxMode: "fdr", pview: "mine" };
  const fcls = f => `fdr f${f ?? 0}`;
  const cd = X.countdown();
  const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");

  const TITLES = { home: ["This week", `GW${G} · deadline ${X.deadlineText()}`], planner: ["Planner", "Your team as it is, what each strategy would do, and your own plan over the next 5 gameweeks."],
    players: ["Players", "Projected points (xP) from FPL LAB's model. Tap a player for the full outlook."], fixtures: ["Fixtures", "FPL's official difficulty, 1 easiest to 5 hardest. Easiest run first."],
    rivals: ["Rivals", "Your mini-league, with the points gap to each rival."], model: ["Model", "How close FPL LAB's projections have been, and whether today's data is fresh."] };

  function shell(view) {
    const [t, sub] = TITLES[view] || ["Not in this prototype", "This screen keeps its current design."];
    $("#sample").innerHTML = `<b>Sample data</b> <span>Snapshot 18 Nov 2026, not live</span><span class="long">· mini-league managers anonymised · Prototype A · Refined</span>`;
    const M = S.manager, H = S.history, last = H[H.length - 1], prev = H[H.length - 2];
    $("#sideTeam").innerHTML = `<b>${esc(M.team)}</b><span>team 8122679 · GW${S.meta.cur_gw}: ${M.gw_points} pts</span>`;
    $("#sidenav").innerHTML = X.NAV.map(([g, items]) => `<div class="navgroup">${g}</div>` + items.map(([k, l, ic]) =>
      `<a class="navlink" href="#${k}" ${k === view ? 'aria-current="page"' : ""}>${icon(ic)}${l}</a>`).join("")).join("");
    $("#topbar").innerHTML = `<span class="wm-mark mobile-only" aria-hidden="true"></span>
      <div class="ptitle"><h1>${esc(t)}</h1><p>${esc(sub)}</p></div>
      <dl class="stats"><div><dt>Overall rank</dt><dd>${rank(M.rank)}</dd><small class="up">▲ ${rank(prev.rank - last.rank)}</small></div>
        <div><dt>Points</dt><dd>${M.points}</dd><small>GW${S.meta.cur_gw}: ${M.gw_points}</small></div>
        <div><dt>Bank</dt><dd>${money(M.bank)}</dd><small>${M.free_transfers} free transfers</small></div></dl>
      <div class="dl" title="GW${G} deadline"><b>${cd.text}</b><span>GW${G}<span class="desk-only"> deadline<br>${X.deadlineText()}</span></span></div>
      <button class="iconbtn mobile-only" aria-label="Search">${icon("search")}</button>`;
    $("#statstrip").innerHTML = `<div><dt>Rank</dt><dd>${X.short(M.rank)}<small class="up">▲${X.short(prev.rank - last.rank)}</small></dd></div>
      <div><dt>Points</dt><dd>${M.points}<small>${M.gw_points}</small></dd></div><div><dt>Bank</dt><dd>${money(M.bank)}</dd></div><div><dt>Free transfers</dt><dd>${M.free_transfers}</dd></div>`;
    $("#statstrip").setAttribute("role", "list");
    $("#bottomnav").innerHTML = [["home", "Home", "home"], ["planner", "Plan", "planner"], ["rivals", "Rivals", "rivals"], ["players", "Players", "players"], ["more", "More", "more"]]
      .map(([k, l, ic]) => `<a href="#${k}" ${k === view || (k === "more" && ["fixtures", "model"].includes(view)) ? 'aria-current="page"' : ""}>${icon(ic)}${l}</a>`).join("");
    document.querySelectorAll("[data-theme-toggle]").forEach(b => { b.textContent = document.documentElement.dataset.theme === "light" ? "☀ Light mode" : "☾ Dark mode"; });
  }

  // ---------- pitch ----------
  const card = (p, gw) => { const f = X.fx(p.team, gw)[0];
    return `<button class="pc" data-p="${p.id}" aria-label="${esc(p.name)}, ${num(X.xp(p.id, gw))} xP">${p.cap ? '<span class="arm">C</span>' : p.vice ? '<span class="arm v">V</span>' : ""}
      <img src="${X.badge(p.team)}" alt=""><div class="nm">${esc(p.name)}</div><div class="xp">${num(X.xp(p.id, gw))}<small>xP</small></div>
      <span class="${fcls(f?.fdr)}">${f ? (f.home ? f.opp : f.opp.toLowerCase()) + " " + f.fdr : "Blank"}</span></button>`; };
  const pitch = (sq, gw) => `<div class="pitch">${sq.lines.map(l => `<div class="pline">${l.map(p => card(p, gw)).join("")}</div>`).join("")}
      <div class="bench">${sq.bench.map(p => card(p, gw)).join("")}</div></div>`;

  function home() {
    const strats = X.strategies(), cur = strats.find(s => s.key === st.strat), sq = X.planSquad(st.strat, st.gw);
    const caps = X.captains(), margin = caps[0].cxp - caps[1].cxp, close = margin < 1;
    const next = cur.weeks.find(w => w.gw > G && w.in.length);
    const watch = X.players({ limit: 3 }).filter(p => !X.inSquad(p.id));
    const flagged = S.squad.map(s => P[s.id]).filter(p => X.statusText(p));
    return `
    <section class="hero" aria-label="Recommendation">
      <div><div class="eyebrow">${esc(S.manager.team)} · GW${G} model recommendation · <em>${cd.text} left</em></div>
        <h2>No moves planned. <span>${esc(X.squad().captain.name)}</span> captain.</h2>
        <p>The Balanced plan rolls the free transfer this week and makes ${next ? next.in.length : 0} moves in GW${next?.gw ?? "–"}. Change anything and it becomes your draft.</p></div>
      <div class="acts"><a class="btn primary" href="#planner">Open planner</a><button class="btn">Compare with model</button></div>
    </section>
    <div class="grid2">
      <section class="card" aria-labelledby="teamH">
        <h2 id="teamH">GW${st.gw} team · ${esc(cur.name)} plan <span class="aside">${num(sq.week.xp)} xP, captain ×2</span></h2>
        <div class="plantabs"><div class="seg" role="group" aria-label="Strategy">${strats.map(s => `<button data-strat="${s.key}" aria-pressed="${s.key === st.strat}">${s.name}</button>`).join("")}</div></div>
        <div class="gwstrip" role="group" aria-label="Gameweek">${cur.weeks.map(w => `<button data-gw="${w.gw}" aria-pressed="${w.gw === st.gw}"><b>GW${w.gw}</b><span>${w.in.length ? w.in.length + " moves" : "No moves"}</span><span>${num(w.xp)} xP</span></button>`).join("")}</div>
        ${pitch(sq, st.gw)}
        <p class="note" style="margin-top:10px">Numbers are xP for GW${st.gw} only. Chips show the opponent (capitals = home) and FPL difficulty.</p>
      </section>
      <div style="display:flex;flex-direction:column;gap:var(--gap)">
        <section class="card" aria-labelledby="decH">
          <h2 id="decH">GW${G} decisions</h2>
          <div class="decision"><header><span class="label">Transfers</span><span class="key">${S.manager.free_transfers + 1}<small>free transfers for GW${G + 1}</small></span></header>
            <h3>Roll this week to start GW${G + 1} with ${S.manager.free_transfers + 1} free transfers.</h3>
            <p class="note">No transfer beats banking one this week by more than the value of a saved transfer.</p></div>
          <div class="decision"><header><span class="label">Captain</span>${close ? `<span class="pill warn" title="Top two within 1 captain xP">Close call · ${num(margin)} xP</span>` : ""}<span class="key">${num(caps[0].cxp)}<small>captain xP</small></span></header>
            <h3>${esc(caps[0].name)}, with ${esc(caps[1].name)} ${num(margin)} xP behind.</h3>
            ${caps.slice(0, 3).map((c, i) => `<div class="capbar ${i ? "" : "top"}"><span>${esc(c.name)}</span><i style="--w:${(c.cxp / caps[0].cxp * 100).toFixed(0)}%"></i><b>${num(c.cxp)}</b></div>`).join("")}
            <p class="note" style="margin-top:6px">Chance of 10+ points: ${esc(caps[0].name)} ${pct(caps[0].dist?.[0])} · ${esc(caps[1].name)} ${pct(caps[1].dist?.[0])}.</p></div>
          <div class="decision"><header><span class="label">Lineup</span><span class="key">${num(S.lineup.xp_best)}<small>xP, best XI</small></span></header>
            <h3>Start the XI shown; ${esc(P[S.lineup.bench[1]].name)} first off the bench.</h3></div>
        </section>
        <section class="card"><h2>Needs attention <span class="aside">${flagged.length} flagged</span></h2>
          ${flagged.length ? `<ul class="list">${flagged.map(p => `<li><span class="pill warn">${p.chance ?? "?"}%</span>${esc(p.name)}<span class="note">${esc(X.statusText(p))}</span></li>`).join("")}</ul>` : `<p class="note">No injury, suspension or doubt flags in your 15.</p>`}</section>
        <section class="card"><h2>Watchlist <span class="aside">one list (audit #9)</span></h2>
          <ul class="list">${watch.map(p => `<li><img class="crest" src="${X.badge(p.team)}" alt=""><b>${esc(p.name)}</b><span class="note">${X.teamShort(p.team)} · ${money(p.price)}</span><span style="margin-left:auto">${num(p.xp5)} <span class="note">xP 5 GWs</span></span></li>`).join("")}</ul></section>
      </div>
    </div>`;
  }

  function planner() {
    const strats = X.strategies();
    const best = strats.reduce((a, b) => b.gain > a.gain ? b : a);
    const tabs = [["mine", "My team", ""], ["suggest", "Suggested", `${best.name} ${sgn(best.gain)}`], ["paths", "Transfer paths", ""], ["edit", "Your plan", "4 moves"]];
    return `<div class="vtabs" role="group" aria-label="Planner view">${tabs.map(([k, l, s]) => `<button data-pview="${k}" aria-pressed="${k === st.pview}">${l}${s ? `<small>${esc(s)}</small>` : ""}</button>`).join("")}</div>
      <div class="row" style="justify-content:space-between"><h2 class="h2" style="margin:0">What each strategy would do</h2><div class="seg"><button>3 GWs</button><button aria-pressed="true">5 GWs</button><button>6 GWs</button></div></div>
      <div class="grid3">${strats.map(s => `<section class="card strat ${s === best ? "rec" : ""}"><div class="row"><b style="font-size:15.5px">${s.name}</b>${s === best ? '<span class="pill good">Recommended</span>' : ""}</div>
        <div class="gain">${sgn(s.gain)}<small>xP vs no transfers, 5 GWs</small></div><div><b>GW${G}:</b> ${esc(s.nowAction.toLowerCase())}</div><p class="note">${esc(s.blurb)}</p></section>`).join("")}</div>
      <p class="note">Gains are projected points over 5 GWs against keeping this team, after hits, with each banked free transfer valued at the end.</p>
      <section class="card"><h2>${esc(best.name)} plan, move by move <span class="aside">${best.moves.reduce((a, m) => a + m.pairs.length, 0)} transfers, ${best.moves.reduce((a, m) => a + m.hits, 0)} hits</span></h2>
        ${best.moves.map(m => m.pairs.map(([o, i]) => `<div class="move"><span class="gw">GW${m.gw}</span><span class="out">${esc(o.name)} <span class="note">${money(o.price)}</span></span>${icon("arrow")}<span class="in">${esc(i.name)} <span class="note">${money(i.price)}</span></span><span class="r note">${sgn(i.xp5 - o.xp5)} xP5</span></div>`).join("")).join("")}
        <p class="note" style="margin-top:8px">GW${G}, GW13–15: no moves; the free transfer is rolled.</p></section>`;
  }

  function players(detail) {
    const list = X.players({ pos: st.pos, limit: 22 });
    const max = Math.max(...list.flatMap(p => S.gws.map(g => p.xp[g] || 0)));
    return `<section class="card">
      <div class="toolbar"><input class="search" placeholder="Search players" aria-label="Search players">
        <div class="seg desk-only"><button>Next GW</button><button>3 GWs</button><button aria-pressed="true">5 GWs</button></div>
        <div class="seg" role="group" aria-label="Position">${["ALL", "GKP", "DEF", "MID", "FWD"].map(k => `<button data-pos="${k}" aria-pressed="${k === st.pos}">${k === "ALL" ? "All" : k}</button>`).join("")}</div>
        <button class="btn">${icon("filter")}Filters</button></div>
      <div class="scrollx"><table class="tbl"><thead><tr><th class="sticky">Player</th><th class="hide-sm">Pos</th><th class="r">£m</th><th class="r hide-sm">Form</th><th class="r hide-sm">Own %</th><th class="r hide-sm">Nailed</th><th class="r">xP next</th><th class="r">xP next 5</th></tr></thead>
      <tbody>${list.map(p => `<tr class="${X.inSquad(p.id) ? "mine" : ""}"><td class="sticky"><div class="pname"><label class="ck hide-sm"><input type="checkbox" aria-label="Compare ${esc(p.name)}"></label><img class="crest" src="${X.badge(p.team)}" alt="">
        <div><a href="#players/${p.id}" style="color:inherit;text-decoration:none"><b>${esc(p.name)}</b></a><br><small>${X.teamShort(p.team)}${p.sp.includes("pen") ? " · Pens" : ""}${X.statusText(p) ? ` · <span style="color:var(--warn)">${p.chance ?? "?"}%</span>` : ""}</small></div></div></td>
        <td class="hide-sm">${p.pos}</td><td class="r">${num(p.price)}</td><td class="r hide-sm">${num(p.form)}</td><td class="r hide-sm">${num(p.own)}</td>
        <td class="r hide-sm"><span class="nailed ${p.nailed < 80 ? "mid" : ""}">${p.nailed}</span></td><td class="r">${num(p.xp1)}</td>
        <td class="r"><span class="heat hide-sm" aria-hidden="true">${S.gws.map(g => `<i style="--h:${Math.round((p.xp[g] || 0) / max * 90)}%"></i>`).join("")}</span><b>${num(p.xp5)}</b></td></tr>`).join("")}</tbody></table></div>
      <p class="note" style="margin-top:10px">Yellow edge = in your squad. xP next is GW${G} only; xP next 5 is GW${G}–${G + 4}. Bars show each of those 5 GWs.</p></section>${detail ? "" : ""}`;
  }

  function sheet(id) {
    const p = P[id]; if (!p) return "";
    const o = X.outcomes(p), parts = X.breakdown(p), top = Math.max(15, Math.ceil(o?.hi || 0));
    const at = v => `${(v / top * 100).toFixed(1)}%`;
    const pmax = parts ? Math.max(...parts.map(x => Math.abs(x.v))) : 1;
    const pts = p.detail?.pts || [];
    return `<div class="grab" aria-hidden="true"></div>
      <div class="ph"><img src="${X.badge(p.team)}" alt=""><div><div class="note">${esc(X.T[p.team].name)} · ${X.POS_NAME[p.pos]}</div><h2 id="sheetTitle">${esc(p.full)}</h2>
        <div class="row" style="margin-top:4px">${X.inSquad(id) ? '<span class="pill hi">In your squad</span>' : ""}<span class="pill good">${p.nailed} nailed on</span>${p.sp.map(s => `<span class="pill info">${{ pen: "Pens", cor: "Corners", fk: "FKs" }[s] || s}</span>`).join("")}</div></div>
        <a class="iconbtn x" href="#players" aria-label="Close">${icon("close")}</a></div>
      <div class="grid3 k2" style="margin-top:16px">
        <div class="kpi"><span class="label">Price</span><b>${money(p.price)}</b><small>Owned by ${num(p.own)}%</small></div>
        <div class="kpi"><span class="label">Form</span><b>${num(p.form)}</b><small>points per game, last 30 days</small></div>
        <div class="kpi"><span class="label">xP GW${G}</span><b style="color:var(--hi-text)">${num(p.xp1)}</b><small>${X.fxLabel(p.team, G)}</small></div>
        <div class="kpi"><span class="label">xP next 5</span><b>${num(p.xp5)}</b><small>${p.xmin} expected mins next GW</small></div></div>
      ${o ? `<div class="sec"><h3>GW${G} outcomes</h3><div class="range" role="img" aria-label="Likely range ${o.lo} to ${o.hi} points"><span class="band" style="left:${at(o.lo)};width:calc(${at(o.hi)} - ${at(o.lo)})"></span><span class="mark" style="left:${at(p.xp1)}"><b>${num(p.xp1)} xP</b></span>${[0, 5, 10, 15].map(t => `<span class="tick" style="left:${at(t)}">${t}</span>`).join("")}</div>
        <p class="note">Likely range <b>${o.lo}–${o.hi} points</b>: 8 in 10 simulated outcomes fall inside the band.</p>
        <div class="grid3 k3" style="margin-top:10px">${[["10+ pts", o.p10], ["6+ pts", o.p6], ["2 or fewer", o.p2]].map(([l, v]) => `<div class="kpi"><span class="label">${l}</span><b>${pct(v)}</b></div>`).join("")}</div></div>` : ""}
      <div class="sec"><h3>Why ${num(p.xp1)} xP in GW${G}?</h3>${parts ? parts.map(x => `<div class="part ${x.v < 0 ? "neg" : ""}"><span>${x.label}</span><i style="--w:${(Math.abs(x.v) / pmax * 100).toFixed(0)}%"></i><b>${sgn(x.v, 2)}</b></div>`).join("") : `<p class="note">No breakdown in this snapshot.</p>`}</div>
      <div class="sec"><h3>Points by gameweek <span class="note">(actual, GW1–${pts.length})</span></h3><div class="bars">${pts.map((v, i) => `<div><b>${v}</b><i style="height:${Math.max(2, v / Math.max(...pts, 1) * 64)}px"></i>${i + 1}</div>`).join("")}</div></div>
      <div class="sec"><h3>Next 5 fixtures</h3><table class="tbl"><tbody>${S.gws.map(g => { const f = X.fx(p.team, g)[0]; return `<tr><td>GW${g}</td><td>${X.fxLabel(p.team, g)}</td><td><span class="${fcls(f?.fdr)}">${f?.fdr ?? "–"}</span></td><td class="r"><b>${num(p.xp[g])}</b> <span class="note">xP</span></td></tr>`; }).join("")}</tbody></table></div>`;
  }

  function fixtures() {
    const rows = X.fixtureGrid();
    return `<section class="card"><div class="toolbar"><div class="seg">${[["fdr", "Difficulty"], ["win", "Win chance"], ["att", "Attack"], ["cs", "Clean sheet"]].map(([k, l]) => `<button aria-pressed="${k === st.fxMode}">${l}</button>`).join("")}</div>
      <div class="seg"><button>3 GWs</button><button aria-pressed="true">5 GWs</button><button class="desk-only">10 GWs</button></div></div>
      <div class="scrollx"><table class="tbl"><thead><tr><th class="sticky">Team</th><th class="r">Avg</th>${S.gws.map(g => `<th>GW${g}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(r => `<tr class="${r.owned ? "mine" : ""}"><td class="sticky"><div class="pname"><img class="crest" src="../../../site/badges/${r.code}.png" alt=""><b class="desk-only">${esc(r.name)}</b><b class="mobile-only">${r.short}</b></div></td><td class="r">${num(r.avg)}</td>
        ${r.cells.map(c => `<td>${c.list.length ? c.list.map(f => `<span class="${fcls(f.fdr)}">${f.home ? f.opp : f.opp.toLowerCase()} ${f.fdr}</span>`).join(" ") : '<span class="fdr f0">Blank</span>'}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
      <p class="note" style="margin-top:10px">Yellow edge = a club you own players from. On phones the sticky column shows the crest and 3-letter code, so 4 gameweeks fit (audit #10).</p></section>`;
  }

  function rivals() {
    const L = S.league, rows = [...L.rows].sort((a, b) => a.rank - b.rank), me = rows.find(r => r.me), lead = rows[0];
    const above = rows.filter(r => r.rank < me.rank).pop();
    return `<div class="row"><select class="search" style="flex:0 1 300px" aria-label="League"><option>${esc(L.name)} (${me.rank}/${rank(L.size)})</option></select>
        <button class="btn" aria-pressed="false">${icon("star")}Pin to This week</button><span class="note">One toggle (audit #11)</span></div>
      <div class="grid2" style="align-items:start">
        <section class="card"><span class="label">After GW${S.meta.cur_gw} · nearest rival above</span>
          <h2 style="font:700 32px/1.1 var(--display);margin:6px 0">${above.total - me.total} point${above.total - me.total === 1 ? "" : "s"} behind ${esc(above.name)}</h2>
          <p class="note">You're ${ord(me.rank)} of ${rank(L.size)}, ${lead.total - me.total} points off the top. ${esc(above.name)} captained ${esc(P[above.cap]?.name || "–")}.</p>
          <div class="grid3 k3" style="margin-top:12px"><div class="kpi"><span class="label">You</span><b>${me.total}</b></div><div class="kpi"><span class="label">${esc(above.name)}</span><b>${above.total}</b></div><div class="kpi"><span class="label">Leader</span><b>${lead.total}</b></div></div></section>
        <section class="card"><h2>You vs ${esc(above.name)}</h2><p class="note">Players they own that you don't, by GW${G} xP.</p>
          <ul class="list">${above.picks.filter(id => !X.inSquad(id) && P[id]).slice(0, 4).map(id => `<li><img class="crest" src="${X.badge(P[id].team)}" alt="">${esc(P[id].name)}<span style="margin-left:auto">${num(P[id].xp1)} <span class="note">xP</span></span></li>`).join("")}</ul></section></div>
      <section class="card"><h2>Season standings <span class="aside">${rank(L.size)} managers · down to your place</span></h2><div class="scrollx"><table class="tbl"><thead><tr><th>#</th><th class="sticky">Manager</th><th class="r">GW${S.meta.cur_gw}</th><th class="r">Total</th><th class="r">Gap</th><th class="hide-sm">GW${S.meta.cur_gw} captain</th></tr></thead>
        <tbody>${rows.map(r => `<tr class="${r.me ? "mine" : ""}"><td>${r.rank} ${r.last > r.rank ? '<span class="up">▲</span>' : r.last < r.rank ? '<span style="color:var(--bad)">▼</span>' : ""}</td><td class="sticky"><b>${esc(r.name)}</b><br><small class="note">${esc(r.team)}</small></td><td class="r">${r.gw}</td><td class="r"><b>${r.total}</b></td><td class="r">${r.me ? "–" : sgn(r.total - me.total, 0)}</td><td class="hide-sm">${esc(P[r.cap]?.name || "–")}</td></tr>`).join("")}</tbody></table></div></section>`;
  }

  function model(tab) {
    const A = S.accuracy, W = A.weeks;
    const w = X.PHONE() ? 380 : 760, h = X.PHONE() ? 190 : 200, pad = { l: 36, r: 26, t: 14, b: 26 };
    const xs = i => pad.l + i * (w - pad.l - pad.r) / (W.length - 1), ys = v => pad.t + (1 - v / 0.7) * (h - pad.t - pad.b);
    const line = W.map((d, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)},${ys(d.corr).toFixed(1)}`).join("");
    const seg = `<div class="seg" role="group" aria-label="Model tabs"><a class="btn" style="border:0;background:${tab ? "transparent" : "var(--raised)"}" href="#model">Model</a><a class="btn" style="border:0;background:${tab ? "var(--raised)" : "transparent"}" href="#model/health">Data health</a></div>`;
    if (tab === "health") {
      const H = S.health, src = H.sources.filter(r => r[1]);
      return `${seg}<section class="card"><h2>Sources <span class="aside">${H.ok ? '<span class="pill good">All checks passed</span>' : '<span class="pill warn">Problems</span>'}</span></h2>
        <table class="tbl wrap"><thead><tr><th>Source</th><th>Status</th><th>Updated</th><th>Details</th></tr></thead><tbody>${src.map(([k, b, d]) => { const old = (X.NOW - new Date(b)) / 864e5 > 3;
          return `<tr><td><b>${esc(X.srcName(k))}</b></td><td>${old ? '<span class="pill warn">Behind</span>' : '<span class="pill good">OK</span>'}</td><td>${X.ago(b)}</td><td class="note">${Object.entries(d).map(([a, v]) => `${v} ${a}`).join(" · ")}</td></tr>`; }).join("")}</tbody></table>
        <p class="note" style="margin-top:8px">Status sits in column 2 and every cell wraps, so nothing hides off the right edge at 1440px (audit #1).</p></section>
        <section class="card"><h2>Warnings <span class="aside">${H.warnings.length}</span></h2><ul class="list">${H.warnings.map(x => `<li><span class="pill warn">Warn</span><span>${esc(x)}</span></li>`).join("")}</ul></section>`;
    }
    return `${seg}<div class="grid3">
      <div class="kpi"><span class="label">Average miss per player (MAE)</span><b>${num(A.mae, 2)}</b><small>points, GW${W[0].gw}–${W[W.length - 1].gw}, ${rank(A.n)} predictions</small></div>
      <div class="kpi"><span class="label">Correlation with actual points</span><b class="good">${num(A.corr, 2)}</b><small>FPL's own projection: ${num(A.base_corr, 2)}</small></div>
      <div class="kpi"><span class="label">RMSE</span><b>${num(A.rmse, 2)}</b><small>FPL's: ${num(A.base_rmse, 2)} (lower is better)</small></div></div>
      <section class="card"><h2>Correlation by gameweek <span class="aside">higher is better</span></h2>
        <svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Correlation per gameweek">${[0, .2, .4, .6].map(v => `<line class="grid" x1="${pad.l}" x2="${w - pad.r}" y1="${ys(v)}" y2="${ys(v)}"/><text x="${pad.l - 8}" y="${ys(v) + 4}" text-anchor="end">${v.toFixed(1)}</text>`).join("")}
          <path d="${line}" fill="none" stroke="var(--accent-text)" stroke-width="2.5"/>${W.map((d, i) => `<circle cx="${xs(i)}" cy="${ys(d.corr)}" r="3.5" fill="var(--accent-text)"/><text x="${xs(i)}" y="${h - 6}" text-anchor="middle">GW${d.gw}</text>`).join("")}</svg>
        <p class="note">The chart fills its card and the last label has room (audit #3).</p></section>
      <section class="card"><h2>Projected vs actual, by projection band</h2><table class="tbl"><thead><tr><th>Projected</th><th class="r">Players</th><th class="r">Avg projected</th><th class="r">Avg actual</th></tr></thead>
        <tbody>${A.buckets.map(([b, n, pr, ac]) => `<tr><td>${b}–${b + 1} xP</td><td class="r">${rank(n)}</td><td class="r">${num(pr, 2)}</td><td class="r">${num(ac, 2)}</td></tr>`).join("")}</tbody></table></section>`;
  }

  function render() {
    const { view, arg } = X.route();
    shell(view);
    const V = { home, planner, players, fixtures, rivals, model };
    app.innerHTML = V[view] ? V[view](arg) : `<section class="card"><h2>Not in this prototype</h2><p class="note">This screen keeps today's design; A's page-title and spacing rules would apply to it unchanged.</p></section>`;
    const sh = $("#sheet"), scrim = $("#scrim");
    X.fadeScrollers(".scrollx, .gwstrip");
    if (view === "players" && arg) { sh.innerHTML = sheet(+arg); sh.hidden = scrim.hidden = false; } else { sh.hidden = scrim.hidden = true; }
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-strat],[data-gw],[data-pos],[data-pview],[data-p],[data-theme-toggle]"); if (!b) return;
    if (b.dataset.strat) { st.strat = b.dataset.strat; }
    if (b.dataset.gw) st.gw = +b.dataset.gw;
    if (b.dataset.pos) st.pos = b.dataset.pos;
    if (b.dataset.pview) st.pview = b.dataset.pview;
    if (b.dataset.p) { location.hash = `players/${b.dataset.p}`; return; }
    if (b.hasAttribute("data-theme-toggle")) { const r = document.documentElement; r.dataset.theme = r.dataset.theme === "light" ? "dark" : "light"; }
    render();
  });
  $("#scrim").onclick = () => { location.hash = "players"; };
  addEventListener("hashchange", render);
  render();
})();
