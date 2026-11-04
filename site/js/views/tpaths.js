// Planner → Transfer paths: every path over the same horizon in one table, from the same starting squad and forecast.
//   Rows     Hold (no transfers, the baseline), each model strategy the build has, your saved paths (the Drafts in
//            Your plan: same storage, same limit of 3, same sync) and, if it isn't one of those, your active plan.
//   Cells    projected team points for the gameweek, before transfer penalties, with the moves and any hit under it.
//   Net xP   the path's total after hits (scoreMoves' tot: the sum of the cells minus 4 per hit, taken once).
//   vs Hold  Net xP minus Hold's Net xP.
// Each row is scored the way it is scored once it's your plan (plan.js scoreMoves), so Use plan shows the same total in
// Your plan, This week and Rivals: Hold and the model rows with Balanced's lineup rule (or the optimiser's own lineups
// for the model rows), a saved path with the strategy, lineup and captain choices it was saved with.
//
// Missing, late or ambiguous data:
//   - A strategy the build has no plan for: its row says so, no numbers. Weeks past the optimiser's plan (a 6-GW view of
//     a 5-GW plan) are marked * and filled with no transfers and the best XI (planner-views.js planScore).
//   - Forecasts: every row is recalculated on the current data.json, so all totals share one forecast. A saved path
//     remembers its Net xP when it was saved (net, over h gameweeks); if the forecast has since moved it by 0.5 or more
//     over the same horizon, the row says so with the old figure. Paths saved before this was recorded show no flag.
//   - Plan expiry (D4): a saved path also remembers, for the players it relies on (everyone it brings in and every
//     captain it picks), their FPL status, chance of playing, club and number of matches in each gameweek it covers.
//     If any of these has since got worse or changed (fit -> doubtful or out, a lower chance, a blank or a moved
//     fixture, a new club), the row shows "Review" with each change listed. Improvements (a player back to fit, a new
//     double) are listed too but don't trigger the flag on their own. Saving the path again clears it. Paths saved
//     before this was recorded show no flag; a player no longer in the data is already shown as dropped.
//   - Squad changes (a new gameweek, a Free Hit restore): saved paths are stored per squad, so paths made for your
//     previous squad show as "needs recalculating" with no totals until you recalculate (moves that no longer apply are
//     dropped, and the row says how many) or discard them.
//   - A saved move naming a player no longer in the data is dropped and the row says so. A path over budget or over the
//     club limit in any week is flagged on its row and in the detail strip; its numbers are shown but marked invalid.
//   - Money: bank after moves uses your real selling prices for players you own now and today's prices for players
//     bought in the path (plan.js bankAt). Squad value is market value at today's prices, without cash. Price changes
//     before a future gameweek aren't forecast, and the strip says so.

const TP = { sel: store.get("fpl.tpsel") || "hold", gw: null, form: false, settings: false, busy: false, msg: "", undo: null, del: null };
const tpMode = () => (["balanced", "safe", "chase"].includes(TP.mode) ? TP.mode : S.mode);
const tpId = () => "p" + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36);
const ovEmpty = ov => !Object.values(ov || {}).some(o => o && (o.start?.length || o.bench?.length || o.cap || o.vice || o.order?.length));
const capsOf = sc => sc.weeks.map(w => w.team.cap).join(",");
function withDraft(d, fn) {
  const keep = { ov: SB.ov, mode: S.mode };
  SB.ov = d.ov || {}; S.mode = MODES[d.mode] ? d.mode : S.mode;
  try { return fn(); } finally { SB.ov = keep.ov; S.mode = keep.mode; }
}
// the server optimiser's own lineups as a "solved" record, so the plan scores the same once it's yours
function solvedFrom(sc) {
  const out = {};
  sc.weeks.forEach(w => { if (!w.filled) out[w.gw] = { sq: w.sq.slice(), xi: w.team.xi.slice(), cap: w.team.cap }; });
  return out;
}
// vs Hold from the two Net figures as shown (to 0.1), so the row always adds up on screen
const r1 = x => Math.round(x * 10) / 10;
const tpGain = (r, hold) => r1(r1(r.sc.tot) - r1(hold.sc.tot));
// a saved path's Net xP now, so a later forecast change can be shown against it; and what it relies on (tpDeps)
function tpStamp(d) {
  const moves = cleanMoves(d.moves.filter(m => P[m.in] && P[m.out] && GWS.includes(m.gw)));
  const sc = withDraft(d, () => scoreMoves(moves, d.solved || null));
  return { ...d, net: r1(sc.tot), h: PG.length, built: D.meta.built, deps: tpDeps(moves, sc) };
}
// the players a path relies on (signings and captains), as they stood: [status, chance, club, {gw: matches}]
function tpDeps(moves, sc) {
  const ids = new Set([...moves.map(m => m.in), ...sc.weeks.map(w => w.team.cap)].filter(i => P[i]));
  const out = {};
  ids.forEach(i => { const p = P[i]; out[i] = [p.status, p.chance ?? null, p.team, Object.fromEntries(PG.map(g => [g, fxFor(p.team, g).length]))]; });
  return out;
}
const chanceOf = (st, ch) => st === "a" && ch == null ? 100 : ch == null ? (["i", "s", "n", "u"].includes(st) ? 0 : 50) : ch;
const fxWord = n => n === 0 ? "a blank" : n === 1 ? "one match" : n === 2 ? "a double" : `${n} matches`;
// what has changed for those players since the path was saved: { worse: [text], better: [text] } or null (no record)
function tpChanges(d) {
  if (!d.deps) return null;
  const worse = [], better = [];
  for (const [id, [st, ch, team, fx]] of Object.entries(d.deps)) {
    const p = P[id]; if (!p) continue;                       // gone from the data: shown as "dropped" already
    const was = chanceOf(st, ch), now = chanceOf(p.status, p.chance), nm = p.name;
    if (now < was) worse.push(`${nm}: ${now === 0 ? `now out${p.news ? ` (${p.news})` : ""}` : `now ${now}% to play`} (was ${was}%)`);
    else if (now > was) better.push(`${nm}: now ${now === 100 ? "fit" : now + "%"} (was ${was}%)`);
    if (p.team !== team) { worse.push(`${nm}: now at ${T[p.team]?.short || "another club"}`); continue; }
    for (const [g, n] of Object.entries(fx)) {
      if (!PG.includes(+g)) continue;
      const m = fxFor(p.team, +g).length;
      if (m < n) worse.push(`${nm}: GW${g} now ${fxWord(m)} (was ${fxWord(n)})`);
      else if (m > n) better.push(`${nm}: GW${g} now ${fxWord(m)} (was ${fxWord(n)})`);
    }
  }
  return { worse, better };
}
const MOVED = 0.5;   // Net xP change, after a forecast update, worth flagging on a saved path
const tpProblems = sc => sc.weeks.filter(w => w.bank < 0 || w.over.length).map(w => `GW${w.gw}: ${w.bank < 0 ? `over budget by ${money(-w.bank)}` : `more than 3 from ${w.over.join(", ")}`}`);

