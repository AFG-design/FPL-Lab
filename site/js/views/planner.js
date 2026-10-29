// Planner, captain planner, drafts and re-plan.
/* ---------- Planner ---------- */
function planCards() {
  const pl = D.plans || {}, rec = recommendedPlan(), base = baseScore().tot, g = D.meta.next_gw;
  let anySel = false;
  const cards = ["roll", "one", "two", "three", "best"].map(k => mk(k)).filter(k => pl[k]).map(k => {
    const mv = planMoves(pl[k]), sc = scoreMoves(mv), sel = sameMoves(mv, SB.moves);
    anySel = anySel || sel;
    const n = mv.filter(m => m.gw === g).length;
    return `<button class="opt ${sel ? "sel" : ""}" data-plan="${k}"><span>${PLAN_LABEL[k.split("_").pop()]}${k.endsWith("best") ? ` (${n} now)` : ""}${k === rec ? " · pick" : ""}</span><b class="${sc.tot - base > 0.05 ? "up" : ""}">${sgn(sc.tot - base)}</b><span>${sc.ftLeft} ${term("ft", "FT")} left after GW${PG[PG.length - 1]}</span></button>`;
  });
  if (!anySel) { const my = scoreMoves(SB.moves); cards.unshift(`<button class="opt sel" disabled><span>Your plan · edited</span><b class="${my.tot - base > 0.05 ? "up" : ""}">${sgn(my.tot - base)}</b><span>${my.ftLeft} FT left after GW${PG[PG.length - 1]}</span></button>`); }
  return `<h3>Optimiser plans · ${MODES[S.mode]}</h3>
    <p class="note" style="margin-top:0">Plans worked out on the server for your strategy, each with a different number of moves this week. Tap one to make it your plan; Undo brings yours back. Numbers are projected points over ${PG.length} GWs vs making no transfers, counting hits.</p>
    <div class="opts">${cards.join("")}</div>`;
}
const adjTotal = sc => sc.weeks.reduce((a, w) => a + w.team.xi.reduce((b, i) => b + adjXI(i, w.gw), 0) + (w.team.cap ? adjCap(w.team.cap, w.gw) : 0) - 4 * w.hits, 0);
let _sugg = { key: "", list: [] };
function transferSuggestions(g) {
  const key = `${mvKey(SB.moves)}|${g}|${S.mode}|${S.horizon}|${JSON.stringify(SB.ov)}|${JSON.stringify(SB.rules)}|${D.meta.built}`;
  if (_sugg.key === key) return _sugg.list;
  const cur = scoreMoves(SB.moves), curAdj = adjTotal(cur), sq = squadAt(g), bank = bankAt(g);
  const base = new Set(D.squad.map(s => s.id)), boughtInPlan = new Set(SB.moves.filter(m => m.gw <= g).map(m => m.in));
  const out = [];
  sq.forEach(o => {
    const po = P[o]; if (!po || SB.rules.locked.includes(o)) return;
    const budget = bank + (base.has(o) && !boughtInPlan.has(o) ? sellPrice(o) : po.price);
    const cc = clubCounts(sq.filter(i => i !== o));
    const ins = D.players.filter(p => p.pos === po.pos && !sq.includes(p.id) && p.ok !== false && !SB.rules.banned.includes(p.id)
      && p.price <= budget + 1e-9 && (cc[p.team] || 0) < 3).sort((a, b) => xpFrom(b.id, g, PG.length) - xpFrom(a.id, g, PG.length)).slice(0, 10);
    const best = [];
    ins.forEach(n => {
      let mv = SB.moves.map(m => ({ ...m }));
      const same = mv.find(m => m.gw === g && m.in === o);
      if (same) same.in = n.id; else { mv = mv.filter(m => !(m.gw >= g && m.out === o)); mv.push({ gw: g, out: o, in: n.id }); }
      mv = cleanMoves(mv);
      const sc = scoreMoves(mv);
      if (sc.weeks.some(w => w.bank < 0 || w.over.length)) return;
      const hitNow = sc.weeks.find(w => w.gw === g).hits > cur.weeks.find(w => w.gw === g).hits;
      best.push({ out: o, in: n.id, gain: sc.tot - cur.tot, adj: adjTotal(sc) - curAdj, hit: hitNow, moves: mv });
    });
    best.sort((a, b) => b.adj - a.adj);
    out.push(...best.slice(0, 2));
  });
  out.sort((a, b) => b.adj - a.adj);
  const seenIn = new Set(), list = [];
  for (const s2 of out) { if (s2.adj <= 0.05 || seenIn.has(s2.in)) continue; seenIn.add(s2.in); list.push(s2); if (list.length >= 3) break; }
  _sugg = { key, list };
  return list;
}
let _pairs = { key: "", list: [] };
function pairSuggestions(g) {
  const key = `${mvKey(SB.moves)}|${g}|${S.mode}|${S.horizon}|${JSON.stringify(SB.ov)}|${JSON.stringify(SB.rules)}|${D.meta.built}`;
  if (_pairs.key === key) return _pairs.list;
  const cur = scoreMoves(SB.moves), curAdj = adjTotal(cur), sq = squadAt(g), bank = bankAt(g);
  const base = new Set(D.squad.map(s => s.id)), bought = new Set(SB.moves.filter(m => m.gw <= g).map(m => m.in));
  const sellOf = o => (base.has(o) && !bought.has(o) ? sellPrice(o) : P[o].price);
  const H = PG.filter(x => x >= g).length;
  const xf = i => xpFrom(i, g, H);
  const outs = sq.filter(o => P[o] && !SB.rules.locked.includes(o));
  const pool = pos => D.players.filter(p => p.pos === pos && !sq.includes(p.id) && p.ok !== false && !SB.rules.banned.includes(p.id));
  // upgrades: best by projection at any price; enablers: best value among cheaper players
  const cand = {};
  outs.forEach(o => {
    const ps = pool(P[o].pos);
    const up = ps.slice().sort((a, b) => xf(b.id) - xf(a.id)).slice(0, 8);
    const down = ps.filter(p => p.price < sellOf(o) - 0.05).sort((a, b) => xf(b.id) - xf(a.id)).slice(0, 5);
    cand[o] = [...new Map([...up, ...down].map(p => [p.id, p])).values()];
  });
  const combos = [];
  for (let a = 0; a < outs.length; a++) for (let b = a + 1; b < outs.length; b++) {
    const o1 = outs[a], o2 = outs[b], money0 = bank + sellOf(o1) + sellOf(o2);
    for (const n1 of cand[o1]) for (const n2 of cand[o2]) {
      if (n1.id === n2.id || n1.price + n2.price > money0 + 1e-9) continue;
      const solo1 = n1.price <= bank + sellOf(o1) + 1e-9, solo2 = n2.price <= bank + sellOf(o2) + 1e-9;
      if (solo1 && solo2) continue;  // each move works alone: singles already cover it
      const est = xf(n1.id) - xf(o1) + xf(n2.id) - xf(o2);
      if (est <= 0.5) continue;
      combos.push({ o1, o2, n1: n1.id, n2: n2.id, est });
    }
  }
  combos.sort((x, y) => y.est - x.est);
  const res = [];
  for (const c of combos.slice(0, 60)) {
    let mv = SB.moves.map(m => ({ ...m }));
    for (const [o, n] of [[c.o1, c.n1], [c.o2, c.n2]]) {
      const same = mv.find(m => m.gw === g && m.in === o);
      if (same) same.in = n; else { mv = mv.filter(m => !(m.gw >= g && m.out === o)); mv.push({ gw: g, out: o, in: n }); }
    }
    mv = cleanMoves(mv);
    const sc = scoreMoves(mv);
    if (sc.weeks.some(w => w.bank < 0 || w.over.length)) continue;
    const hits = sc.weeks.find(w => w.gw === g).hits - cur.weeks.find(w => w.gw === g).hits;
    res.push({ ...c, gain: sc.tot - cur.tot, adj: adjTotal(sc) - curAdj, hits, moves: mv });
  }
  res.sort((x, y) => y.adj - x.adj);
  const bestSingle = Math.max(0, ...transferSuggestions(g).map(x => x.adj));
  const seen = new Set(), list = [];
  for (const r of res) {
    if (r.adj <= bestSingle + 0.5) break;  // only show pairs that beat the best single move clearly
    const k = [r.n1, r.n2].sort().join("-"); if (seen.has(k)) continue; seen.add(k);
    list.push(r); if (list.length >= 3) break;
  }
  _pairs = { key, list };
  return list;
}
function pairsHTML(g) {
  const list = pairSuggestions(g);
  if (!list.length) return `<h3 style="margin-top:14px">Pairs that fund an upgrade</h3><p class="muted">None right now: no pair where one sale funds a bigger upgrade beats your best single move. That's normal when the best upgrades are already affordable. Check again after price changes or injuries, or try a longer plan length.</p>`;
  return `<h3 style="margin-top:14px">Pairs that fund an upgrade</h3>
    <p class="note" style="margin-top:0">Two moves together, where one sale frees the money for a bigger upgrade. Only shown when the pair clearly beats the best single move.</p>
    ${list.map(r => {
      const v = r.hits ? (r.gain >= 4 ? { t: "Worth the hit", c: "good" } : { t: "Not worth the hit", c: "bad" }) : verdict(r.gain, 3, 1);
      const line = (o, n) => `<div class="move"><span class="out">▼ ${esc(P[o].name)}</span><span class="in">▲ <button data-p="${n}" style="all:unset;cursor:pointer">${esc(P[n].name)}</button></span><span class="muted mono">${money(P[n].price)} · ${T[P[n].team].short}</span></div>`;
      const up = P[r.n1].price - P[r.o1].price > P[r.n2].price - P[r.o2].price ? [r.o1, r.n1, r.o2, r.n2] : [r.o2, r.n2, r.o1, r.n1];
      return `<div class="sugg"><div class="sg-top"><div class="moves" style="margin:0">${line(r.o1, r.n1)}${line(r.o2, r.n2)}</div><span class="sg-gain ${r.gain > 0.05 ? "up" : "down"}">${sgn(r.gain)}</span></div>
        <div class="sg-meta">${vPill(v)}${r.hits ? ` <span class="pill bad">−${4 * r.hits} hit</span>` : ""}</div>
        <div class="sg-why">Moving ${esc(P[up[2]].name)} to ${esc(P[up[3]].name)} frees the money for ${esc(P[up[0]].name)} → ${esc(P[up[1]].name)}. In: ${whyIn(up[1], g)}</div>
        <button class="btn primary sg-add" data-pair="${r.o1}:${r.n1}:${r.o2}:${r.n2}">Add both to plan</button></div>`;
    }).join("")}`;
}
function whyOut(o, g) {
  const p = P[o], bits = [];
  if (p.status !== "a") bits.push(p.news || "flagged");
  if (p.mflag) bits.push(p.mflag.toLowerCase());
  else if (p.nailed < 60) bits.push(`not nailed (${p.nailed})`);
  if ((p.price_proj?.[0] ?? 0) <= -80) bits.push("may drop in price tonight");
  bits.push(`${f1(xpFrom(o, g, PG.length))} xP over ${PG.length} GWs`);
  return bits.join(" · ");
}
function whyIn(i, g) {
  const p = P[i], bits = [`${f1(xpFrom(i, g, PG.length))} xP over ${PG.length} GWs`];
  if (["MID", "FWD"].includes(p.pos)) bits.push(`${p.xgi90_4.toFixed(2)} ${term("xgi", "xGI")}/90 L4`);
  if (p.us && ["MID", "FWD"].includes(p.pos) && p.us.bc_4) bits.push(`${p.us.bc_4} ${term("bigchance", "big chances")} L4`);
  if (p.pos === "DEF" && p.dc_rate >= 0.3) bits.push(`${Math.round(p.dc_rate * 100)}% ${term("dc", "DC")} chance`);
  bits.push(`${term("nailed", "nailed")} ${p.nailed}`);
  const eo = fieldEO(); if (eo) { const e = eo[i] || 0; bits.push(e < 10 ? `differential (${e.toFixed(0)}% ${term("eo", "EO")})` : `${e.toFixed(0)}% ${term("eo", "EO")}`); }
  if ((p.price_proj?.[0] ?? 0) >= 80) bits.push("may rise tonight");
  return bits.join(" · ");
}
function suggestionsHTML(g) {
  const list = transferSuggestions(g), w = ftTable().find(r => r.gw === g), freeLeft = Math.max(0, w.ft - w.n);
  const rows = list.map(s2 => {
    const v = s2.hit ? (s2.gain >= 3 ? { t: "Worth the hit", c: "good" } : { t: "Not worth the hit", c: "bad" }) : verdict(s2.gain, 3, 1);
    const po = P[s2.out], pi = P[s2.in];
    return `<div class="sugg">
      <div class="sg-top"><div class="move"><span class="out">▼ ${esc(po.name)}</span><span class="in">▲ <button data-p="${pi.id}" style="all:unset;cursor:pointer">${esc(pi.name)}</button></span><span class="muted mono">${money(pi.price)} · <span class="club-dot" style="--club:${clubCol(pi)}" aria-hidden="true"></span>${T[pi.team].short}</span></div>
        <span class="sg-gain ${s2.gain > 0.05 ? "up" : "down"}">${sgn(s2.gain)}</span></div>
      <div class="sg-meta">${vPill(v)}${s2.hit ? ' <span class="pill bad">−4 hit</span>' : ""}<span class="fx sgfx">${fxChips(pi, g, 4)}</span></div>
      <div class="sg-why"><b>Out:</b> ${whyOut(s2.out, g)}<br><b>In:</b> ${whyIn(s2.in, g)}</div>
      <button class="btn primary sg-add" data-sugg="${s2.out}:${s2.in}">Add to plan</button></div>`;
  }).join("");
  return `<div class="bar"><h3>Transfer suggestions · GW${g}</h3><span class="tag">${freeLeft} free left</span></div>
    <p class="note" style="margin-top:0">The top 3 single moves on top of your current plan, judged on your whole squad's projected points over the rest of the plan${S.mode !== "balanced" ? ` and your ${MODES[S.mode].toLowerCase()} strategy` : ""}.</p>
    ${rows || `<p class="muted">No single move improves your plan from GW${g}. Try another gameweek or Re-plan.</p>`}
    ${pairsHTML(g)}`;
}
/* ---------- captain planner ---------- */
function captainsHTML() {
  const sc = scoreMoves(SB.moves);
  const F = D.crowd ? (D.crowd.near?.n >= 100 ? D.crowd.near : D.crowd.top10k) : null;
  const tc = D.chips.find(c => c.key === "3xc" && c.available && c.from <= PG[0] && c.to >= PG[0]);
  let bestTc = null;
  const rows = sc.weeks.map(w => {
    const g = w.gw, t = w.team;
    const opts = t.xi.slice().sort((a, b) => adjCap(b, g) - adjCap(a, g)).slice(0, 3);
    if (!opts.includes(t.cap)) opts.unshift(t.cap);
    const capX = xpg(t.cap, g);
    if (tc && g <= tc.to && (!bestTc || capX > bestTc.x)) bestTc = { g, id: t.cap, x: capX };
    const gap = opts.length > 1 ? capX - Math.max(...opts.filter(i => i !== t.cap).map(i => xpg(i, g))) : 0;
    const v = t.capMine ? { t: "Your pick", c: "mut" } : F && (F.cap[t.cap] || 0) >= 50 && gap > -0.3 ? { t: "Safe pick", c: "good" } : verdict(gap, 1, 0.4);
    return `<tr><td><b>GW${g}</b></td>
      <td><span class="pname">${esc(P[t.cap].name)}</span> ${vPill(v)}<br><span class="muted" style="font-size:12.5px">${fxText(P[t.cap], g)} · ${f1(capX)} xP${F ? ` · ${(F.cap[t.cap] || 0).toFixed(0)}% field C` : ""}</span></td>
      <td>${opts.filter(i => i !== t.cap).slice(0, 2).map(i => `<div class="capalt"><span>${esc(P[i].name)} <span class="muted">${f1(xpg(i, g))}${F ? ` · ${(F.cap[i] || 0).toFixed(0)}%` : ""}</span></span><button class="btn" data-setcap="${g}:${i}">Make C</button></div>`).join("")}
        ${t.capMine ? `<button class="btn" data-setcap="${g}:0">Back to auto</button>` : ""}</td></tr>`;
  }).join("");
  return `<div class="bar"><h3>Captain planner</h3><span class="tag">${MODES[S.mode]}</span></div>
    <p class="note" style="margin-top:0">Your captain for each gameweek of the plan, from the team your plan has that week. "Field C" = share of managers around your rank who captained him last week. Tap Make C to override any week; This week and Re-plan follow your choice.</p>
    <div class="tablebox"><table><thead><tr><th>GW</th><th>Captain</th><th>Alternatives</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${tc ? `<p class="verdict" style="margin-top:12px">${bestTc ? `Best Triple Captain week in view: <b>GW${bestTc.g}</b>, ${esc(P[bestTc.id].name)} (${f1(bestTc.x)} xP, so about +${f1(bestTc.x)} from the chip).` : ""} Your first-half Triple Captain expires after GW${tc.to}. It's worth most in a double gameweek, when the captain plays twice.</p>` : ""}`;
}

