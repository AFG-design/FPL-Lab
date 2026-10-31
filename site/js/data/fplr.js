// FPL Review import: your own FPL Review CSV export, read in this browser and kept on this device only.
// Nothing is uploaded or committed: the file never leaves the device, and the public site stays FPL LAB's own numbers.
//
// Missing, late or ambiguous data (see CLAUDE.md):
//  - Wrong file / changed format (no ID or Team column, no "N_Pts" + "N_xMins" pairs, values out of range):
//    the import is rejected with the reason, and anything already imported is kept.
//  - IDs that don't line up with FPL's (more than 5% of matched players at a different club, e.g. last season's export):
//    rejected. A few club differences (deadline-day moves) are kept and listed.
//  - A player in FPL LAB but not in the file, or a gameweek the file doesn't cover: shown as "–" with the reason,
//    never as 0, and left out of every sum (a 5-GW total needs all 5 weeks, otherwise it shows "–").
//  - Rows in the file that FPL LAB doesn't list (players with no minutes and little projection) are counted, and the
//    ones FPL Review projects for real points are listed by name.
//  - Late: once a deadline passes, an export taken before it is marked "out of date" everywhere it shows; weeks it
//    still covers keep showing, the weeks already played drop out.
const FPLR_KEY = "fpl.fplr";
let FPLR = store.get(FPLR_KEY);
if (FPLR && (FPLR.v !== 1 || !FPLR.rows)) FPLR = null;   // an older or broken save: ignore it rather than half-use it
const FR_COLS = [["fr1", "FPLR next", 1, 1], ["fr5", "FPLR 5", 1, 1], ["frd", "LAB − FPLR", 1, 1]];

// CSV with quoted fields; strips the byte-order mark Excel and FPL Review put at the start
function parseCSV(text) {
  text = text.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n");
  const rows = []; let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; }
    else cell += c;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  return rows.filter(r => r.some(x => x.trim() !== ""));
}

// Reads the export and checks it against today's data.json. Returns { ok, save, error }.
function readFplr(text, fileName, fileDate) {
  const fail = error => ({ ok: false, error });
  const rows = parseCSV(text);
  if (rows.length < 2) return fail("The file is empty.");
  const head = rows[0].map(h => h.trim()), col = n => head.indexOf(n);
  for (const n of ["ID", "Name", "Team", "Pos"]) if (col(n) < 0) return fail(`No "${n}" column. Is this an FPL Review projections export?`);
  const gws = head.map(h => /^(\d+)_Pts$/.exec(h)).filter(Boolean).map(m => +m[1]).filter(g => col(`${g}_xMins`) >= 0).sort((a, b) => a - b);
  if (!gws.length) return fail('No gameweek columns found (expected pairs like "10_Pts" and "10_xMins").');
  const next = D.meta.next_gw;
  if (gws[gws.length - 1] < next) return fail(`This export only covers up to GW${gws[gws.length - 1]}, which has been played. Download this week's.`);
  const out = {}, notListed = [], clubDiff = [], bad = [];
  let matched = 0;
  for (const r of rows.slice(1)) {
    const id = +r[col("ID")], name = (r[col("Name")] || "").trim(), team = (r[col("Team")] || "").trim();
    if (!Number.isInteger(id) || id <= 0) { bad.push(`a row with no player ID (${name || "no name"})`); continue; }
    const xp = {}, xm = {};
    for (const g of gws) {
      const pts = parseFloat(r[col(`${g}_Pts`)]), mins = parseFloat(r[col(`${g}_xMins`)]);
      // a double gameweek can reach about 180 minutes and roughly 25 points; anything outside is a broken row
      if (!Number.isFinite(pts) || !Number.isFinite(mins) || pts < -3 || pts > 30 || mins < 0 || mins > 200) { bad.push(`${name} GW${g}`); continue; }
      xp[g] = pts; xm[g] = mins;
    }
    const p = P[id];
    if (!p) { const tot = gws.filter(g => g >= next).slice(0, 5).reduce((a, g) => a + (xp[g] || 0), 0); notListed.push([name, team, tot]); continue; }
    matched++;
    if (T[p.team]?.short !== team) clubDiff.push(`${name} (${team} in the file, ${T[p.team]?.short} in FPL)`);
    out[id] = { xp, xm, elite: col("Elite%") >= 0 ? parseFloat(r[col("Elite%")]) : null };
  }
  if (bad.length > 20) return fail(`${bad.length} values can't be read or are out of range (first: ${bad.slice(0, 3).join(", ")}). The export format may have changed.`);
  if (matched < 100) return fail(`Only ${matched} players matched FPL LAB's list by ID. This doesn't look like an export for this season.`);
  if (clubDiff.length > matched * 0.05) return fail(`${clubDiff.length} of ${matched} players are at a different club in the file, so the IDs don't line up with FPL's (an export from another season?).`);
  // FPL Review names exports fplreview_<unix seconds>.csv; otherwise fall back to the file's own date
  const stamp = /fplreview_(\d{9,11})/.exec(fileName || "");
  return { ok: true, save: {
    v: 1, file: fileName || "export.csv", exported: stamp ? +stamp[1] * 1000 : fileDate || null, imported: Date.now(),
    gws, first: Math.max(gws[0], next), rows: out, matched, clubDiff, bad,
    notListed: notListed.filter(x => x[2] >= 1).sort((a, b) => b[2] - a[2]).map(x => `${x[0]} (${x[1]}, ${x[2].toFixed(1)} over 5)`), notListedN: notListed.length,
  } };
}

