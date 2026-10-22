// Chips.
/* ---------- Chips ---------- */
function vChips() {
  const g = D.meta.next_gw;
  const chips = D.chips.map(c => `<div class="chip ${c.used ? "used" : ""}"><h3>${c.name}</h3><span class="muted">GW${c.from}–${c.to}</span><div style="margin-top:6px">${c.used ? `<span class="pill mut">Used GW${c.used}</span>` : c.available ? `<span class="pill good">Available</span>` : `<span class="pill bad">Expired</span>`}</div></div>`).join("");
  const rows = (D.gw_info || []).map(r => `<tr><td>GW${r.gw}</td><td class="n">${r.squad_playing}/15</td><td class="n">${f1(r.bench_xp)}</td><td>${esc(P[r.tc_player]?.name || "–")}</td><td class="n">${f1(r.tc_xp * 3)}</td></tr>`).join("");
  const dgw = D.season_gws.filter(r => r.gw >= g && (r.doubles.length || r.blanks.length));
  const tc1 = D.chips.find(c => c.key === "3xc" && c.to <= 19);
  const bestTc = (D.gw_info || []).reduce((a, r) => (!a || r.tc_xp > a.tc_xp) ? r : a, null);
  const adv = [];
  if (tc1 && tc1.available) adv.push(`Your first-half <b>Triple Captain</b> must be played by GW${tc1.to}. ${dgw.some(r => r.gw <= tc1.to && r.doubles.length) ? "A double gameweek falls before then, which is the best spot." : `No doubles are scheduled before then, so aim it at the best single fixture. In view now: <b>GW${bestTc.gw}</b> (${esc(P[bestTc.tc_player]?.name)}, ${f1(bestTc.tc_xp * 3)} pts with TC).`}`);
  adv.push("The second set of chips unlocks in GW20. Save Bench Boost and Free Hit for the doubles and blanks, which usually get announced around the cup rounds.");
  return `<div class="panel"><h2 style="margin-bottom:12px">Chip planner</h2><p class="verdict">${adv.join("<br><br>")}</p></div>
    <div class="chips">${chips}</div>
    <div class="panel"><h3>Your squad, next ${(D.gw_info || []).length} gameweeks</h3><div class="tablebox"><table><thead><tr><th>GW</th><th class="n">Playing</th><th class="n">Bench xP</th><th>Best captain</th><th class="n">TC xP</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="note">${dgw.length ? `Known blanks/doubles: ${dgw.map(r => `GW${r.gw}${r.doubles.length ? " double: " + r.doubles.join(", ") : ""}${r.blanks.length ? " blank: " + r.blanks.join(", ") : ""}`).join("; ")}.` : "No blank or double gameweeks are scheduled yet. This updates automatically when the fixture list changes."}</p></div>`;
}
