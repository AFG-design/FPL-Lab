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

/* ---------- plan sync between devices (GitHub, "sync" branch) ---------- */
const SYNC = { branch: "sync", path: "plan.json", msg: "", timer: null, busy: false };
const syncToken = () => { try { return localStorage.getItem("fpl.gh") || ""; } catch (e) { return ""; } };
const b64e = str => btoa(unescape(encodeURIComponent(str)));
const b64d = str => decodeURIComponent(escape(atob(str.replace(/\n/g, ""))));
function syncHeaders(auth) {
  const h = { Accept: "application/vnd.github+json" };
  if (auth && syncToken()) h.Authorization = "Bearer " + syncToken();
  return h;
}
async function syncGet() {
  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${SYNC.path}?ref=${SYNC.branch}&t=${Date.now()}`, { headers: syncHeaders(true), cache: "no-store" });
  if (r.status === 404) return { doc: { plans: {} }, sha: null };
  if (!r.ok) throw new Error("GitHub said " + r.status);
  const j = await r.json();
  return { doc: JSON.parse(b64d(j.content)), sha: j.sha };
}
function setSyncMsg(t) { SYNC.msg = t; const el = $("#syncMsg"); if (el) el.textContent = t; }
async function syncPull() {
  try {
    const { doc } = await syncGet();
    const r = doc.plans?.[sbKey()];
    if (r && (r.updated || 0) > (SB.updated || 0)) {
      SB.moves = (r.moves || []).filter(m => P[m.in] && P[m.out] && GWS.includes(m.gw));
      SB.source = r.source || "custom"; SB.updated = r.updated; applyExtras(r); sanitize(); _base = null;
      if (Array.isArray(r.drafts)) store.set(sbKey() + ".drafts", r.drafts);
      store.set(sbKey(), sbState());
      setSyncMsg("Plan loaded from your other device");
      render();
    }
  } catch (e) { /* offline or rate-limited: local plan stays */ }
}
function syncPush() {
  if (!syncToken()) return;
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
        const body = { message: "Plan sync", content: b64e(JSON.stringify(doc)), branch: SYNC.branch };
        if (sha) body.sha = sha;
        const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${SYNC.path}`, { method: "PUT", headers: { ...syncHeaders(true), "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (r.ok) { setSyncMsg("Plan synced"); break; }
        if (r.status === 401 || r.status === 403) { setSyncMsg("Sync failed: the token was refused. Check it in Sync settings."); break; }
        if (attempt) setSyncMsg("Sync failed (" + r.status + "). Your plan is still saved on this device.");
      } catch (e) { if (attempt) setSyncMsg("Sync failed: offline? Your plan is still saved on this device."); }
    }
    SYNC.busy = false;
  }, 1200);
}
function openSync() {
  const has = !!syncToken();
  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" id="dlgX">×</button>
    <h2>Sync and one-tap refresh</h2>
    <p>Your plan is always saved on this device. Every device can read your synced plan. To save changes from a device to the sync, it needs a GitHub access token, set up once per device.</p>
    <ol style="margin:0;padding-left:20px;display:grid;gap:4px;font-size:14px">
      <li>Open <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">GitHub → new fine-grained token</a>.</li>
      <li>Name it "FPL Lab sync". Under <b>Repository access</b> choose <b>Only select repositories</b> → <b>FPL-Lab</b>.</li>
      <li>Under <b>Permissions</b>, set <b>Contents</b> to <b>Read and write</b> and <b>Actions</b> to <b>Read and write</b>. Contents lets it save your plan; Actions lets the Refresh button start an update. Generate it and copy it.</li>
      <li>Paste it below. It stays in this browser only.</li></ol>
    <div class="filters" style="margin:0"><input id="ghTok" type="password" autocomplete="off" placeholder="${has ? "Token saved. Paste a new one to replace it" : "github_pat_…"}" aria-label="GitHub token" style="flex:1"></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" id="tokSave">Save and sync now</button>${has ? '<button class="btn" id="tokDel">Stop syncing from this device</button>' : ""}</div>
    <p class="note">${esc(SYNC.msg || (has ? "Sync is on for this device." : "Sync is off for this device."))} The plan is stored in your FPL-Lab repository on a separate "sync" branch, so it never triggers a site rebuild.</p>`;
  const dlg = $("#dlg"); dlg.showModal();
  $("#dlgX").onclick = () => dlg.close();
  $("#tokSave").onclick = () => {
    const v = $("#ghTok").value.trim();
    try { if (v) localStorage.setItem("fpl.gh", v); } catch (e) {}
    if (!syncToken()) { setSyncMsg("Paste a token first."); return; }
    SB.updated = Date.now(); store.set(sbKey(), sbState());
    syncPush(); dlg.close(); header();
  };
  const del = $("#tokDel"); if (del) del.onclick = () => { try { localStorage.removeItem("fpl.gh"); } catch (e) {} setSyncMsg("Sync off on this device"); dlg.close(); header(); };
}
