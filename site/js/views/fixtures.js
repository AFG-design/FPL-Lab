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
  const mode = ["overall", "att", "def"].includes(S.fxMode) ? S.fxMode : "overall";
  const n = Math.min(S.fxN || 6, GWS.length), gws = GWS.slice(0, n);
  const myTeams = new Set(D.squad.map(s => P[s.id]?.team));
  const rows = Object.values(T).map(t => {
    let sum = 0, cnt = 0;
    const cells = gws.map(g => {
      const fx = t.fx[g] || [];
      if (!fx.length) return `<td class="fxc"><span class="d5">Blank</span></td>`;
      return `<td class="fxc">${fx.map(x => {
        let label, cls, v;
        if (mode === "overall") { const r = wdl(x.xgf, x.xga); v = r.w; label = Math.round(r.w * 100) + "%"; cls = winClass(r.w); }
        else if (mode === "att") { v = x.xgf; label = x.xgf.toFixed(1); cls = attClass(x.xgf); }
        else { v = csChance(x.xga); label = Math.round(v * 100) + "%"; cls = csClass(v); }
        sum += v; cnt++;
        const r = wdl(x.xgf, x.xga);
        const tip = `${T[x.opp].name} ${x.home ? "(home)" : "(away)"}: win ${Math.round(r.w * 100)}%, draw ${Math.round(r.d * 100)}%, loss ${Math.round(r.l * 100)}% · projected ${x.xgf.toFixed(1)}–${x.xga.toFixed(1)} · clean sheet ${Math.round(csChance(x.xga) * 100)}%${x.eu ? ` · also plays ${x.eu}` : ""}`;
        return `<span class="${cls}" title="${esc(tip)}" data-fxtip="${esc(tip)}" tabindex="0">${oppTxt(x)} <small>${label}</small>${x.eu ? '<i class="eudot" aria-label="European game nearby"></i>' : ""}</span>`;
      }).join("")}</td>`;
    }).join("");
    const st = teamStrength(t);
    const avg = cnt ? sum / cnt : 0;
    const avgTxt = mode === "att" ? avg.toFixed(2) : Math.round(avg * 100) + "%";
    return { sum: avg, html: `<tr class="${myTeams.has(t.id) ? "mine" : ""}"><td class="pname">${t.name}</td><td class="n">${Math.round(mode === "att" ? st.att : mode === "def" ? st.def : st.pts)}%</td><td class="n"><b>${avgTxt}</b></td>${cells}</tr>` };
  }).sort((a, b) => b.sum - a.sum);
  const help = {
    overall: "Each team's chance of winning each fixture, from projected goals for and against. Best overall run first.",
    att: "Projected goals each team should score. Green = easy to attack. Best run for attackers first.",
    def: "Each team's chance of keeping a clean sheet. Green = best clean-sheet chance. Best run for defenders and keepers first.",
  }[mode];
  const strengthHead = { overall: "Strength", att: "Attack", def: "Defence" }[mode];
  return `<div class="panel"><div class="bar"><h2>Fixture tracker</h2>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <div class="seg" role="group" aria-label="View"><button data-fx="overall" aria-pressed="${mode === "overall"}">Overall</button><button data-fx="att" aria-pressed="${mode === "att"}">Attack</button><button data-fx="def" aria-pressed="${mode === "def"}">Defence</button></div>
      <div class="seg" role="group" aria-label="Gameweeks">${[3, 6].filter(k => k <= GWS.length).map(k => `<button data-fxn="${k}" aria-pressed="${n === k}">${k} GWs</button>`).join("")}</div></div></div>
    <p class="note" style="margin-top:0">${help} Tap or hover a fixture for win, draw and loss chances, the projected score and clean-sheet chance. Capitals = home. Gold edge = a team you own players from. Dot = a European game within 3 days.</p>
    <div class="tablebox tick"><table><thead><tr><th>Team</th><th class="n">${term("strength", strengthHead + " %")}</th><th class="n">Avg</th>${gws.map(g => `<th>GW${g}</th>`).join("")}</tr></thead><tbody>${rows.map(r => r.html).join("")}</tbody></table></div></div>`;
}