/* ---------- saved drafts (up to 3 per gameweek) ---------- */
const draftKey = () => sbKey() + ".drafts";
function getDrafts() { return (store.get(draftKey()) || []).filter(d => Array.isArray(d.moves)); }
function setDrafts(list) { store.set(draftKey(), list); SB.updated = Date.now(); store.set(sbKey(), sbState()); syncPush(); }
function draftSummary(d) {
  // score each draft with the strategy and captain/bench choices it was saved with
  const keep = { ov: SB.ov, mode: S.mode };
  SB.ov = d.ov || {}; S.mode = d.mode || S.mode;
  const moves = cleanMoves((d.moves || []).filter(m => P[m.in] && P[m.out] && GWS.includes(m.gw)));
  const sc = scoreMoves(moves), w0 = sc.weeks[0], base = scoreMoves([]);
  const mult = {}; w0.team.xi.forEach(i => mult[i] = 1); mult[w0.team.cap] = 2;
  const out = { name: d.name, moves, tot: sc.tot, gain: sc.tot - base.tot, w0: w0.team.pts, cap: w0.team.cap,
    hits: sc.weeks.reduce((a, w) => a + w.hits, 0), ftLeft: sc.ftLeft, spread: spreadVsField(mult, PG[0]), mode: d.mode, bank: w0.bank };
  SB.ov = keep.ov; S.mode = keep.mode;
  return out;
}
function draftsHTML() {
  const ds = getDrafts();
  const cur = draftSummary({ name: "Current plan", moves: SB.moves, ov: SB.ov, mode: S.mode });
  const cols = [cur, ...ds.map(draftSummary)];
  const best = (f, dir = 1) => Math.max(...cols.map(c => dir * f(c)));
  const cell = (c, f, fmt, dir = 1) => `<td class="n ${cols.length > 1 && dir * f(c) === best(f, dir) ? "up" : ""}">${fmt(f(c))}</td>`;
  const rows = [
    ["Projected points", c => c.tot, f1], ["vs no transfers", c => c.gain, sgn], [`GW${PG[0]} points`, c => c.w0, f1],
    ["Hits", c => c.hits, x => x ? "−" + 4 * x : "0", -1], ["FT left at the end", c => c.ftLeft, x => x],
    [term("spread", "Spread vs field"), c => c.spread ?? 0, x => "±" + f1(x), -1],
  ];
  return `<div class="bar"><h3>Drafts</h3><span class="tag">${ds.length}/3 saved</span></div>
    <p class="note" style="margin-top:0">Save different versions of your plan (say a template one, a differential one and a roll) and compare them over ${PG.length} GWs. Each draft keeps the strategy it was saved with. Loading one makes it your plan and switches to its strategy; Undo brings the old plan back.</p>
    <div class="filters" style="margin:0 0 10px"><input id="draftName" maxlength="24" placeholder="Name this version, e.g. Differential" aria-label="Draft name" style="flex:1 1 180px;min-width:0">
      <button class="btn primary" data-draftsave="1" ${ds.length >= 3 ? "disabled" : ""}>Save current plan</button></div>
    ${ds.length >= 3 ? '<p class="note">3 drafts saved: delete one to save another.</p>' : ""}
    <div class="tablebox"><table><thead><tr><th></th>${cols.map((c, k) => `<th class="n">${esc(c.name)}${k ? `<br><span style="font-weight:400;text-transform:none;letter-spacing:0">${esc(MODES[c.mode] || "")}</span>` : ""}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(([l, f, fmt, dir]) => `<tr><td>${l}</td>${cols.map(c => cell(c, f, fmt, dir || 1)).join("")}</tr>`).join("")}
      <tr><td>GW${PG[0]} captain</td>${cols.map(c => `<td class="n">${esc(P[c.cap]?.name || "–")}</td>`).join("")}</tr>
      <tr><td>Moves</td>${cols.map(c => `<td class="n" style="white-space:normal;min-width:140px;font-size:12.5px">${c.moves.length ? c.moves.map(m => `GW${m.gw} ${esc(P[m.out].name)} → ${esc(P[m.in].name)}`).join("<br>") : "None"}</td>`).join("")}</tr>
      ${ds.length ? `<tr><td></td><td></td>${ds.map((d, k) => `<td class="n"><button class="btn" data-draftload="${k}">Load</button> <button class="btn" data-draftdel="${k}" aria-label="Delete draft">Delete</button></td>`).join("")}</tr>` : ""}</tbody></table></div>`;
}
function vPlanner() {
  const sum = sandboxSummary();
  const g = SB.gw, wk = sum.weeks.find(w => w.gw === g);
  const t = wk.team;
  const fresh = new Set(SB.moves.filter(m => m.gw <= g).map(m => m.in));
  const problems = sum.weeks.filter(w => w.bank < 0 || w.over.length);
  const gwButtons = sum.weeks.map(w => `<button data-sbgw="${w.gw}" aria-pressed="${w.gw === g}">GW${w.gw}<small>${w.n} move${w.n === 1 ? "" : "s"}${w.hits ? ` · −${4 * w.hits}` : ""} · ${f1(w.team.pts)}</small></button>`).join("");
  const movesList = SB.moves.length ? SB.moves.map((m, k) => `<div class="move" data-mv="${m.gw}:${m.in}" style="justify-content:space-between"><span><span class="tag">GW${m.gw}</span> <span class="out">▼ ${esc(P[m.out].name)}</span> <span class="in">▲ ${esc(P[m.in].name)}</span> <span class="muted mono">${sgn(xpFrom(m.in, m.gw, PG.length) - xpFrom(m.out, m.gw, PG.length))}</span></span><button class="btn" data-undo="${k}" aria-label="Remove move">Remove</button></div>`).join("") : `<p class="muted" style="margin:0">No moves yet. Add a suggestion, tap a player on the pitch, or load an optimiser plan.</p>`;
  const delta = sum.tot - sum.baseTot;
  const mult = {}; t.xi.forEach(i => mult[i] = 1); mult[t.cap] = 2;
  const sp = spreadVsField(mult, g);
  const tab = S.ptab || "suggest";
  const tabs = [["suggest", "Suggestions"], ["captains", "Captains"], ["plans", "Optimiser plans"], ["rules", "Re-plan"], ["drafts", "Drafts"]];
  const right = SB.sel ? selPanel() : tab === "plans" ? planCards() : tab === "rules" ? replanPanel(true) : tab === "drafts" ? draftsHTML() : tab === "captains" ? captainsHTML() : suggestionsHTML(g);
  return `
  <header class="page-title"><h1>Planner</h1><p>Plan transfers, captains and your lineup over the next ${PG.length} gameweeks.</p></header>
  <div class="panel" style="padding:12px 14px"><div class="bar" style="margin:0"><span class="lbl">${term("strategy", "Strategy")}</span>
    <div class="seg" role="group" aria-label="Strategy">${Object.entries(MODES).map(([k, l]) => `<button data-mode="${k}" aria-pressed="${S.mode === k}">${l}</button>`).join("")}</div></div>
    <p class="note" style="margin:8px 0 0">${MODE_HELP[S.mode]}${sp != null ? ` Your GW${g} team: <b>±${f1(sp)}</b> ${term("spread", "vs the managers around your rank")}.` : ""}</p>
    <div class="bar" style="margin:10px 0 0"><span class="lbl">${term("horizon", "Plan length")}</span>
      <div class="seg" role="group" aria-label="Plan length">${[3, 5, 6].filter(h => h <= GWS.length).map(h => `<button data-horizon="${h}" aria-pressed="${S.horizon === h}">${h} GWs</button>`).join("")}</div></div></div>
  <div class="plansum">
    <div class="kpi"><span class="lbl">${esc(planName())} · ${PG.length} GWs</span><b>${f1(sum.tot)}</b><span class="delta muted">best XI + captain, minus hits</span></div>
    <div class="kpi"><span class="lbl">vs no transfers</span><b class="${delta > 0.05 ? "up" : delta < -0.05 ? "down" : ""}">${sgn(delta)}</b><span class="delta muted">${f1(sum.baseTot)} if you do nothing</span></div>
    <div class="kpi"><span class="lbl">GW${g} bank</span><b class="${wk.bank < 0 ? "down" : ""}">${money(wk.bank)}</b><span class="delta muted">after this week's moves</span></div>
    <div class="kpi"><span class="lbl">GW${g} ${term("ft", "free transfers")}</span><b>${wk.ft}</b><span class="delta muted">${wk.hits ? `${wk.hits} hit (−${wk.hits * 4})` : `next week: ${wk.next}`}</span></div>
  </div>
  ${problems.length ? `<p class="verdict" style="border-color:var(--bad)">${problems.map(w => `GW${w.gw}: ${w.bank < 0 ? `over budget by ${money(-w.bank)}` : ""}${w.bank < 0 && w.over.length ? "; " : ""}${w.over.length ? `more than 3 players from ${w.over.join(", ")}` : ""}`).join(". ")}. Adjust the plan before you make it on the FPL site.</p>` : ""}
  <div class="grid2">
    <div style="min-width:0;display:grid;gap:10px;align-content:start">
      <div class="gwsel" role="group" aria-label="Gameweek">${gwButtons}</div>
      ${pitch(t.xi, t.bench, g, { cap: t.cap, vice: t.vice, act: "sbp", sel: SB.sel, fresh })}
      <p class="note">Tap a player to make him captain, bench or start him, lock him, or replace him. Or drag: a starter onto a sub to swap them, a sub onto another sub to change the bench order, or a replacement from the list onto the player he replaces. On a phone, press and hold to drag. Anything you don't set is picked automatically for the best projected score.</p>
      <div class="panel"><h3>Week by week</h3><div class="tablebox"><table><thead><tr><th>GW</th><th class="n">FT</th><th class="n">Moves</th><th class="n">Hits</th><th class="n">Bank</th><th>Captain</th><th class="n">xP</th><th class="n">vs none</th></tr></thead>
        <tbody>${sum.weeks.map(w => `<tr><td>GW${w.gw}</td><td class="n">${w.ft}</td><td class="n">${w.n}</td><td class="n ${w.hits ? "down" : ""}">${w.hits ? "−" + 4 * w.hits : "0"}</td><td class="n ${w.bank < 0 ? "down" : ""}">${w.bank.toFixed(1)}</td><td>${esc(P[w.team.cap]?.name)}</td><td class="n">${f1(w.team.pts)}</td><td class="n ${w.team.pts - 4 * w.hits - w.base > 0.05 ? "up" : ""}">${sgn(w.team.pts - 4 * w.hits - w.base)}</td></tr>`).join("")}</tbody></table></div>
        <p class="note">Free transfers roll over one per week up to 5. Moves beyond your free transfers cost 4 points each. Players bought in the plan sell back at their current price.</p></div>
    </div>
    <div style="display:grid;gap:20px;min-width:0;align-content:start">
      ${SB.sel ? "" : `<div class="seg ptabs" role="group" aria-label="Planner tools">${tabs.map(([k, l]) => `<button data-ptab="${k}" aria-pressed="${tab === k}">${l}</button>`).join("")}</div>`}
      <div class="panel" id="candPanel">${right}</div>
      <div class="panel"><div class="bar"><h3>Your moves</h3>${SB.prev ? `<button class="btn" data-undoplan="1">Undo last change</button>` : ""}</div>
        <div class="moves">${movesList}</div>
        <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" data-howto="${g}">Make GW${g} moves on FPL</button>${SB.moves.length ? `<button class="btn" data-reset="1">Clear all moves</button>` : ""}</div>
        <p class="note">Saved on this device${syncToken() ? " and synced" : ""}. This week and Rivals use this plan.</p></div>
    </div>
  </div>`;
}
function selPanel() {
  const g = SB.gw, id = SB.sel, p = P[id], t = scoreMoves(SB.moves).weeks.find(w => w.gw === g).team;
  const ov = SB.ov[g] || {}, inXI = t.xi.includes(id), isCap = t.cap === id && t.capMine;
  const locked = SB.rules.locked.includes(id);
  return `<div class="bar"><h3>${esc(p.name)} · GW${g}</h3><button class="btn" data-cancel="1">Done</button></div>
    <div class="acts">
      ${inXI ? `<button class="btn ${isCap ? "primary" : ""}" data-act="cap">${isCap ? "Captain ✓" : "Make captain"}</button>` : ""}
      ${inXI ? `<button class="btn ${(ov.vice === id) ? "primary" : ""}" data-act="vice">${ov.vice === id ? "Vice ✓" : "Make vice"}</button>` : ""}
      <button class="btn ${(ov.bench || []).includes(id) || (ov.start || []).includes(id) ? "primary" : ""}" data-act="${inXI ? "bench" : "start"}">${inXI ? ((ov.start || []).includes(id) ? "Starting ✓ (tap to bench)" : "Bench him") : ((ov.bench || []).includes(id) ? "Benched ✓ (tap to start)" : "Start him")}</button>
      <button class="btn ${locked ? "primary" : ""}" data-act="lock">${locked ? "Locked ✓" : "Lock in plan"}</button>
      ${Object.keys(ov).some(k => k !== "start" && k !== "bench" || (ov[k] || []).length) ? `<button class="btn" data-act="reset">Reset GW${g} picks</button>` : ""}
    </div>
    <p class="note" style="margin:6px 0 10px">Captain, vice and bench choices apply to GW${g} only. A locked player is kept by Re-plan.</p>
    ${candidates()}`;
}
function replanPanel(inner) {
  const R = SB.rules, nm = i => esc(P[i]?.name || "?");
  const chips = (list, kind) => list.length ? list.map(i => `<button class="btn" data-unrule="${kind}:${i}" aria-label="Remove ${nm(i)}">${nm(i)} ✕</button>`).join(" ") : `<span class="muted">none</span>`;
  const caps = Object.entries(SB.ov).filter(([, o]) => o.cap).map(([g, o]) => `GW${g} ${nm(o.cap)}`).join(", ");
  return `${inner ? "" : '<div class="panel">'}<div class="bar"><h3>Re-plan for me</h3><span class="tag">${MODES[S.mode]}</span></div>
    <p class="note" style="margin-top:0">Runs the optimiser here in your browser with your rules, planning transfers, lineups and captains over ${PG.length} GWs.</p>
    <div class="rules">
      <span class="lbl">Keep</span><div>${chips(R.locked, "locked")}</div>
      <span class="lbl">Never pick</span><div>${chips(R.banned, "banned")} <span class="note">Ban a player from his info panel.</span></div>
      <span class="lbl">Captains</span><div>${caps || '<span class="muted">chosen by the optimiser</span>'}</div>
      <span class="lbl">Hits</span><div><select id="hitsSel" aria-label="Hits allowed" class="sel">${[["", "Allowed when worth it"], ["0", "No hits"], ["1", "At most 1 a week"]].map(([v, l]) => `<option value="${v}" ${String(R.maxHits ?? "") === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px"><button class="btn primary" data-replan="1" ${SOLVE.busy ? "disabled" : ""}>${SOLVE.busy ? "Planning…" : "Re-plan"}</button><span class="note" id="replanMsg">${esc(SOLVE.msg)}</span></div>
    ${vsCurrentTeam()}${inner ? "" : "</div>"}`;
}
// how much the plan adds over keeping the team you have, week by week, after hits
function vsCurrentTeam() {
  const base = baseScore(), plan = scoreMoves(SB.moves);
  const rows = plan.weeks.map((w, k) => { const b = base.weeks[k].team.pts, v = w.team.pts - 4 * w.hits;
    return `<tr><td>GW${w.gw}</td><td class="n">${w.n}${w.hits ? ` <span class="down">−${4 * w.hits}</span>` : ""}</td><td class="n">${f1(b)}</td><td class="n">${f1(v)}</td><td class="n ${v - b > 0.05 ? "up" : v - b < -0.05 ? "down" : ""}">${sgn(v - b)}</td></tr>`; }).join("");
  const gain = plan.tot - base.tot;
  return `<div class="vscur"><div class="bar" style="margin:14px 0 6px"><h3>${SB.moves.length ? "Your plan" : "No moves yet"} vs your current team</h3><b class="${gain > 0.05 ? "up" : gain < -0.05 ? "down" : ""}" style="font-size:var(--fs-lg)">${sgn(gain)}</b></div>
    <p class="note" style="margin-top:0">Over ${PG.length} GWs, after hits: ${f1(plan.tot)} projected points vs ${f1(base.tot)} if you keep your squad and just pick the best XI and captain each week.${plan.ftLeft ? ` The plan also leaves ${plan.ftLeft} free transfer${plan.ftLeft === 1 ? "" : "s"} banked at the end.` : ""}</p>
    <div class="tablebox"><table><thead><tr><th>GW</th><th class="n">Moves</th><th class="n">Keep team</th><th class="n">Plan</th><th class="n">Gain</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}
// what the strategy did to the team: upside (haul chance), how template it is, how nailed the starters are
function planTraits(sc) {
  const eo = fieldEO() || {};
  let haul = 0, eoS = 0, nail = 0, n = 0;
  sc.weeks.forEach((w, k) => {
    const p10 = i => P[i]?.dist?.[w.gw]?.[0] || 0;
    w.team.xi.forEach(i => { haul += p10(i); nail += P[i]?.nailed ?? 100; n++; if (k === 0) eoS += (eo[i] || 0) / 100; });
    haul += p10(w.team.cap);
  });
  return { haul, eo: eoS / 11, nailed: nail / Math.max(1, n), hits: sc.weeks.reduce((a, w) => a + w.hits, 0) };
}
function leanText() {
  // compare with the Balanced optimiser plan for the same squad, so the message shows what the strategy changed
  const balK = D.plans?.best ? "best" : null;
  const a = balK ? planTraits(scoreMoves(planMoves(D.plans[balK]))) : planTraits(baseScore()), b = planTraits(scoreMoves(SB.moves));
  const vs = balK ? "the Balanced plan" : "your current team", pct = (x, y) => y ? Math.round(100 * (x - y) / y) : 0;
  const hits = b.hits ? ` ${b.hits} hit${b.hits > 1 ? "s" : ""} taken.` : " No hits.";
  const hp = pct(b.haul, a.haul), own = `field ownership of your XI ${Math.round(b.eo * 100)}% vs ${Math.round(a.eo * 100)}%`;
  if (S.mode === "chase") return `Chase rank vs ${vs}: chance of 10+ point hauls ${hp >= 0 ? "+" : "−"}${Math.abs(hp)}%, ${own}.${hits}`;
  if (S.mode === "safe") return `Play safe vs ${vs}: ${own}, starters averaging ${Math.round(b.nailed)} nailed (vs ${Math.round(a.nailed)}); hits only when they gain 6+.${hits}`;
  return `Balanced: purely the most projected points.${hits}`;
}
const SOLVE = { busy: false, msg: "", highs: null };
function loadScript(src) { return new Promise((res, rej) => { const s = document.createElement("script"); s.src = src; s.onload = res; s.onerror = () => rej(new Error("couldn't load " + src)); document.head.appendChild(s); }); }
async function getHighs() {
  if (SOLVE.highs) return SOLVE.highs;
  if (!window.FPLSolver) await loadScript("plan-solver.js");
  if (!window.Module) await loadScript("vendor/highs.js");
  SOLVE.highs = await window.Module({ locateFile: f => "vendor/" + f });
  return SOLVE.highs;
}
async function runReplan() {
  if (SOLVE.busy) return;
  SOLVE.busy = true; SOLVE.msg = "Loading the optimiser…"; render();
  try {
    const highs = await getHighs();
    SOLVE.msg = "Planning…"; render();
    await new Promise(r => setTimeout(r, 30));
    const players = {};
    D.players.forEach(p => players[p.id] = { pos: p.pos, team: p.team, price: p.price, xp: p.xp, ok: p.ok !== false,
      p10: Object.fromEntries(Object.entries(p.dist || {}).map(([g, d]) => [g, d[0]])), nailed: p.nailed ?? 100 });
    const eo = fieldEO(), eoFrac = eo ? Object.fromEntries(Object.entries(eo).map(([k, v]) => [k, v / 100])) : null;
    const captains = {}; Object.entries(SB.ov).forEach(([g, o]) => { if (o.cap) captains[g] = o.cap; });
    const t0 = performance.now();
    const res = await window.FPLSolver.solve(highs, {
      players, squad: D.squad.map(s => s.id), sell: Object.fromEntries(D.squad.map(s => [s.id, s.sell])), bank: D.manager.bank,
      ft0: Math.min(5, D.manager.free_transfers), gws: PG, locked: SB.rules.locked, banned: SB.rules.banned, captains,
      maxHits: SB.rules.maxHits, eo: LAM[S.mode] ? eoFrac : null, lam: LAM[S.mode] || 0, poolExtra: SB.moves.map(m => m.in),
      ...STRAT[S.mode],
    }, () => { SOLVE.highs = null; return getHighs(); });
    const before = scoreMoves(SB.moves).tot;
    setPlan(res.moves, "replan:" + S.mode);
    const after = scoreMoves(SB.moves).tot, cur = baseScore().tot;
    SOLVE.msg = `Done in ${((performance.now() - t0) / 1000).toFixed(1)}s: ${res.moves.length} move${res.moves.length === 1 ? "" : "s"}, ${sgn(after - cur)} vs your current team (${sgn(after - before)} vs your previous plan). ${leanText()} Undo is in Your moves.`;
  } catch (e) {
    SOLVE.msg = "Re-plan failed: " + (e.message || e) + ". Your plan hasn't changed.";
  }
  SOLVE.busy = false; render();
}
function candidates() {
  const g = SB.gw, out = SB.sel, po = P[out];
  const sq = squadAt(g);
  const budget = bankAt(g) + (D.squad.some(s => s.id === out) && !SB.moves.some(m => m.in === out) ? sellPrice(out) : po.price);
  const cc = clubCounts(sq.filter(i => i !== out));
  const q = (SB.q || "").toLowerCase();
  const base = xpFrom(out, g, PG.length);
  const list = D.players.filter(p => p.pos === po.pos && !sq.includes(p.id) && p.ok !== false && p.price <= budget + 1e-9 && (cc[p.team] || 0) < 3 && (!q || (p.name + " " + p.full).toLowerCase().includes(q)))
    .map(p => ({ p, v: xpFrom(p.id, g, PG.length) })).sort((a, b) => b.v - a.v).slice(0, 30);
  return `<div class="bar"><h3>Replace ${esc(po.name)} from GW${g}</h3><button class="btn" data-cancel="1">Cancel</button></div>
    <p class="note" style="margin-top:0">Budget ${money(budget)} · ${esc(po.name)} projects ${f1(base)} over the rest of the plan.</p>
    <div class="filters"><input type="search" id="candq" placeholder="Search ${po.pos}s" value="${esc(SB.q)}" aria-label="Search replacements"></div>
    <div style="max-height:420px;overflow:auto">${list.map(({ p, v }) => `<button class="cand" data-pick="${p.id}"><span class="pname">${esc(p.name)} <span class="muted">${T[p.team].short} · ${money(p.price)}</span>${playerTags(p, 2)}</span><span class="${v > base ? "up" : "down"} mono">${sgn(v - base)}</span><b>${f1(v)}</b><span class="d">${GWS.filter(x => x >= g).slice(0, 4).map(x => `GW${x} ${fxFor(p.team, x).map(oppTxt).join("+") || "–"} ${xpCell(p.id, x)}`).join(" · ")}${p.status !== "a" ? ` · <span class="down">${esc(p.news)}</span>` : ""}</span></button>`).join("") || `<p class="muted">No affordable ${po.pos}s fit the budget and club limits.</p>`}</div>`;
}