/* ---------- rows ---------- */
function tpRows() {
  const rows = [{ key: "hold", name: "Hold / no transfers", sub: "Baseline", kind: "hold", sc: pvBase(), moves: [], ov: {}, mode: "balanced" }];
  const bal = pvStrat("balanced"), also = [];
  PV_MODES.forEach(m => {
    const r = pvStrat(m), name = `${MODES[m]} suggestion`;
    // a strategy that lands on exactly Balanced's plan (same moves, captains and total) is folded into its row
    if (m !== "balanced" && r.key && bal.key && sameMoves(r.moves, bal.moves) && Math.abs(r.sc.tot - bal.sc.tot) < 0.05 && capsOf(r.sc) === capsOf(bal.sc)) { also.push(m); return; }
    if (!r.key) { rows.push({ key: "m:" + m, name, kind: "model", mode: m, missing: m === "balanced" ? "The optimiser made no plans in this build." : "Needs field-ownership data, which isn't in this build." }); return; }
    const same = m !== "balanced" && sameMoves(r.moves, bal.moves || []);
    rows.push({ key: "m:" + m, name, sub: `Model · ${PV_VAR_LABEL[r.key.split("_").pop()]}${same ? " · Balanced's moves, different lineups" : ""}`, kind: "model", mode: m, pk: r.key,
      sc: r.sc, moves: r.moves, ov: {}, filled: r.filled, dropped: r.dropped, solved: solvedFrom(r.sc) });
  });
  const b = rows.find(r => r.key === "m:balanced");
  if (b && b.sc && also.length) { b.name = `Balanced${also.map(m => " · " + MODES[m]).join("")}`; b.sub += ` · ${also.map(m => MODES[m]).join(" and ")} make${also.length === 1 ? "s" : ""} the same plan`; b.also = also; }
  getDrafts().forEach((d, k) => {
    const valid = d.moves.filter(m => P[m.in] && P[m.out] && GWS.includes(m.gw));
    const moves = cleanMoves(valid), dropped = d.moves.length - moves.length;
    const sc = withDraft(d, () => scoreMoves(moves, d.solved || null));
    rows.push({ key: "d:" + (d.id || "i" + k), idx: k, name: d.name || `Path ${k + 1}`, kind: "draft", d, mode: MODES[d.mode] ? d.mode : S.mode,
      sub: `Saved · ${MODES[d.mode] || MODES[S.mode]}${d.from ? ` · from ${d.from}` : ""}`, sc, moves, ov: d.ov || {}, dropped, solved: d.solved || null,
      moved: d.net != null && d.h === PG.length && Math.abs(r1(sc.tot) - d.net) >= MOVED ? d : null, problems: tpProblems(sc),
      changes: tpChanges(d) });
  });
  // the active plan: marked on the row it matches (same moves, captains and total), otherwise a row of its own
  const act = scoreMoves(SB.moves), live = rows.filter(r => r.sc);
  const hit = live.find(r => sameMoves(r.moves, SB.moves) && Math.abs(r.sc.tot - act.tot) < 0.05 && capsOf(r.sc) === capsOf(act));
  if (hit) hit.active = true;
  else rows.push({ key: "active", name: "Your plan", sub: `Active · not saved as a path · ${MODES[S.mode]}`, kind: "active", active: true, sc: act, moves: SB.moves.slice(),
    ov: SB.ov, mode: S.mode, solved: SB.solved, problems: tpProblems(act) });
  tpOldDrafts().forEach((o, n) => rows.push({ key: "old:" + n, kind: "old", o, name: o.d.name || "Saved path", sub: `Made for your squad at the GW${o.gw} deadline` }));
  return rows;
}
// paths saved for a squad you no longer have (keys are per squad, see plan.js sbKey): this gameweek's and the last one's
function tpOldDrafts() {
  const pre = `fpl.sb.${D.meta.team_id}.`, cur = draftKey(), out = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (!k || !k.startsWith(pre) || !k.endsWith(".drafts") || k === cur) continue;
      const gw = +k.slice(pre.length).split(".")[0];
      if (!(gw >= D.meta.next_gw - 1)) continue;
      const list = store.get(k);
      if (Array.isArray(list)) list.forEach((d, j) => { if (d && Array.isArray(d.moves)) out.push({ k, j, d, gw }); });
    }
  } catch (e) {}
  return out;
}

