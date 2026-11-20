// Read-only decision drafts. All scoring uses the Planner; only explicit Save / Make active writes a plan.
// Missing solver/data or an invalid route is explained, never replaced with an invented projection.
let DECISION = null;
const decisionScore = d => withDraft(d, () => scoreMoves(d.moves, d.solved, d.chips || {}));
function decisionValid(d) {
  if (d.moves.some(m => !P[m.in] || !P[m.out]) || cleanMoves(d.moves, d.chips).length !== d.moves.length) return false;
  const sc = decisionScore(d);
  return sc.weeks.length && sc.weeks.every(w => w.bank >= 0 && !w.over.length && w.sq.length === 15 && new Set(w.sq).size === 15 && w.team.xi.length === 11 && (d.mode === "chase" || !w.hits));
}
function decisionAlternative() {
  return pvKeys(S.mode).map(k => {
    const moves = planMoves(D.plans[k]), sc = withMode(S.mode, () => planScore(D.plans[k], moves));
    return { ...completePlan({ moves, ov: {}, chips: {}, solved: solvedFrom(sc), mode: S.mode }), name: planLabel(k) };
  }).find(d => d.moves.some(m => m.gw === PG[0]) && decisionValid(d));
}
function decisionMoves(d) {
  return d.moves.filter(m => PG.includes(m.gw)).map(m => `<li>GW${m.gw}: ${esc(P[m.out]?.name)} → ${esc(P[m.in]?.name)}</li>`).join("") || "<li>No transfers across this horizon.</li>";
}
async function openDecision(kind = "roll", keep = null) {
  if (!PG.length || SOLVE.busy) return;
  const a = { ...completePlan(), name: "Suggested route" };
  if (kind === "roll" && !a.moves.some(m => m.gw === PG[0])) {
    const alternative = decisionAlternative();
    if (!alternative) return;
    Object.assign(a, alternative);
  }
  const state = DECISION = { a, b: null, title: kind === "captain" ? "Compare my captain" : kind === "keep" ? `What if I keep ${P[keep]?.name}?` : "Compare with saving the transfer", kind, keep, scope: sbKey(), built: D.meta.built, horizon: PG.join(), busy: true };
  if (kind === "captain") {
    const sc = decisionScore(a), w = sc.weeks[0];
    a.name = `Captain ${P[w.team.cap].name}`;
    state.original = completePlan(a); state.xi = w.team.xi.slice(); state.cap = w.team.cap;
    state.busy = false; setDecisionCaptain(w.team.xi.filter(i => i !== w.team.cap).sort((a, b) => xpg(b, PG[0]) - xpg(a, PG[0]))[0]); return;
  }
  drawDecision(); SOLVE.busy = true;
  try {
    if (["wildcard", "freehit"].includes(chipAt(PG[0], a.chips))) throw new Error("A Wildcard or Free Hit is pinned this week. Remove that pin in the Planner before comparing a saved transfer.");
    const rules = { locked: kind === "keep" ? [...new Set([...SB.rules.locked, keep])] : [], banned: kind === "keep" ? SB.rules.banned.filter(i => i !== keep) : [], maxHits: SB.rules.maxHits };
    const result = await optimiseMoves(a.mode, { rules, chips: a.chips, week1Moves: kind === "roll" ? 0 : null });
    state.b = { ...completePlan({ ...result, chips: a.chips, ov: {}, mode: a.mode }), name: kind === "keep" ? `Keep ${P[keep].name}` : "Save the transfer" };
    if ((kind === "roll" && state.b.moves.some(m => m.gw === PG[0])) || (kind === "keep" && state.b.moves.some(m => m.out === keep)) || !decisionValid(state.b)) throw new Error("No legal saving route could be evaluated with this data.");
  } catch (e) { state.error = e.message; }
  finally { SOLVE.busy = false; state.busy = false; if (DECISION === state && $("#dlg").open) drawDecision(); }
}
function setDecisionCaptain(id) {
  const d = DECISION, g = PG[0]; if (!d.xi.includes(id)) return;
  const sc = decisionScore(d.original), w = sc.weeks[0];
  // Freeze every XI and captain, then change exactly one armband. TC adds two copies, otherwise one.
  const fixed = completePlan(d.original);
  fixed.ov = Object.fromEntries(sc.weeks.map(w => [w.gw, { start: w.team.xi.slice(), bench: w.team.bench.slice(), order: w.team.bench.slice(), cap: w.team.cap, vice: w.team.vice }]));
  d.a = { ...completePlan(fixed), name: `Captain ${P[d.cap].name}` };
  d.b = { ...completePlan(fixed), name: `Captain ${P[id].name}` };
  d.b.ov[g].cap = id; d.b.ov[g].vice = id === w.team.vice ? d.cap : w.team.vice;
  d.selected = id; drawDecision();
}
function drawDecision() {
  const d = DECISION, g = PG[0], stale = d.scope !== sbKey() || d.built !== D.meta.built || d.horizon !== PG.join();
  const scores = d.b && !stale ? [decisionScore(d.a), decisionScore(d.b)] : null;
  const diff = scores ? scores[0].tot - scores[1].tot : 0;
  const value = scores ? diff + ftBonus(scores[0].ftLeft) - ftBonus(scores[1].ftLeft) : 0;
  const card = (p, sc, k) => `<section class="panel"><h3>${esc(p.name)}</h3><p><b>${f1(sc.tot)} projected points after hits</b></p>
    <p>${money(sc.weeks[0].bank)} remaining after GW${g} · ${sc.weeks[0].next} free transfers next gameweek.</p>
    <p>Hits across the horizon: −${4 * sc.weeks.reduce((n, w) => n + w.hits, 0)} points.</p><ul>${decisionMoves(p)}</ul>
    <div class="acts"><button class="btn" data-decision-save="${k}" ${getDrafts().length >= 3 || !decisionValid(p) ? "disabled" : ""}>Save as an alternative</button><button class="btn primary" data-decision-use="${k}" ${!decisionValid(p) ? "disabled" : ""}>Make this my active plan</button></div></section>`;
  $("#dlgBody").innerHTML = `<button class="x" id="decisionClose" aria-label="Close comparison">×</button><h2 id="decisionTitle">${esc(d.title)}</h2>
    <p>From your current squad · GW${g}–${PG.at(-1)} (${PG.length} weeks). Previewing preserves your active plan.</p>
    ${d.kind === "keep" ? `<p class="note">Assumption: keep ${esc(P[d.keep]?.name)} throughout these ${PG.length} weeks. Other legal transfers may be chosen.</p>` : d.kind === "captain" ? `<div class="filters"><label for="decisionCaptain">Alternative captain</label><select class="sel" id="decisionCaptain">${d.xi.filter(i => i !== d.cap).map(i => `<option value="${i}" ${i === d.selected ? "selected" : ""}>${esc(P[i].name)}</option>`).join("")}</select></div><p class="note">Same lineup, transfers and chip in both routes. Only GW${g} captaincy changes (vice swaps if needed).</p>` : `<p class="note">Saving means zero transfers in GW${g}; later weeks may include moves.</p>`}
    ${stale ? '<p role="status">Data or planning weeks changed. Close and reopen this comparison to recalculate.</p>' : d.busy ? '<p role="status">Finding a legal route…</p>' : d.error ? `<p role="alert">${esc(d.error)}</p>` : scores ? `<p class="verdict">${esc(d.a.name)}: <b>${sgn(diff)} projected points</b> versus ${esc(d.b.name)} over ${PG.length} weeks, after hits. ${vPill(d.kind === "captain" ? verdict(Math.abs(diff), ...CUT_WEEK) : verdict(Math.abs(value)))}</p><p class="note">${d.kind === "captain" ? `Confidence uses the existing captain scale for GW${g}; later weeks are identical.` : ftScale() ? `Confidence includes banked free transfers left at the end on a falling scale (${ftScale().map(f1).join("/")}; ${scores[0].ftLeft} vs ${scores[1].ftLeft}). Later moves shown below are assumptions, not commitments.` : `Confidence includes ${f1(ftValue())} assumed points per free transfer left at the end (${scores[0].ftLeft} vs ${scores[1].ftLeft}). Later moves shown below are assumptions, not commitments.`}</p><div class="grid2">${card(d.a, scores[0], "a")}${card(d.b, scores[1], "b")}</div>` : ""}
    ${getDrafts().length >= 3 ? '<p class="note">Three alternatives saved. Delete one in Planner → Drafts to save another.</p>' : ""}`;
  const dlg = $("#dlg"); dlg.setAttribute("aria-labelledby", "decisionTitle"); if (!dlg.open) dlg.showModal();
  $("#decisionClose").onclick = () => dlg.close();
  if ($("#decisionCaptain")) $("#decisionCaptain").onchange = e => setDecisionCaptain(+e.target.value);
  document.querySelectorAll("[data-decision-use], [data-decision-save]").forEach(b => b.onclick = () => {
    if (stale || d.built !== D.meta.built || d.scope !== sbKey()) return;
    const p = d[b.dataset.decisionUse || b.dataset.decisionSave]; if (!decisionValid(p)) return;
    if (b.dataset.decisionUse) { activatePlan(p, "custom"); dlg.close(); render(); toast("Comparison is now your active plan. Undo is available in the Planner."); }
    else { const ds = getDrafts(); if (ds.length >= 3) return; ds.push(tpStamp({ ...p, id: tpId(), saved: Date.now(), from: d.title })); setDrafts(ds); drawDecision(); toast("Saved as an alternative. Your active plan is unchanged."); }
  });
}
