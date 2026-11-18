// Chips.
/* ---------- Chips ---------- */
function vChips() {
  const g = D.meta.next_gw;
  const chipCard = c => `<div class="chip ${c.used ? "used" : ""}"><h3>${c.name}</h3><span class="muted">GW${c.from}–${c.to}</span><div style="margin-top:6px">${c.used ? `<span class="pill mut">Used GW${c.used}</span>` : c.available ? `<span class="pill good">Available</span>` : `<span class="pill bad">Expired</span>`}</div></div>`;
  // FL-143: first-half and second-half chips apart, with the GW20 renewal between them
  const half1 = D.chips.filter(c => c.to <= 19), half2 = D.chips.filter(c => c.to > 19);
  const chips = half1.map(chipCard).join("") + (half1.length && half2.length ? `<div class="chip-divider" role="separator"><span>Chips renew at GW20</span></div>` : "") + half2.map(chipCard).join("");
  const rows = (D.gw_info || []).map(r => `<tr><td>GW${r.gw}</td><td class="n">${r.squad_playing}/15</td><td class="n">${f1(r.bench_xp)}</td><td>${esc(P[r.tc_player]?.name || "–")}</td><td class="n">${f1(r.tc_xp * 3)}</td></tr>`).join("");
  const dgw = D.season_gws.filter(r => r.gw >= g && (r.doubles.length || r.blanks.length));
  const tc1 = D.chips.find(c => c.key === "3xc" && c.to <= 19);
  const bestTc = (D.gw_info || []).reduce((a, r) => (!a || r.tc_xp > a.tc_xp) ? r : a, null);
  // No feasible roll plan means no gameweek projections: keep chip dates/statuses and say so.
  const tcProjection = bestTc ? ` In view now: <b>GW${bestTc.gw}</b> (${esc(P[bestTc.tc_player]?.name)}, ${f1(bestTc.tc_xp * 3)} pts with TC).` : "";
  const adv = [];
  if (tc1 && tc1.available) adv.push(`Your first-half <b>Triple Captain</b> must be played by GW${tc1.to}. ${dgw.some(r => r.gw <= tc1.to && r.doubles.length) ? "A double gameweek falls before then, which is the best spot." : `No doubles are scheduled before then, so aim it at the best single fixture.${tcProjection}`}`);
  if (!bestTc) adv.push("No projection for the best week yet");
  adv.push("The second set of chips unlocks in GW20. Save Bench Boost and Free Hit for the doubles and blanks, which usually get announced around the cup rounds.");
  return `<div class="panel"><h2 style="margin-bottom:12px">Chip planner</h2><p class="verdict">${adv.join("<br><br>")}</p></div>
    <div class="chips">${chips}</div>
    ${benchBoostCompare()}
    ${chipNowVsBest(g)}
    ${chipLedger()}
    <div class="panel"><h3>Your squad, next ${(D.gw_info || []).length} gameweeks</h3><div class="tablebox"><table><thead><tr><th>GW</th><th class="n">Playing</th><th class="n">Bench xP</th><th>Best captain</th><th class="n">TC xP</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="note">${dgw.length ? `Known blanks/doubles: ${dgw.map(r => `GW${r.gw}${r.doubles.length ? " double: " + r.doubles.join(", ") : ""}${r.blanks.length ? " blank: " + r.blanks.join(", ") : ""}`).join("; ")}.` : "No blank or double gameweeks are scheduled yet. This updates automatically when the fixture list changes."}</p></div>`;
}

/* FL-143: use now v best week, for each chip still available this half. Projected points only (xP from the Roll plan's
   weeks, D.gw_info): Bench Boost = your bench's xP that week; Triple Captain = the extra captain xP (one more helping).
   Free Hit and Wildcard need a whole new team solved, so they aren't projected here and the card says so.
   Missing: no plan weeks (no feasible Roll plan) -> the card says there's no projection. */