/* ---------- page ---------- */
function vTpaths() {
  const rows = tpRows(), hold = rows[0], valid = rows.filter(r => r.sc);
  if (!valid.some(r => r.key === TP.sel) && !rows.some(r => r.key === TP.sel)) TP.sel = "hold";
  const sel = rows.find(r => r.key === TP.sel) || hold;
  const g = TP.gw && PG.includes(TP.gw) ? TP.gw : null;
  const nDrafts = getDrafts().length, full = nDrafts >= 3;
  // heat: each gameweek column shaded from its lowest to its highest projected score among the paths
  const heat = Object.fromEntries(PG.map(gw => {
    const v = valid.map(r => r.sc.weeks.find(w => w.gw === gw)?.team.pts ?? 0);
    return [gw, { lo: Math.min(...v), hi: Math.max(...v) }];
  }));
  const lvl = (gw, x) => { const h = heat[gw]; return h.hi - h.lo < 0.05 ? 1 : Math.round(1 + 4 * (x - h.lo) / (h.hi - h.lo)); };

  const optWhat = sel.kind === "draft" ? `Re-optimise “${sel.name}” (replaces its moves; Undo is offered)` : full ? "Optimising makes a new path, and 3 are already saved: delete one first" : `Optimise into a new path, starting from your confirmed squad`;
  const bar = `<div class="tp-bar">
      <h2>Transfer paths</h2>
      <button class="btn primary sm" data-tpopt="1" ${TP.busy || SOLVE.busy || (sel.kind !== "draft" && full) ? "disabled" : ""} title="${esc(optWhat)}">${TP.busy ? "Optimising…" : sel.kind === "draft" ? `Optimise “${esc(sel.name.length > 14 ? sel.name.slice(0, 13) + "…" : sel.name)}”` : "Optimise → new path"}</button>
      <button class="btn sm" data-tpnew="1" aria-expanded="${TP.form}" ${full ? `disabled title="3 paths saved: delete one to add another"` : ""}>+ New path</button>
      <div class="seg" role="group" aria-label="Plan length">${[3, 5, 6].filter(h => h <= GWS.length).map(h => `<button data-horizon="${h}" aria-pressed="${S.horizon === h}">${h} GWs</button>`).join("")}</div>
      <span class="tp-bar-r"><button class="btn sm" data-tpset="1" aria-expanded="${TP.settings}" aria-controls="tpSettings">Settings</button>
      <button class="btn sm" data-v-go="chips">Chips ↗</button></span>
    </div>
    <p class="tp-lead">Same squad, same forecast, GW${PG[0]}–GW${PG[PG.length - 1]}. Cells are projected points before hits; Net xP is after hits. ${nDrafts}/3 saved paths <span class="muted">(shared with Drafts in Your plan)</span>.</p>
    <p class="tp-msg" role="status" aria-live="polite">${TP.msg ? esc(TP.msg) : sel.kind === "draft" || full ? "" : `Optimise acts on the selected path: ${esc(sel.name)}.`}
      ${TP.undo ? ` <button class="linkish" data-tpundo="1">Undo</button>` : ""}${SB.prev ? ` <button class="linkish" data-undoplan="1">Undo plan change</button>` : ""}</p>`;

  const settings = TP.settings ? `<div class="tp-panel" id="tpSettings">
      <div class="rules">
        <span class="lbl">Optimise as</span><div class="seg" role="group" aria-label="Strategy for Optimise">${Object.entries(MODES).map(([k, l]) => `<button data-tpmode="${k}" aria-pressed="${tpMode() === k}">${l}</button>`).join("")}</div>
        <span class="lbl">Keep</span><div>${SB.rules.locked.length ? SB.rules.locked.map(i => `<button class="btn sm" data-unrule="locked:${i}" aria-label="Remove ${esc(P[i]?.name)}">${esc(P[i]?.name || "?")} ✕</button>`).join(" ") : '<span class="muted">none: lock a player from the pitch in Your plan</span>'}</div>
        <span class="lbl">Never pick</span><div>${SB.rules.banned.length ? SB.rules.banned.map(i => `<button class="btn sm" data-unrule="banned:${i}" aria-label="Remove ${esc(P[i]?.name)}">${esc(P[i]?.name || "?")} ✕</button>`).join(" ") : '<span class="muted">none: ban a player from his info panel</span>'}</div>
        <span class="lbl">Hits</span><div>${tpMode() === "chase" ? `<select id="hitsSel" aria-label="Hits allowed" class="sel">${[["", "At most 1 a week, when it pays"], ["0", "No hits"]].map(([v, l]) => `<option value="${v}" ${String(SB.rules.maxHits ?? "") === v ? "selected" : ""}>${l}</option>`).join("")}</select>` : `<span class="muted">${MODES[tpMode()]} never takes a hit</span>`}</div>
      </div>
      <p class="note">Locks, bans and the hit limit are the same ones Re-plan uses in Your plan. Captains you fixed in a path are kept when it's optimised.</p></div>` : "";

  const form = TP.form ? `<form class="tp-panel tp-form" id="tpForm">
      <label>Name <input id="tpName" maxlength="24" required value="${esc(`Path ${nDrafts + 1}`)}"></label>
      <label>Start from <select id="tpFrom">${rows.filter(r => r.sc).map(r => `<option value="${esc(r.key)}" ${r.key === sel.key && sel.sc ? "selected" : ""}>${esc(r.name)}</option>`).join("")}</select></label>
      <button class="btn primary sm" type="submit">Create</button><button class="btn sm" type="button" data-tpnew="0">Cancel</button>
      <p class="note">Copies that path's moves, strategy and captain choices into a new saved path. Edit it in Your plan.</p></form>` : "";

  const cell = (r, w) => {
    const on = r.key === sel.key && w.gw === g, filled = r.filled?.includes(w.gw);
    const mv = `${w.n} move${w.n === 1 ? "" : "s"}${w.hits ? ` · −${4 * w.hits} hit` : ""}`;
    return `<td class="tp-c h${lvl(w.gw, w.team.pts)}${on ? " tp-on" : ""}"><button type="button" data-tpcell="${esc(r.key)}|${w.gw}" aria-pressed="${on}"
      aria-label="${esc(`${r.name}, GW${w.gw}: ${f1(w.team.pts)} projected points before hits, ${mv}${filled ? ", past the optimiser's plan: no transfers" : ""}`)}">
      <b>${f1(w.team.pts)}${filled ? "*" : ""}</b><small>${mv}</small></button></td>`;
  };
  const body = rows.map(r => {
    const isSel = r.key === sel.key;
    const ch = r.changes, rv = ch?.worse.length ? ch : null;
    const review = rv ? `<span class="pill warn tp-review" title="${esc(`Since this path was saved: ${[...rv.worse, ...rv.better].join("; ")}. Save the path again to clear this.`)}">Review · ${rv.worse.length} change${rv.worse.length === 1 ? "" : "s"}</span>` : "";
    // flags stack: an invalid path can also have gone stale, and both are worth knowing
    const flag = [r.problems?.length ? `<span class="pill bad">Invalid</span>` : "", review,
      r.moved ? `<span class="pill warn" title="Net xP was ${f1(r.moved.net)} when saved${r.moved.saved ? ` (${whenTxt(new Date(r.moved.saved).toISOString())})` : ""}; the forecast has changed since">Forecast moved · was ${f1(r.moved.net)}</span>` : "",
      r.dropped ? `<span class="pill warn">${r.dropped} dropped</span>` : ""].filter(Boolean).join(" ");
    const name = `<th scope="row" class="sticky-col tp-n"><button type="button" data-tprow="${esc(r.key)}" aria-pressed="${isSel}">
        <span class="tp-nm">${esc(r.name)}${r.active ? ' <span class="pill good">Active plan</span>' : ""} ${flag}</span><small>${esc(r.sub || "")}</small>
        ${r.sc ? `<small class="tp-mob">Net ${f1(r.sc.tot)} · ${r.kind === "hold" ? "baseline" : sgn(tpGain(r, hold)) + " vs Hold"}</small>` : ""}</button></th>`;
    if (!r.sc) {
      const act = r.kind === "old" ? `<button class="btn sm" data-tprecalc="${r.key}" ${full ? 'disabled title="3 paths saved: delete one first"' : ""}>Recalculate</button> <button class="btn sm" data-tpdiscard="${r.key}">Discard</button>` : "";
      return `<tr class="tp-row tp-none${isSel ? " tp-sel" : ""}">${name}<td colspan="${PG.length + 2}" class="tp-why">${r.kind === "old" ? "Needs recalculating for your current squad: no totals until then, so nothing incomparable is shown." : esc(r.missing)}</td><td class="tp-act">${act}</td></tr>`;
    }
    const gain = tpGain(r, hold);
    const nMv = SB.moves.length;
    const act = r.active ? `<span class="tp-actv">In use</span>`
      : r.kind === "hold" ? `<button class="btn sm${TP.armHold ? " tp-arm" : ""}" data-tpuse="hold" aria-label="${TP.armHold ? `Confirm: clear all ${nMv} moves from your plan` : "Clear my plan: no transfers"}">${TP.armHold ? `Clear ${nMv} move${nMv === 1 ? "" : "s"}?` : "Clear my plan"}</button>`
      : `<button class="btn sm" data-tpuse="${esc(r.key)}" aria-label="Use ${esc(r.name)} as your plan">Use plan</button>`;
    return `<tr class="tp-row${isSel ? " tp-sel" : ""}">${name}${r.sc.weeks.map(w => cell(r, w)).join("")}
      <td class="n tp-net">${f1(r.sc.tot)}</td><td class="n tp-gain ${r.kind === "hold" ? "" : gain > 0.05 ? "up" : gain < -0.05 ? "down" : ""}">${r.kind === "hold" ? "—" : sgn(gain)}</td><td class="tp-act">${act}</td></tr>`;
  }).join("");
  const table = `<div class="tablebox tpbox"><table class="tp"><caption class="sr">Transfer paths: projected points per gameweek before hits, net after hits, gain over holding</caption>
    <thead><tr><th class="sticky-col" scope="col">Path</th>${PG.map(gw => `<th class="n" scope="col">GW${gw}</th>`).join("")}<th class="n" scope="col">Net xP</th><th class="n" scope="col">vs Hold</th><th scope="col"><span class="sr">Action</span></th></tr></thead>
    <tbody>${body}</tbody></table></div>`;

  return `<section class="panel tp-wrap" aria-label="Transfer paths">${bar}${settings}${form}${table}${g && sel.sc ? tpStrip(sel, g, rows) : ""}
    <div class="tp-foot"><span class="note">Cell values before hits · totals after hits${valid.some(r => r.filled?.length) ? " · * past the optimiser's plan: no transfers, best XI" : ""}</span>
      <details class="tp-calc"><summary>Calculation</summary>${tpCalc(valid, hold)}</details></div>
  </section>
  <p class="note">Select a gameweek to inspect its moves. Use plan makes a path your active plan, which This week, Rivals and Your plan all use. Saving or using a plan never sends transfers to FPL.</p>
  <details class="panel tp-more"><summary>Strategy details: field ownership, haul chance, free transfers left</summary>${pvCompare()}</details>`;
}
function tpCalc(rows, hold) {
  const ftv = 1.5;
  return `<p class="note">For each path: <b>cells</b> are the best XI's projected points that week with the captain doubled, before hits. <b>Net xP</b> = the sum of the cells − 4 × hits (each hit counted once). <b>vs Hold</b> = Net xP − Hold's ${f1(hold.sc.tot)}, both as shown to one decimal. Every row uses the same starting squad, bank, free transfers and forecast (updated ${whenTxt(D.meta.built)}). Hold keeps your 15 and still picks the best XI and captain each week. Model rows use the optimiser's own lineups; saved paths keep the strategy and captain choices they were saved with.</p>
    <p class="note">The optimiser and the verdicts elsewhere also give each free transfer still banked at the end an assumed value of ${ftv} points. That is a planning assumption, not projected points, so it is shown here and kept out of Net xP.</p>
    <div class="tablebox"><table><thead><tr><th>Path</th><th class="n">Sum of cells</th><th class="n">Hits</th><th class="n">Net xP</th><th class="n">FT left at end</th><th class="n">Banked FT value (assumed)</th></tr></thead>
    <tbody>${rows.map(r => { const sum = r.sc.weeks.reduce((a, w) => a + w.team.pts, 0), h = r.sc.weeks.reduce((a, w) => a + w.hits, 0);
      return `<tr><td>${esc(r.name)}</td><td class="n">${f1(sum)}</td><td class="n">${h ? "−" + 4 * h : "0"}</td><td class="n"><b>${f1(r.sc.tot)}</b></td><td class="n">${r.sc.ftLeft}</td><td class="n muted">${f1(ftv * r.sc.ftLeft)}</td></tr>`; }).join("")}</tbody></table></div>`;
}
// the selected path and gameweek, in one strip under the table
function tpStrip(r, g, rows) {
  const w = r.sc.weeks.find(x => x.gw === g), mv = r.moves.filter(m => m.gw === g);
  const tv = squadValue(w.sq), owned = new Set(D.squad.map(s => s.id));
  const editTxt = r.active ? "Edit in Your plan ↗" : "Use and edit in Your plan ↗";
  const extra = r.kind === "draft" ? `<div class="tp-tools">
      <label class="tp-ren">Rename <input id="tpRename" maxlength="24" value="${esc(r.name)}"></label><button class="btn sm" data-tpren="${esc(r.key)}">Save name</button>
      <button class="btn sm" data-tpdup="${esc(r.key)}" ${getDrafts().length >= 3 ? 'disabled title="3 paths saved"' : ""}>Duplicate</button>
      ${!r.active && rows.some(x => x.kind === "active") ? `<button class="btn sm" data-tpover="${esc(r.key)}" title="Replace this path with your active plan">Save Your plan over it</button>` : ""}
      <button class="btn sm tp-del" data-tpdel="${esc(r.key)}">Delete</button></div>` : "";
  // plan expiry (D4): what changed for the players this saved path relies on, readable on a phone (not only a tooltip)
  const ch = r.kind === "draft" && r.changes?.worse.length ? r.changes : null;
  const review = ch ? `<div class="tp-review-box" role="status"><b>Review this path: things it relies on have changed since you saved it.</b>
      <ul class="alerts">${ch.worse.map(t => `<li class="warn"><span>${esc(t)}</span></li>`).join("")}${ch.better.map(t => `<li class="info"><span>${esc(t)}</span></li>`).join("")}</ul>
      <button class="btn sm" data-tpreviewed="${esc(r.key)}">Mark as reviewed</button></div>` : "";
  return `<section class="tp-strip" aria-label="${esc(r.name)}, GW${g}">${review}
    <div class="tp-strip-h"><button type="button" class="tp-x" data-tpclose="1" aria-expanded="true" aria-label="Close GW${g} details">▾</button><h3>GW${g} · ${esc(r.name)}</h3>
      <button class="linkish tp-edit" data-tpedit="${esc(r.key)}|${g}">${editTxt}</button></div>
    ${mv.length ? `<ul class="tp-moves">${mv.map(m => `<li><span class="out"><span class="sr">Out: </span>${esc(P[m.out].name)}${owned.has(m.out) && !r.moves.some(x => x.in === m.out) ? ` <small class="muted">sells ${money(sellPrice(m.out))}</small>` : ""}</span><span aria-hidden="true">→</span><span class="in"><span class="sr">In: </span>${esc(P[m.in].name)} <small class="muted">${money(P[m.in].price)}</small></span></li>`).join("")}</ul>`
      : `<p class="tp-none-mv">No transfers in GW${g}${w.next > w.ft ? `: rolls to ${w.next} free next week` : ""}.</p>`}
    <dl class="tp-facts">
      <div><dt>Free transfers before</dt><dd>${w.ft}</dd></div>
      <div><dt>Moves</dt><dd>${w.n}${w.hits ? ` · <span class="down">−${4 * w.hits} hit</span>` : " · no hit"}</dd></div>
      <div><dt>Bank after</dt><dd class="${w.bank < 0 ? "down" : ""}">${money(w.bank)}</dd></div>
      <div><dt>Squad value</dt><dd>${tv != null ? money(tv) : "Unavailable"}</dd></div>
      <div><dt>Captain</dt><dd>${esc(P[w.team.cap]?.name || "–")}</dd></div>
      <div><dt>Projected</dt><dd>${f1(w.team.pts)} xP${w.hits ? ` (${f1(w.team.pts - 4 * w.hits)} after hit)` : ""}</dd></div>
    </dl>
    ${r.problems?.length ? `<p class="verdict tp-bad">Not a valid plan: ${esc(r.problems.join("; "))}. Fix it in Your plan before using it.</p>` : ""}
    <p class="note">Bank uses your real selling prices for players you own and today's prices for players bought in the path; squad value is market value at today's prices, without the bank. Price changes before GW${g} aren't forecast.${r.active ? "" : " Editing makes this path your active plan (Undo is offered); changes there aren't saved back to this path unless you save them over it."}</p>
    ${extra}</section>`;
}