/* ---------- reading values: null means "not in the file", never 0 ---------- */
const frOn = () => !!FPLR;
// the export was taken before a deadline that has since passed
const frStale = () => !!FPLR && D.meta.next_gw > FPLR.first;
function frXp(id, g) { const v = FPLR?.rows[id]?.xp[g]; return v == null ? null : v; }
function frMins(id, g) { const v = FPLR?.rows[id]?.xm[g]; return v == null ? null : v; }
// sum over the same weeks as FPL LAB's figure; null unless the file covers every one of them
function frFrom(id, gws) {
  let t = 0;
  for (const g of gws) { const v = frXp(id, g); if (v == null) return null; t += v; }
  return t;
}
const frWhy = id => !FPLR ? "No FPL Review file imported" : !FPLR.rows[id] ? "Not in your FPL Review file" : "Your FPL Review file doesn't cover this gameweek";
function frCell(v, id, sign = false) {
  if (v == null) return `<span class="muted" title="${frWhy(id)}">–</span>`;
  const txt = sign ? sgn(v) : f1(v);
  return frStale() ? `<span class="asm" title="From an FPL Review export taken before the GW${FPLR.first} deadline">${txt}</span>` : txt;
}

/* ---------- import / clear ---------- */
function importFplr(file) {
  if (!file) return;
  if (file.size > 5e6) { toast("That file is too big to be an FPL Review export."); return; }
  const rd = new FileReader();
  rd.onerror = () => toast("Couldn't read that file.");
  rd.onload = () => {
    const r = readFplr(String(rd.result), file.name, file.lastModified);
    if (!r.ok) { openFplrDialog(r.error); return; }
    FPLR = r.save;
    try { localStorage.setItem(FPLR_KEY, JSON.stringify(FPLR)); } catch (e) { toast("Imported for this visit only: this browser won't let the site save it."); }
    // show the comparison columns straight away
    const cur = new Set(colsOn()); ["fr5", "frd"].forEach(k => cur.add(k));
    store.set("fpl.cols", playerCols().map(c => c[0]).filter(k => cur.has(k)));
    render(); openFplrDialog();
  };
  rd.readAsText(file);
}
function clearFplr() {
  FPLR = null; try { localStorage.removeItem(FPLR_KEY); } catch (e) {}
  const v = store.get("fpl.cols"); if (Array.isArray(v)) store.set("fpl.cols", v.filter(k => !k.startsWith("fr")));
  render(); toast("FPL Review data removed from this device.");
}

