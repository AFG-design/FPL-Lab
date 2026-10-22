// Loading data.json and refreshing it in the background.
/* ---------- load ---------- */
async function fetchData() {
  const r = await fetch("data.json?t=" + Date.now(), { cache: "no-store" });
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
  try { ingest(await fetchData()); } catch (e) {
    $("#app").innerHTML = `<p class="empty">The data file could not be loaded. Reload the page to try again.</p>`; return;
  }
  header(); render();
}
setInterval(async () => {
  try { const nd = await fetchData(); if (D && nd.meta.built !== D.meta.built) { ingest(nd); header(); render(); } } catch (e) {}
}, 5 * 60 * 1000);