/* ---------- actions ---------- */
function tpFind(key) { return tpRows().find(r => r.key === key); }
function tpDraftIdx(key) { const r = tpFind(key); return r && r.kind === "draft" ? r.idx : -1; }
function tpActivate(r) {
  tpEditing(r.kind === "draft" ? r.d.id || r.key.slice(2) : null);
  if (r.kind === "hold") setPlan([], "custom");
  else if (r.kind === "model") { S.mode = r.mode; store.set("fpl.mode", r.mode); setPlan(r.moves, "plan:" + r.pk, r.solved); }
  else if (r.kind === "draft") { SB.ov = JSON.parse(JSON.stringify(r.ov || {})); S.mode = r.mode; store.set("fpl.mode", r.mode); setPlan(r.moves, "custom", r.solved || null); }
}
// a saved path from any row: its moves, strategy, captain choices and (for model rows) the optimiser's lineups
function tpNewDraftRaw(r, name) {
  return { id: tpId(), name: name.slice(0, 24), moves: r.moves.map(m => ({ ...m })), ov: JSON.parse(JSON.stringify(r.ov || {})), mode: r.mode || S.mode,
    solved: r.solved ? JSON.parse(JSON.stringify(r.solved)) : null, saved: Date.now(), built: D.meta.built, from: r.name };
}
function tpNewDraft(r, name) {
  return tpStamp(tpNewDraftRaw(r, name));
}
// give old drafts an id the first time a path is changed, so selection follows the path rather than its position
const tpIds = ds => ds.map((d, k) => d.id ? d : { ...d, id: "i" + k });
async function tpOptimise() {
  if (TP.busy || SOLVE.busy) return;
  const r = tpFind(TP.sel) || tpFind("hold"), mode = tpMode(), ds = tpIds(getDrafts());
  if (r.kind !== "draft" && ds.length >= 3) { TP.msg = "3 paths are saved, so there's no room for an optimised one. Delete a path first."; render(); return; }
  TP.busy = true; SOLVE.busy = true; TP.undo = null; TP.msg = "Loading the optimiser…"; render();
  try {
    const t0 = performance.now();
    const res = await optimiseMoves(mode, { ov: r.ov || {}, rules: SB.rules, poolExtra: r.moves.map(m => m.in), status: m => { TP.msg = m; render(); } });
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    const now = getDrafts().length === ds.length ? ds : tpIds(getDrafts());
    if (r.kind === "draft") {
      const k = now.findIndex(d => d.id === r.key.slice(2)), prev = now[k];
      now[k] = tpStamp({ ...prev, moves: res.moves, solved: res.solved, mode, saved: Date.now() });
      setDrafts(now); TP.undo = { list: ds };
      TP.msg = `“${prev.name}” optimised as ${MODES[mode]} in ${secs}s: ${res.moves.length} move${res.moves.length === 1 ? "" : "s"}. Other paths and Hold are unchanged.`;
    } else {
      const d = tpNewDraft({ ...r, moves: res.moves, solved: res.solved, mode }, `Optimised · ${MODES[mode]}`);
      d.from = `${r.name}, optimised`;
      setDrafts([...now, d]); TP.sel = "d:" + d.id; store.set("fpl.tpsel", TP.sel); TP.undo = { list: ds };
      TP.msg = `New path “${d.name}” in ${secs}s: ${res.moves.length} move${res.moves.length === 1 ? "" : "s"}. ${r.name} is unchanged.`;
    }
  } catch (e) {
    TP.msg = `Optimise failed: ${e.message || e}. No path was changed.`;
  }
  TP.busy = false; SOLVE.busy = false; render();
}
function bindTpaths() {
  const on = (sel, fn, ev = "onclick") => document.querySelectorAll(sel).forEach(el => el[ev] = e => fn(el, e));
  const pick = key => { TP.sel = key; store.set("fpl.tpsel", key); TP.armHold = false; };
  on("[data-tprow]", b => { pick(b.dataset.tprow); render(); document.querySelector(`[data-tprow="${CSS.escape(TP.sel)}"]`)?.focus(); });
  on("[data-tpcell]", b => {
    const [key, gw] = b.dataset.tpcell.split("|"); pick(key); TP.gw = +gw; render();
    document.querySelector(`[data-tpcell="${CSS.escape(b.dataset.tpcell)}"]`)?.focus();
  });
  on("[data-tpclose]", () => { const c = `${TP.sel}|${TP.gw}`; TP.gw = null; render(); document.querySelector(`[data-tpcell="${CSS.escape(c)}"]`)?.focus(); });
  on("[data-tpopt]", () => tpOptimise());
  on("[data-tpnew]", b => { TP.form = b.dataset.tpnew === "1" && !TP.form; render(); if (TP.form) $("#tpName")?.select(); });
  on("[data-tpset]", () => { TP.settings = !TP.settings; render(); });
  on("[data-tpmode]", b => { TP.mode = b.dataset.tpmode; render(); });
  const f = $("#tpForm");
  if (f) f.onsubmit = e => {
    e.preventDefault();
    const r = tpFind($("#tpFrom").value), ds = tpIds(getDrafts()); if (!r || !r.sc || ds.length >= 3) return;
    const d = tpNewDraft(r, ($("#tpName").value || "").trim() || `Path ${ds.length + 1}`);
    setDrafts([...ds, d]); pick("d:" + d.id); TP.form = false; TP.undo = { list: ds };
    TP.msg = `“${d.name}” created from ${r.name}. Select a gameweek to inspect it, or edit it in Your plan.`; render();
  };
  on("[data-tpuse]", b => {
    const r = tpFind(b.dataset.tpuse); if (!r || !r.sc) return;
    // Hold wipes your moves: the first tap asks, the second clears (Undo is still offered)
    if (r.kind === "hold" && SB.moves.length && !TP.armHold) { TP.armHold = true; render(); document.querySelector('[data-tpuse="hold"]')?.focus(); return; }
    TP.armHold = false;
    if (r.problems?.length) { TP.msg = `${r.name} isn't a valid plan (${r.problems.join("; ")}). Fix it in Your plan first.`; render(); return; }
    tpActivate(r); TP.msg = ""; render();
    toast(`${r.name} is now your active plan, used by This week, Rivals and Your plan. Nothing is sent to FPL.`);
  });
  on("[data-tpedit]", b => {
    const [key, gw] = b.dataset.tpedit.split("|"), r = tpFind(key); if (!r) return;
    if (!r.active) { tpActivate(r); toast(`${r.name} is now your active plan. Undo is in Your moves.`); }
    SB.gw = +gw; SB.sel = null; S.pview = "edit"; store.set("fpl.pview", "edit"); render(); window.scrollTo({ top: 0 });
  });
  on("[data-tpren]", () => {
    const k = tpDraftIdx(TP.sel), v = ($("#tpRename")?.value || "").trim(); if (k < 0 || !v) return;
    const ds = tpIds(getDrafts()); ds[k] = { ...ds[k], name: v.slice(0, 24) }; setDrafts(ds); pick("d:" + ds[k].id); TP.msg = `Renamed to “${v.slice(0, 24)}”.`; render();
  });
  // keep the path as it is but record today's status, chances and fixtures, so the Review flag clears
  on("[data-tpreviewed]", () => {
    const k = tpDraftIdx(TP.sel); if (k < 0) return;
    const ds = tpIds(getDrafts()); ds[k] = tpStamp({ ...ds[k] }); setDrafts(ds); pick("d:" + ds[k].id); TP.msg = "Marked as reviewed."; render();
  });
  on("[data-tpdup]", () => {
    const r = tpFind(TP.sel), ds = tpIds(getDrafts()); if (!r || r.kind !== "draft" || ds.length >= 3) return;
    const d = { ...JSON.parse(JSON.stringify(ds[r.idx])), id: tpId(), name: `${r.name} copy`.slice(0, 24), saved: Date.now() };
    setDrafts([...ds, d]); pick("d:" + d.id); TP.undo = { list: ds }; TP.msg = `Duplicated as “${d.name}”.`; render();
  });
  on("[data-tpover]", () => {
    const r = tpFind(TP.sel), ds = tpIds(getDrafts()); if (!r || r.kind !== "draft") return;
    const a = tpFind("active"); if (!a) return;
    const prev = JSON.parse(JSON.stringify(ds));
    ds[r.idx] = tpStamp({ ...ds[r.idx], moves: a.moves.map(m => ({ ...m })), ov: JSON.parse(JSON.stringify(SB.ov)), mode: S.mode, solved: SB.solved, saved: Date.now() });
    setDrafts(ds); TP.undo = { list: prev };
    TP.msg = `“${r.name}” now holds your active plan.`; render();
  });
  on("[data-tpdel]", () => {
    const r = tpFind(TP.sel), ds = tpIds(getDrafts()); if (!r || r.kind !== "draft") return;
    setDrafts(ds.filter((_, k) => k !== r.idx)); TP.undo = { list: ds }; pick("hold"); TP.gw = null;
    TP.msg = `Deleted “${r.name}”.`; render();
  });
  on("[data-tpundo]", () => { if (!TP.undo) return; if (TP.undo.list) setDrafts(TP.undo.list); if (TP.undo.old) store.set(TP.undo.old.k, TP.undo.old.list); TP.undo = null; TP.msg = "Undone."; render(); });
  on("[data-tprecalc]", b => {
    const r = tpFind(b.dataset.tprecalc), ds = tpIds(getDrafts()); if (!r || r.kind !== "old" || ds.length >= 3) return;
    const { k, j, d } = r.o, list = store.get(k) || [];
    const fit = d.moves.filter(m => P[m.in] && P[m.out] && PG.includes(m.gw)), moves = cleanMoves(fit), drop = d.moves.length - moves.length;
    const nd = tpStamp({ ...d, id: tpId(), moves, solved: null, saved: Date.now(), from: `${d.from || "an older squad"}, recalculated` });
    TP.undo = { list: ds, old: { k, list: list.slice() } };
    setDrafts([...ds, nd]); store.set(k, list.filter((_, n) => n !== j)); pick("d:" + nd.id);
    TP.msg = `“${nd.name}” recalculated for your current squad${drop ? `: ${drop} move${drop === 1 ? "" : "s"} no longer applied and ${drop === 1 ? "was" : "were"} dropped` : ""}.`; render();
  });
  on("[data-tpdiscard]", b => {
    const r = tpFind(b.dataset.tpdiscard); if (!r || r.kind !== "old") return;
    const { k, j } = r.o, list = store.get(k) || [];
    TP.undo = { old: { k, list: list.slice() } }; store.set(k, list.filter((_, n) => n !== j)); pick("hold");
    TP.msg = `Discarded “${r.name}”.`; render();
  });
}

