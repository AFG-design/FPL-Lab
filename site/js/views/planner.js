// Planner, captain planner, drafts and re-plan.
/* ---------- Planner ---------- */
// The optimiser's plans per strategy are shown in the strategy tabs (views/planner-views.js).
const adjTotal = sc => sc.weeks.reduce((a, w) => a + w.team.xi.reduce((b, i) => b + adjXI(i, w.gw), 0) + (w.team.cap ? adjCap(w.team.cap, w.gw) : 0) - 4 * w.hits, 0);
// Score points over the selected horizon, but count hits through every saved move.
// ftTable is also the source for scoreMoves; only costs outside its scoring window need adding.
function suggestionScore(moves, sc, cur, curAdj, before) {
  const after = ftTable(moves, GWS), hitWeeks = [];
  let extra = 0, beyond = 0;
  for (const [i, week] of after.entries()) {
    const delta = week.hits - before[i].hits;
    extra += delta;
    if (i >= sc.weeks.length) beyond += delta;
    if (delta > 0) hitWeeks.push({ gw: week.gw, hits: delta });
  }
  const gain = sc.tot - cur.tot - 4 * beyond;
  if (extra > 0 && (S.mode !== "chase" || extra > (D.plan_rules?.max_hits?.chase ?? 1)
    || gain < extra * (D.plan_rules?.hit_gain ?? 2))) return null;
  return { gain, adj: adjTotal(sc) - curAdj - 4 * beyond, hitWeeks };
}
function hitPills(weeks) {
  return weeks.map(w => ` <span class="pill bad">GW${w.gw} · −${4 * w.hits} hit</span>`).join("");
}
let _sugg = { key: "", list: [] };
function transferSuggestions(g) {
  const key = `${mvKey(SB.moves)}|${g}|${S.mode}|${S.horizon}|${JSON.stringify(SB.ov)}|${JSON.stringify(SB.rules)}|${D.meta.built}`;
  if (_sugg.key === key) return _sugg.list;
  const cur = scoreMoves(SB.moves), curAdj = adjTotal(cur), sq = squadAt(g), bank = bankAt(g);
  const before = ftTable(SB.moves, GWS);
  const base = new Set(D.squad.map(s => s.id)), boughtInPlan = new Set(SB.moves.filter(m => m.gw <= g).map(m => m.in));
  const out = [];
  sq.forEach(o => {
    const po = P[o]; if (!po || SB.rules.locked.includes(o)) return;
    const budget = bank + (base.has(o) && !boughtInPlan.has(o) ? sellPrice(o) : po.price);
    const cc = clubCounts(sq.filter(i => i !== o));
    const ins = D.players.filter(p => p.pos === po.pos && !sq.includes(p.id) && p.ok !== false && !SB.rules.banned.includes(p.id)
      && p.price <= budget + 1e-9 && (cc[p.team] || 0) < 3).sort((a, b) => xpFrom(b.id, g, planLeft(g)) - xpFrom(a.id, g, planLeft(g))).slice(0, 10);
    const best = [];
    ins.forEach(n => {
      let mv = SB.moves.map(m => ({ ...m }));
      const same = mv.find(m => m.gw === g && m.in === o);
      if (same) same.in = n.id; else { mv = mv.filter(m => !(m.gw >= g && m.out === o)); mv.push({ gw: g, out: o, in: n.id }); }
      mv = cleanMoves(mv);
      const sc = scoreMoves(mv);
      if (sc.weeks.some(w => w.bank < 0 || w.over.length)) return;
      const score = suggestionScore(mv, sc, cur, curAdj, before);
      if (score) best.push({ out: o, in: n.id, moves: mv, ...score });
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
  const before = ftTable(SB.moves, GWS);
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
    const score = suggestionScore(mv, sc, cur, curAdj, before);
    if (score) res.push({ ...c, moves: mv, ...score });
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
      // only hits that pass the hit rule are listed; the gain is after the hit, and the −4 pill says it took one
      const v = { ...verdict(r.gain, 3, 1), tag: r.hitWeeks.length ? "Chase rank" : null };
      const line = (o, n) => `<div class="move"><span class="out">▼ ${esc(P[o].name)}</span><span class="in">▲ <button data-p="${n}" class="linkish">${esc(P[n].name)}</button></span><span class="muted mono">${money(P[n].price)} · ${T[P[n].team].short}</span></div>`;
      const up = P[r.n1].price - P[r.o1].price > P[r.n2].price - P[r.o2].price ? [r.o1, r.n1, r.o2, r.n2] : [r.o2, r.n2, r.o1, r.n1];
      return `<div class="sugg"><div class="sg-top"><div class="moves" style="margin:0">${line(r.o1, r.n1)}${line(r.o2, r.n2)}</div><span class="sg-gain ${r.gain > 0.05 ? "up" : "down"}">${sgn(r.gain)}</span></div>
        <div class="sg-meta">${vPill(v)}${hitPills(r.hitWeeks)}</div>
        <div class="sg-why">Moving ${esc(P[up[2]].name)} to ${esc(P[up[3]].name)} frees the money for ${esc(P[up[0]].name)} → ${esc(P[up[1]].name)}. In: ${whyIn(up[1], g)}</div>
        <button class="btn primary sg-add" data-pair="${r.o1}:${r.n1}:${r.o2}:${r.n2}">Add both to plan</button></div>`;
    }).join("")}`;
}
function whyOut(o, g) {
  const p = P[o], bits = [];
  // FPL's news note and the model's flag are outside text: escaped, as everywhere else they're shown (the result is
  // inserted as HTML in the suggestion cards)
  if (p.status !== "a") bits.push(esc(p.news || "flagged"));
  if (p.mflag) bits.push(esc(p.mflag.toLowerCase()));
  else if (p.nailed < 60) bits.push(`not nailed (${p.nailed})`);
  if (priceFalling(p.price_proj?.[0]) && fallCostsYou(o)) bits.push(priceMove(p.price_proj[0]));
  bits.push(`${f1(xpFrom(o, g, planLeft(g)))} xP over ${planSpan(g)}`);
  return bits.join(" · ");
}
function whyIn(i, g) {
  const p = P[i], bits = [`${f1(xpFrom(i, g, planLeft(g)))} xP over ${planSpan(g)}`];
  if (["MID", "FWD"].includes(p.pos)) bits.push(`${p.xgi90_4.toFixed(2)} ${term("xgi", "xGI")}/90 L4`);
  if (p.us && ["MID", "FWD"].includes(p.pos) && p.us.bc_4) bits.push(`${p.us.bc_4} ${term("bigchance", "big chances")} L4`);
  if (p.pos === "DEF" && p.dc_rate >= 0.3) bits.push(`${Math.round(p.dc_rate * 100)}% ${term("dc", "DC")} chance`);
  bits.push(`${term("nailed", "nailed")} ${p.nailed}`);
  const sample = fieldSample(), eo = sample?.data.eo; if (eo) { const e = eo[i] || 0; bits.push(e < 10 ? `differential (${e.toFixed(0)}% ${term("eo", "EO")} among ${sample.label})` : `${e.toFixed(0)}% ${term("eo", "EO")} among ${sample.label}`); }
  if (priceRising(p.price_proj?.[0])) bits.push(priceMove(p.price_proj[0]));
  return bits.join(" · ");
}
function suggestionsHTML(g) {
  // Without the starting allowance the app cannot tell whether adding a move costs points.
  if (!Number.isInteger(D.manager.free_transfers)) return '<p class="muted">Transfer suggestions are unavailable until the free-transfer allowance is known.</p>';
  const list = transferSuggestions(g), w = ftTable().find(r => r.gw === g), freeLeft = Math.max(0, w.ft - w.n);
  const rows = list.map(s2 => {
    const v = { ...verdict(s2.gain, 3, 1), tag: s2.hitWeeks.length ? "Chase rank" : null };   // only hits that pass the hit rule are listed
    const po = P[s2.out], pi = P[s2.in];
    return `<div class="sugg">
      <div class="sg-top"><div class="move"><span class="out">▼ ${esc(po.name)}</span><span class="in">▲ <button data-p="${pi.id}" class="linkish">${esc(pi.name)}</button></span><span class="muted mono">${money(pi.price)} · <span class="club-dot" style="--club:${clubCol(pi)}" aria-hidden="true"></span>${T[pi.team].short}</span></div>
        <span class="sg-gain ${s2.gain > 0.05 ? "up" : "down"}">${sgn(s2.gain)}</span></div>
      <div class="sg-meta">${vPill(v)}${hitPills(s2.hitWeeks)}<span class="fx sgfx">${fxChips(pi, g, 4)}</span></div>
      <div class="sg-why"><b>Out:</b> ${whyOut(s2.out, g)}<br><b>In:</b> ${whyIn(s2.in, g)}</div>
      <button class="btn primary sg-add" data-sugg="${s2.out}:${s2.in}">Add to plan</button></div>`;
  }).join("");
  return `<div class="bar"><h3>Transfer suggestions · GW${g}</h3><span class="tag">${freeLeft} free left</span></div>
    <p class="note" style="margin-top:0">The top 3 single moves on top of your current plan, judged on your whole squad's projected points over the rest of the plan${S.mode !== "balanced" ? ` and your ${MODES[S.mode].toLowerCase()} strategy` : ""}.</p>
    ${rows || `<p class="muted">No single move improves your plan from GW${g}. Try another gameweek or Re-plan.</p>`}
    ${pairsHTML(g)}`;
}
/* ---------- captain planner ---------- */
// One card a gameweek (every week of the plan length): the captain, who picked him (you, Re-plan or automatic), how
// clear the pick is (the confidence scale on the gap to the next best), his fixtures, xP and field share, then the two
// best alternatives with Make captain, and Back to auto when the week has your own pick. A choice is saved for that
// gameweek only (SB.ov[gw].cap). No captaincy sample: the field share is left out and the note says why.
function captainsHTML() {
  const sc = scoreMoves(SB.moves);
  const sample = fieldSample(), F = sample?.data;
  const tc = D.chips.find(c => c.key === "3xc" && c.available && c.from <= PG[0] && c.to >= PG[0]);
  let bestTc = null;
  const cards = sc.weeks.map(w => {
    const g = w.gw, t = w.team;
    const opts = t.xi.slice().sort((a, b) => adjCap(b, g) - adjCap(a, g)).slice(0, 3);
    if (!opts.includes(t.cap)) opts.unshift(t.cap);
    const capX = xpg(t.cap, g);
    if (tc && g <= tc.to && (!bestTc || capX > bestTc.x)) bestTc = { g, id: t.cap, x: capX };
    const gap = opts.length > 1 ? capX - Math.max(...opts.filter(i => i !== t.cap).map(i => xpg(i, g))) : 0;
    const src = t.capMine ? "Your pick" : t.fromPlan ? "Re-plan's pick" : "Auto pick";
    const conf = { ...verdict(gap, ...CUT_WEEK), tag: F && (F.cap[t.cap] || 0) >= 50 ? "Field's pick" : null };
    const alts = opts.filter(i => i !== t.cap).slice(0, 2).map(i => `<div class="capalt"><span><b>${esc(P[i].name)}</b><span class="muted"> ${fxText(P[i], g)} · ${f1(xpg(i, g))} xP${F ? ` · ${(F.cap[i] || 0).toFixed(0)}% field C` : ""}</span></span><button class="btn" data-setcap="${g}:${i}" aria-label="Make ${esc(P[i].name)} captain in GW${g} only">Make captain</button></div>`).join("");
    return `<section class="capwk${t.capMine ? " mine" : ""}" aria-labelledby="capwk-${g}"><div class="capwk-h"><h4 id="capwk-${g}">GW${g}${w.chip ? ` <span class="tag" title="${CHIP_NAME[w.chip]}">${CHIP_SHORT[w.chip]}</span>` : ""}</h4><span class="pill mut">${src}</span></div>
      <div class="capwk-c"><span>Captain: <b class="pname">${esc(P[t.cap].name)}</b> ${vPill(conf)}</span><b class="mono">${f1(capX)} xP</b></div>
      <p class="capwk-m">${fxText(P[t.cap], g)}${F ? ` · ${(F.cap[t.cap] || 0).toFixed(0)}% field C` : ""} · vice ${esc(P[t.vice]?.name || "–")}</p>
      ${alts ? `<div class="capwk-alts"><span class="lbl">Alternatives</span>${alts}</div>` : ""}
      ${t.capMine ? `<button class="btn" data-setcap="${g}:0" aria-label="Back to the automatic captain in GW${g}">Back to auto</button>` : ""}</section>`;
  }).join("");
  return `<div class="bar"><h3>Captain planner</h3><span class="tag">${MODES[S.mode]}</span></div>
    <p class="note" style="margin-top:0">Your captain for each gameweek of the plan, from the team your plan has that week. A choice applies to that gameweek only; This week and Re-plan follow it. ${sample ? `"Field C" = share of ${sample.label} who captained him in GW${sample.gw}.` : "Captaincy sample unavailable: neither managers near your rank nor the top 10k has a usable sample."} Confidence is how far the captain is ahead of the next best: Strong at 2+ xP, Marginal at 1.5–2 (one-week gaps smaller than that came off barely more than half the time).</p>
    <div class="capwks">${cards}</div>
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
  const sc = scoreMoves(moves, d.solved || null), w0 = sc.weeks[0], base = scoreMoves([]);   // with its saved lineups, as Transfer paths scores it
  const mult = {}; w0.team.xi.forEach(i => mult[i] = 1); mult[w0.team.cap] = 2;
  const out = { name: d.name, moves, tot: sc.tot, gain: gainVsNone(sc, base), w0: w0.team.pts, cap: w0.team.cap,
    hits: sc.weeks.reduce((a, w) => a + w.hits, 0), ftLeft: sc.ftLeft, spread: spreadVsField(mult, PG[0]), mode: d.mode, bank: w0.bank };
  SB.ov = keep.ov; S.mode = keep.mode;
  return out;
}
// Saved plans (drafts), one card each so they read without sideways scrolling in the tools column (a table there was
// about 580px wide in a 300px column at every width): the active plan first (with Undo), then up to 3 drafts, each
// with the same figures in the same order and the best figure among them in green (and "(best)" for screen readers). A saved plan the active one matches (same moves,
// strategy, captain and bench choices and lineups, tpaths.js samePath) is marked Active. "Make active" replaces the
// active plan with it and switches to the strategy it was saved with (activatePlan); Undo brings the old plan back.
function draftIsActive(d) {
  const saved = completePlan(d);
  saved.moves = cleanMoves(saved.moves.filter(m => P[m.in] && P[m.out] && GWS.includes(m.gw)));
  return samePath(saved, completePlan());
}
function draftsHTML() {
  const ds = getDrafts();
  const cur = draftSummary({ name: "Active plan", moves: SB.moves, ov: SB.ov, mode: S.mode, solved: SB.solved });
  const act = ds.map(draftIsActive);
  const cols = [cur, ...ds.map(draftSummary)];
  const best = (f, dir = 1) => Math.max(...cols.map(c => dir * f(c)));
  const rows = [
    ["Projected points", c => c.tot, f1], ["vs no transfers", c => c.gain, sgn], [`GW${PG[0]} points`, c => c.w0, f1],
    ["Hits", c => c.hits, x => x ? "−" + 4 * x : "0", -1], ["FT left at the end", c => c.ftLeft, x => x],
    [term("spread", "Spread vs field"), c => c.spread ?? 0, x => "±" + f1(x), -1],
  ];
  return `<div class="bar"><h3>Drafts</h3><span class="tag">${ds.length}/3 saved</span></div>
    <p class="note" style="margin-top:0">Save versions of your plan as drafts (say a template one, a differential one and a roll) and compare them over ${PG.length} GWs. Each keeps the strategy it was saved with. <b>Make active</b> makes a draft your active plan and switches to its strategy; This week and Rivals then follow it, and Undo brings the old plan back. Saving never changes your active plan.</p>
    <div class="filters" style="margin:0 0 10px"><input id="draftName" maxlength="24" placeholder="Name this version, e.g. Differential" aria-label="Draft name" style="flex:1 1 180px;min-width:0">
      <button class="btn primary" data-draftsave="1" ${ds.length >= 3 ? "disabled" : ""}>Save active plan</button></div>
    ${ds.length >= 3 ? '<p class="note">3 drafts saved: delete one to save another.</p>' : ""}
    ${cols.length > 1 ? '<p class="note" style="margin:0 0 8px">Green marks the best figure among your plans.</p>' : ""}
    <div class="drcards">${cols.map((c, k) => {
      const d = k ? ds[k - 1] : null, on = k ? act[k - 1] : true;
      const metrics = rows.map(([l, fn, fmt, dir]) => { const top = new Set(cols.map(fn)).size > 1 && (dir || 1) * fn(c) === best(fn, dir || 1);   // a tie everywhere marks nothing
        return `<div><dt>${l}</dt><dd class="${top ? "up" : ""}">${fmt(fn(c))}${top ? '<span class="sr"> (best)</span>' : ""}</dd></div>`; }).join("");
      return `<section class="drcard${k ? "" : " cur"}${on && k ? " on" : ""}" aria-labelledby="drh-${k}">
        <div class="drcard-h"><h4 id="drh-${k}">${k ? esc(c.name) : `Active plan: ${esc(planName())}`}</h4>${k ? (on ? '<span class="pill good">Active</span>' : '<span class="pill mut">Saved</span>') : '<span class="pill good">In use</span>'}</div>
        <p class="drcard-s">${esc(MODES[k ? c.mode : S.mode] || MODES[S.mode])} strategy${d?.from ? ` · from ${esc(d.from)}` : ""}${!k ? " · This week and Rivals use it" : ""}</p>
        <dl class="drcard-m">${metrics}</dl>
        <p class="drcard-mv"><b>GW${PG[0]} captain</b> ${esc(P[c.cap]?.name || "–")}</p>
        <p class="drcard-mv"><b>Moves</b> ${c.moves.length ? c.moves.map(m => `GW${m.gw} ${esc(P[m.out].name)} → ${esc(P[m.in].name)}`).join(" · ") : "None"}</p>
        ${k ? `<div class="acts">${on ? '<span class="dr-on">This is your active plan</span>' : `<button class="btn primary" data-draftload="${k - 1}" aria-label="Make ${esc(d.name || "this draft")} your active plan (switches to ${esc(MODES[d.mode] || MODES[S.mode])})">Make active</button>`}<button class="btn" data-draftdel="${k - 1}" aria-label="Delete ${esc(d.name || "draft")}">Delete</button></div>` : SB.prev ? `<div class="acts"><button class="btn sm" data-undoplan="1">Undo last change</button></div>` : ""}
      </section>`;
    }).join("")}</div>`;
}
// "Your plan" tab: the full editor (pitch, suggestions, captains, Re-plan, drafts). The page shell and the view tabs
// live in vPlanner (views/planner-views.js); in this tab the plan length sits with the strategy under Planning settings.
// Phone order: which plan is active, a compact summary of the selected week (xP, bank, free transfers, gain over the
// plan), the settings (collapsed, current choices in their summary), then the gameweek, the squad and its lineup tools.
// The detailed week-by-week forecast is collapsed under the pitch. Nothing is computed differently: every figure is
// the one the old KPI row and table showed (sandboxSummary).
const PE = { set: false, weeks: false, edit: false };   // which of the editor's folds are open (this visit only)
function activePlanLine() {
  const sc = scoreMoves(SB.moves), e = tpEditInfo();
  return `<div class="pe-active" role="status"><span><span class="lbl">Active plan</span> <b>${esc(planName())}</b>${e ? ` · from saved plan “${esc(e.d.name)}”` : ""} · ${MODES[S.mode]} · ${f1(sc.tot)} pts over ${PG.length} GWs</span>${SB.prev ? `<button class="btn sm" data-undoplan="1">Undo last change</button>` : ""}</div>`;
}
function planSettings(sp, g) {
  return `<details class="pe-set" data-pefold="set" ${PE.set ? "open" : ""}><summary>Planning settings <span class="pe-cur">${MODES[S.mode]} · ${PG.length} GWs</span></summary>
    <div class="pe-set-body">
      <div class="bar" style="margin:0"><span class="lbl">${term("strategy", "Strategy")}</span>
        <div class="seg" role="group" aria-label="Strategy">${Object.entries(MODES).map(([k, l]) => `<button data-mode="${k}" aria-pressed="${S.mode === k}">${l}</button>`).join("")}</div></div>
      <p class="note" style="margin:0">${MODE_HELP[S.mode]} Suggestions, captains and Re-plan follow this strategy.${sp != null ? ` Your GW${g} team: <b>±${f1(sp)}</b> ${term("spread", "vs " + fieldSample().label)}.` : ""}</p>
      <div class="bar" style="margin:0"><span class="lbl">${term("horizon", "Plan length")}</span>
        <div class="seg" role="group" aria-label="Plan length">${[3, 5, 6].filter(h => h <= GWS.length).map(h => `<button data-horizon="${h}" aria-pressed="${S.horizon === h}">${h} GWs</button>`).join("")}</div></div>
    </div></details>`;
}
function plannerEditor() {
  const sum = sandboxSummary();
  const g = SB.gw, wk = sum.weeks.find(w => w.gw === g);
  const t = wk.team;
  const fresh = new Set(SB.moves.filter(m => m.gw <= g).map(m => m.in));
  const problems = sum.weeks.filter(w => w.bank < 0 || w.over.length);
  const gwButtons = sum.weeks.map(w => `<button data-sbgw="${w.gw}" aria-pressed="${w.gw === g}">GW${w.gw}${w.chip ? ` <span class="tag">${CHIP_SHORT[w.chip]}</span>` : ""}<small>${w.n} move${w.n === 1 ? "" : "s"}${w.hits ? ` · −${4 * w.hits}` : ""} · ${f1(w.team.pts)}</small></button>`).join("");
  const movesList = SB.moves.length ? SB.moves.map((m, k) => `<div class="move" data-mv="${m.gw}:${m.in}" style="justify-content:space-between"><span><span class="tag">GW${m.gw}</span> <span class="out">▼ ${esc(P[m.out].name)}</span> <span class="in">▲ ${esc(P[m.in].name)}</span> <span class="muted mono" title="Player xP over ${planSpan(m.gw)}, in minus out">${sgn(xpFrom(m.in, m.gw, planLeft(m.gw)) - xpFrom(m.out, m.gw, planLeft(m.gw)))}</span></span><button class="btn" data-undo="${k}" aria-label="Remove move ${esc(P[m.out].name)} to ${esc(P[m.in].name)}">Remove</button></div>`).join("") : `<p class="muted" style="margin:0">No moves yet. Add a suggestion, tap a player on the pitch, or load an optimiser plan.</p>`;
  const delta = sum.gain;
  const mult = {}; t.xi.forEach(i => mult[i] = 1); mult[t.cap] = 2;
  const sp = spreadVsField(mult, g);
  const tab = S.ptab || "suggest";
  const tabs = [["suggest", "Suggestions"], ["captains", "Captains"], ["rules", "Re-plan"], ["drafts", "Drafts"]];
  const right = SB.sel ? selPanel() : tab === "rules" ? replanPanel(true) : tab === "drafts" ? draftsHTML() : tab === "captains" ? captainsHTML() : suggestionsHTML(g);
  const cls = x => x > 0.05 ? "up" : x < -0.05 ? "down" : "";
  return `${tpEditBar()}${activePlanLine()}
  <div class="gwsel" role="group" aria-label="Gameweek">${gwButtons}</div>
  <div class="panel pe-head">
    <dl class="pe-sum">
      <div class="pe-k"><dt>GW${g} xP</dt><dd>${f1(t.pts)}</dd><dd class="pe-s">projected, this week</dd></div>
      <div class="pe-k"><dt>Bank after moves</dt><dd class="${wk.bank < 0 ? "down" : ""}">${money(wk.bank)}</dd><dd class="pe-s">after GW${g} moves</dd></div>
      <div class="pe-k"><dt>${term("ft", "Free transfers")}</dt><dd>${wk.ft}</dd><dd class="pe-s pe-ft">${wk.hits ? `${wk.hits} hit (−${wk.hits * 4})` : `${wk.n} used · next week ${wk.next}`}</dd></div>
      <div class="pe-k pe-gain"><dt>vs no transfers · ${PG.length} GWs</dt><dd class="${cls(delta)}" title="${GAIN_NOTE()}">${sgn(delta)}</dd><dd class="pe-s">${f1(sum.tot)} pts vs ${f1(sum.baseTot)} · banked FTs counted</dd></div>
    </dl>
    ${planSettings(sp, g)}
  </div>
  ${problems.length ? `<p class="verdict" style="border-color:var(--bad)">${problems.map(w => `GW${w.gw}: ${w.bank < 0 ? `over budget by ${money(-w.bank)}` : ""}${w.bank < 0 && w.over.length ? "; " : ""}${w.over.length ? `more than 3 players from ${w.over.join(", ")}` : ""}`).join(". ")}. Adjust the plan before you make it on the FPL site.</p>` : ""}
  <div class="grid2 lu-cols">
    <div style="min-width:0;display:grid;gap:10px;align-content:start">
      <div class="bar lu-bar"><h3>GW${g} team · ${esc(planName())}</h3>${lineupToggle()}</div>
      ${pitch(t.xi, t.bench, g, { cap: t.cap, vice: t.vice, act: "sbp", sel: SB.sel, fresh, run: 3, price: true })}
      <p class="pe-cap"><span>Captain: <b>${esc(P[t.cap]?.name || "–")}</b> · Vice: <b>${esc(P[t.vice]?.name || "–")}</b>${t.capMine ? " · your pick" : ""}</span><button class="linkish" data-pecap="1">All captains</button></p>
      <p class="note" style="margin:0">Tap a player to make him captain, bench or start him, lock him, or replace him. Anything you don't set is picked automatically for the best projected score.</p>
      <details class="pe-fold" data-pefold="edit" ${PE.edit ? "open" : ""}><summary>Drag and keyboard</summary><p class="note">Drag a starter onto a sub to swap them, a sub onto another sub to change the bench order, or a replacement from the list onto the player he replaces. On a phone, press and hold to drag. Every drag has a tap or keyboard equivalent: select a player, then use his actions (Bench him, Start him) or choose his replacement from the list.</p></details>
      <details class="panel pe-fold pe-weeks" data-pefold="weeks" ${PE.weeks ? "open" : ""}><summary>Week-by-week forecast <span class="pe-cur">${PG.length} GWs · ${f1(sum.tot)} pts</span></summary><div class="tablebox"><table><thead><tr><th>GW</th><th class="n">FT</th><th class="n">Moves</th><th class="n">Hits</th><th class="n">Bank</th><th>Captain</th><th class="n">xP</th><th class="n">vs none</th></tr></thead>
        <tbody>${sum.weeks.map(w => `<tr><td>GW${w.gw}${w.chip ? ` <span class="tag" title="${CHIP_NAME[w.chip]}">${CHIP_SHORT[w.chip]}</span>` : ""}</td><td class="n">${w.ft}</td><td class="n">${w.n}</td><td class="n ${w.hits ? "down" : ""}">${w.hits ? "−" + 4 * w.hits : "0"}</td><td class="n ${w.bank < 0 ? "down" : ""}">${w.bank.toFixed(1)}</td><td>${esc(P[w.team.cap]?.name)}</td><td class="n">${f1(w.team.pts)}</td><td class="n ${w.team.pts - 4 * w.hits - w.base > 0.05 ? "up" : ""}">${sgn(w.team.pts - 4 * w.hits - w.base)}</td></tr>`).join("")}</tbody></table></div>
        <p class="note">Free transfers roll over one per week up to 5. Moves beyond your free transfers cost 4 points each. Players bought in the plan sell back at their current price.${Object.keys(SB.chips || {}).length ? " Chips: WC Wildcard and FH Free Hit weeks' moves are free and keep your banked transfers (a Free Hit's last that week only); BB Bench Boost adds the bench to xP; TC Triple Captain counts the captain three times." : ""}</p></details>
    </div>
    <div style="display:grid;gap:20px;min-width:0;align-content:start">
      ${SB.sel ? "" : `<div class="seg ptabs" role="group" aria-label="Planner tools">${tabs.map(([k, l]) => `<button data-ptab="${k}" aria-pressed="${tab === k}">${l}</button>`).join("")}</div>`}
      <div class="panel" id="candPanel">${right}</div>
      <div class="panel"><div class="bar"><h3>Your moves</h3>${SB.prev ? `<button class="btn" data-undoplan="1">Undo last change</button>` : ""}</div>
        <div class="moves">${movesList}</div>
        <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" data-howto="${g}">Make GW${g} moves on FPL</button>${SB.moves.length ? `<button class="btn" data-reset="1">Clear all moves</button>` : ""}</div>
        <p class="note">Planning only: nothing is sent to FPL. Saved on this device${syncReady() ? " and synced" : ""}. This week and Rivals use this plan.</p></div>
    </div>
  </div>`;
}
function selPanel() {
  const g = SB.gw, id = SB.sel, p = P[id], t = scoreMoves(SB.moves).weeks.find(w => w.gw === g).team;
  const ov = SB.ov[g] || {}, inXI = t.xi.includes(id), isCap = t.cap === id && t.capMine;
  const locked = SB.rules.locked.includes(id);
  return `<div class="bar"><h3 id="selHead" tabindex="-1">${esc(p.name)} · GW${g}</h3><button class="btn" data-cancel="1">Done</button></div>
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
      <span class="lbl">Chips</span><div>${chipPinsHTML()}</div>
      <span class="lbl">Hits</span><div>${S.mode === "chase" ? `<select id="hitsSel" aria-label="Hits allowed" class="sel">${[["", "At most 1 a week, when it pays"], ["0", "No hits"]].map(([v, l]) => `<option value="${v}" ${String(R.maxHits ?? "") === v ? "selected" : ""}>${l}</option>`).join("")}</select>` : `<span class="muted">None: ${MODES[S.mode]} never takes a hit</span>`}</div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px"><button class="btn primary" data-replan="1" ${SOLVE.busy ? "disabled" : ""}>${SOLVE.busy ? "Planning…" : "Re-plan"}</button><span class="note" id="replanMsg">${esc(SOLVE.msg)}</span></div>
    ${vsCurrentTeam()}${inner ? "" : "</div>"}`;
}
// FL-005: pin a chip to a gameweek. Each chip you can still play in one of the plan's weeks gets a picker of the weeks
// in its window; a chip already used, or with no week of its window in the plan, is listed as not available and why
function chipPinsHTML() {
  const pins = SB.chips || {}, rows = [];
  Object.keys(CHIP_NAME).forEach(k => {
    const weeks = PG.filter(g => chipWindow(k, g));
    if (!weeks.length) {
      const next = (D.chips || []).find(c => c.key === k && c.available && c.from > PG[PG.length - 1]);
      rows.push(`<span class="muted chip-na">${CHIP_NAME[k]}: ${next ? `from GW${next.from}` : "used"}</span>`);
      return;
    }
    const taken = new Set(Object.entries(pins).filter(([c]) => c !== k).map(([, g]) => g));
    rows.push(`<label class="chip-pin"><span>${CHIP_NAME[k]}</span><select class="sel" data-chippin="${k}" aria-label="${CHIP_NAME[k]} gameweek">
      <option value="">Not in this plan</option>${weeks.map(g => `<option value="${g}" ${pins[k] === g ? "selected" : ""} ${taken.has(g) ? "disabled" : ""}>GW${g}${taken.has(g) ? " (another chip)" : ""}</option>`).join("")}</select></label>`);
  });
  return `<div class="chip-pins">${rows.join("")}</div><p class="note" style="margin:4px 0 0">Re-plan builds around these. Wildcard and Free Hit weeks' moves are free and keep your banked transfers; a Free Hit's moves last that week only.</p>`;
}
function setChipPin(k, g) {
  rememberPlan();
  const c = { ...(SB.chips || {}) };
  if (g) c[k] = +g; else delete c[k];
  SB.chips = cleanChips(c); SB.solved = null; SB.source = SB.moves.length ? "custom" : SB.source;
  sanitize(); saveSandbox();
}
// how much the plan adds over keeping the team you have, week by week, after hits
function vsCurrentTeam() {
  const base = baseScore(), plan = scoreMoves(SB.moves);
  const rows = plan.weeks.map((w, k) => { const b = base.weeks[k].team.pts, v = w.team.pts - 4 * w.hits;
    return `<tr><td>GW${w.gw}</td><td class="n">${w.n}${w.hits ? ` <span class="down">−${4 * w.hits}</span>` : ""}</td><td class="n">${f1(b)}</td><td class="n">${f1(v)}</td><td class="n ${v - b > 0.05 ? "up" : v - b < -0.05 ? "down" : ""}">${sgn(v - b)}</td></tr>`; }).join("");
  const gain = gainVsNone(plan, base), ftGap = plan.ftLeft - base.ftLeft;
  return `<div class="vscur"><div class="bar" style="margin:14px 0 6px"><h3>${SB.moves.length ? "Your plan" : "No moves yet"} vs no transfers</h3><b class="${gain > 0.05 ? "up" : gain < -0.05 ? "down" : ""}" style="font-size:var(--fs-lg)">${sgn(gain)}</b></div>
    <p class="note" style="margin-top:0">Over ${PG.length} GWs, after hits: ${f1(plan.tot)} projected points vs ${f1(base.tot)} if you keep your squad and just pick the best XI and captain each week.${ftGap ? ` The plan leaves ${plan.ftLeft} free transfer${plan.ftLeft === 1 ? "" : "s"} banked at the end against ${base.ftLeft} if you keep your squad, so the figure above ${ftGap < 0 ? "takes off" : "adds"} ${f1(Math.abs(ftGap) * ftValue())} (${f1(ftValue())} a transfer); the weekly gains below are points only.` : ""}</p>
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
  const sample = fieldSample();
  const hp = pct(b.haul, a.haul), own = sample ? `effective ownership of your XI among ${sample.label} ${Math.round(b.eo * 100)}% vs ${Math.round(a.eo * 100)}%` : "ownership sample unavailable";
  if (S.mode === "chase") return `Chase rank vs ${vs}: chance of 10+ point hauls ${hp >= 0 ? "+" : "−"}${Math.abs(hp)}%, ${own}.${hits}`;
  if (S.mode === "safe") return `Play safe vs ${vs}: ${own}, starters averaging ${Math.round(b.nailed)} nailed (vs ${Math.round(a.nailed)}).${hits}`;
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
// The browser optimiser, shared by Re-plan (Your plan) and Optimise (Transfer paths). Plans moves, lineups and captains
// over PG for one strategy from your confirmed squad, with the rules given: locks and bans (rules.locked/banned), a
// stricter hit limit (rules.maxHits) and any captains you fixed (ov[gw].cap). Returns { moves, solved, none } or throws
// with a reason you can act on. status(msg) reports progress.
async function optimiseMoves(mode, { ov = {}, rules = SB.rules, poolExtra = [], status = () => {}, chips = {} } = {}) {
  const highs = await getHighs();
  status("Planning…");
  await new Promise(r => setTimeout(r, 30));
  const players = {};
  D.players.forEach(p => players[p.id] = { pos: p.pos, team: p.team, price: p.price, xp: p.xp, ok: p.ok !== false,
    p10: Object.fromEntries(Object.entries(p.dist || {}).map(([g, d]) => [g, d[0]])), nailed: p.nailed ?? 100 });
  const eo = fieldEO(), eoFrac = eo ? Object.fromEntries(Object.entries(eo).map(([k, v]) => [k, v / 100])) : null;
  const captains = {}; Object.entries(ov).forEach(([g, o]) => { if (o.cap) captains[g] = o.cap; });
  // Same rules as the server plans (optimise.strategy_plans): Balanced first, then Play safe / Chase rank held to their
  // points budget against it, no transfers unless they beat keeping the squad by the profit rule, and no hits unless
  // they pay (hit rule).
  // Missing input: no field ownership -> Play safe / Chase rank can't be worked out, so it says so and stops.
  // FL-075: every setting comes from the build (data.json plan_rules), the same numbers the server's plans used. A
  // data.json without them (older than FL-075) can't be re-planned the same way, so it says so instead of guessing.
  const R = D.plan_rules;
  const settings = window.FPLSolver.settingsFrom(R);
  const ruleKeys = ["safe_budget", "chase_budget", "min_profit", "hit_gain", "tie", "strategy"];
  if (!settings || ruleKeys.some(k => R[k] == null)) throw new Error("this data update doesn't carry the planner's settings; try again after the next refresh");
  if (mode !== "balanced" && !eoFrac) throw new Error(`${MODES[mode]} needs the field-ownership data, which isn't in this build`);
  const common = { players, squad: D.squad.map(s => s.id), sell: Object.fromEntries(D.squad.map(s => [s.id, s.sell])), bank: D.manager.bank,
    ft0: Math.min(5, D.manager.free_transfers), gws: PG, locked: rules.locked, banned: rules.banned, captains,
    maxHits: 0, poolExtra, ...settings, chips };
  // FL-005: keeping the squad still plays a pinned Bench Boost or Triple Captain (not transfers); a Wildcard or Free
  // Hit needs moves, so the no-transfers yardstick goes without them, as baseScore does
  const holdChips = Object.fromEntries(Object.entries(chips).filter(([k]) => k === "bboost" || k === "3xc"));
  // hits: Balanced and Play safe never take one; Chase rank at most plan_rules.max_hits.chase a week, or your own
  // "Hits" choice if that is stricter
  const chaseCap = Math.min(R.max_hits?.chase ?? 1, rules.maxHits ?? 99);
  const remake = () => { SOLVE.highs = null; return getHighs(); };
  const solveP = inp => window.FPLSolver.solve(SOLVE.highs || highs, inp, remake);
  const hitsOf = r => r.weeks.reduce((a, w) => a + w.hits, 0);
  // hit rule (optimise.HIT_GAIN): keep a plan's hits only if it beats the best hit-free plan by hit_gain a hit,
  // in plain projected points after the -4; with no hit-free plan possible, it must beat keeping the squad by that
  const hitRule = async (r, inp) => {
    const h = hitsOf(r); if (!h) return r;
    let alt = null; try { alt = await solveP({ ...inp, maxHits: 0 }); } catch (e) { alt = null; }
    const ref = alt ? alt.value : none.value;
    return r.value >= ref + (R.hit_gain ?? 2) * h ? r : alt;
  };
  // Your locks and bans can force moves: a ban on a player you own means selling him, a lock on one you don't means
  // buying him. "Keep the squad" is then not an option, so it is scored without them (just the yardstick that every
  // "vs your current team" figure uses) and the profit rule below can't throw the forced moves away.
  const owned = new Set(common.squad);
  const forced = [...common.banned.filter(i => owned.has(i)), ...common.locked.filter(i => !owned.has(i))];
  // Captain overrides belong to the real plan: a planned signing is absent from this baseline squad.
  // With no override, the baseline chooses its best projected captain each week (also when no captain was set).
  const none = await solveP({ ...common, locked: [], banned: [], captains: {}, maxMovesWeek: 0, chips: holdChips });
  let bal;
  try { bal = await solveP(common); } catch (e) {
    // no plan meets your locks and bans: say which ones force it rather than quietly handing back an unchanged squad
    if (forced.length) throw new Error(`no plan meets your locks and bans (${forced.map(i => P[i]?.name || i).join(", ")} ${forced.length === 1 ? "forces a move" : "force moves"}). Check you have enough free transfers and money, or lift a lock or ban`);
    bal = { ...none, moves: [] };
  }
  let res = bal, stratInp = null;
  if (mode !== "balanced") {
    status(`Planning ${MODES[mode]}…`); await new Promise(r => setTimeout(r, 30));
    const st = R.strategy?.[mode] || {};
    let floor = mode === "safe" ? bal.value - R.safe_budget - R.tie : bal.value - R.chase_budget;
    if (!forced.length && bal.value >= none.value + R.min_profit) floor = Math.max(floor, none.value + R.min_profit);
    const inp = { ...common, eo: eoFrac, floor, lam: st.lam || 0, haulW: st.haul_w || 0, nailW: st.nail_w || 0, hitMargin: st.hit_margin || 0 };
    if (mode === "chase" && chaseCap > 0) inp.maxHits = chaseCap;
    try { res = (await hitRule(await solveP(inp), { ...inp, maxHits: 0 })) || bal; } catch (e) { res = bal; }
    stratInp = inp;
  }
  // no moves for the sake of it (optimise.strategy_plans, FL-110; forced moves always stay): moves this week must beat
  // rolling this week (the same rules with no moves in the first gameweek) by min_profit, and a plan that only moves
  // later must beat keeping the squad by as much (FL-073). Missing roll plan (the solver found none): measured
  // against keeping the squad, as before.
  // The roll plan is worked out as the server's is: Balanced with no moves this week, then for Play safe / Chase rank
  // their own terms held to the same budget against Balanced's roll plan (falling back to it).
  // a Wildcard or Free Hit pinned to this week is a choice to move now, so there's no rolling it to compare against
  const chipNow = chips.wildcard === PG[0] || chips.freehit === PG[0];
  if (!forced.length && !chipNow && res.moves.some(m => m.gw === PG[0])) {
    status("Checking against rolling the transfer…"); await new Promise(r => setTimeout(r, 30));
    let roll = null;
    try { roll = await solveP({ ...common, week1Moves: 0 }); } catch (e) { roll = null; }
    if (roll && stratInp) {
      const floor = mode === "safe" ? roll.value - R.safe_budget - R.tie : roll.value - R.chase_budget;
      const ri = { ...stratInp, week1Moves: 0, floor };
      try { roll = (await hitRule(await solveP(ri), { ...ri, maxHits: 0 })) || roll; } catch (e) { /* keep Balanced's roll */ }
    }
    if (roll && res.value < roll.value + R.min_profit) res = roll;
  }
  if (!forced.length && res.moves.length && res.value < none.value + R.min_profit) res = { ...none, moves: [] };
  // keep the optimiser's own lineup and captain with its moves, so what's shown (and the gain) is the plan that
  // passed the points budget, not one re-picked by the browser's milder rules
  // a Free Hit week's squad comes back from the solver as that week's squad, not as transfers: turn it into that
  // week's moves (same position out and in), which the plan keeps for that week only (plan.js movesFor)
  const fhg = chips.freehit;
  const fhw = res.weeks?.find(w => w.gw === fhg && w.chip === "freehit");
  if (fhw) {
    const held = squadAt(fhg, res.moves, chips), outs = held.filter(i => !fhw.squad.includes(i));
    fhw.squad.filter(i => !held.includes(i)).forEach(i => {
      const k = outs.findIndex(o => P[o]?.pos === P[i]?.pos);
      if (k >= 0) res.moves = [...res.moves, { gw: fhg, out: outs.splice(k, 1)[0], in: i }];
    });
  }
  const solved = {};
  PG.forEach((g, w) => {
    const sq = squadAt(g, res.moves, chips);
    const wk = res.weeks?.[w];
    if (wk && wk.gw === g && wk.xi?.length === 11) {
      solved[g] = { sq: sq.slice(), xi: wk.xi.slice(), cap: wk.captain };
      // The browser solver supplies XI and captain. Record the resulting vice and bench as shown.
      const team = withMode(mode, () => bestXI(sq, g, {}, solved));
      Object.assign(solved[g], { vice: team.vice, bench: team.bench });
    }
  });
  return { moves: res.moves, solved, none };
}
async function runReplan() {
  if (SOLVE.busy) return;
  SOLVE.busy = true; SOLVE.msg = "Loading the optimiser…"; render();
  try {
    const t0 = performance.now();
    const scope = sbKey();
    const res = await optimiseMoves(S.mode, { ov: SB.ov, rules: SB.rules, poolExtra: SB.moves.map(m => m.in), chips: SB.chips || {}, status: m => { SOLVE.msg = m; render(); } });
    if (scope !== sbKey()) throw new Error("Your starting squad changed during Re-plan");
    const before = scoreMoves(SB.moves).tot;
    setPlan(res.moves, "replan:" + S.mode, res.solved);
    const after = scoreMoves(SB.moves).tot, cur = baseScore().tot;
    SOLVE.msg = `Done in ${((performance.now() - t0) / 1000).toFixed(1)}s: ${res.moves.length} move${res.moves.length === 1 ? "" : "s"}, ${sgn(after - cur)} vs your current team (${sgn(after - before)} vs your previous plan). ${leanText()} Undo is in Your moves.`;
  } catch (e) {
    SOLVE.msg = "Re-plan failed: " + (e.message || e) + ". Your plan hasn't changed.";
  }
  SOLVE.busy = false; render();
}
// Replace a player: the eligible-player search (same position, affordable this week, at most 3 a club, not already
// owned). Choosing a candidate opens a preview first; "Add <name> to plan" makes the move (makeTransfer, so Undo works
// as for any edit). Drag-and-drop from the list still adds the move straight away, as before.
// Figures, all over the rest of the plan from the move's week (GW g to the plan's last week, H gameweeks):
//   - player forecast: the incoming player's projected points minus the outgoing player's (xpFrom over H weeks). The
//     list used PG.length weeks from g, which ran past the plan's end for a later week; it now uses H, as the preview.
//   - team change: the active plan's projected total after the move minus before (scoreMoves over the whole plan,
//     after hits, with the plan's chips), so lineups, captains and the bench are re-picked the way they will be.
//   - planning value: the same plus ftValue() for each free transfer banked at the end, the measure "vs no
//     transfers" uses; shown separately because it isn't projected points.
// Missing or ambiguous: a move FPL wouldn't allow (money, club limit) shows the reason and no Add button; a move that
// leaves a later week over budget or over a club limit is allowed (as before) and the preview says which week.
function replaceWith(g, out, inn) {
  let mv = SB.moves.map(m => ({ ...m }));
  const same = mv.find(m => m.gw === g && m.in === out);
  if (same) { same.in = inn; if (same.in === same.out) mv = mv.filter(m => m !== same); }
  else { mv = mv.filter(m => !(m.gw >= g && m.out === out)); mv.push({ gw: g, out, in: inn }); }
  return cleanMoves(mv, SB.chips || {});
}
function replacePreview(g, out, inn) {
  const pi = P[inn], po = P[out], why = canBuy(g, out, inn);
  const H = planLeft(g), span = planSpan(g);
  const head = `<div class="rp-h"><b>${esc(po.name)} → ${esc(pi.name)}</b><span class="muted">from GW${g}</span></div>`;
  if (why) return `<div class="rp" role="region" aria-label="Preview: ${esc(pi.name)} for ${esc(po.name)}">${head}<p class="verdict" style="margin:0">${esc(why)}</p></div>`;
  const before = scoreMoves(SB.moves), mv = replaceWith(g, out, inn), after = scoreMoves(mv, null, SB.chips || {});
  const base = baseScore(), wk = after.weeks.find(w => w.gw === g);
  const ind = xpFrom(inn, g, H) - xpFrom(out, g, H);
  const team = after.tot - before.tot;
  const hitsB = before.weeks.reduce((a, w) => a + w.hits, 0), hitsA = after.weeks.reduce((a, w) => a + w.hits, 0);
  const value = gainVsNone(after, base) - gainVsNone(before, base);
  // a later planned move of the same player is replaced by this one (makeTransfer's rule): say which, as it moves points
  const gone = SB.moves.filter(m => !mv.some(x => x.gw === m.gw && x.out === m.out && x.in === m.in) && !(m.gw === g && m.in === out));
  const later = after.weeks.filter(w => w.bank < 0 || w.over.length).map(w => `GW${w.gw}: ${w.bank < 0 ? `over budget by ${money(-w.bank)}` : `more than 3 from ${w.over.join(", ")}`}`);
  const cls = x => x > 0.05 ? "up" : x < -0.05 ? "down" : "";
  return `<div class="rp" role="region" aria-label="Preview: ${esc(pi.name)} for ${esc(po.name)}">${head}
    <p class="rp-base">Compared with your active plan, ${span} (${H} GW${H === 1 ? "" : "s"}).</p>
    <dl class="rp-g">
      <div><dt>${esc(pi.name)} vs ${esc(po.name)}</dt><dd class="${cls(ind)}">${sgn(ind)}</dd><dd class="pe-s">player xP: ${f1(xpFrom(inn, g, H))} vs ${f1(xpFrom(out, g, H))}</dd></div>
      <div><dt>Team projected points</dt><dd class="${cls(team)}">${sgn(team)}</dd><dd class="pe-s">plan total ${f1(before.tot)} → ${f1(after.tot)}, after hits</dd></div>
      <div><dt>Hit cost</dt><dd class="${hitsA > hitsB ? "down" : ""}">${hitsA > hitsB ? "−" + 4 * (hitsA - hitsB) : "No hit"}</dd><dd class="pe-s">${hitsA > hitsB ? "included in team points" : `${Math.max(0, wk.ft - wk.n)} free transfer${wk.ft - wk.n === 1 ? "" : "s"} left in GW${g}`}</dd></div>
      <div><dt>Bank after GW${g}</dt><dd class="${wk.bank < 0 ? "down" : ""}">${money(wk.bank)}</dd><dd class="pe-s">${wk.next} free transfer${wk.next === 1 ? "" : "s"} next week</dd></div>
    </dl>
    <p class="rp-val">Planning value ${sgn(value)}: team points plus ${f1(ftValue())} for each free transfer banked at the end (${after.ftLeft} vs ${before.ftLeft}). Not projected points.${SB.solved ? " The optimiser's own lineups are replaced by automatic picks once you edit, and that is counted in team points." : ""}</p>
    ${Math.abs(ind - team) > 0.05 ? `<p class="rp-val">The team figure differs from the player figure because only starters and the captain score: ${esc(pi.name)} may not start every week, lineups and captains are re-picked${gone.length ? ", and the move it replaces no longer counts" : ""}.</p>` : ""}
    ${gone.length ? `<p class="rp-warn">This replaces your planned ${gone.map(m => `GW${m.gw} move ${esc(P[m.out].name)} → ${esc(P[m.in].name)}`).join(" and ")}, which is counted in the team figure.</p>` : ""}
    ${later.length ? `<p class="rp-warn">${later.join(". ")}. You can still add it and fix that week later.</p>` : ""}
    <div class="acts"><button class="btn primary" data-pickadd="${inn}">Add ${esc(pi.name)} to plan</button><button class="btn" data-pickclose="1">Not now</button></div></div>`;
}
function candidates() {
  const g = SB.gw, out = SB.sel, po = P[out];
  const sq = squadAt(g);
  const budget = bankAt(g) + (D.squad.some(s => s.id === out) && !SB.moves.some(m => m.in === out) ? sellPrice(out) : po.price);
  const cc = clubCounts(sq.filter(i => i !== out));
  const q = (SB.q || "").toLowerCase();
  const H = PG.filter(x => x >= g).length;
  const base = xpFrom(out, g, H);
  const list = D.players.filter(p => p.pos === po.pos && !sq.includes(p.id) && p.ok !== false && p.price <= budget + 1e-9 && (cc[p.team] || 0) < 3 && (!q || (p.name + " " + p.full).toLowerCase().includes(q)))
    .map(p => ({ p, v: xpFrom(p.id, g, H) })).sort((a, b) => b.v - a.v).slice(0, 30);
  return `<div class="bar"><h3>Replace ${esc(po.name)} from GW${g}</h3><button class="btn" data-cancel="1">Cancel</button></div>
    <p class="note" style="margin-top:0">Budget ${money(budget)} · ${esc(po.name)} projects ${f1(base)} over the rest of the plan (${H} GW${H === 1 ? "" : "s"}). Each row: the player's xP over the same weeks and the difference from ${esc(po.name)}. Choose one to preview the move.</p>
    <div class="filters"><input type="search" id="candq" placeholder="Search ${po.pos}s" value="${esc(SB.q)}" aria-label="Search replacements"></div>
    <div class="candlist">${list.map(({ p, v }) => `<button class="cand${SB.pick === p.id ? " on" : ""}" data-pick="${p.id}" aria-expanded="${SB.pick === p.id}"><span class="pname">${esc(p.name)} <span class="muted">${T[p.team].short} · ${money(p.price)}</span>${playerTags(p, 2)}</span><span class="${v > base ? "up" : "down"} mono">${sgn(v - base)}</span><b>${f1(v)}</b><span class="d">${GWS.filter(x => x >= g).slice(0, 4).map(x => `GW${x} ${fxFor(p.team, x).map(oppTxt).join("+") || "–"} ${xpCell(p.id, x)}`).join(" · ")}${p.status !== "a" ? ` · <span class="down">${esc(p.news)}</span>` : ""}</span></button>${SB.pick === p.id ? replacePreview(g, out, p.id) : ""}`).join("") || `<p class="muted">No affordable ${po.pos}s fit the budget and club limits.</p>`}</div>`;
}
