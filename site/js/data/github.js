// GitHub: one-tap refresh and plan sync. Tokens live only in this browser.
/* ---------- one-tap refresh (starts the GitHub job; needs a token with Actions access) ---------- */
const REFRESH = { busy: false, msg: "", poll: null };
async function startRefresh() {
  if (!syncToken()) { window.open(`https://github.com/${REPO}/actions/workflows/refresh.yml`, "_blank", "noopener"); return; }
  REFRESH.busy = true; REFRESH.msg = ""; header();
  try {
    const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/refresh.yml/dispatches`, {
      method: "POST", headers: { ...syncHeaders(true), "Content-Type": "application/json" }, body: JSON.stringify({ ref: "main" }) });
    if (r.status === 204) {
      REFRESH.msg = "Refresh started. New data usually arrives in 3–6 minutes and the page updates itself.";
      const built = D.meta.built; let n = 0;
      clearInterval(REFRESH.poll);
      REFRESH.poll = setInterval(async () => {
        n++;
        try { const nd = await fetchData(); if (nd.meta.built !== built) { clearInterval(REFRESH.poll); REFRESH.busy = false; REFRESH.msg = "Updated just now."; ingest(nd); header(); render(); return; } } catch (e) {}
        if (n > 40) { clearInterval(REFRESH.poll); REFRESH.busy = false; REFRESH.msg = "Still waiting on GitHub. The data will update when the job finishes."; header(); }
      }, 20000);
    } else if (r.status === 401 || r.status === 403 || r.status === 404) {
      REFRESH.busy = false;
      REFRESH.msg = "Your token can't start the refresh. Give it Actions: Read and write (Sync plan → instructions), or use GitHub's Run workflow button.";
    } else { REFRESH.busy = false; REFRESH.msg = "GitHub said " + r.status + ". Try again in a minute."; }
  } catch (e) { REFRESH.busy = false; REFRESH.msg = "Couldn't reach GitHub. Check your connection."; }
  header();
}

/* ---------- plan sync between devices (GitHub, a private repository of yours) ---------- */
// Your plan, watchlist and journal notes are kept in plan.json on the default branch of a PRIVATE repository you
// choose in the Sync dialog (saved on this device as fpl.syncRepo, "owner/name"). Until 11 Nov 2026 they went to a
// "sync" branch of this public repository, where anyone could read them (FL-088).
// Missing / late / ambiguous: no repository chosen, or no token -> sync is off and says so (the plan stays on this
// device); it never falls back to the old public branch. A repository GitHub reports as public, the site's own
// repository, or one the token can't see is refused when you save, with the reason; if GitHub can't be reached to
// check, nothing is saved. A private repository with no plan.json yet simply starts empty.
const SYNC = { path: "plan.json", msg: "", timer: null, busy: false };
const syncToken = () => { try { return localStorage.getItem("fpl.gh") || ""; } catch (e) { return ""; } };
// owner: letters, digits and hyphens; name: also dots and underscores, but never "." or ".." (no path tricks)
const SYNC_REPO_RE = /^[A-Za-z0-9][A-Za-z0-9-]*\/(?!\.{1,2}$)[A-Za-z0-9_.-]+$/;
const syncRepo = () => { try { const r = localStorage.getItem("fpl.syncRepo") || ""; return SYNC_REPO_RE.test(r) && r.toLowerCase() !== REPO.toLowerCase() ? r : ""; } catch (e) { return ""; } };
const syncReady = () => !!(syncToken() && syncRepo());
// Is this a repository the plan may go to? Returns { ok: true } or { ok: false, why }. Only a repository GitHub
// itself reports as private passes; anything unclear (network error, odd reply) is a no.
async function syncRepoCheck(repo, token) {
  if (!SYNC_REPO_RE.test(repo)) return { ok: false, why: "Write the repository as owner/name, for example your-name/fpl-lab-sync." };
  if (repo.toLowerCase() === REPO.toLowerCase()) return { ok: false, why: "That's the public site repository. Choose a separate private one." };
  if (!token) return { ok: false, why: "Paste a token first." };
  let r;
  try { r = await fetch(`https://api.github.com/repos/${repo}`, { headers: { Accept: "application/vnd.github+json", Authorization: "Bearer " + token }, cache: "no-store" }); }
  catch (e) { return { ok: false, why: "Couldn't reach GitHub to check the repository, so nothing was changed. Try again." }; }
  if (r.status === 401) return { ok: false, why: "GitHub refused the token. Check it and try again." };
  if (r.status === 404 || r.status === 403) return { ok: false, why: "The token can't see that repository. Check the name, and that the token includes it." };
  if (!r.ok) return { ok: false, why: "GitHub said " + r.status + ", so nothing was changed. Try again in a minute." };
  let j; try { j = await r.json(); } catch (e) { j = null; }
  if (!j || j.private !== true) return { ok: false, why: "That repository is public. Your plan only syncs to a private one." };
  return { ok: true };
}
const b64e = str => btoa(unescape(encodeURIComponent(str)));
const b64d = str => decodeURIComponent(escape(atob(str.replace(/\n/g, ""))));
function syncHeaders(auth) {
  const h = { Accept: "application/vnd.github+json" };
  if (auth && syncToken()) h.Authorization = "Bearer " + syncToken();
  return h;
}
async function syncGet() {
  if (!syncReady()) throw new Error("Sync isn't set up on this device");
  const r = await fetch(`https://api.github.com/repos/${syncRepo()}/contents/${SYNC.path}?t=${Date.now()}`, { headers: syncHeaders(true), cache: "no-store" });
  if (r.status === 404) return { doc: { plans: {} }, sha: null };
  if (!r.ok) throw new Error("GitHub said " + r.status);
  const j = await r.json();
  return { doc: JSON.parse(b64d(j.content)), sha: j.sha };
}
function setSyncMsg(t) { SYNC.msg = t; const el = $("#syncMsg"); if (el) el.textContent = t; }
async function syncPull() {
  try {
    const { doc } = await syncGet();
    if (typeof mergeStars === "function" && mergeStars(doc.stars)) render();
    if (typeof mergeReasons === "function" && mergeReasons(doc.reasons)) render();
    const r = doc.plans?.[sbKey()];
    if (r && (r.updated || 0) > (SB.updated || 0)) {
      SB.updated = r.updated; SB.prev = null; applyExtras(r); _base = null;
      if (Array.isArray(r.drafts)) store.set(sbKey() + ".drafts", r.drafts);
      store.set(sbKey(), sbState());
      setSyncMsg("Plan loaded from your other device");
      render();
    }
  } catch (e) { /* offline or rate-limited: local plan stays */ }
}
function syncPush() {
  if (!syncReady()) return;
  clearTimeout(SYNC.timer);
  SYNC.timer = setTimeout(async () => {
    if (SYNC.busy) return syncPush();
    SYNC.busy = true; setSyncMsg("Syncing…");
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const { doc, sha } = await syncGet();
        doc.plans = doc.plans || {};
        const cutoff = Date.now() - 30 * 864e5;
        Object.keys(doc.plans).forEach(k => { if ((doc.plans[k].updated || 0) < cutoff) delete doc.plans[k]; });
        doc.plans[sbKey()] = sbState();
        if (typeof STARS !== "undefined" && STARS.updated >= (doc.stars?.updated || 0)) doc.stars = STARS;
        // journal reasons (D5b): merged item by item, newest edit wins, so neither device loses one
        if (typeof REASONS !== "undefined") { mergeReasons(doc.reasons); doc.reasons = REASONS; }
        const body = { message: "Plan sync", content: b64e(JSON.stringify(doc)) };
        if (sha) body.sha = sha;
        const r = await fetch(`https://api.github.com/repos/${syncRepo()}/contents/${SYNC.path}`, { method: "PUT", headers: { ...syncHeaders(true), "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (r.ok) { setSyncMsg("Plan synced"); break; }
        if (r.status === 401 || r.status === 403) { setSyncMsg("Sync failed: the token was refused. Check it in Sync settings."); break; }
        if (attempt) setSyncMsg("Sync failed (" + r.status + "). Your plan is still saved on this device.");
      } catch (e) { if (attempt) setSyncMsg("Sync failed: offline? Your plan is still saved on this device."); }
    }
    SYNC.busy = false;
  }, 1200);
}
function openSync() {
  const has = !!syncToken(), repo = syncRepo(), on = syncReady();
  const state = on ? `Sync is on for this device, to ${repo}.` : has ? "Sync is paused on this device until you choose a private repository below. Your plan is still saved here." : "Sync is off for this device.";
  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" id="dlgX">×</button>
    <h2>Sync and one-tap refresh</h2>
    <p>Your plan is always saved on this device. Sync copies your plan, watchlist and journal notes to a <b>private</b> GitHub repository that only you can read, so your other devices can pick them up. Each device needs the repository name and an access token, set up once.</p>
    <ol style="margin:0;padding-left:20px;display:grid;gap:4px;font-size:14px">
      <li><a href="https://github.com/new" target="_blank" rel="noopener">Create a repository</a> for the sync, for example "fpl-lab-sync". Choose <b>Private</b> and tick <b>Add a README</b>. You only do this once.</li>
      <li>Open <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">GitHub → new fine-grained token</a> and name it "FPL Lab sync". Under <b>Repository access</b> choose <b>Only select repositories</b> and pick both <b>FPL-Lab</b> and your private sync repository.</li>
      <li>Under <b>Permissions</b>, set <b>Contents</b> to <b>Read and write</b> and <b>Actions</b> to <b>Read and write</b>. Contents lets it save your plan; Actions lets the Refresh button start an update. Generate it and copy it.</li>
      <li>Enter the repository and paste the token below. Both stay in this browser only.</li></ol>
    <div class="filters" style="margin:0"><input id="ghRepo" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" value="${esc(repo)}" placeholder="your-name/fpl-lab-sync" aria-label="Private sync repository, as owner/name" style="flex:1"></div>
    <div class="filters" style="margin:0"><input id="ghTok" type="password" autocomplete="off" placeholder="${has ? "Token saved. Paste a new one to replace it" : "github_pat_…"}" aria-label="GitHub token" style="flex:1"></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" id="tokSave">Save and sync now</button>${has ? '<button class="btn" id="tokDel">Stop syncing from this device</button>' : ""}</div>
    <p class="note" id="syncDlgMsg" role="status">${esc(SYNC.msg || state)}</p>
    <p class="note">Before 11 Nov 2026 the plan was stored on a "sync" branch of the public FPL-Lab repository, where anyone could read it. Nothing is written there any more. Once a device here shows "Plan synced", delete that branch on GitHub (<a href="https://github.com/${REPO}/branches" target="_blank" rel="noopener">FPL-Lab → Branches</a>) so its history goes too.</p>`;
  const dlg = $("#dlg"); dlg.showModal();
  $("#dlgX").onclick = () => dlg.close();
  const say = t => { const el = $("#syncDlgMsg"); if (el) el.textContent = t; };
  $("#tokSave").onclick = async () => {
    const v = $("#ghTok").value.trim() || syncToken(), rp = $("#ghRepo").value.trim();
    say("Checking the repository…");
    const chk = await syncRepoCheck(rp, v);
    if (!chk.ok) { say(chk.why); return; }      // nothing is saved unless GitHub confirms a private repository
    try { localStorage.setItem("fpl.gh", v); localStorage.setItem("fpl.syncRepo", rp); } catch (e) {}
    if (!syncReady()) { say("This browser wouldn't save the settings (private browsing?). Sync stays off."); return; }
    SB.updated = Date.now(); store.set(sbKey(), sbState());
    syncPush(); dlg.close(); header();
  };
  const del = $("#tokDel"); if (del) del.onclick = () => { try { localStorage.removeItem("fpl.gh"); localStorage.removeItem("fpl.syncRepo"); } catch (e) {} setSyncMsg("Sync off on this device"); dlg.close(); header(); };
}

/* ---------- refresh health: is the data fresh, and did the last refresh job work? ---------- */
const HEALTH = { last: null, running: false, checked: 0 };
async function checkHealth() {
  try {
    const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/refresh.yml/runs?per_page=20&t=${Date.now()}`, { headers: syncHeaders(true), cache: "no-store" });
    if (!r.ok) return;
    const runs = (await r.json()).workflow_runs || [];
    HEALTH.runs = runs;
    HEALTH.last = runs.find(x => x.status === "completed" && x.conclusion !== "skipped") || null;
    HEALTH.running = runs.some(x => x.status !== "completed" && Date.now() - new Date(x.created_at) < 3 * 36e5);
    HEALTH.checked = Date.now();
    if (D) { header(); if (S.view === "health") render(); }
  } catch (e) { /* offline or rate-limited: the age check still works */ }
}
function healthBanner() {
  const ageH = (Date.now() - new Date(D.meta.built)) / 36e5, L = HEALTH.last;
  const failed = L && L.conclusion && !["success", "cancelled", "skipped"].includes(L.conclusion) && new Date(L.updated_at) > new Date(D.meta.built);
  if (ageH <= 2 && !failed) return "";
  const t = iso => new Date(iso).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
  const age = ageH >= 48 ? `${Math.floor(ageH / 24)} days` : ageH >= 1.5 ? `${Math.round(ageH)} hours` : `${Math.round(ageH * 60)} minutes`;
  const why = failed ? `The last refresh failed (${t(L.updated_at)}). <a href="${L.html_url}" target="_blank" rel="noopener">See what went wrong</a>.`
    : HEALTH.running ? "A refresh is running now; new data should arrive in a few minutes."
    : "GitHub hasn't run the refresh recently. Its schedule can be delayed at busy times.";
  return `<div class="health ${failed || ageH > 6 ? "bad" : "warn"}" role="alert">${icon("alert")}<span><b>${ageH > 2 ? `Data is ${age} old.` : "Refresh problem."}</b> ${why}${ageH > 2 ? " Prices, injuries and projections may be out of date." : ""}</span>${HEALTH.running ? "" : `<button class="btn sm" data-refresh="1">${icon("refresh")}Refresh now</button>`}</div>`;
}
checkHealth();
setInterval(checkHealth, 10 * 60 * 1000);