function chipNowVsBest(g) {
  const W = D.gw_info || [];
  const avail = D.chips.filter(c => c.available && c.from <= g && g <= c.to);
  if (!avail.length) return "";
  const rows = avail.map(c => {
    const inHalf = W.filter(w => w.gw >= c.from && w.gw <= c.to);
    const val = c.key === "bboost" ? w => w.bench_xp : c.key === "3xc" ? w => w.tc_xp : null;
    if (!val) return `<tr><td>${c.name}</td><td colspan="2" class="muted">Not projected here: it needs a whole new team worked out.</td></tr>`;
    if (!inHalf.length) return `<tr><td>${c.name}</td><td colspan="2" class="muted">No projection: no plan weeks before it expires.</td></tr>`;
    const now = inHalf.find(w => w.gw === g), best = inHalf.reduce((a, w) => val(w) > val(a) ? w : a);
    const who = w => c.key === "3xc" ? `<br><small class="muted">${esc(P[w.tc_player]?.name || "–")}</small>` : "";
    return `<tr><td>${c.name}</td><td class="n">${now ? `${f1(val(now))}${who(now)}` : "–"}</td><td class="n">${f1(val(best))} in GW${best.gw}${who(best)}</td></tr>`;
  }).join("");
  return `<div class="panel"><h3>Use now or wait? (projected)</h3><div class="tablebox"><table><thead><tr><th>Chip</th><th class="n">GW${g}</th><th class="n">Best week</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="note">Bench Boost shows projected bench xP, not extra points after possible autosubs without the chip. Triple Captain shows the extra captain xP. Only the ${W.length} gameweeks the plan covers are compared.</p></div>`;
}

/* FL-143: what each chip you've played actually earned (actual points, finished gameweeks; build.py chip_ledger). */
function chipLedger() {
  const L = D.chip_ledger || [];
  if (!L.length) return "";
  // phone width: four short columns; a missing figure is "–" with its reason in the cell's title (the Wildcard's is also
  // in the note below), so Earned never gets pushed off-screen
  const earned = r => r.earned != null ? `<b>${r.earned > 0 ? "+" : ""}${r.earned}</b>` : r.why === "pending" ? `<span class="muted">Pending: GW${r.gw} not finished</span>` : `<span class="muted" title="${esc(r.why || "")}">–</span>`;
  const how = { bboost: "bench points", "3xc": "captain's 3rd helping", freehit: "v your squad before it", wildcard: "" };
  const why = r => r.why && r.why !== "pending" && r.key !== "wildcard" ? esc(r.why) : "";
  const row = r => `<tr><td>${r.name}${how[r.key] || why(r) ? `<br><small class="muted">${how[r.key] || ""}${r.key === "freehit" && r.without != null ? ` (${r.without})` : ""}${why(r)}</small>` : ""}</td><td class="n">GW${r.gw}</td><td class="n">${r.pts ?? "–"}</td><td class="n">${earned(r)}</td></tr>`;
  const h1 = L.filter(r => r.half === 1), h2 = L.filter(r => r.half === 2);
  return `<div class="panel"><h3>Chips played: what they earned (actual)</h3><div class="tablebox"><table><thead><tr><th>Chip</th><th class="n">GW</th><th class="n">Points</th><th class="n">Earned</th></tr></thead><tbody>${h1.map(row).join("")}${h1.length && h2.length ? `<tr class="divider"><td colspan="4">Chips renew at GW20</td></tr>` : ""}${h2.map(row).join("")}</tbody></table></div>
    <p class="note">Actual points from finished gameweeks. A Wildcard has no single "earned" figure, because it changes every week after it.</p></div>`;
}