/* ---------- editing a saved path in Your plan ---------- */
// The active plan remembers which saved path it was taken from (per squad, like the plan itself), so Your plan can
// offer to save changes back to it. Missing path (deleted, or from another squad): no bar.
const tpEditKey = () => sbKey() + ".editing";
function tpEditing(id) { if (id === undefined) return store.get(tpEditKey()); store.set(tpEditKey(), id || null); }
function tpEditInfo() {
  const id = tpEditing(); if (!id) return null;
  const ds = getDrafts(), k = ds.findIndex((d, n) => (d.id || "i" + n) === id); if (k < 0) return null;
  const d = ds[k], same = sameMoves(cleanMoves(d.moves.filter(m => P[m.in] && P[m.out] && GWS.includes(m.gw))), SB.moves)
    && JSON.stringify(d.ov || {}) === JSON.stringify(SB.ov || {}) && (d.mode || S.mode) === S.mode;
  return { d, k, same };
}
function tpEditBar() {
  const e = tpEditInfo(); if (!e) return "";
  return `<div class="tp-editbar" role="status"><span>Editing saved path <b>“${esc(e.d.name)}”</b>${e.same ? " · no unsaved changes" : " · <span class=\"warn-t\">unsaved changes</span>"}</span>
    ${e.same ? "" : `<button class="btn primary sm" data-tpesave="1">Save changes to path</button><button class="btn sm" data-tpediscard="1">Discard changes</button>`}
    <button class="btn sm" data-tpestop="1">Stop editing</button></div>`;
}
function bindTpEdit() {
  const on = (sel, fn) => document.querySelectorAll(sel).forEach(el => el.onclick = () => fn(el));
  on("[data-tpesave]", () => {
    const e = tpEditInfo(); if (!e) return; const ds = tpIds(getDrafts());
    ds[e.k] = tpStamp({ ...ds[e.k], moves: SB.moves.map(m => ({ ...m })), ov: JSON.parse(JSON.stringify(SB.ov)), mode: S.mode, solved: SB.solved, saved: Date.now() });
    setDrafts(ds); tpEditing(ds[e.k].id); render(); toast(`Saved to “${e.d.name}”.`);
  });
  on("[data-tpediscard]", () => {
    const e = tpEditInfo(); if (!e) return;
    SB.ov = JSON.parse(JSON.stringify(e.d.ov || {})); if (MODES[e.d.mode]) { S.mode = e.d.mode; store.set("fpl.mode", S.mode); }
    setPlan(cleanMoves(e.d.moves.filter(m => P[m.in] && P[m.out] && GWS.includes(m.gw))), "custom", e.d.solved || null);
    render(); toast(`Back to “${e.d.name}” as saved. Undo is in Your moves.`);
  });
  on("[data-tpestop]", () => { tpEditing(null); render(); });
}
