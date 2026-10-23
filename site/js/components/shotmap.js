// Shot map: where a player's shots came from this season and how good the chances were (Understat).
const SHOTS = { data: null, loading: null };
function loadShots() {
  if (SHOTS.data) return Promise.resolve(SHOTS.data);
  if (!SHOTS.loading) SHOTS.loading = fetch("shots.json?t=" + encodeURIComponent(D.meta.built)).then(r => r.ok ? r.json() : null).then(j => (SHOTS.data = j)).catch(() => null);
  return SHOTS.loading;
}
function shotMapSVG(list) {
  // Understat: x 0-100 towards the goal being attacked, y 0-100 across. Half pitch, goal at the top.
  const W = 300, H = 210, sx = y => (y / 100) * W, sy = x => (100 - x) / 50 * H;
  const box = `<rect x="${sx(21.1)}" y="0" width="${sx(78.9) - sx(21.1)}" height="${sy(84.3)}" class="sm-line"/>
    <rect x="${sx(36.8)}" y="0" width="${sx(63.2) - sx(36.8)}" height="${sy(94.8)}" class="sm-line"/>
    <rect x="${sx(44.2)}" y="-4" width="${sx(55.8) - sx(44.2)}" height="4" class="sm-goal"/>
    <circle cx="${sx(50)}" cy="${sy(88.5)}" r="1.6" class="sm-dot"/>
    <path d="M ${sx(39)} ${sy(84.3)} A ${sx(9.2)} ${sx(9.2)} 0 0 0 ${sx(61)} ${sy(84.3)}" class="sm-line"/>`;
  const cls = { G: "g", S: "s", P: "s", B: "b", M: "m", O: "m" };
  const dots = list.slice().sort((a, b) => b[2] - a[2]).map(([x, y, xg, res, sit, head, date]) => {
    const r = 3 + Math.sqrt(xg) * 10;
    return `<circle cx="${sx(y).toFixed(1)}" cy="${sy(x).toFixed(1)}" r="${r.toFixed(1)}" class="sm-shot sm-${cls[res] || "m"}"><title>${date}: ${({ G: "Goal", S: "Saved", P: "Hit the post", B: "Blocked", M: "Missed", O: "Own goal" })[res] || res}, ${xg.toFixed(2)} xG${head ? ", header" : ""}${sit === "P" ? ", penalty" : sit !== "O" ? ", set piece" : ""}</title></circle>`;
  }).join("");
  return `<svg class="shotmap" viewBox="0 -6 ${W} ${H + 8}" role="img" aria-label="Shot map: ${list.length} shots">
    <rect x="0" y="0" width="${W}" height="${H}" class="sm-pitch"/>${box}${dots}</svg>`;
}
async function fillShotMap(pid) {
  const el = document.getElementById("shotmap"); if (!el) return;
  const d = await loadShots(), list = d?.players?.[pid] || [];
  if (!document.getElementById("shotmap") || +el.dataset.pid !== pid) return;
  if (!list.length) { el.innerHTML = `<h3>Shot map</h3><p class="note">No shots this season.</p>`; return; }
  const goals = list.filter(s => s[3] === "G").length, xg = list.reduce((a, s) => a + s[2], 0);
  const inBox = list.filter(s => s[0] >= 84.3 && s[1] >= 21.1 && s[1] <= 78.9).length, big = list.filter(s => s[2] >= 0.3).length;
  el.innerHTML = `<h3>Shot map</h3>
    <div class="sm-wrap">${shotMapSVG(list)}
      <div class="brk">${[["Shots", list.length], ["Goals", goals], ["xG", xg.toFixed(1)], ["xG per shot", (xg / list.length).toFixed(2)], ["In the box", Math.round(100 * inBox / list.length) + "%"], ["Big chances", big], ["Headers", list.filter(s => s[5]).length]].map(([l, v]) => `<div><span>${l}</span><b>${v}</b></div>`).join("")}</div></div>
    <p class="note"><span class="sm-key sm-g"></span>Goal <span class="sm-key sm-s"></span>Saved or post <span class="sm-key sm-m"></span>Missed or blocked. Bigger circles are better chances (higher xG). This season, from Understat; tap a shot for details.</p>`;
}
