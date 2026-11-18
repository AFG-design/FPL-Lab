// B · Premium Analytics (round 2). Prototype only: static sample data, no network, no writes.
(function () {
  const X = window.PROTO; X.theme();
  const { S, P, G, icon, esc, money, num, rank, pct, sgn } = X;
  const $ = s => document.querySelector(s);
  const st = { pos: "ALL", h: 5 };
  const fc = f => `fd f${f ?? 0}`;
  // heat from 2 xP (faint) to the column-set max (strong): the useful spread is 2-5 xP, not 0-5
  const heatA = (v, max) => (0.04 + 0.62 * Math.max(0, Math.min(1, (v - 2) / (max - 2)))).toFixed(2);
  const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");

  // ---------- tiny chart kit (inline SVG, viewBox scales to its column; labels never clipped) ----------
  const spark = (vals, { bars = false, invert = false, hiLast = true } = {}) => {
    const w = 160, h = 26, mn = Math.min(...vals), mx = Math.max(...vals), sx = i => i * (w - 4) / (vals.length - 1) + 2;
    const sy = v => { const t = (v - mn) / ((mx - mn) || 1); return 2 + (invert ? t : 1 - t) * (h - 4); };
    if (bars) { const bw = (w - 2) / vals.length - 2; return `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true">${vals.map((v, i) => `<rect x="${1 + i * (bw + 2)}" y="${h - Math.max(1.5, v / mx * (h - 2))}" width="${bw}" height="${Math.max(1.5, v / mx * (h - 2))}" rx="1" fill="${hiLast && i === vals.length - 1 ? "var(--accent-text)" : "var(--rule-2)"}"/>`).join("")}</svg>`; }
    return `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true"><path d="${vals.map((v, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join("")}" fill="none" stroke="var(--accent-text)" stroke-width="1.6"/><circle cx="${sx(vals.length - 1)}" cy="${sy(vals[vals.length - 1])}" r="2.6" fill="var(--accent-text)"/></svg>`;
  };
  function lineChart({ xs, series, w = 640, h = 210, yTicks, yFmt = v => v, yMin, yMax, invert = false, log = false, label }) {
    if (X.PHONE()) { h = Math.round(h * 380 / w); w = 380; }   // keep 11px labels readable on a phone
    const pad = { l: 46, r: 60, t: 12, b: 24 };
    const tf = v => log ? Math.log10(v) : v;
    const lo = tf(yMin), hi = tf(yMax);
    const X_ = i => pad.l + i * (w - pad.l - pad.r) / (xs.length - 1);
    const Y_ = v => { const t = (tf(v) - lo) / (hi - lo); return pad.t + (invert ? t : 1 - t) * (h - pad.t - pad.b); };
    return `<svg class="ch" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}">
      ${yTicks.map(v => `<line class="g" x1="${pad.l}" x2="${w - pad.r}" y1="${Y_(v)}" y2="${Y_(v)}"/><text x="${pad.l - 8}" y="${Y_(v) + 4}" text-anchor="end">${yFmt(v)}</text>`).join("")}
      ${xs.map((x, i) => `<text x="${X_(i)}" y="${h - 6}" text-anchor="middle">${x}</text>`).join("")}
      ${series.map((s, si) => `<path d="${s.vals.map((v, i) => `${i ? "L" : "M"}${X_(i).toFixed(1)},${Y_(v).toFixed(1)}`).join("")}" fill="none" stroke="${s.c}" stroke-width="${s.w || 2.2}" ${s.dash ? 'stroke-dasharray="4 4"' : ""}/>
        <circle cx="${X_(s.vals.length - 1)}" cy="${Y_(s.vals[s.vals.length - 1])}" r="3.5" fill="${s.c}"/>
        <text class="lbl" x="${X_(s.vals.length - 1) + 8}" y="${Y_(s.vals[s.vals.length - 1]) + 4 + si * 14}" style="fill:${s.c}">${esc(s.name)}</text>`).join("")}</svg>`;
  }

  function shell(view) {
    const titles = { home: "This week", planner: "Planner", players: "Players", fixtures: "Fixtures", rivals: "Rivals", model: "Model" };
    $("#sample").innerHTML = `<b>Sample data</b> <span>Snapshot 18 Nov 2026, not live</span><span class="long">· mini-league managers anonymised · Prototype B · Premium Analytics</span>`;
    $("#sidenav").innerHTML = X.NAV.map(([g, items]) => `<div class="grp">${g}</div>` + items.map(([k, l, ic]) => `<a class="nl" href="#${k}" ${k === view ? 'aria-current="page"' : ""}>${icon(ic)}${l}</a>`).join("")).join("");
    const cd = X.countdown();
    $("#ctx").innerHTML = `<h1>${titles[view] || "Not in this prototype"}</h1><span class="crumb">${esc(S.manager.team)} · GW${G} · ${X.deadlineText()}</span><span class="sp"></span>
      <span class="dlchip"><b>${cd.text}</b><span>to GW${G} deadline</span></span>
      <div class="seg desk" role="group" aria-label="Forecast horizon">${[1, 3, 5].map(h => `<button data-h="${h}" aria-pressed="${h === st.h}">${h === 1 ? "Next GW" : h + " GWs"}</button>`).join("")}</div>
      <span class="kbd desk">${icon("search")}Search players, clubs<kbd>/</kbd></span>`;
    const H = S.history, M = S.manager, A = S.accuracy, bal = S.plans.balanced;
    const benchTot = H.filter(x => x.chip !== "bboost").reduce((a, x) => a + x.bench, 0);
    $("#ribbon").innerHTML = [
      ["Overall rank", rank(M.rank), `<span class="up">▲ ${rank(H[H.length - 2].rank - M.rank)}</span>`, spark(H.map(x => Math.log10(x.rank)), { invert: true })],
      ["Points", M.points, `GW${S.meta.cur_gw}: ${M.gw_points}`, spark(H.map(x => x.pts), { bars: true })],
      [`Plan xP · GW${G}–${G + 4}`, num(bal.xp_total), `${sgn(bal.vs_none)} vs no moves`, spark(bal.weeks.map(w => w.xp), { bars: true, hiLast: false })],
      ["Left on bench", benchTot, "pts, excl. Bench Boost", spark(H.map(x => x.bench), { bars: true })],
      ["Model correlation", num(A.corr, 2), `FPL's: ${num(A.base_corr, 2)}`, spark(A.weeks.map(w => w.corr))],
    ].map(([t, v, s, sp]) => `<div class="k"><div class="t">${t}</div><div class="v"><b>${v}</b><small>${s}</small></div>${sp}</div>`).join("");
    $("#tabbar").innerHTML = [["home", "Home", "home"], ["planner", "Plan", "planner"], ["rivals", "Rivals", "rivals"], ["players", "Players", "players"], ["model", "More", "more"]]
      .map(([k, l, ic]) => `<a href="#${k}" ${k === view || (k === "model" && view === "fixtures") ? 'aria-current="page"' : ""}>${icon(ic)}${l}</a>`).join("");
  }

  const xpH = p => st.h === 1 ? p.xp1 : S.gws.slice(0, st.h).reduce((a, g) => a + (p.xp[g] || 0), 0);

  function home() {
    const sq = X.squad(), caps = X.captains(), strats = X.strategies(), H = S.history;
    const all = [...sq.xi, ...sq.bench], max = Math.max(...all.flatMap(p => S.gws.map(g => p.xp[g] || 0)));
    const gwTot = S.gws.map(g => sq.xi.reduce((a, p) => a + (p.xp[g] || 0) * (p.cap ? 2 : 1), 0));
    return `
    <section class="p c7"><div class="ph"><h2>Decision board · GW${G}</h2><span class="m">${X.countdown().text} to deadline</span></div>
      <table class="t call"><tbody>
        <tr><td>Transfers</td><td><div class="verdict">Roll the free transfer</div><small class="note">Balanced plan: no GW${G} move; 4 moves in GW${G + 1}, ${sgn(strats[0].gain)} xP over 5 GWs vs none</small></td><td class="r"><span class="big">${S.manager.free_transfers + 1}</span><br><small class="note">FT for GW${G + 1}</small></td></tr>
        <tr><td>Captain</td><td><div class="verdict">${esc(caps[0].name)} <span class="tag w">Close · ${num(caps[0].cxp - caps[1].cxp)} xP lead</span></div><small class="note">Next: ${caps.slice(1, 3).map(c => `${esc(c.name)} ${num(c.cxp)}`).join(" · ")}</small></td><td class="r"><span class="big">${num(caps[0].cxp)}</span><br><small class="note">captain xP</small></td></tr>
        <tr><td>Vice</td><td><div class="verdict">${esc(sq.vice.name)}</div><small class="note">The second-highest projected starter</small></td><td class="r"><span class="big">${num(sq.vice.xp1 * 2)}</span><br><small class="note">if captained</small></td></tr>
        <tr><td>Lineup</td><td><div class="verdict">Best XI as shown below</div><small class="note">Bench order: ${sq.bench.slice(1).map(p => esc(p.name)).join(", ")}</small></td><td class="r"><span class="big">${num(sq.xp)}</span><br><small class="note">xP, captain ×2</small></td></tr>
      </tbody></table></section>
    <section class="p c5"><div class="ph"><h2>Overall rank</h2><span class="m">GW1–${H.length}, log scale, up = better</span></div>
      ${lineChart({ xs: H.map(x => "GW" + x.gw), series: [{ name: X.short(S.manager.rank), vals: H.map(x => x.rank), c: "var(--accent-text)" }], yMin: 30000, yMax: 3e6, log: true, invert: true, yTicks: [3e6, 1e6, 3e5, 1e5, 3e4], yFmt: X.short, label: "Overall rank by gameweek", w: 460, h: 210 })}</section>
    <section class="p c8"><div class="ph"><h2>Squad xP matrix</h2><span class="m">xP per gameweek · captain ×2 not applied in cells</span></div>
      <div class="scroll"><table class="t"><thead><tr><th class="st">Player</th><th class="hide-sm">Pos</th><th class="r hide-sm">Nailed</th>${S.gws.map(g => `<th class="c">GW${g}</th>`).join("")}<th class="r">Σ 5</th><th class="hide-sm">GW${G} range</th></tr></thead>
      <tbody>${all.map((p, i) => { const o = X.outcomes(p);
        return `<tr ${i === 11 ? 'style="border-top:2px solid var(--rule-2)"' : ""}><td class="st"><div class="pl"><img src="${X.badge(p.team)}" alt=""><a href="#players/${p.id}">${esc(p.name)}</a>${p.cap ? '<span class="cap">C</span>' : p.vice ? '<span class="cap v">V</span>' : ""}${i >= 11 ? ' <small>bench</small>' : ""}</div></td>
        <td class="hide-sm">${p.pos}</td><td class="r hide-sm">${p.nailed}</td>${S.gws.map(g => `<td class="hm" style="--a:${heatA(p.xp[g] || 0, max)}">${num(p.xp[g])}</td>`).join("")}<td class="r"><b>${num(p.xp5)}</b></td>
        <td class="hide-sm">${o ? `<span class="rng" title="${o.lo}–${o.hi} pts"><i style="left:${o.lo / 15 * 100}%;width:${(o.hi - o.lo) / 15 * 100}%"></i><b style="left:${Math.min(98, p.xp1 / 15 * 100)}%"></b></span> <small class="note">${o.lo}–${o.hi}</small>` : "–"}</td></tr>`; }).join("")}
      <tr><td class="st"><b>XI total</b></td><td class="hide-sm"></td><td class="hide-sm"></td>${gwTot.map(v => `<td class="c"><b>${num(v)}</b></td>`).join("")}<td class="r"><b>${num(gwTot.reduce((a, b) => a + b, 0))}</b></td><td class="hide-sm"><small class="note">XI as it is, captain ×2</small></td></tr></tbody></table></div>
      <p class="note">Range = where 8 in 10 of the model's simulated GW${G} outcomes fall; tick = xP. Yellow = captain.</p></section>
    <section class="p c4"><div class="ph"><h2>Strategies · 5 GWs</h2><span class="m">xP vs no moves</span></div>
      ${strats.map(s => `<div style="display:grid;grid-template-columns:90px 1fr 44px;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--rule)"><span>${s.name}</span><span class="meter" style="width:100%;height:10px;--w:${s.gain / 8 * 100}%"></span><b class="r" style="text-align:right">${sgn(s.gain)}</b></div>`).join("")}
      <p class="note">Balanced and Play safe never take a hit; Chase rank may give up up to 2 xP for differentials.</p>
      <div class="ph" style="margin-top:18px"><h2>Captain · GW${G} upside</h2><span class="m">chance of 10+ pts</span></div>
      <table class="t"><tbody>${caps.slice(0, 4).map(c => `<tr><td>${esc(c.name)}</td><td class="r">${num(c.cxp)} <small class="note">cxP</small></td><td class="r"><span class="meter" style="--w:${(c.dist?.[0] || 0) / .25 * 100}%;--c:var(--hi)"></span> ${pct(c.dist?.[0])}</td></tr>`).join("")}</tbody></table></section>`;
  }

  function planner() {
    const strats = X.strategies(), b = strats[0];
    return `<section class="p c12"><div class="ph"><h2>Strategy comparison · GW${G}–${G + 4}</h2><span class="m">projected points, after hits; banked FT valued at the end</span></div>
      <table class="t"><thead><tr><th>Strategy</th><th class="r">vs no moves</th><th class="r">Plan xP</th>${S.gws.map(g => `<th class="c">GW${g}</th>`).join("")}<th class="r">Transfers</th><th class="r">Hits</th><th class="r hide-sm">FT left</th></tr></thead>
      <tbody>${strats.map(s => `<tr class="${s === b ? "sel" : ""}"><td><b>${s.name}</b>${s === b ? ' <span class="tag g">Recommended</span>' : ""}</td><td class="r up"><b>${sgn(s.gain)}</b></td><td class="r">${num(s.total)}</td>
        ${s.weeks.map(w => `<td class="c">${w.in.length ? `<span class="tag b">${w.in.length} in</span>` : '<small class="note">roll</small>'}<br><small>${num(w.xp)}</small></td>`).join("")}<td class="r">${s.moves.reduce((a, m) => a + m.pairs.length, 0)}</td><td class="r">${s.moves.reduce((a, m) => a + m.hits, 0)}</td><td class="r hide-sm">${s.ftLeft}</td></tr>`).join("")}</tbody></table></section>
    <section class="p c7"><div class="ph"><h2>Balanced · transfers</h2><span class="m">xP over GW${G}–${G + 4} for each player</span></div>
      <table class="t"><thead><tr><th>GW</th><th>Out</th><th class="r">xP5</th><th></th><th>In</th><th class="r">xP5</th><th class="r">Gain</th></tr></thead><tbody>
      ${b.moves.flatMap(m => m.pairs.map(([o, i]) => `<tr><td>GW${m.gw}</td><td><div class="pl"><img src="${X.badge(o.team)}" alt="">${esc(o.name)}</div></td><td class="r">${num(o.xp5)}</td><td class="c">${icon("arrow")}</td><td><div class="pl"><img src="${X.badge(i.team)}" alt="">${esc(i.name)}</div></td><td class="r">${num(i.xp5)}</td><td class="r ${i.xp5 - o.xp5 >= 0 ? "up" : "dn"}">${sgn(i.xp5 - o.xp5)}</td></tr>`)).join("")}</tbody></table>
      <p class="note">Each player's xP5 is his own next-5 total; the plan's gain differs because the moves happen in GW${G + 1}, not now.</p></section>
    <section class="p c5"><div class="ph"><h2>Plan xP by gameweek</h2><span class="m">XI with captain ×2</span></div>
      ${lineChart({ xs: S.gws.map(g => "GW" + g), series: [{ name: "Balanced", vals: S.plans.balanced.weeks.map(w => w.xp), c: "var(--accent-text)" }, { name: "Chase", vals: S.plans.chase.weeks.map(w => w.xp), c: "var(--s3)", dash: 1, w: 1.6 }], yMin: 44, yMax: 54, yTicks: [44, 48, 52], label: "Plan xP by gameweek", w: 460, h: 220 })}</section>`;
  }

  function detail(p) {
    const o = X.outcomes(p), parts = X.breakdown(p) || [], tot = parts.filter(x => x.v > 0).reduce((a, x) => a + x.v, 0);
    const cols = ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s1", "--s2"];
    const pts = p.detail?.pts || [], xgi = p.detail?.xgi || [];
    const w = 420, h = 150, pad = { l: 26, r: 26, t: 10, b: 22 }, n = pts.length, bw = (w - pad.l - pad.r) / n;
    const mx = Math.max(15, ...pts), y = v => h - pad.b - v / mx * (h - pad.t - pad.b), yx = v => h - pad.b - v / 2 * (h - pad.t - pad.b);
    return `<div class="dh"><img src="${X.badge(p.team)}" alt=""><div><h2>${esc(p.full)}</h2><span class="note" style="margin:0">${esc(X.T[p.team].name)} · ${X.POS_NAME[p.pos]} · ${money(p.price)}</span>
        <div style="display:flex;gap:6px;margin-top:6px">${X.inSquad(p.id) ? '<span class="tag y">In your squad</span>' : ""}<span class="tag g">Nailed ${p.nailed}</span>${p.sp.includes("pen") ? '<span class="tag b">Pens</span>' : ""}</div></div></div>
      <div class="kv"><div><span>xP GW${G}</span><b style="color:var(--hi-text)">${num(p.xp1)}</b></div><div><span>xP next 5</span><b>${num(p.xp5)}</b></div><div><span>Expected mins</span><b>${p.xmin}</b></div><div><span>Owned</span><b>${num(p.own)}%</b></div></div>
      ${o ? `<div class="ph" style="margin-top:16px"><h2>GW${G} outcomes</h2><span class="m">8 in 10 simulations inside the band</span></div>
        <svg class="ch" viewBox="0 0 420 70" role="img" aria-label="Likely ${o.lo} to ${o.hi} points">${[0, 5, 10, 15].map(t => `<line class="g" x1="${10 + t * 26.7}" x2="${10 + t * 26.7}" y1="8" y2="44"/><text x="${10 + t * 26.7}" y="60" text-anchor="middle">${t}</text>`).join("")}
          <rect x="${10 + o.lo * 26.7}" y="18" width="${(o.hi - o.lo) * 26.7}" height="16" rx="8" fill="rgb(var(--heat) / .3)" stroke="var(--accent-text)"/><line x1="${10 + p.xp1 * 26.7}" x2="${10 + p.xp1 * 26.7}" y1="10" y2="42" stroke="var(--fg)" stroke-width="2"/><text class="lbl" x="${16 + p.xp1 * 26.7}" y="14">${num(p.xp1)} xP</text></svg>
        <table class="t"><tbody><tr><td>10+ pts</td><td class="r"><span class="meter" style="--w:${o.p10 * 100}%;--c:var(--hi)"></span> ${pct(o.p10)}</td><td>6+ pts</td><td class="r"><span class="meter" style="--w:${o.p6 * 100}%"></span> ${pct(o.p6)}</td><td>≤2 pts</td><td class="r"><span class="meter" style="--w:${o.p2 * 100}%;--c:var(--bad)"></span> ${pct(o.p2)}</td></tr></tbody></table>` : ""}
      <div class="ph" style="margin-top:16px"><h2>Why ${num(p.xp1)} xP</h2><span class="m">model parts, GW${G}</span></div>
      ${parts.length ? `<div class="stack" role="img" aria-label="xP made of ${parts.map(x => x.label + " " + num(x.v, 2)).join(", ")}">${parts.filter(x => x.v > 0).map((x, i) => `<i style="flex:${x.v / tot};--c:var(${cols[i]})"></i>`).join("")}</div>
        <div class="legend">${parts.map((x, i) => `<span><i style="--c:var(${x.v > 0 ? cols[parts.filter(q => q.v > 0).indexOf(x)] : "--bad"})"></i>${x.label}<b>${sgn(x.v, 2)}</b></span>`).join("")}</div>` : '<p class="note">No breakdown in this snapshot.</p>'}
      <div class="ph" style="margin-top:16px"><h2>Points vs xGI · GW1–${n}</h2><span class="m">bars actual pts · line xG + xA</span></div>
      <svg class="ch" viewBox="0 0 ${w} ${h}" role="img" aria-label="Actual points and expected goal involvement by gameweek">${[0, 5, 10, 15].map(v => `<line class="g" x1="${pad.l}" x2="${w - pad.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${pad.l - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`).join("")}
        ${pts.map((v, i) => `<rect x="${pad.l + i * bw + 3}" y="${y(Math.max(0, v))}" width="${bw - 6}" height="${Math.max(1, Math.max(0, v) / mx * (h - pad.t - pad.b))}" rx="2" fill="var(--rule-2)"/><text x="${pad.l + i * bw + bw / 2}" y="${h - 6}" text-anchor="middle">${i + 1}</text>`).join("")}
        <path d="${xgi.map((v, i) => `${i ? "L" : "M"}${(pad.l + i * bw + bw / 2).toFixed(1)},${yx(v).toFixed(1)}`).join("")}" fill="none" stroke="var(--accent-text)" stroke-width="2"/>
        <text x="${w - pad.r + 4}" y="${yx(2) + 4}">2.0</text><text x="${w - pad.r + 4}" y="${yx(1) + 4}">1.0</text></svg>
      <div class="ph" style="margin-top:16px"><h2>Next 5</h2><span class="m">FDR and xP</span></div>
      <table class="t"><tbody><tr>${S.gws.map(g => { const f = X.fx(p.team, g)[0]; return `<td class="${fc(f?.fdr)}">${X.fxShort(p.team, g)}</td>`; }).join("")}</tr><tr>${S.gws.map(g => `<td class="c"><b>${num(p.xp[g])}</b></td>`).join("")}</tr></tbody></table>`;
  }

  function players(arg) {
    const list = X.players({ pos: st.pos, limit: 24 }).sort((a, b) => xpH(b) - xpH(a));
    const sel = arg ? +arg : list[0].id, max = Math.max(...list.flatMap(p => S.gws.map(g => p.xp[g] || 0)));
    const phoneDetail = matchMedia("(max-width: 899px)").matches && arg;
    if (phoneDetail) return `<section class="p"><a href="#players" class="tag" style="text-decoration:none">${icon("back", "ic")} Players</a></section><section class="p">${detail(P[sel])}</section>`;
    return `<section class="p ${matchMedia("(max-width: 1180px)").matches ? "" : "c7"}"><div class="ph"><h2>Screener</h2><span class="m">${list.length} of 472 · sorted by xP ${st.h === 1 ? "next GW" : "next " + st.h}</span></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0"><div class="seg" role="group" aria-label="Position">${["ALL", "GKP", "DEF", "MID", "FWD"].map(k => `<button data-pos="${k}" aria-pressed="${k === st.pos}">${k === "ALL" ? "All" : k}</button>`).join("")}</div>
        <span class="tag">Price ≤ £15.0m ×</span><span class="tag">Nailed ≥ 70 ×</span><span class="tag">${icon("filter")} Add filter</span></div>
      <div class="scroll"><table class="t"><thead><tr><th class="st">Player</th><th class="r">£m</th><th class="r hide-sm">Own</th><th class="r hide-sm">xMin</th><th class="r hide-sm">xGI/90 L4</th>${S.gws.map(g => `<th class="c">${g}</th>`).join("")}<th class="r">Σ</th></tr></thead>
      <tbody>${list.map(p => `<tr class="${p.id === sel ? "sel" : ""} ${X.inSquad(p.id) ? "own" : ""}"><td class="st"><div class="pl"><img src="${X.badge(p.team)}" alt=""><a href="#players/${p.id}"><b>${esc(p.name)}</b></a><small>${X.teamShort(p.team)} ${p.pos}</small></div></td>
        <td class="r">${num(p.price)}</td><td class="r hide-sm">${num(p.own)}</td><td class="r hide-sm">${p.xmin}</td><td class="r hide-sm">${num(p.xgi90_4, 2)}</td>
        ${S.gws.map(g => `<td class="hm" style="--a:${heatA(p.xp[g] || 0, max)}">${num(p.xp[g])}</td>`).join("")}<td class="r"><b>${num(xpH(p))}</b></td></tr>`).join("")}</tbody></table></div>
      <p class="note">Columns 11–15 are xP per gameweek. Yellow edge = in your squad. Select a row to load it on the right.</p></section>
      <section class="p c5 desk" style="position:sticky;top:12px">${detail(P[sel])}</section>`;
  }

  function fixtures() {
    const rows = X.fixtureGrid();
    return `<section class="p"><div class="ph"><h2>Fixture difficulty · GW${G}–${G + 4}</h2><span class="m">FPL FDR 1 (easy) to 5 (hard) · capitals = home · sorted by average</span></div>
      <div class="scroll"><table class="t"><thead><tr><th class="st">Club</th><th class="r">Avg</th><th class="hide-sm">Run</th>${S.gws.map(g => `<th class="c">GW${g}</th>`).join("")}</tr></thead><tbody>
      ${rows.map(r => `<tr class="${r.owned ? "own" : ""}"><td class="st"><div class="pl"><img src="../../../site/badges/${r.code}.png" alt=""><b>${r.short}</b><small class="hide-sm">${esc(r.name)}</small></div></td><td class="r"><b>${num(r.avg)}</b></td>
        <td class="hide-sm"><span class="meter" style="width:110px;--w:${(5 - r.avg) / 4 * 100}%"></span></td>${r.cells.map(c => `<td class="${fc(c.list[0]?.fdr)}">${c.list.length ? c.list.map(f => (f.home ? f.opp : f.opp.toLowerCase()) + " " + f.fdr).join(" + ") : "blank"}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
      <p class="note">Yellow edge = a club you own players from. Bar = how easy the 5-GW run is (longer = easier).</p></section>`;
  }

  function rivals() {
    const L = S.league, rows = [...L.rows].sort((a, b) => a.rank - b.rank), me = rows.find(r => r.me);
    const mine = new Set(S.lineup.xi), rivalsOnly = rows.filter(r => !r.me);
    const eo = {}; rivalsOnly.forEach(r => r.picks.forEach(id => { eo[id] = (eo[id] || 0) + 1; }));
    const diffs = Object.entries(eo).filter(([id]) => !X.inSquad(+id) && P[id]).sort((a, b) => b[1] - a[1]).slice(0, 6);
    const gapMax = Math.max(...rows.map(r => Math.abs(r.total - me.total)));
    return `<section class="p c8"><div class="ph"><h2>${esc(L.name)} · standings</h2><span class="m">You: ${ord(me.rank)} of ${rank(L.size)} · rows down to your place</span></div>
      <div class="scroll"><table class="t"><thead><tr><th class="r">#</th><th class="st">Manager</th><th class="r">GW${S.meta.cur_gw}</th><th class="r">Total</th><th>Gap to you</th><th class="hide-sm">GW${S.meta.cur_gw} captain</th><th class="r hide-sm">XI overlap</th></tr></thead><tbody>
      ${rows.map(r => { const d = r.total - me.total, ov = r.picks.filter(id => mine.has(id)).length;
        return `<tr class="${r.me ? "me" : ""}"><td class="r">${r.rank}</td><td class="st"><b>${esc(r.name)}</b> <small class="note hide-sm">${esc(r.team)}</small></td><td class="r">${r.gw}</td><td class="r"><b>${r.total}</b></td>
        <td>${r.me ? '<small class="note">you</small>' : `<span style="display:inline-flex;align-items:center;gap:6px"><span class="meter" style="width:70px;--w:${Math.abs(d) / gapMax * 100}%;--c:${d > 0 ? "var(--bad)" : "var(--good)"}"></span>${sgn(d, 0)}</span>`}</td>
        <td class="hide-sm">${esc(P[r.cap]?.name || "–")}</td><td class="r hide-sm">${r.me ? "–" : `${ov}/11`}</td></tr>`; }).join("")}</tbody></table></div>
      <p class="note">Gap = their total minus yours (red = ahead of you). XI overlap = starters they share with your XI.</p></section>
    <section class="p c4"><div class="ph"><h2>Their players, not yours</h2><span class="m">owned by n of ${rivalsOnly.length} rivals shown</span></div>
      <table class="t"><tbody>${diffs.map(([id, n]) => `<tr><td><div class="pl"><img src="${X.badge(P[id].team)}" alt="">${esc(P[id].name)}</div></td><td><span class="meter" style="--w:${n / rivalsOnly.length * 100}%"></span></td><td class="r">${n}</td><td class="r">${num(P[id].xp1)} <small class="note">xP</small></td></tr>`).join("")}</tbody></table>
      <p class="note">If they haul and you don't own them, you drop. Sorted by how many rivals own them.</p></section>`;
  }

  function model(tab) {
    const A = S.accuracy, W = A.weeks;
    if (tab === "health") {
      const H = S.health;
      return `<section class="p"><div style="display:flex;gap:8px"><a class="tag" href="#model">Model</a><a class="tag y" href="#model/health">Data health</a></div></section>
      <section class="p c8"><div class="ph"><h2>Sources · freshness</h2><span class="m">${H.ok ? "All publish checks passed" : "Publish blocked"}</span></div>
        <table class="t"><thead><tr><th>Source</th><th>Status</th><th>Age</th><th>Updated</th><th class="hide-sm">Details</th></tr></thead><tbody>${H.sources.filter(r => r[1]).map(([k, b, d]) => { const days = (X.NOW - new Date(b)) / 864e5;
          return `<tr><td><b>${esc(X.srcName(k))}</b></td><td>${days > 3 ? '<span class="tag w">Behind</span>' : '<span class="tag g">OK</span>'}</td><td><span class="meter" style="--w:${Math.min(100, days / 20 * 100)}%;--c:${days > 3 ? "var(--warn)" : "var(--accent-text)"}"></span></td><td>${X.ago(b)}</td><td class="hide-sm" style="white-space:normal"><small class="note">${Object.entries(d).map(([a, v]) => `${v} ${a}`).join(" · ")}</small></td></tr>`; }).join("")}</tbody></table>
        <p class="note">Bar = age, full at 20 days. Status is column 2 and details wrap, so nothing hides off-screen.</p></section>
      <section class="p c4"><div class="ph"><h2>Warnings</h2><span class="m">${H.warnings.length}</span></div>${H.warnings.map(w => `<p style="padding:8px 0;border-bottom:1px solid var(--rule)"><span class="tag w">Warn</span> ${esc(w)}</p>`).join("")}</section>`;
    }
    const cw = 300, ch = 240, cp = 34, sc = v => cp + v / 10 * (cw - cp - 10), scy = v => ch - cp - v / 10 * (ch - cp - 10);
    return `<section class="p"><div style="display:flex;gap:8px"><a class="tag y" href="#model">Model</a><a class="tag" href="#model/health">Data health</a></div></section>
      <section class="p c8"><div class="ph"><h2>Accuracy by gameweek</h2><span class="m">correlation with actual points · higher is better</span></div>
        ${lineChart({ xs: W.map(w => "GW" + w.gw), series: [{ name: "FPL LAB " + num(A.corr, 2), vals: W.map(w => w.corr), c: "var(--accent-text)" }], yMin: 0.3, yMax: 0.55, yTicks: [0.3, 0.4, 0.5], yFmt: v => v.toFixed(1), label: "Correlation by gameweek", h: 220 })}
        <p class="note">Season to date: correlation ${num(A.corr, 2)} vs FPL's own ${num(A.base_corr, 2)}; average miss ${num(A.mae, 2)} pts per player over ${rank(A.n)} predictions.</p></section>
      <section class="p c4"><div class="ph"><h2>Calibration</h2><span class="m">avg actual vs avg projected</span></div>
        <svg class="ch" viewBox="0 0 ${cw} ${ch}" role="img" aria-label="Calibration: projected vs actual by band">${[0, 2, 4, 6, 8, 10].map(v => `<line class="g" x1="${cp}" x2="${cw - 10}" y1="${scy(v)}" y2="${scy(v)}"/><text x="${cp - 6}" y="${scy(v) + 4}" text-anchor="end">${v}</text><text x="${sc(v)}" y="${ch - cp + 16}" text-anchor="middle">${v}</text>`).join("")}
          <line x1="${sc(0)}" y1="${scy(0)}" x2="${sc(10)}" y2="${scy(10)}" stroke="var(--faint)" stroke-dasharray="4 4"/>
          ${A.buckets.map(([, n, pr, ac]) => `<circle cx="${sc(pr)}" cy="${scy(ac)}" r="${Math.max(3, Math.sqrt(n) / 3)}" fill="rgb(var(--heat) / .35)" stroke="var(--accent-text)"/>`).join("")}
          <text x="${cw - 12}" y="${scy(10) + 28}" text-anchor="end">perfect</text><text x="${(cw + cp) / 2}" y="${ch - 2}" text-anchor="middle">projected</text></svg>
        <p class="note">Circle size = players in the band. The top bands sit above the line: big hauls are under-projected.</p></section>
      <section class="p c12"><div class="ph"><h2>Top-30 projected players</h2><span class="m">their average projected vs actual points, each GW</span></div>
        <table class="t"><thead><tr><th>Gameweek</th>${W.map(w => `<th class="c">GW${w.gw}</th>`).join("")}</tr></thead><tbody>
        <tr><td>Projected</td>${W.map(w => `<td class="c">${num(w.top_pred, 2)}</td>`).join("")}</tr><tr><td>Actual</td>${W.map(w => `<td class="c ${w.top_act >= w.top_pred ? "up" : "dn"}"><b>${num(w.top_act, 2)}</b></td>`).join("")}</tr>
        <tr><td>MAE (all)</td>${W.map(w => `<td class="c">${num(w.mae, 2)}</td>`).join("")}</tr></tbody></table></section>`;
  }

  function render() {
    const { view, arg } = X.route(); shell(view);
    const V = { home, planner, players, fixtures, rivals, model };
    $("#app").innerHTML = V[view] ? V[view](arg) : `<section class="p"><div class="ph"><h2>Not in this prototype</h2></div><p class="note">This screen would take B's rules: hairline panels, tabular figures, one h1.</p></section>`;
    // every table scrolls inside its own panel, never the page
    document.querySelectorAll("#app table.t").forEach(t => { if (!t.closest(".scroll")) { const d = document.createElement("div"); d.className = "scroll"; t.replaceWith(d); d.append(t); } });
    X.fadeScrollers("#app .scroll");
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-pos],[data-h]"); if (!b) return;
    if (b.dataset.pos) st.pos = b.dataset.pos; if (b.dataset.h) st.h = +b.dataset.h; render();
  });
  addEventListener("hashchange", render);
  render();
})();
