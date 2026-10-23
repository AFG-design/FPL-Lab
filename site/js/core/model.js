// Fixture colouring, projections and the lineup/captain rules (same maths as the optimiser).
/* ---------- helpers ---------- */
function attClass(x) { return x >= 1.9 ? "d1" : x >= 1.5 ? "d2" : x >= 1.15 ? "d3" : x >= 0.85 ? "d4" : "d5"; }
function defClass(x) { return x <= 0.85 ? "d1" : x <= 1.1 ? "d2" : x <= 1.4 ? "d3" : x <= 1.75 ? "d4" : "d5"; }
const fxFor = (tid, g) => T[tid].fx[g] || [];
const oppTxt = x => x.home ? T[x.opp].short : T[x.opp].short.toLowerCase();
function fxChips(p, from, n = 3) {
  // official FPL difficulty, with the number printed on each chip (see fdrChip)
  return GWS.filter(g => g >= from).slice(0, n).map(g => {
    const fx = fxFor(p.team, g);
    return fx.length ? fx.map(x => fdrChip(x, { gw: g, size: "xs" })).join("") : blankChip(g);
  }).join("");
}
const fxText = (p, g) => fxFor(p.team, g).map(x => `${T[x.opp].short} (${x.home ? "H" : "A"})`).join(" + ") || "Blank";
function flag(p) {
  if (p.status === "a") return "";
  return `<span class="flag ${p.status}" title="${esc(p.news)}">${p.chance != null ? p.chance + "%" : "!"}</span>`;
}
const xpg = (id, g) => (P[id]?.xp[g]) || 0;
const xpFrom = (id, g, n = 99) => GWS.filter(x => x >= g).slice(0, n).reduce((a, x) => a + xpg(id, x), 0);

// strategy-aware values (same maths as the optimiser): Safe leans to what the field owns, Chase away from it
const LAM = { balanced: 0, safe: 0.02, chase: -0.03 };
// strategy extras for Re-plan; same numbers as STRATEGY in build.py
const STRAT = { balanced: {}, safe: { hitMargin: 2, nailW: 0.5 }, chase: { haulW: 10 } };
function fieldEO() { const F = D.crowd ? (D.crowd.near?.n >= 100 ? D.crowd.near : D.crowd.top10k) : null; return F ? F.eo : null; }
function adjXI(i, g) {
  const lam = LAM[S.mode] || 0, eo = fieldEO(), x = xpg(i, g);
  if (!lam || !eo || PG.indexOf(g) > 1) return x;
  const k = 1 - 2 * (eo[i] || 0) / 100;
  // Chase only rewards differentials; it never pushes you to drop players the field owns
  return x - lam * variance(P[i].pos, x) * (lam < 0 ? Math.max(0, k) : k);
}
function adjCap(i, g) {  // value of the captain's extra multiplier
  const lam = LAM[S.mode] || 0, eo = fieldEO(), x = xpg(i, g);
  if (!lam || !eo || PG.indexOf(g) > 1) return x;
  const k = 3 - 2 * (eo[i] || 0) / 100;
  return x - lam * variance(P[i].pos, x) * (lam < 0 ? Math.max(0, k) : k);  // matches the optimiser's captain term
}
// one captain rule everywhere: best value, but an attacker beats a GKP/DEF that only edges it
function capPick(xi, g) {
  const order = xi.slice().sort((a, b) => adjCap(b, g) - adjCap(a, g));
  let cap = order[0], vice = order[1], swapped = null;
  const att = order.find(i => ["MID", "FWD"].includes(P[i]?.pos));
  if (att && att !== cap && ["GKP", "DEF"].includes(P[cap]?.pos) && adjCap(cap, g) - adjCap(att, g) < 0.6) { swapped = cap; vice = cap; cap = att; }
  return { cap, vice, swapped };
}
function bestXI(ids, g, ov = (SB && SB.ov ? SB.ov[g] : null)) {
  const fs = new Set(ov?.start || []), fb = new Set(ov?.bench || []);
  const ps = ids.filter(i => P[i]).slice().sort((a, b) => adjXI(b, g) - adjXI(a, g));
  const MIN = { GKP: 1, DEF: 3, MID: 2, FWD: 1 }, MAX = { GKP: 1, DEF: 5, MID: 5, FWD: 3 };
  const xi = [], cnt = { GKP: 0, DEF: 0, MID: 0, FWD: 0 };
  const need = () => Object.keys(MIN).reduce((a, k) => a + Math.max(0, MIN[k] - cnt[k]), 0);
  const tryAdd = i => {
    const pos = P[i].pos;
    if (xi.includes(i) || xi.length >= 11 || cnt[pos] >= MAX[pos]) return false;
    cnt[pos]++;
    if (xi.length + 1 + need() > 11) { cnt[pos]--; return false; }  // keep the formation possible
    xi.push(i); return true;
  };
  ps.filter(i => fs.has(i)).forEach(tryAdd);                                  // your forced starters
  for (const pos of Object.keys(MIN)) ps.filter(i => P[i].pos === pos && !fb.has(i)).forEach(i => { if (cnt[pos] < MIN[pos]) tryAdd(i); });
  ps.filter(i => !fb.has(i)).forEach(tryAdd);
  ps.forEach(tryAdd);                                                         // only if benching left too few
  let out = ps.filter(i => !xi.includes(i) && P[i].pos !== "GKP");
  if (ov?.order?.length) { const rk = i => { const k = ov.order.indexOf(i); return k < 0 ? 99 : k; }; out = out.map((i, k) => [i, k]).sort((a, b) => rk(a[0]) - rk(b[0]) || a[1] - b[1]).map(x => x[0]); }  // your bench order
  const bench = [...ps.filter(i => !xi.includes(i) && P[i].pos === "GKP"), ...out];
  let c = capPick(xi, g), mine = false;
  if (ov?.cap && xi.includes(ov.cap)) {
    mine = true;
    const others = xi.filter(i => i !== ov.cap).sort((a, b) => adjCap(b, g) - adjCap(a, g));
    c = { cap: ov.cap, vice: ov.vice && xi.includes(ov.vice) && ov.vice !== ov.cap ? ov.vice : others[0], swapped: null };
  }
  const pts = xi.reduce((a, i) => a + xpg(i, g), 0) + (c.cap ? xpg(c.cap, g) : 0);
  return { xi, bench, cap: c.cap, vice: c.vice, swapped: c.swapped, pts, capMine: mine };
}