/* ---------- UI ---------- */
// small control beside the Players filters: shows what's loaded, opens the details
function fplrButton() {
  if (!FPLR) return `<label class="btn ghost sm fr-btn" title="Load your FPL Review CSV export to compare. It stays on this device.">FPL Review CSV<input type="file" accept=".csv,text/csv" data-frfile class="vh"></label>`;
  return `<button class="btn ghost sm fr-btn ${frStale() ? "warn" : ""}" data-frinfo="1">FPL Review · ${frStale() ? "out of date" : `GW${FPLR.first}`}</button>`;
}
function openFplrDialog(error) {
  const F = FPLR, when = t => t ? ukWhen(new Date(t).toISOString()) : "–";
  const list = (h, xs, n = 12) => xs.length ? `<details class="fr-list"><summary>${h} (${xs.length})</summary><p class="note">${xs.slice(0, n).map(esc).join(", ")}${xs.length > n ? `, and ${xs.length - n} more` : ""}</p></details>` : "";
  const body = error
    ? `<p class="verdict" style="border-color:var(--bad)">${esc(error)}</p>${F ? `<p class="note">Your earlier import (${esc(F.file)}) is still in use.</p>` : ""}`
    : !F ? "" : `<div class="kpis">
        <div class="kpi"><span class="lbl">Covers</span><b>GW${F.gws[0]}–${F.gws[F.gws.length - 1]}</b><span class="delta muted">${F.gws.length} gameweeks</span></div>
        <div class="kpi"><span class="lbl">Players matched</span><b>${F.matched}</b><span class="delta muted">${F.notListedN} more in the file aren't in FPL LAB's list</span></div>
        <div class="kpi"><span class="lbl">Exported</span><b class="${frStale() ? "down" : ""}">${frStale() ? "Out of date" : ageTxt(F.exported)}</b><span class="delta muted">${when(F.exported)}</span></div></div>
      ${frStale() ? `<p class="verdict" style="border-color:var(--warn)">This export was taken before the GW${F.first} deadline. Weeks already played are dropped; the rest show in grey italics. Import this week's to refresh.</p>` : ""}
      ${list("Players FPL Review projects that FPL LAB doesn't list", F.notListed)}
      ${list("At a different club in the file (kept)", F.clubDiff)}
      ${list("Values that couldn't be read (shown as –)", F.bad)}
      <p class="note">Imported ${when(F.imported)} from ${esc(F.file)}.</p>`;
  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" data-close>×</button><h2 id="frTitle">FPL Review import</h2>
    ${body}
    <p class="note">The file is read in this browser and kept on this device only: nothing is uploaded, and the public site never shows it. Import on each device you use. FPL Review figures are labelled FPLR wherever they appear.</p>
    <div class="fr-actions"><label class="btn primary">${F ? "Import a newer file" : "Choose CSV"}<input type="file" accept=".csv,text/csv" data-frfile class="vh"></label>${F ? '<button class="btn ghost" data-frclear="1">Remove from this device</button>' : ""}</div>`;
  const d = $("#dlg"); d.setAttribute("aria-labelledby", "frTitle"); if (!d.open) d.showModal();
  bindFplr($("#dlgBody"));
  $("#dlgBody [data-close]").onclick = () => d.close();
}
function bindFplr(root = document) {
  root.querySelectorAll("[data-frfile]").forEach(el => { el.onchange = () => { const f = el.files?.[0]; el.value = ""; if ($("#dlg").open) $("#dlg").close(); importFplr(f); }; });
  root.querySelectorAll("[data-frinfo]").forEach(el => { el.onclick = () => openFplrDialog(); });
  root.querySelectorAll("[data-frclear]").forEach(el => { el.onclick = () => { $("#dlg").close(); clearFplr(); }; });
}

// player sheet: FPL Review next to FPL LAB, week by week, with expected minutes (their weakest-vs-ours check)
function fplrSection(p) {
  if (!FPLR) return "";
  const id = p.id, gws = GWS.slice(0, 5), r = FPLR.rows[id];
  if (!r) return `<section class="ph-sec"><h3>FPL Review</h3><p class="note">Not in your FPL Review file.</p></section>`;
  const mine = gws.reduce((a, g) => a + xpg(id, g), 0), theirs = frFrom(id, gws);
  return `<section class="ph-sec"><h3>FPL LAB vs FPL Review${frStale() ? ' <span class="pill warn">out of date</span>' : ""}</h3>
    <div class="tablebox"><table><thead><tr><th></th>${gws.map(g => `<th class="n">GW${g}</th>`).join("")}<th class="n">Next ${gws.length}</th></tr></thead><tbody>
      <tr><th scope="row">xP · LAB</th>${gws.map(g => `<td class="n">${xpCell(id, g)}</td>`).join("")}<td class="n"><b>${f1(mine)}</b></td></tr>
      <tr><th scope="row">xP · FPLR</th>${gws.map(g => `<td class="n">${frCell(frXp(id, g), id)}</td>`).join("")}<td class="n"><b>${frCell(theirs, id)}</b></td></tr>
      <tr><th scope="row">xMins · FPLR</th>${gws.map(g => `<td class="n">${frMins(id, g) ?? "–"}</td>`).join("")}<td class="n muted">LAB ${p.xmin}</td></tr>
    </tbody></table></div>
    <p class="note">Projected points per gameweek. LAB's expected minutes (${p.xmin}) are for next gameweek${r.elite != null && Number.isFinite(r.elite) ? `; FPL Review shows him in ${r.elite.toFixed(1)}% of elite teams` : ""}.</p></section>`;
}
