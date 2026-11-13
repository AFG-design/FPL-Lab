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
    const who = w => c.key === "3xc" ? ` (${esc(P[w.tc_player]?.name || "–")})` : "";
    return `<tr><td>${c.name}</td><td class="n">${now ? `${f1(val(now))}${who(now)}` : "–"}</td><td class="n">GW${best.gw}: ${f1(val(best))}${who(best)}</td></tr>`;
  }).join("");
  return `<div class="panel"><h3>Use now or wait? (projected)</h3><div class="tablebox"><table><thead><tr><th>Chip</th><th class="n">GW${g} xP gain</th><th class="n">Best week in view</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="note">Projected points the chip adds: Bench Boost = your bench's xP; Triple Captain = one more helping of your captain's xP. Only the ${W.length} gameweeks the plan covers are compared.</p></div>`;
}

/* FL-143: what each chip you've played actually earned (actual points, finished gameweeks; build.py chip_ledger). */
function chipLedger() {
  const L = D.chip_ledger || [];
  if (!L.length) return "";
  const earned = r => r.earned != null ? `<b>${r.earned > 0 ? "+" : ""}${r.earned}</b>` : r.why === "pending" ? `<span class="muted">Pending: GW${r.gw} not finished</span>` : `<span class="muted">${esc(r.why || "–")}</span>`;
  const how = { bboost: "your bench's points", "3xc": "the third helping of your captain's points", freehit: "points v the squad you had before it", wildcard: "" };
  const row = r => `<tr><td>${r.name}</td><td class="n">GW${r.gw}</td><td class="n">${r.pts ?? "–"}</td><td class="n">${earned(r)}</td><td class="muted">${how[r.key] || ""}${r.key === "freehit" && r.without != null ? ` (that squad: ${r.without})` : ""}</td></tr>`;
  const h1 = L.filter(r => r.half === 1), h2 = L.filter(r => r.half === 2);
  return `<div class="panel"><h3>Chips played: what they earned (actual)</h3><div class="tablebox"><table><thead><tr><th>Chip</th><th class="n">GW</th><th class="n">GW points</th><th class="n">Earned</th><th>Measured as</th></tr></thead><tbody>${h1.map(row).join("")}${h1.length && h2.length ? `<tr class="divider"><td colspan="5">Chips renew at GW20</td></tr>` : ""}${h2.map(row).join("")}</tbody></table></div>
    <p class="note">Actual points from finished gameweeks. A Wildcard has no single "earned" figure, because it changes every week after it.</p></div>`;
}
