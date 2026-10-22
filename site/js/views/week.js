// This week.
/* ---------- This week ---------- */
function modeBar() {
  if (!D.plans?.safe_roll) return "";
  return `<div class="panel" style="padding:12px 14px"><div class="bar" style="margin:0"><span class="lbl">${term("strategy", "Strategy")}</span>
    <div class="seg" role="group" aria-label="Strategy">${Object.entries(MODES).map(([k, l]) => `<button data-mode="${k}" aria-pressed="${S.mode === k}">${l}</button>`).join("")}</div></div>
    <p class="note" style="margin:8px 0 0">${MODE_HELP[S.mode]}</p></div>`;
}
function vWeek() {
  const g = D.meta.next_gw, pl = D.plans || {};
  if (!PG.length) return `<div class="panel"><p>No gameweek to plan yet.</p></div>`;
  const rec = recommendedPlan(), me = myTeam(), w0 = me.week, ft = D.manager.free_transfers;
  const base = baseScore().tot, myGain = me.score.tot - base;
  const moves0 = me.moves0, later = me.later;
  const roll = scoreMoves(planMoves(pl[mk("roll")]));
  const vsRoll = (me.score.tot + 1.5 * me.score.ftLeft) - (roll.tot + 1.5 * roll.ftLeft);

  const tV = moves0.length ? verdict(vsRoll) : verdict(-vsRoll + 1, 3, 1.5);
  const t1 = moves0.length ? `Make ${moves0.length} transfer${moves0.length > 1 ? "s" : ""}${w0.hits ? ` (−${4 * w0.hits} hit)` : ""}` : `Roll your transfer${ft > 1 ? "s" : ""}`;
  const mvHTML = moves0.length ? `<div class="moves">${moves0.map(m => `<div class="move"><span class="out">▼ ${esc(P[m.out].name)}</span><span class="in">▲ ${esc(P[m.in].name)}</span><span class="muted mono">${money(P[m.in].price)} · ${T[P[m.in].team].short}</span></div>`).join("")}</div>` : "";
  const t1why = moves0.length
    ? `${vsRoll >= 0 ? sgn(vsRoll) : sgn(vsRoll)} projected points over ${PG.length} GWs compared with rolling, after valuing banked transfers at 1.5 pts each.`
    : `Nothing beats rolling by enough. You'll have ${Math.min(5, ft + 1)} free transfers next week.`;
  const undo = SB.prev ? ` <button class="btn" data-undoplan="1">Undo plan change</button>` : "";

  // lineup
  const curXI = new Set(D.lineup.current_xi || []), newXI = new Set(me.xi);
  const starts = me.xi.filter(i => !curXI.has(i)), benches = [...curXI].filter(i => !newXI.has(i) && me.bench.includes(i));
  const lineupTxt = starts.length || benches.length
    ? `${starts.length ? `Start <b>${starts.map(i => esc(P[i].name)).join(", ")}</b>` : ""}${starts.length && benches.length ? "; " : ""}${benches.length ? `bench <b>${benches.map(i => esc(P[i].name)).join(", ")}</b>` : ""}`
    : "Keep last week's starting XI";
  const benchFirst = me.bench.filter(i => P[i].pos !== "GKP")[0], weakest = me.xi.filter(i => P[i].pos !== "GKP").sort((a, b) => xpg(a, g) - xpg(b, g))[0];
  const benchGap = benchFirst && weakest ? xpg(weakest, g) - xpg(benchFirst, g) : 9;
  const lV = benchGap < 0.3 ? { t: "Close call", c: "mut" } : { t: "Clear", c: "good" };

  // captain
  const capOpts = me.xi.slice().sort((a, b) => xpg(b, g) - xpg(a, g)).slice(0, 5), cmax = xpg(capOpts[0], g) || 1;
  const capGap = xpg(me.cap, g) - xpg(me.vice, g);
  const F = D.crowd ? (D.crowd.near?.n >= 100 ? D.crowd.near : D.crowd.top10k) : null;
  const capEO = F ? (F.cap[me.cap] || 0) : null;
  const cV = capEO != null && capEO >= 50 && capGap > -0.3 ? { t: "Safe pick", c: "good" }
    : me.swapped ? { t: "Coin flip", c: "mut" } : verdict(capGap, 1, 0.4);
  const capNote = me.capMine ? `Your choice, set in the planner. The model's pick would be ${esc(P[capPick(me.xi, g).cap].name)}.` : me.swapped
    ? `${esc(P[me.swapped].name)} projects ${f1(xpg(me.swapped, g) - xpg(me.cap, g))} more on clean-sheet odds, but that's too small a gap to give up ${esc(P[me.cap].name)}'s much higher ceiling.`
    : `${f1(capGap)} pts ahead of ${esc(P[me.vice].name)}.`;

  // chip
  const tc = D.chips.find(c => c.key === "3xc" && c.available && c.to <= 19);
  const tcWeeks = me.score.weeks.map(w => ({ gw: w.gw, id: w.team.cap, x: xpg(w.team.cap, w.gw) }));
  const bestTc = tcWeeks.reduce((a, r) => (!a || r.x > a.x) ? r : a, null);
  const chipNow = tc && bestTc && bestTc.gw === g && bestTc.x >= 6.5;
  const chipTxt = chipNow ? `Consider Triple Captain on ${esc(P[bestTc.id].name)}` : "No chip this week";
  const chipSub = tc ? `Triple Captain (first half) is unused and expires after GW${tc.to}.${bestTc ? ` Best spot in view: GW${bestTc.gw} (${esc(P[bestTc.id]?.name)}, ${f1(bestTc.x)} xP).` : ""} It's worth most in a double gameweek.` : "Your other first-half chips are used. The second set unlocks in GW20.";

  // risks
  const risks = [];
  me.week.sq.forEach(i => {
    const p = P[i]; if (!p) return;
    if (p.status !== "a") risks.push(["bad", `<b>${esc(p.name)}</b>: ${esc(p.news || "flagged")}`]);
    const pr = p.price_proj?.[0];
    if (pr != null && pr <= -80) risks.push(["warn", `<b>${esc(p.name)}</b> may drop in price tonight (${pr.toFixed(0)}% of the way).`]);
    if (newXI.has(i) && p.mflag && p.mflag.startsWith("Dropped")) risks.push(["warn", `<b>${esc(p.name)}</b>: ${esc(p.mflag)}.`]);
    else if (newXI.has(i) && p.status === "a" && p.nailed < 60) risks.push(["warn", `<b>${esc(p.name)}</b> is starting but isn't nailed on (${p.nailed}/100).`]);
    const eu = fxFor(p.team, g).find(x => x.eu);
    if (newXI.has(i) && eu && p.nailed < 95 && p.status === "a") risks.push(["info", `<b>${esc(p.name)}</b>: ${T[p.team].short} played ${esc(eu.eu)}. Slight rotation risk.`]);
  });
  if (w0.bank < 0) risks.push(["bad", `Your plan is ${money(-w0.bank)} over budget in GW${g}.`]);
  if (w0.over.length) risks.push(["bad", `Your plan has more than 3 players from ${w0.over.join(", ")}.`]);
  threats(2).forEach(r => risks.push(["warn", `<b>${esc(P[r.id].name)}</b> is in ${r.own.toFixed(0)}% of top-10k teams and not in yours. If he hauls, you lose ground (${sgn(r.impact)} projected).`]));
  moves0.forEach(m => { const pr = P[m.in].price_proj?.[0]; if (pr != null && pr >= 80) risks.push(["good", `<b>${esc(P[m.in].name)}</b> may rise tonight. Buy before the next price update.`]); });
  const bad = risks.filter(r => r[0] === "bad" || r[0] === "warn").length;

  const sp = spreadVsField(me.mult, g);
  const step = (n, state, title, pill, doTxt, details) => `<div class="stepcard ${state}"><span class="no">${state === "ok" ? "✓" : n}</span><div class="sbody">
    <h3>${title} ${pill ? `<span class="pillwrap">${pill}</span>` : ""}</h3><div class="do">${doTxt}</div>${details ? `<details><summary>Details</summary><div class="dbody">${details}</div></details>` : ""}</div></div>`;
  return `
  <div class="grid2">
    <div class="steps">
      <div class="bar" style="margin:0"><h2>Before the GW${g} deadline</h2><span>${term("verdict", "What the labels mean")}</span><span class="muted">${countdown(D.meta.deadline)} left</span></div>
      ${step(1, moves0.length ? "act" : "ok", "Transfers", vPill(tV), `${t1}${mvHTML}`,
        `<p class="sub">${t1why}${later.length ? ` Your plan has ${later.length} more move${later.length > 1 ? "s" : ""} in later weeks.` : ""} Bank after: ${money(w0.bank)}.</p>
         <p class="sub">Strategy: <b>${MODES[S.mode]}</b>. Change it, compare the optimiser's plans and see transfer suggestions in the Planner.</p>
         <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" data-v-go="planner">Open planner</button>${undo}</div>`)}
      ${step(2, starts.length || benches.length ? "act" : "ok", "Lineup", vPill(lV), lineupTxt,
        `<p class="sub">Best XI projects <b>${f1(me.pts)}</b> pts including the captain. Bench order: ${me.bench.map(i => esc(P[i].name)).join(", ")}.${benchFirst ? ` First sub ${esc(P[benchFirst].name)} (${f1(xpg(benchFirst, g))}) vs weakest starter ${esc(P[weakest].name)} (${f1(xpg(weakest, g))}).` : ""}</p>`)}
      ${step(3, "act", "Captain", vPill(cV), `C ${esc(P[me.cap].name)} · V ${esc(P[me.vice].name)}`,
        `<p class="sub">${capNote}${capEO != null ? ` ${capEO.toFixed(0)}% of managers around your rank captained ${esc(P[me.cap].name)} last week.` : ""}</p>
         <div class="capbars">${capOpts.map(i => `<div class="cb ${i === me.cap ? "top" : ""}"><span class="pname">${esc(P[i].name)}<br><span class="muted" style="font-weight:400;font-size:12.5px">${fxText(P[i], g)}</span></span><div class="track"><div class="fill" style="width:${xpg(i, g) / cmax * 100}%"></div></div><span class="val">${f1(xpg(i, g))}</span></div>`).join("")}</div>`)}
      ${step(4, chipNow ? "act" : "ok", "Chip", "", chipTxt, `<p class="sub">${chipSub}</p>`)}
      ${step(5, bad ? "act" : "ok", "Risks", bad ? `<span class="pill warn">${bad} to check</span>` : `<span class="pill good">Clear</span>`, bad ? risks.filter(r => r[0] === "bad" || r[0] === "warn").slice(0, 2).map(r => r[1]).join("<br>") : "No injury flags, price drops or minutes worries.",
        risks.length ? `<ul class="alerts">${risks.map(([c, t]) => `<li class="${c}"><span>${t}</span></li>`).join("")}</ul>` : "")}
    </div>
    <div style="min-width:0;display:grid;gap:10px;align-content:start">
      <div class="bar" style="margin:0"><h3>GW${g} team · ${esc(planName())}</h3><span class="tag">${f1(me.pts)} ${term("xp", "xP")}${sp != null ? ` · ±${f1(sp)} ${term("spread", "vs field")}` : ""}</span></div>
      ${pitch(me.xi, me.bench, g, { cap: me.cap, vice: me.vice, fresh: new Set(moves0.map(m => m.in)) })}
      <p class="note">The team from your plan, also used by Planner and Rivals. Big number = projected points. Chips show the next 3 opponents (capitals = home). ${sp != null ? `<b>±${f1(sp)}</b> is how far your score typically lands from the managers around your rank: lower means safer.` : ""}</p>
    </div>
  </div>`;
}
