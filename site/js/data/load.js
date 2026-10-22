// Loading data.json and refreshing it in the background.
/* ---------- load ---------- */
async function fetchData() {
  const r = await fetch("data.json?t=" + Date.now(), { cache: "no-store" });
  if (!r.ok) throw new Error("data.json returned " + r.status);
  return r.json();
}
function ingest(d) {
  D = d; P = {}; D.players.forEach(p => P[p.id] = p);
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
