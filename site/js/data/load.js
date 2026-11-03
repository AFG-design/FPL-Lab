// Loading data.json and refreshing it in the background.
/* ---------- load ---------- */
async function fetchData() {
  const r = await fetch("data.json?t=" + Date.now(), { cache: "no-store" });
  if (!r.ok) throw new Error("data.json returned " + r.status);
  return r.json();
}
/* player detail (shots, bonus, defence, history, breakdown) arrives in a second file, after the page is up */
// The detail file must come from the same build as data.json (its "built" stamp): during a site update GitHub Pages
// can briefly serve one file from the old build and the other from the new one, and mixing them would show one
// build's detail against another's headline numbers.
// Missing / late / mismatched: a failed download, an error response, a file with no players or a different "built" is
// retried after 3 s, 10 s and 30 s, and nothing is merged. If all fail, EXTRA.failed says why: Stats and Players show
// an error with Try again, and the player sheet opens with a note that its detail is missing. Nothing is marked ready
// without the detail. A newer data.json arriving meanwhile stops these tries; its own load starts afresh.
const EXTRA = { ready: false, built: null, wait: null, busy: false, failed: null };
const NEEDS_EXTRA = ["stats", "players"];
const EXTRA_RETRY_MS = window.__fastRetry ? [50, 50, 50] : [3000, 10000, 30000];   // __fastRetry: behaviour check only
async function fetchExtra(built) {
  let r;
  try { r = await fetch("data-extra.json?t=" + encodeURIComponent(built), { cache: "no-store" }); }
  catch (e) { return { why: "couldn't be reached" }; }
  if (!r.ok) return { why: `returned ${r.status}` };
  let x;
  try { x = await r.json(); } catch (e) { return { why: "wasn't readable" }; }
  if (!x || !x.players) return { why: "had no player detail" };
  if (x.built !== built) return { why: `is from another update (${x.built || "no date"}, page data ${built})` };
  return { x };
}
function loadExtra() {
  const built = D.meta.built;
  if (EXTRA.built === built && (EXTRA.ready || EXTRA.busy)) return EXTRA.wait;
  Object.assign(EXTRA, { built, ready: false, busy: true, failed: null });
  EXTRA.wait = (async () => {
    let res;
    for (let n = 0; n <= EXTRA_RETRY_MS.length; n++) {
      if (n) await new Promise(f => setTimeout(f, EXTRA_RETRY_MS[n - 1]));
      if (D.meta.built !== built) return;               // newer data arrived meanwhile; its own load takes over
      res = await fetchExtra(built);
      if (D.meta.built !== built) return;
      if (res.x) break;
    }
    EXTRA.busy = false;
    if (res.x) {
      for (const [id, ex] of Object.entries(res.x.players)) if (P[id]) Object.assign(P[id], ex);
      EXTRA.ready = true;
    } else {
      EXTRA.failed = "The detail file " + res.why;
      console.warn("data-extra.json: " + res.why);
    }
    if (NEEDS_EXTRA.includes(S.view)) render();
  })();
  return EXTRA.wait;
}
const withExtra = fn => EXTRA.ready ? fn() : loadExtra().then(fn);
function ingest(d) {
  D = d; P = {}; D.players.forEach(p => P[p.id] = p);
  Object.assign(EXTRA, { ready: false, busy: false, failed: null }); setTimeout(loadExtra, 0);
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
