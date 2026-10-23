// Loading data.json and refreshing it in the background.
/* ---------- load ---------- */
async function fetchData() {
  const r = await fetch("data.json?t=" + Date.now(), { cache: "no-store" });
  if (!r.ok) throw new Error("data.json returned " + r.status);
  return r.json();
}
/* player detail (shots, bonus, defence, history, breakdown) arrives in a second file, after the page is up */
const EXTRA = { ready: false, built: null, wait: null };
const NEEDS_EXTRA = ["stats", "players"];
function loadExtra() {
  const built = D.meta.built;
  if (EXTRA.built === built && EXTRA.wait) return EXTRA.wait;
  EXTRA.built = built; EXTRA.ready = false;
  EXTRA.wait = fetch("data-extra.json?t=" + encodeURIComponent(built), { cache: "no-store" }).then(r => r.ok ? r.json() : null).catch(() => null).then(x => {
    if (D.meta.built !== built) return;                  // newer data arrived meanwhile; its own fetch will merge
    if (x && x.players) for (const [id, ex] of Object.entries(x.players)) if (P[id]) Object.assign(P[id], ex);
    EXTRA.ready = true;
    if (NEEDS_EXTRA.includes(S.view)) render();
  });
  return EXTRA.wait;
}
const withExtra = fn => EXTRA.ready ? fn() : loadExtra().then(fn);
function ingest(d) {
  D = d; P = {}; D.players.forEach(p => P[p.id] = p);
  EXTRA.ready = false; setTimeout(loadExtra, 0);
  T = D.teams; GWS = D.meta.proj_gws; PG = GWS.slice(0, Math.min(S.horizon, GWS.length));
  MINE = new Set(D.squad.map(s => s.id));
  if (!S.trendTeam) S.trendTeam = P[D.squad[0]?.id]?.team || 1;
  _base = null;
  loadSandbox();
  syncPull();
}
async function load() {
  render();                                   // highlights the current section in the nav
  if (!D) $("#app").innerHTML = skeleton();
  try { ingest(await fetchData()); } catch (e) {
    if (D) return;                            // keep showing what we have
    $("#app").innerHTML = stateView({
      kind: "error", title: "The latest data didn't load",
      body: navigator.onLine === false
        ? "You're offline and there's no saved copy on this device yet. Connect and try again."
        : "The data file couldn't be reached. This is usually a brief hiccup while the site updates.",
      action: '<button class="btn primary" id="retryLoad">Try again</button>' });
    $("#retryLoad").onclick = load;
    return;
  }
  header(); render();
}
setInterval(async () => {
  try { const nd = await fetchData(); if (D && nd.meta.built !== D.meta.built) { ingest(nd); header(); render(); } } catch (e) {}
}, 5 * 60 * 1000);
