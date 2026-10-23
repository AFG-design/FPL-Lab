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
    return { sum: mode === "fdr" ? -avg : avg, html: `<tr class="${myTeams.has(t.id) ? "mine" : ""}"><td class="pname sticky-col"><button data-team="${t.id}" class="linkish fx-club">${badge(t.id, 20)}<span>${t.name}</span></button></td>${strength}<td class="n"><b>${avgTxt}</b></td>${cells}</tr>` };
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
    <div class="tablebox tick"><table><thead><tr><th class="sticky-col">Team</th>${mode === "fdr" ? "" : `<th class="n">${term("strength", strengthHead + " %")}</th>`}<th class="n">${mode === "fdr" ? "Avg FDR" : "Avg"}</th>${gws.map(g => `<th>GW${g}</th>`).join("")}</tr></thead><tbody>${rows.map(r => r.html).join("")}</tbody></table></div></div>${swingsPanel()}`;
}

/* ---------- fixture swings: when a team's run turns easy or hard ---------- */
// expected goals for and against per gameweek over the next 12: the model's own numbers where it has them,
// beyond that from the team ratings (league average x attack x opponent's defence, with home advantage)
function teamRun(t) {
  const L = D.meta.league_goals || 1.4, H = 1.05, out = {};
  for (const [g, opp, home] of t.far || []) {
    const f = (t.fx[g] || []).find(x => x.opp === opp && x.home === home);
    const o = T[opp]; if (!o) continue;
    const xgf = f ? f.xgf : L * t.att * o.def * (home ? H : 1 / H), xga = f ? f.xga : L * o.att * t.def * (home ? 1 / H : H);
    (out[g] = out[g] || []).push({ xgf, xga, cs: Math.exp(-xga), opp, home });
  }
  return out;
}
function swings() {
  const g0 = D.meta.next_gw, W = 4, res = [];
  Object.values(T).forEach(t => {
    const run = teamRun(t), gw = Array.from({ length: 12 }, (_, k) => g0 + k);
    // per gameweek value (a blank counts as zero; a double counts both games)
    const att = gw.map(g => (run[g] || []).reduce((a, x) => a + x.xgf, 0)), def = gw.map(g => (run[g] || []).reduce((a, x) => a + x.cs, 0));
    const roll = (arr, s) => arr.slice(s, s + W).reduce((a, b) => a + b, 0) / W;
    [["att", att], ["def", def]].forEach(([kind, arr]) => {
      const now = roll(arr, 0);
      let best = null;
      for (let s = 2; s <= 6; s++) { const d = roll(arr, s) - now; if (!best || Math.abs(d) > Math.abs(best.d)) best = { s, d }; }
      if (best) res.push({ t, kind, from: g0 + best.s, d: best.d, now, later: roll(arr, best.s), arr, gw });
    });
  });
  return res;
}
function swingsPanel() {
  const all = swings(); if (!all.length) return "";
  const thr = { att: 0.12, def: 0.04 };   // goals per game / clean-sheet chance per game: real swings are modest
  const pick = (kind, sign) => all.filter(r => r.kind === kind && r.d * sign > thr[kind]).sort((a, b) => sign * (b.d - a.d)).slice(0, 4);
  const targets = (r) => {
    const posOK = r.kind === "att" ? ["MID", "FWD"] : ["DEF", "GKP"];
    return D.players.filter(p => p.team === r.t.id && posOK.includes(p.pos) && p.nailed >= 60 && p.ok !== false).sort((a, b) => b.xp5 - a.xp5).slice(0, 2);
  };
  const spark = r => `<span class="swing-spark" aria-hidden="true">${r.arr.slice(0, 10).map((v, k) => { const mx = r.kind === "att" ? 3 : 0.6;
    return `<i style="height:${Math.max(2, Math.min(1, v / mx) * 22).toFixed(0)}px" class="${r.gw[k] >= r.from && r.gw[k] < r.from + 4 ? "hl" : ""}"></i>`; }).join("")}</span>`;
  const rel = r => `${r.later >= r.now ? "+" : "−"}${Math.abs(Math.round(100 * (r.later - r.now) / r.now))}%`;
  const fmt = r => r.kind === "att" ? `${r.now.toFixed(2)} → ${r.later.toFixed(2)} expected goals a game (${rel(r)})` : `${Math.round(r.now * 100)}% → ${Math.round(r.later * 100)}% clean-sheet chance (${rel(r)})`;
  const item = (r, easy) => `<li class="${easy ? "good" : "bad"}"><span><b>${esc(r.t.name)}</b> ${r.kind === "att" ? "attack" : "defence"} ${easy ? "turns easy" : "turns hard"} from <b>GW${r.from}</b>: ${fmt(r)} over GW${r.from}–${r.from + 3}.
      ${targets(r).length ? `<span class="muted">${easy ? "Targets" : "Owners beware"}: ${targets(r).map(p => `<button data-p="${p.id}" class="linkish">${esc(p.name)}</button>${MINE.has(p.id) ? " (yours)" : ""}`).join(", ")}.</span>` : ""}</span>${spark(r)}</li>`;
  const sec = (title, list, easy) => `<div><h3 style="margin:6px 0 8px">${title}</h3>${list.length ? `<ul class="alerts swings">${list.map(r => item(r, easy)).join("")}</ul>` : '<p class="muted">No big swings coming.</p>'}</div>`;
  const mine = all.filter(r => r.d < -thr[r.kind] && D.squad.some(s => P[s.id]?.team === r.t.id && (r.kind === "att" ? ["MID", "FWD"] : ["DEF", "GKP"]).includes(P[s.id].pos)));
  return `<div class="panel"><div class="bar"><h2>Fixture swings</h2><span class="muted">next 12 gameweeks</span></div>
    <p class="note" style="margin-top:0">Teams whose next four-gameweek run gets much easier or harder than the one they're on now. Buy into a run just before it starts; sell before a hard one. The bars show each gameweek, with the four-week run highlighted.${mine.length ? ` <b>Your players affected:</b> ${[...new Set(mine.map(r => r.t.short))].join(", ")} turn harder soon.` : ""}</p>
    <div class="statgrid">${sec("Turning easy", [...pick("att", 1), ...pick("def", 1)].sort((a, b) => a.from - b.from), true)}${sec("Turning hard", [...pick("att", -1), ...pick("def", -1)].sort((a, b) => a.from - b.from), false)}</div>
    <p class="note">Goals and clean-sheet chances come from the model for the next ${GWS.length} gameweeks and from team ratings after that. Blanks count as zero.</p></div>`;
}
