// C · Modern & Interactive (round 2). Prototype only: static sample data, no network, no writes.
// Working interactions: decision steps, captain choice → pitch + projected total, GW scrubber, strategy switch, command
// palette ("/" or ⌘K), compare tray, tabbed player sheet, fixture window re-sort (FLIP), rivals race, tappable chart.
(function () {
  const X = window.PROTO; X.theme();
  const { S, P, G, icon, esc, money, num, rank, pct, sgn } = X;
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const q = new URLSearchParams(location.search);
  const byName = n => S.players.find(p => p.name === n)?.id;
  const st = { step: "captain", done: new Set(), cap: S.lineup.captain, strat: "balanced", gw: G, pos: "ALL", cmp: new Set(), ptab: "outlook",
    fxN: 5, fxMine: false, rival: null, mgw: null, pstrat: "balanced", pnode: null, palette: q.get("state") === "palette", psel: 0, pq: "" };
  if (q.get("state") === "compare") [byName("Haaland"), byName("N.Jackson"), byName("Isak")].filter(Boolean).forEach(id => st.cmp.add(id));
  const cd = X.countdown(), weekMs = 7 * 864e5, left = new Date(S.meta.deadline) - X.NOW;
  const ringP = Math.max(0.04, Math.min(1, left / weekMs));
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");
  const thumbs = {};

  const seg = (key, opts, cur, attr) => `<div class="segm" data-seg="${key}" role="group">${opts.map(([v, l]) => `<button ${attr}="${v}" aria-pressed="${String(v) === String(cur)}">${l}</button>`).join("")}<span class="thumb" aria-hidden="true"></span></div>`;
  function placeThumbs() {   // slide from the last known position to the new one (transform only, interruptible)
    $$(".segm").forEach(sg => { const b = sg.querySelector('[aria-pressed="true"]'), t = sg.querySelector(".thumb"); if (!b || !t) return;
      const k = sg.dataset.seg, nx = b.offsetLeft - 4, nw = b.offsetWidth, prev = thumbs[k];
      if (prev && !reduce) { t.style.transition = "none"; t.style.setProperty("--tx", prev.x + "px"); t.style.setProperty("--tw", prev.w + "px"); t.offsetWidth; t.style.transition = ""; }
      t.style.setProperty("--tx", nx + "px"); t.style.setProperty("--tw", nw + "px"); thumbs[k] = { x: nx, w: nw }; });
  }

  function shell(view) {
    const titles = { home: ["This week", `${S.manager.team} · ${X.deadlineText()}`], planner: ["Planner", "Pick a strategy, then scrub through its weeks."], players: ["Players", "Tick up to three to compare them side by side."],
      fixtures: ["Fixtures", "Choose a window; clubs re-sort by the easiest run."], rivals: ["Rivals", "Tap a manager to see where your teams differ."], model: ["Model", "How close the projections have been, and how fresh today's data is."] };
    const [t, sub] = titles[view] || ["Not in this prototype", "This screen keeps its current design."];
    $("#sample").innerHTML = `<b>Sample data</b> <span>Snapshot 18 Nov 2026, not live</span><span class="long">· mini-league managers anonymised · Prototype C · Modern &amp; Interactive</span>`;
    $("#dcard").innerHTML = `<span class="ring" style="--p:${ringP}"><span>${cd.d}d</span></span><span><b>GW${G} deadline in ${cd.text}</b><small>${X.deadlineText()}</small></span>`;
    $("#sidenav").innerHTML = X.NAV.map(([g, items]) => `<div class="grp">${g}</div>` + items.map(([k, l, ic]) => `<a class="nl" href="#${k}" ${k === view ? 'aria-current="page"' : ""}>${icon(ic)}${l}</a>`).join("")).join("");
    const M = S.manager;
    $("#top").innerHTML = `<div><h1>${t}</h1><p>${esc(sub)}</p></div><span class="sp"></span>
      <div class="chipstat"><span>Rank <b>${rank(M.rank)}</b> <span style="color:var(--good);padding:0;box-shadow:none;background:none">▲${X.short(S.history[S.history.length - 2].rank - M.rank)}</span></span><span><b>${M.points}</b> pts</span><span><b>${money(M.bank)}</b> bank</span><span><b>${M.free_transfers}</b> FT</span></div>
      <span class="ringsm mob"><span class="ring" style="--p:${ringP}"><span>${cd.d}d</span></span><span>${cd.text}<br><span class="note" style="font-size:11px">GW${G}</span></span></span>
      <button class="btn mob" data-palette aria-label="Search" style="width:40px;padding:0">${icon("search")}</button>`;
    $("#dock").innerHTML = [["home", "Home", "home"], ["planner", "Plan", "planner"], ["rivals", "Rivals", "rivals"], ["players", "Players", "players"], ["model", "More", "more"]]
      .map(([k, l, ic]) => `<a href="#${k}" ${k === view || (k === "model" && view === "fixtures") ? 'aria-current="page"' : ""}>${icon(ic)}${l}</a>`).join("");
  }

  // ---------- home ----------
  const capXI = () => S.lineup.xp_best - (P[S.lineup.captain].xp1 || 0) + (P[st.cap].xp1 || 0);
  function pitchHTML() {
    const sq = X.planSquad(st.strat, st.gw), useCap = st.gw === G;
    const card = p => { const cap = useCap ? p.id === st.cap : p.cap, f = X.fx(p.team, st.gw)[0];
      return `<button class="pc press ${cap ? "is-cap" : ""}" data-open="${p.id}" aria-label="${esc(p.name)} ${num(X.xp(p.id, st.gw))} xP">${cap ? '<span class="arm">C</span>' : !useCap && p.vice ? '<span class="arm v">V</span>' : ""}
        <img src="${X.badge(p.team)}" alt=""><div class="nm">${esc(p.name)}</div><div class="xp">${num(X.xp(p.id, st.gw) * (cap ? 2 : 1))}<small>${cap ? "×2" : "xP"}</small></div><div class="fx">${f ? (f.home ? f.opp : f.opp.toLowerCase()) : "Blank"}</div></button>`; };
    return `<div class="pitch" id="pitch">${sq.lines.map(l => `<div class="pline">${l.map(card).join("")}</div>`).join("")}<div class="bench">${sq.bench.map(card).join("")}</div></div>`;
  }
  const weekXP = () => { const w = S.plans[st.strat].weeks.find(x => x.gw === st.gw); return st.gw === G && st.strat === "balanced" ? capXI() : w.xp; };
  function home() {
    const caps = X.captains(), strats = X.strategies(), bal = strats[0], nxt = bal.moves[0];
    const steps = [["transfers", "1 · Transfers", "Roll"], ["captain", "2 · Captain", P[st.cap].name], ["lineup", "3 · Lineup", "Best XI"]];
    const delta = capXI() - S.lineup.xp_best;
    const body = {
      transfers: `<p style="font-size:16px;font-weight:650">Roll the free transfer: start GW${G + 1} with ${S.manager.free_transfers + 1}.</p>
        <p class="note" style="margin-top:4px">The Balanced plan's first moves are in GW${nxt.gw}: ${nxt.pairs.map(([o, i]) => `${esc(o.name)} → ${esc(i.name)}`).join(", ")}.</p>
        <div class="row" style="margin-top:12px"><button class="btn pri press" data-confirm="transfers">${icon("check")}Roll this week</button><a class="btn press" href="#planner">See the plan</a></div>`,
      captain: `<div class="capgrid" role="radiogroup" aria-label="Captain">${caps.slice(0, 4).map(c => `<button class="capopt press" role="radio" aria-checked="${c.id === st.cap}" data-cap="${c.id}"><div class="n"><img src="${X.badge(c.team)}" alt="">${esc(c.name)}</div>
          <div class="v">${num(c.cxp)}<small>captain xP</small></div><div class="p10" style="--w:${(c.dist?.[0] || 0) / .25 * 100}%"></div><small class="note">${pct(c.dist?.[0])} chance of 10+</small></button>`).join("")}</div>
        <div class="impact"><span class="note">XI with ${esc(P[st.cap].name)} (C)</span><b>${num(capXI())} xP</b><span class="delta ${delta < 0 ? "dn" : ""}">${Math.abs(delta) < 0.05 ? "the model's pick" : sgn(delta) + " vs the model's pick"}</span>
          <button class="btn pri press" style="margin-left:auto" data-confirm="captain">${icon("check")}Confirm</button></div>`,
      lineup: `<p style="font-size:16px;font-weight:650">Start the XI on the pitch.</p><p class="note">Bench order: ${S.lineup.bench.slice(1).map(id => esc(P[id].name)).join(", ")}. No starter is flagged.</p>
        <div class="row" style="margin-top:12px"><button class="btn pri press" data-confirm="lineup">${icon("check")}Looks right</button></div>`,
    }[st.step];
    return `<section class="hero"><span class="ring" style="--p:${ringP}"><span>${cd.text.split(" ")[0]}<small>${cd.text.split(" ")[1] || ""} LEFT</small></span></span>
        <div><div class="k">GW${G} · ${st.done.size} of 3 decisions confirmed</div><h2>No moves. <em>${esc(P[st.cap].name)}</em> captain.</h2><p>Straight from the Balanced plan. Work through the three steps; nothing is sent to FPL.</p>
          <div class="progress">${steps.map(([k]) => `<i class="${st.done.has(k) ? "on" : ""}"></i>`).join("")}</div></div>
        <div class="acts row"><button class="btn press" data-palette style="background:rgb(0 0 0 / 25%);color:#fff;border-color:rgb(255 255 255 / 22%)">${icon("search")}Find a player</button></div></section>
      <div class="cols">
        <section class="panel"><h2>GW${st.gw} · ${esc(strats.find(s => s.key === st.strat).name)} <span class="m" id="wxp">${num(weekXP())} xP</span></h2>
          ${seg("hstrat", strats.map(s => [s.key, s.name]), st.strat, "data-strat")}
          <div class="scrub" style="margin-top:12px"><label for="gwr" class="note">Gameweek</label><input id="gwr" type="range" min="${G}" max="${G + 4}" step="1" value="${st.gw}" aria-valuetext="GW${st.gw}"><output id="gwo">GW${st.gw} · ${S.plans[st.strat].weeks.find(w => w.gw === st.gw).in.length || "no"} moves</output></div>
          <div class="ticks" aria-hidden="true">${S.gws.map(g => `<span>${g}</span>`).join("")}</div>
          <div id="pitchwrap">${pitchHTML()}</div>
          <p class="note" style="margin-top:10px">xP for the gameweek shown; the captain's number is doubled. Tap a player for the full outlook.</p></section>
        <section class="panel"><h2>Your decisions</h2>
          <div class="steps">${steps.map(([k, l, v]) => `<button class="step press ${st.done.has(k) ? "done" : ""}" data-step="${k}" aria-pressed="${k === st.step}"><small>${l}</small><b>${esc(v)}</b></button>`).join("")}</div>
          ${body}
          ${st.step === "captain" ? `<p class="note" style="margin-top:12px">Close call: ${esc(caps[0].name)} leads ${esc(caps[1].name)} by ${num(caps[0].cxp - caps[1].cxp)} captain xP. Picking another updates the pitch and the total.</p>` : ""}</section>
      </div>`;
  }

  // ---------- planner ----------
  function planner() {
    const strats = X.strategies(), cur = strats.find(s => s.key === st.pstrat);
    const firstMv = cur.weeks.find(w => w.in.length)?.gw ?? G; const node = st.pnode ?? firstMv;
    const mv = cur.moves.find(m => m.gw === node), w = cur.weeks.find(x => x.gw === node);
    return `<div class="stratcards" role="radiogroup" aria-label="Strategy">${strats.map(s => `<button class="sc press" role="radio" aria-checked="${s.key === st.pstrat}" data-pstrat="${s.key}">
        <div class="row"><b style="font-size:16px">${s.name}</b>${s.key === "balanced" ? '<span class="pill g">Recommended</span>' : ""}</div><div class="gain">${sgn(s.gain)}<small>xP vs no moves · 5 GWs</small></div><p class="note">${esc(s.blurb)}</p></button>`).join("")}</div>
      <section class="panel"><h2>${esc(cur.name)} · week by week <span class="m">${seg("hz", [[3, "3 GWs"], [5, "5 GWs"], [6, "6 GWs"]], 5, "data-hz")}</span></h2>
        <div class="tl" role="group" aria-label="Gameweeks">${cur.weeks.map(x => `<button class="node ${x.in.length ? "mv" : ""}" data-node="${x.gw}" aria-pressed="${x.gw === node}"><span class="dot">${x.in.length || "–"}</span><b>GW${x.gw}</b><small>${num(x.xp)} xP</small></button>`).join("")}</div>
        <div style="margin-top:18px">${mv ? mv.pairs.map(([o, i]) => `<div class="mvcard"><span class="o">${esc(o.name)} <span class="note">${money(o.price)}</span></span>${icon("arrow")}<span class="i">${esc(i.name)} <span class="note">${money(i.price)}</span></span></div>`).join("") : `<div class="mvcard" style="grid-template-columns:1fr"><span>GW${node}: no moves. The free transfer is rolled (${w.ft} available).</span></div>`}</div>
        <p class="note" style="margin-top:10px">Numbers under each week are that week's XI xP with captain ×2. Dots show transfers made that week.</p></section>`;
  }

  // ---------- players ----------
  function players() {
    const list = X.players({ pos: st.pos, limit: 18 }), mx = Math.max(...list.flatMap(p => S.gws.map(g => p.xp[g] || 0)));
    return `<div class="chips" role="group" aria-label="Position">${["ALL", "GKP", "DEF", "MID", "FWD"].map(k => `<button class="chip press" data-pos="${k}" aria-pressed="${k === st.pos}">${k === "ALL" ? "All players" : X.POS_NAME[k] + "s"}</button>`).join("")}
        <button class="chip press">${icon("filter")} Under £8.0m</button><button class="chip press">Nailed only</button></div>
      <section class="panel"><div class="lrow lhead" style="padding-top:0"><span></span><span>Player</span><span class="c">£m</span><span class="c hs">Own %</span><span class="c">xP next</span><span class="hs" style="text-align:right">xP, next 5 GWs</span></div>
        ${list.map(p => `<div class="lrow ${X.inSquad(p.id) ? "own" : ""} ${st.cmp.has(p.id) ? "sel" : ""}"><button class="tick press" role="checkbox" aria-checked="${st.cmp.has(p.id)}" data-cmp="${p.id}" aria-label="Compare ${esc(p.name)}">${icon("check")}</button>
          <button class="who" data-open="${p.id}" style="border:0;background:none;padding:0;text-align:left"><img src="${X.badge(p.team)}" alt=""><div><b>${esc(p.name)}</b><small>${X.teamShort(p.team)} · ${p.pos}${X.inSquad(p.id) ? " · in your squad" : ""}</small></div></button>
          <span class="c">${num(p.price)}</span><span class="c hs">${num(p.own)}</span><span class="c"><b>${num(p.xp1)}</b></span>
          <span class="hs x5"><span class="spark" style="width:64px" aria-hidden="true">${S.gws.map(g => `<i style="--h:${((p.xp[g] || 0) / mx * 100).toFixed(0)}%;--a:${Math.round((p.xp[g] || 0) / mx * 85)}%"></i>`).join("")}</span><b>${num(p.xp5)}</b></span></div>`).join("")}
        <p class="note" style="margin-top:10px">Bars: xP in each of GW${G}–${G + 4}. Yellow wash = in your squad.</p></section>`;
  }
  function tray() {
    const el = $("#tray"), ids = [...st.cmp];
    if (X.route().view !== "players" || ids.length < 2) { el.dataset.hidden = ""; setTimeout(() => { if (el.dataset.hidden != null) el.hidden = true; }, 330); return; }
    el.hidden = false; requestAnimationFrame(() => delete el.dataset.hidden);
    const ps = ids.map(i => P[i]);
    const rows = [["xP next GW", p => p.xp1, 1], ["xP next 5", p => p.xp5, 1], ["Chance of 10+", p => p.dist?.[0] || 0, 1, pct], ["Expected mins", p => p.xmin, 1, v => v], ["Price", p => p.price, -1, money], ["Owned", p => p.own, 0, v => num(v) + "%"]];
    el.innerHTML = `<div class="row" style="margin-bottom:10px"><b>Compare ${ps.length}</b><span class="note">best in each row is green</span><button class="btn press" data-clear style="margin-left:auto;height:32px">Clear</button></div>
      <div class="cmpgrid"><span></span>${ps.map(p => `<span class="h"><img src="${X.badge(p.team)}" alt="">${esc(p.name)}</span>`).join("")}
      ${rows.map(([l, f, dir, fmt = v => num(v)]) => { const vs = ps.map(f), mx = Math.max(...vs), best = dir > 0 ? mx : dir < 0 ? Math.min(...vs) : null;
        return `<span class="note">${l}</span>${ps.map((p, i) => `<span class="cmpbar ${vs[i] === best ? "best" : ""}"><i style="--w:${(vs[i] / mx * 100).toFixed(0)}%;--c:${vs[i] === best ? "var(--accent-text)" : "var(--faint)"}"></i><b>${fmt(vs[i])}</b></span>`).join("")}`; }).join("")}</div>`;
  }

  // ---------- player sheet ----------
  function sheetHTML(id) {
    const p = P[id], o = X.outcomes(p), parts = X.breakdown(p), top = 15, at = v => `${Math.min(100, v / top * 100).toFixed(1)}%`;
    let tab = "";
    if (st.ptab === "outlook") {
      let run = 0; const scale = v => `${(v / Math.max(p.xp1, 0.1) * 100).toFixed(1)}%`;
      tab = `${o ? `<h3 style="font-size:15px;margin:4px 0 0">GW${G} likely range</h3><div class="range" role="img" aria-label="Likely ${o.lo} to ${o.hi} points"><span class="band" style="left:${at(o.lo)};width:calc(${at(o.hi)} - ${at(o.lo)})"></span><span class="mark" style="left:${at(p.xp1)}"></span><b class="mlab" style="left:${at(p.xp1)}">${num(p.xp1)} xP</b>${[0, 5, 10, 15].map(t => `<span class="tk" style="left:${at(t)}">${t}</span>`).join("")}</div>
        <p class="note">8 in 10 of the model's simulated outcomes land between <b>${o.lo}</b> and <b>${o.hi}</b> points.</p>
        <div class="ch3">${[["10+ pts", o.p10], ["6+ pts", o.p6], ["2 or fewer", o.p2]].map(([l, v]) => `<div><span>${l}</span><b>${pct(v)}</b></div>`).join("")}</div>` : ""}
        <h3 style="font-size:15px;margin:18px 0 4px">How ${num(p.xp1)} xP adds up</h3>
        ${parts ? `<div class="wf">${parts.map(x => { const l = x.v >= 0 ? run : run + x.v; run += x.v; return `<div class="${x.v < 0 ? "neg" : ""}"><span>${x.label}</span><i style="--l:${scale(Math.max(0, l))};--w:${scale(Math.abs(x.v))}"></i><b>${sgn(x.v, 2)}</b></div>`; }).join("")}
          <div class="tot"><span><b style="text-align:left">Total</b></span><i style="--w:100%"></i><b>${num(p.xp1, 2)}</b></div></div>` : '<p class="note">No breakdown in this snapshot.</p>'}`;
    } else if (st.ptab === "form") {
      const pts = p.detail?.pts || [], mx = Math.max(...pts, 1);
      tab = `<p class="note">Actual FPL points, GW1–${pts.length}. Season: ${p.pts} pts, ${p.goals} goals, ${p.assists} assists.</p><div style="display:flex;gap:6px;align-items:flex-end;height:150px;margin-top:14px">${pts.map((v, i) => `<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;justify-content:flex-end;height:100%"><b style="font-size:12px">${v}</b><i style="width:100%;border-radius:6px 6px 2px 2px;background:var(--accent-text);height:${Math.max(2, v / mx * 110)}px;opacity:${i >= pts.length - 4 ? 1 : .45}"></i><small class="note">${i + 1}</small></div>`).join("")}</div><p class="note" style="margin-top:8px">Brighter bars = the last 4 gameweeks.</p>`;
    } else {
      tab = `<div style="display:grid;gap:8px">${S.gws.map(g => { const f = X.fx(p.team, g); return `<div style="display:grid;grid-template-columns:56px 1fr 70px;gap:10px;align-items:center"><b>GW${g}</b><span class="tile f${f[0]?.fdr ?? 0}" style="justify-items:start;padding:0 12px;place-items:center start">${X.fxLabel(p.team, g)} · FDR ${f[0]?.fdr ?? "–"}</span><b style="text-align:right">${num(p.xp[g])} <span class="note">xP</span></b></div>`; }).join("")}</div>`;
    }
    return `<div class="grab" aria-hidden="true"></div>
      <div class="shh"><span class="crest"><img src="${X.badge(p.team)}" alt=""></span><div><div class="note">${esc(X.T[p.team].name)} · ${X.POS_NAME[p.pos]} · ${money(p.price)}</div><h2 id="shTitle">${esc(p.full)}</h2>
        <div class="row" style="gap:6px;margin-top:4px">${X.inSquad(id) ? '<span class="pill y">In your squad</span>' : ""}<span class="pill g">Nailed ${p.nailed}</span>${p.sp.includes("pen") ? '<span class="pill b">Pens</span>' : ""}${X.statusText(p) ? `<span class="pill w">${esc(X.statusText(p))}</span>` : ""}</div></div>
        <button class="btn x press" data-close aria-label="Close">${icon("close")}</button></div>
      <div class="big4"><div><span>xP GW${G}</span><b style="color:var(--hi-text)">${num(p.xp1)}</b></div><div><span>xP next 5</span><b>${num(p.xp5)}</b></div><div><span>Expected minutes</span><b>${p.xmin}</b></div><div><span>Form</span><b>${num(p.form)}</b></div></div>
      ${seg("ptab", [["outlook", "Outlook"], ["form", "Form"], ["fix", "Fixtures"]], st.ptab, "data-ptab")}
      <div style="margin-top:14px">${tab}</div>`;
  }

  // ---------- fixtures (window re-sort with FLIP) ----------
  function fixtures() {
    const gws = S.gws.slice(0, st.fxN);
    const rows = X.fixtureGrid().map(r => { const v = r.cells.filter(c => gws.includes(c.gw)).flatMap(c => c.list.map(f => f.fdr)); return { ...r, w: v.reduce((a, b) => a + b, 0) / (v.length || 1) }; })
      .filter(r => !st.fxMine || r.owned).sort((a, b) => a.w - b.w);
    return `<div class="row">${seg("fxn", [[1, "Next GW"], [3, "3 GWs"], [5, "5 GWs"]], st.fxN, "data-fxn")}<button class="chip press" data-mine aria-pressed="${st.fxMine}">My clubs only</button></div>
      <section class="panel"><div class="fxrow" style="font-size:12px;color:var(--muted)"><span>Club</span><span>Avg</span>${S.gws.map(g => `<span style="text-align:center">GW${g}</span>`).join("")}</div>
        <div id="fxl">${rows.map(r => `<div class="fxrow ${r.owned ? "own" : ""}" data-k="${r.id}"><span class="t" data-s="${r.short}"><img src="../../../site/badges/${r.code}.png" alt=""><span>${esc(r.name)}</span></span><b>${num(r.w)}</b>
          ${r.cells.map(c => `<span class="tile f${c.list[0]?.fdr ?? 0} ${gws.includes(c.gw) ? "" : "out"}">${c.list.length ? c.list.map(f => f.home ? f.opp : f.opp.toLowerCase()).join("+") : "—"}</span>`).join("")}</div>`).join("")}</div>
        <p class="note" style="margin-top:10px">FPL difficulty 1 (green) to 5 (red); capitals = home. Faded tiles sit outside the window. Yellow edge = a club you own players from.</p></section>`;
  }

  // ---------- rivals ----------
  function rivals() {
    const rows = [...S.league.rows].sort((a, b) => a.rank - b.rank), me = rows.find(r => r.me);
    const sel = rows.find(r => r.rank === st.rival) || rows.filter(r => r.rank < me.rank).pop();
    const lead = rows[0].total, base = Math.min(...rows.map(r => r.total)) - 20;
    const theirs = sel.picks.filter(id => !X.inSquad(id) && P[id]), mine = S.lineup.xi.filter(id => !sel.picks.includes(id));
    return `<div class="cols"><section class="panel"><h2>${esc(S.league.name)} <span class="m">you're ${ord(me.rank)} of ${rank(S.league.size)}</span></h2>
        <div class="race">${rows.map(r => `<button class="rr press ${r.me ? "me" : ""}" data-rival="${r.rank}" aria-pressed="${r === sel}"><span class="rk">${r.rank}</span><span><b style="text-align:left;display:block">${esc(r.name)}</b><small class="note tm">${esc(r.team)}</small></span>
          <span class="bar"><i style="--w:${((r.total - base) / (lead - base) * 100).toFixed(1)}%"></i></span><b>${r.total}</b></button>`).join("")}</div>
        <p class="note" style="margin-top:8px">Bars start ${base} points in so the gaps are visible. Yellow = you.</p></section>
      <section class="panel"><h2>${sel.me ? "You" : esc(sel.name)} <span class="m">${sel.me ? "" : (() => { const d = sel.total - me.total; return d === 0 ? "level with you" : `${Math.abs(d)} pt${Math.abs(d) === 1 ? "" : "s"} ${d > 0 ? "ahead of" : "behind"} you`; })()}</span></h2>
        ${sel.me ? '<p class="note">Pick a rival on the left.</p>' : `<div class="ch3" style="margin-top:0"><div><span>GW${S.meta.cur_gw}</span><b>${sel.gw}</b></div><div><span>Captain</span><b style="font-size:19px">${esc(P[sel.cap]?.name || "–")}</b></div><div><span>Shared starters</span><b>${sel.picks.filter(id => S.lineup.xi.includes(id)).length}/11</b></div></div>
        <h3 style="font-size:14.5px;margin:16px 0 6px">They have, you don't</h3><div class="row" style="gap:6px">${theirs.slice(0, 6).map(id => `<span class="pill">${esc(P[id].name)} · ${num(P[id].xp1)}</span>`).join("") || '<span class="note">Nobody</span>'}</div>
        <h3 style="font-size:14.5px;margin:14px 0 6px">You have, they don't</h3><div class="row" style="gap:6px">${mine.slice(0, 6).map(id => `<span class="pill g">${esc(P[id].name)} · ${num(P[id].xp1)}</span>`).join("")}</div>
        <p class="note" style="margin-top:10px">Numbers are GW${G} xP. These are the players that decide the gap this week.</p>`}</section></div>`;
  }

  // ---------- model ----------
  function model(tab) {
    const A = S.accuracy, W = A.weeks, sel = W.find(w => w.gw === st.mgw) || W[W.length - 1];
    const head = seg("mtab", [["model", "Model"], ["health", "Data health"]], tab === "health" ? "health" : "model", "data-mtab");
    if (tab === "health") {
      const H = S.health;
      return `${head}<div class="lights">${H.sources.filter(r => r[1]).map(([k, b]) => { const old = (X.NOW - new Date(b)) / 864e5 > 3; return `<div class="light ${old ? "w" : ""}"><i></i><span><b>${esc(X.srcName(k))}</b><small>${old ? "Behind · " : ""}updated ${X.ago(b)}</small></span></div>`; }).join("")}</div>
        <section class="panel"><h2>Warnings <span class="m">${H.warnings.length} · publish ${H.ok ? "allowed" : "blocked"}</span></h2>${H.warnings.map(w => `<p style="padding:10px 0;border-top:1px solid var(--line)"><span class="pill w">Warn</span> ${esc(w)}</p>`).join("")}</section>`;
    }
    const w = X.PHONE() ? 380 : 560, h = X.PHONE() ? 210 : 250, pl = 40, pr = 20, pt = 16, pb = 30, xs = i => pl + i * (w - pl - pr) / (W.length - 1), ys = v => pt + (1 - (v - .3) / .25) * (h - pt - pb);
    return `${head}<div class="cols"><section class="panel"><h2>Correlation with actual points <span class="m">tap a week</span></h2>
        <svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Correlation by gameweek">${[.3, .4, .5].map(v => `<line class="g" x1="${pl}" x2="${w - pr}" y1="${ys(v)}" y2="${ys(v)}"/><text x="${pl - 8}" y="${ys(v) + 4}" text-anchor="end">${v.toFixed(1)}</text>`).join("")}
          <path d="${W.map((d, i) => `${i ? "L" : "M"}${xs(i)},${ys(d.corr)}`).join("")} L${xs(W.length - 1)},${h - pb} L${xs(0)},${h - pb}Z" fill="var(--accent-soft)"/>
          <path d="${W.map((d, i) => `${i ? "L" : "M"}${xs(i)},${ys(d.corr)}`).join("")}" fill="none" stroke="var(--accent-text)" stroke-width="2.5"/>
          ${W.map((d, i) => `<line x1="${xs(i)}" x2="${xs(i)}" y1="${pt}" y2="${h - pb}" stroke="${d === sel ? "var(--line-2)" : "transparent"}"/><circle cx="${xs(i)}" cy="${ys(d.corr)}" r="${d === sel ? 7 : 4}" fill="${d === sel ? "var(--hi)" : "var(--accent-text)"}"/>
            <text x="${xs(i)}" y="${h - 8}" text-anchor="middle" style="${d === sel ? "fill:var(--fg);font-weight:700" : ""}">GW${d.gw}</text><rect class="hit" data-mgw="${d.gw}" x="${xs(i) - 30}" y="0" width="60" height="${h}"/>`).join("")}</svg>
        <div class="tip"><span>GW${sel.gw}</span><span>correlation <b>${num(sel.corr, 2)}</b></span><span>avg miss <b>${num(sel.mae, 2)}</b></span><span>top-30 projected <b>${num(sel.top_pred, 1)}</b> → actual <b>${num(sel.top_act, 1)}</b></span></div></section>
      <section class="panel"><h2>Season so far</h2><div class="ch3" style="grid-template-columns:1fr 1fr;margin:0"><div><span>FPL LAB correlation</span><b style="color:var(--accent-text)">${num(A.corr, 2)}</b></div><div><span>FPL's own</span><b>${num(A.base_corr, 2)}</b></div><div><span>Average miss</span><b>${num(A.mae, 2)}</b></div><div><span>Predictions</span><b>${rank(A.n)}</b></div></div>
        <p class="note" style="margin-top:10px">Higher correlation is better; the average miss is in FPL points per player per gameweek.</p></section></div>`;
  }

  // ---------- palette ----------
  function palette() {
    const el = $("#palette"), scr = $("#scrim");
    if (!st.palette) { el.hidden = true; if ($("#sheet").hidden) scr.hidden = true; return; }
    const qv = st.pq.toLowerCase();
    const secs = X.NAV.flatMap(([, it]) => it).filter(([, l]) => !qv || l.toLowerCase().includes(qv)).slice(0, qv ? 4 : 3);
    const ps = S.players.filter(p => !qv || p.name.toLowerCase().includes(qv) || X.T[p.team].name.toLowerCase().includes(qv)).sort((a, b) => b.xp5 - a.xp5).slice(0, 6);
    const items = [...secs.map(([k, l, ic]) => ({ href: `#${k}`, html: `${icon(ic)}${l}<small>Section</small>` })), ...ps.map(p => ({ open: p.id, html: `<img src="${X.badge(p.team)}" alt="">${esc(p.name)} <span class="note">${X.teamShort(p.team)} · ${p.pos}</span><small>${num(p.xp1)} xP next GW</small>` }))];
    st.psel = Math.min(st.psel, items.length - 1);
    el.hidden = false; scr.hidden = false;
    el.innerHTML = `<input id="pq" placeholder="Search players, clubs and sections" value="${esc(st.pq)}" aria-label="Search" autocomplete="off"><ul role="listbox">${items.map((it, i) => `<li role="option" aria-selected="${i === st.psel}" ${it.href ? `data-href="${it.href}"` : `data-open="${it.open}"`}>${it.html}</li>`).join("") || '<li>No match</li>'}</ul>`;
    el._items = items;
    const inp = $("#pq"); inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length);
    // no open/close animation: the palette is a keyboard surface used many times a day (emil-design-eng)
  }

  function openSheet(id) {
    const sh = $("#sheet"), first = sh.hidden; sh.dataset.id = id; sh.innerHTML = sheetHTML(id); sh.hidden = false; $("#scrim").hidden = false; placeThumbs();
    if (first && !reduce) { const phone = matchMedia("(max-width: 899px)").matches;
      sh.animate(phone ? [{ transform: "translateY(100%)" }, { transform: "translateY(0)" }] : [{ opacity: 0, transform: "translate(-50%,-50%) scale(.97)" }, { opacity: 1, transform: "translate(-50%,-50%) scale(1)" }], { duration: phone ? 380 : 220, easing: "cubic-bezier(.32,.72,0,1)" }); }
  }
  function closeAll() { $("#sheet").hidden = true; st.palette = false; $("#palette").hidden = true; $("#scrim").hidden = true; if (X.route().view === "players" && X.route().arg) location.hash = "players"; }

  function render() {
    const { view, arg } = X.route(); shell(view);
    const V = { home, planner, players, fixtures, rivals, model };
    $("#app").innerHTML = V[view] ? V[view](arg) : `<section class="panel"><h2>Not in this prototype</h2><p class="note">This screen keeps today's design; C's motion and sheet patterns would apply.</p></section>`;
    placeThumbs(); tray(); palette();
    if (view === "players" && arg) openSheet(+arg); else if (!$("#sheet").hidden && view !== "players") closeAll();
  }

  // partial updates that animate instead of re-rendering the page
  function swapPitch() {
    $("#pitchwrap").innerHTML = pitchHTML(); $("#wxp").textContent = `${num(weekXP())} xP`;
    $("#gwo").textContent = `GW${st.gw} · ${S.plans[st.strat].weeks.find(w => w.gw === st.gw).in.length || "no"} moves`;
    if (!reduce) $$("#pitch .pc").forEach((c, i) => c.animate([{ opacity: .35, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }], { duration: 200, delay: Math.min(i * 12, 120), easing: "cubic-bezier(.23,1,.32,1)", fill: "backwards" }));
  }
  function flip(fn) {   // fixtures re-sort: measure, change, animate each row from where it was
    const before = new Map($$("#fxl .fxrow").map(r => [r.dataset.k, r.getBoundingClientRect().top]));
    fn();
    if (reduce) return;
    $$("#fxl .fxrow").forEach(r => { const b = before.get(r.dataset.k); if (b == null) return; const d = b - r.getBoundingClientRect().top; if (d) r.animate([{ transform: `translateY(${d}px)` }, { transform: "none" }], { duration: 320, easing: "cubic-bezier(.77,0,.175,1)" }); });
  }

  document.addEventListener("click", e => {
    const t = e.target.closest("[data-step],[data-cap],[data-confirm],[data-strat],[data-open],[data-close],[data-pos],[data-cmp],[data-clear],[data-ptab],[data-pstrat],[data-node],[data-fxn],[data-mine],[data-rival],[data-mgw],[data-mtab],[data-palette],[data-href],[data-hz]");
    if (!t) { if (e.target.id === "scrim") closeAll(); return; }
    const d = t.dataset;
    if (d.step) { st.step = d.step; render(); }
    else if (d.cap) { st.cap = +d.cap; render(); }
    else if (d.confirm) { st.done.add(d.confirm); st.step = ["transfers", "captain", "lineup"].find(k => !st.done.has(k)) || d.confirm; render(); }
    else if (d.strat) { st.strat = d.strat; placeStrat(); }
    else if (d.open) { st.palette = false; $("#palette").hidden = true; if (X.route().view === "players") location.hash = `players/${d.open}`; else openSheet(+d.open); }
    else if (t.hasAttribute("data-close")) closeAll();
    else if (d.pos) { st.pos = d.pos; render(); }
    else if (d.cmp) { const id = +d.cmp; st.cmp.has(id) ? st.cmp.delete(id) : st.cmp.size < 3 && st.cmp.add(id); render(); }
    else if (t.hasAttribute("data-clear")) { st.cmp.clear(); render(); }
    else if (d.ptab) { st.ptab = d.ptab; openSheet(+$("#sheet").dataset.id); }
    else if (d.pstrat) { st.pstrat = d.pstrat; st.pnode = null; render(); }
    else if (d.node) { st.pnode = +d.node; render(); }
    else if (d.fxn) { st.fxN = +d.fxn; flip(render); }
    else if (t.hasAttribute("data-mine")) { st.fxMine = !st.fxMine; render(); }
    else if (d.rival) { st.rival = +d.rival; render(); }
    else if (d.mgw) { st.mgw = +d.mgw; render(); }
    else if (d.mtab) { location.hash = d.mtab === "health" ? "model/health" : "model"; }
    else if (t.hasAttribute("data-palette")) { st.palette = true; st.pq = ""; st.psel = 0; palette(); }
    else if (d.href) { st.palette = false; location.hash = d.href.slice(1); render(); }
  });
  function placeStrat() { $$('[data-seg="hstrat"] button').forEach(b => b.setAttribute("aria-pressed", String(b.dataset.strat === st.strat))); placeThumbs(); swapPitch();
    const h2 = $("#pitchwrap").closest(".panel").querySelector("h2"); h2.firstChild.textContent = `GW${st.gw} · ${X.strategies().find(s => s.key === st.strat).name} `; }
  document.addEventListener("input", e => {
    if (e.target.id === "gwr") { st.gw = +e.target.value; e.target.setAttribute("aria-valuetext", "GW" + st.gw); swapPitch(); $("#pitchwrap").closest(".panel").querySelector("h2").firstChild.textContent = `GW${st.gw} · ${X.strategies().find(s => s.key === st.strat).name} `; }
    if (e.target.id === "pq") { st.pq = e.target.value; st.psel = 0; palette(); }
  });
  document.addEventListener("keydown", e => {
    const typing = /INPUT|TEXTAREA/.test(document.activeElement?.tagName);
    if ((e.key === "/" && !typing) || (e.key === "k" && (e.metaKey || e.ctrlKey))) { e.preventDefault(); st.palette = true; st.pq = ""; st.psel = 0; palette(); return; }
    if (e.key === "Escape") closeAll();
    if (st.palette && ["ArrowDown", "ArrowUp", "Enter"].includes(e.key)) { e.preventDefault(); const items = $("#palette")._items || [];
      if (e.key === "Enter") { const it = items[st.psel]; if (it?.href) { st.palette = false; location.hash = it.href.slice(1); render(); } else if (it) { st.palette = false; $("#palette").hidden = true; openSheet(it.open); } return; }
      st.psel = (st.psel + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length; palette(); }
  });
  addEventListener("hashchange", () => { if (!X.route().arg) $("#sheet").hidden = true; render(); });
  addEventListener("resize", placeThumbs);
  render();
  if (st.palette) { st.pq = "ha"; palette(); }   // ?state=palette: show it mid-search, as a person would see it
})();