// Forecasts contain expected player points, not joint appearance probabilities. Live autosubs require actual
// minutes and cannot predict future substitutions: this is a bench-total estimate, NOT a marginal chip gain.
const BB_COMPARE = { a: null, b: null };
function benchBoostWeek(g, plan = completePlan()) {
  if (!GWS.includes(g)) return { error: `No player projections for GW${g}; the model currently covers GW${GWS[0]}–${GWS.at(-1)}.` };
  const chips = plan.chips || {}, sq = squadAt(g, plan.moves, chips);
  if (sq.length !== 15 || new Set(sq).size !== 15 || sq.some(i => !P[i] || !T[P[i].team]?.fx)) return { error: "Squad or fixture data is incomplete." };
  if (sq.some(i => P[i].xp?.[g] == null && fxFor(P[i].team, g).length)) return { error: "A player with a fixture has no projection for this week." };
  const weeks = GWS.filter(w => w <= g), ft = ftTable(plan.moves, weeks, chips);
  if (weeks.some(w => bankAt(w, plan.moves, chips) < 0 || Object.values(clubCounts(squadAt(w, plan.moves, chips))).some(n => n > 3))) return { error: "The active plan is over budget or over the club limit before this week. Fix it in the Planner first." };
  const team = withDraft(plan, () => bestXI(sq, g, undefined, plan.solved));
  if (team.bench.length !== 4) return { error: "A legal four-player bench could not be selected." };
  const bench = team.bench.map(id => ({ id, xp: xpg(id, g), fixtures: fxFor(P[id].team, g).length }));
  const conflict = Object.entries(chips).find(([k, w]) => k !== "bboost" && w === g);
  const used = D.chips.find(c => c.key === "bboost" && c.from <= g && c.to >= g);
  const unavailable = !chipWindow("bboost", g) ? used?.used ? `Bench Boost was used in GW${used.used} in this chip window.` : "Bench Boost is unavailable in this chip window." : conflict ? `${CHIP_NAME[conflict[0]]} is already planned in GW${g}; only one chip can be played.` : "";
  return { bench, total: bench.reduce((n, p) => n + p.xp, 0), moves: movesFor(g, plan.moves, chips), unavailable, hits: ft.reduce((n, w) => n + w.hits, 0) };
}
function benchBoostCompare() {
  const g = D.meta.next_gw;
  if (!g) return "";
  const options = Array.from({ length: 39 - g }, (_, i) => g + i);
  if (!options.includes(BB_COMPARE.a)) BB_COMPARE.a = g;
  if (!options.includes(BB_COMPARE.b)) BB_COMPARE.b = Math.min(38, g + 1);
  const values = [BB_COMPARE.a, BB_COMPARE.b], results = values.map(w => benchBoostWeek(w));
  const select = (key, n) => `<label>Week ${n} <select data-bbweek="${key}">${options.map(w => `<option value="${w}" ${BB_COMPARE[key] === w ? "selected" : ""}>GW${w}${GWS.includes(w) ? "" : " (no projection)"}</option>`).join("")}</select></label>`;
  const card = (r, i) => `<section class="panel"><h3>GW${values[i]}</h3>${r.error ? `<p>${esc(r.error)}</p>` : `<p><b>${f1(r.total)} xP projected bench total</b></p>${r.unavailable ? `<p class="note">${esc(r.unavailable)} Bench shown for reference only.</p>` : ""}<ul>${r.bench.map(p => `<li>${esc(P[p.id].name)} · ${f1(p.xp)} xP · ${p.fixtures === 0 ? "Blank" : p.fixtures === 2 ? "Double gameweek" : `${p.fixtures} match${p.fixtures === 1 ? "" : "es"}`}</li>`).join("")}</ul><h4>Planned transfers needed</h4><ul>${r.moves.map(m => `<li>GW${m.gw}: ${esc(P[m.out]?.name)} → ${esc(P[m.in]?.name)}</li>`).join("") || '<li>None: your current squad.</li>'}</ul>${r.hits ? `<p class="note">These moves include −${r.hits * 4} points in hits; these are transfer costs, not deducted from the bench total.</p>` : ""}`}</section>`;
  const [a, b] = results;
  const verdictTxt = a.error || b.error ? "Both weeks need projections for a comparison." : values[0] === values[1] ? "Choose two different weeks." : Math.abs(a.total - b.total) < 0.05 ? "The two benches are level on projected points." : `GW${a.total > b.total ? values[0] : values[1]} has ${f1(Math.abs(a.total - b.total))} more projected bench points.${a.unavailable || b.unavailable ? " Chip availability prevents a like-for-like playable comparison." : ""}`;
  return `<section class="panel"><h2 style="margin-bottom:8px">Compare two Bench Boost weeks</h2><div class="filters">${select("a", 1)}${select("b", 2)}</div><p class="verdict">${verdictTxt}</p><p class="note">Read-only, using your active plan and its lineup choices. These are bench-total estimates, not the additional points attributable to Bench Boost: a substitute may score without the chip. The forecast model does not estimate future autosubs, so that extra gain is unavailable. Double-gameweek projections are already combined.</p><div class="grid2">${results.map(card).join("")}</div></section>`;
}
