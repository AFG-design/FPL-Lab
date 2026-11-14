// This week.
/* ---------- This week ---------- */
const rankShort = n => n >= 1e6 ? (n / 1e6).toFixed(1) + "m" : n >= 1e4 ? Math.round(n / 1e3) + "k" : rankFmt(n);
// Everything the homepage's Next deadline view says about the coming deadline, worked out once from the plan
// (the same scorer, verdicts and risk checks the old single-page homepage used). Returns null when there's no
// gameweek to plan.
// Missing data: no roll plan from the optimiser (build.py failed to solve) -> rolling is scored as "no moves" with
// the same scorer, which is what the roll plan is; no field ownership -> an unavailable captain ownership note and no template
// threats; no haul distribution -> no haul line.
function weekCalls() {
  const g = D.meta.next_gw, pl = D.plans || {};
  if (!PG.length || !g) return null;
  const me = myTeam(), w0 = me.week, ft = D.manager.free_transfers;
  const moves0 = me.moves0, later = me.later;
  const roll = pl[mk("roll")] ? scoreMoves(planMoves(pl[mk("roll")])) : baseScore();
  // projected points and the assumed value of banked transfers, kept apart so neither hides in the other
  // banked free transfers at the build's value (plan_rules.ft_value via ftValue(), FL-075; it was a fixed 1.5 here)
  const ptsVsRoll = me.score.tot - roll.tot, ftBank = ftValue() * (me.score.ftLeft - roll.ftLeft);
  const vsRoll = ptsVsRoll + ftBank;
  const tV = moves0.length ? verdict(vsRoll) : verdict(-vsRoll + 1, 3, 1.5);
  // lineup
  const curXI = new Set(D.lineup.current_xi || []), newXI = new Set(me.xi);
  const starts = me.xi.filter(i => !curXI.has(i)), benches = [...curXI].filter(i => !newXI.has(i) && me.bench.includes(i));
  const benchFirst = me.bench.filter(i => P[i].pos !== "GKP")[0], weakest = me.xi.filter(i => P[i].pos !== "GKP").sort((a, b) => xpg(a, g) - xpg(b, g))[0];
  const benchGap = benchFirst && weakest ? xpg(weakest, g) - xpg(benchFirst, g) : 9;
  // lineup: the gap between your weakest starter and first sub, on the one-week scale (CUT_WEEK: 2 pts Strong, 1.5 Marginal).
  // No bench outfielder to compare (benchGap 9): nothing to weigh, so Strong.
  const lV = verdict(benchGap, ...CUT_WEEK);
  // captain
  const capOpts = me.xi.slice().sort((a, b) => xpg(b, g) - xpg(a, g)).slice(0, 5);
  const alt = capOpts.find(i => i !== me.cap);
  const capGap = xpg(me.cap, g) - xpg(me.vice, g);
  const capSample = fieldSample(), F = capSample?.data;
  const capEO = F ? (F.cap[me.cap] || 0) : null;
  // captain: confidence from the projection only; following the field is shown beside it, not instead of it.
  // No field ownership (capEO null): no tag, never a guess.
  const cV = { ...verdict(capGap, ...CUT_WEEK), tag: capEO != null && capEO >= 50 ? "Field's pick" : null };
  // chip
  const tc = D.chips.find(c => c.key === "3xc" && c.available && c.to <= 19);
  const tcWeeks = me.score.weeks.map(w => ({ gw: w.gw, id: w.team.cap, x: xpg(w.team.cap, w.gw) }));
  const bestTc = tcWeeks.reduce((a, r) => (!a || r.x > a.x) ? r : a, null);
  const chipNow = !!(tc && bestTc && bestTc.gw === g && bestTc.x >= 6.5);
  // risks: [class, html], worst first as found
  const risks = [];
  w0.sq.forEach(i => {
    const p = P[i]; if (!p) return;
    if (p.status !== "a") risks.push(["bad", `<b>${esc(p.name)}</b>: ${esc(p.news || "flagged")}`]);
    const pr = p.price_proj?.[0];
    if (priceFalling(pr) && fallCostsYou(i)) risks.push([priceTonight(pr) ? "warn" : "info", `<b>${esc(p.name)}</b> ${priceTonight(pr) ? `may drop in price tonight (${pr.toFixed(0)}% of the way)` : priceMove(pr)}.`]);
    if (newXI.has(i) && p.mflag && p.mflag.startsWith("Dropped")) risks.push(["warn", `<b>${esc(p.name)}</b>: ${esc(p.mflag)}.`]);
    else if (newXI.has(i) && p.status === "a" && p.nailed < 60) risks.push(["warn", `<b>${esc(p.name)}</b> is starting but isn't nailed on (${p.nailed}/100).`]);
    const eu = fxFor(p.team, g).find(x => x.eu);
    if (newXI.has(i) && eu && p.nailed < 95 && p.status === "a") risks.push(["info", `<b>${esc(p.name)}</b>: ${T[p.team].short} played ${esc(eu.eu)}. Slight rotation risk.`]);
  });
  if (w0.bank < 0) risks.push(["bad", `Your plan is ${money(-w0.bank)} over budget in GW${g}.`]);
  if (w0.over.length) risks.push(["bad", `Your plan has more than 3 players from ${w0.over.join(", ")}.`]);
  threats(2).forEach(r => risks.push(["warn", `<b>${esc(P[r.id].name)}</b> is in ${r.own.toFixed(0)}% of top-10k teams and not in yours. If he hauls, you lose ground (${sgn(r.impact)} projected).`]));
  moves0.forEach(m => { const pr = P[m.in].price_proj?.[0]; if (priceRising(pr)) risks.push(["good", priceTonight(pr) ? `<b>${esc(P[m.in].name)}</b> may rise tonight. Buy before the next price update.` : `<b>${esc(P[m.in].name)}</b> is ${priceMove(pr)}.`]); });
  return { g, me, w0, ft, moves0, later, roll, ptsVsRoll, ftValue: ftBank, vsRoll, tV, starts, benches, benchFirst, weakest, benchGap, lV,
    capOpts, alt, capGap, capEO, capSample, cV, tc, bestTc, chipNow, risks };
}
// the homepage route: two views (views/home.js)
function vWeek() { return vHome(); }
