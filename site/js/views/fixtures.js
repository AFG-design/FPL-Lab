// Fixtures.
/* ---------- Fixtures ---------- */
// match outcome chances from projected goals (independent Poisson), as the model uses
function wdl(mf, ma) {
  const pf = k => Math.exp(-mf) * mf ** k / fact(k), pa = k => Math.exp(-ma) * ma ** k / fact(k);
  let w = 0, d = 0, l = 0;
  for (let i = 0; i <= 10; i++) for (let j = 0; j <= 10; j++) { const p = pf(i) * pa(j); if (i > j) w += p; else if (i === j) d += p; else l += p; }
  const t = w + d + l; return { w: w / t, d: d / t, l: l / t };
}
const fact = n => n < 2 ? 1 : n * fact(n - 1);
const csChance = xga => Math.exp(-0.9 * xga);
// team strength as percentages, from the model's attack and defence ratings
function teamStrength(t) {
  const L = D.meta.league_goals || 1.4, r = wdl(L * t.att, L * t.def);
  return { att: t.att * 100, def: 100 / t.def, win: r.w * 100, pts: (3 * r.w + r.d) / 3 * 100 };
}
function winClass(p) { return p >= 0.6 ? "d1" : p >= 0.45 ? "d2" : p >= 0.3 ? "d3" : p >= 0.2 ? "d4" : "d5"; }
function csClass(p) { return p >= 0.45 ? "d1" : p >= 0.35 ? "d2" : p >= 0.25 ? "d3" : p >= 0.15 ? "d4" : "d5"; }
function vFixtures() {
  const mode = ["fdr", "overall", "att", "def"].includes(S.fxMode) ? S.fxMode : "fdr";
  const n = Math.min(S.fxN || 6, GWS.length), gws = GWS.slice(0, n);
  const myTeams = new Set(D.squad.map(s => P[s.id]?.team));
  const rows = Object.values(T).map(t => {
    let sum = 0, cnt = 0;
    const cells = gws.map(g => {
      const fx = t.fx[g] || [];
      if (!fx.length) { if (mode === "fdr") { sum += 5; cnt++; } return `<td class="fxc">${blankChip(g)}</td>`; }
      return `<td class="fxc">${fx.map(x => {
        if (mode === "fdr") { sum += x.fdr || 3; cnt++; return fdrChip(x, { gw: g, size: "cellchip" }); }
        let label, cls, v;
        if (mode === "overall") { const r = wdl(x.xgf, x.xga); v = r.w; label = Math.round(r.w * 100) + "%"; cls = winClass(r.w); }
        else if (mode === "att") { v = x.xgf; label = x.xgf.toFixed(1); cls = attClass(x.xgf); }
        else { v = csChance(x.xga); label = Math.round(v * 100) + "%"; cls = csClass(v); }
        sum += v; cnt++;
        const r = wdl(x.xgf, x.xga);
        const tip = `${T[x.opp].name} ${x.home ? "(home)" : "(away)"}: win ${Math.round(r.w * 100)}%, draw ${Math.round(r.d * 100)}%, loss ${Math.round(r.l * 100)}%. Projected ${x.xgf.toFixed(1)}–${x.xga.toFixed(1)}, clean sheet ${Math.round(csChance(x.xga) * 100)}%${x.eu ? `. Also plays ${x.eu}` : ""}`;
        return `<span class="${cls}" title="${esc(tip)}" data-fxtip="${esc(tip)}" tabindex="0">${oppTxt(x)} <small>${label}</small>${x.eu ? '<i class="eudot" aria-label="European game nearby"></i>' : ""}</span>`;
      }).join("")}</td>`;
    }).join("");
    const st = teamStrength(t);
    const avg = cnt ? sum / cnt : 0;
    const avgTxt = mode === "fdr" ? avg.toFixed(1) : mode === "att" ? avg.toFixed(2) : Math.round(avg * 100) + "%";
    const strength = mode === "fdr" ? "" : `<td class="n">${Math.round(mode === "att" ? st.att : mode === "def" ? st.def : st.pts)}%</td>`;
    return { sum: mode === "fdr" ? -avg : avg, html: `<tr class="${myTeams.has(t.id) ? "mine" : ""}"><td class="pname sticky-col">${t.name}</td>${strength}<td class="n"><b>${avgTxt}</b></td>${cells}</tr>` };
  }).sort((a, b) => b.sum - a.sum);
  const help = {
    fdr: "FPL's official fixture difficulty for each match, 1 easiest to 5 hardest. Easiest run first.",
    overall: "Each team's chance of winning each fixture, from the model's projected goals for and against. Best run first.",
    att: "Projected goals each team should score, from the model. Best run for attackers first.",
    def: "Each team's chance of keeping a clean sheet, from the model. Best run for defenders and keepers first.",
  }[mode];
  const strengthHead = { overall: "Strength", att: "Attack", def: "Defence" }[mode];
  const lengths = [...new Set([3, 5, GWS.length].filter(k => k <= GWS.length))];
  return `<div class="panel fixtures"><div class="bar"><h2>Fixtures</h2>
    <div class="fx-controls">
      <div class="seg" role="group" aria-label="Colour by">${[["fdr", "Difficulty"], ["overall", "Win chance"], ["att", "Attack"], ["def", "Clean sheet"]].map(([k, l]) => `<button data-fx="${k}" aria-pressed="${mode === k}">${l}</button>`).join("")}</div>
      <div class="seg" role="group" aria-label="Gameweeks">${lengths.map(k => `<button data-fxn="${k}" aria-pressed="${n === k}">${k} GWs</button>`).join("")}</div></div></div>
    <div class="fx-help"><p class="note">${help}${mode === "fdr" ? "" : " Colours use the same green-to-red scale; tap a fixture for win, draw and loss chances."}${mode === "fdr" ? "" : " Capitals = home."} Yellow edge = a team you own players from.</p>${mode === "fdr" ? fdrKey() : ""}</div>
    <div class="tablebox tick"><table><thead><tr><th class="sticky-col">Team</th>${mode === "fdr" ? "" : `<th class="n">${term("strength", strengthHead + " %")}</th>`}<th class="n">${mode === "fdr" ? "Avg FDR" : "Avg"}</th>${gws.map(g => `<th>GW${g}</th>`).join("")}</tr></thead><tbody>${rows.map(r => r.html).join("")}</tbody></table></div></div>`;
}
