// Player explorer.
/* ---------- Players ---------- */
// [key, header, numeric, shown by default]
const COLS = [["team", "Team", 0, 1], ["pos", "Pos", 0, 1], ["price", "£m", 1, 1], ["form", "Form", 1, 1], ["pts", "Pts", 1, 1],
  ["xg", "xG", 1, 1], ["xa", "xA", 1, 1], ["xgi90_4", "xGI/90 L4", 1, 1], ["own", "Own %", 1, 1], ["t10k", "Top 10k", 1, 0],
  ["nailed", "Nailed", 1, 1], ["xmin", "xMins", 1, 0], ["xp1", "xP next", 1, 1], ["xp5", "xP 5", 1, 1], ["val", "xP5/£m", 1, 0], ["pc", "Price change", 1, 1]];
// the columns shown, in the order shown (FL-156: you can reorder them). "fpl.cols" was always a list of keys, so the
// columns you'd picked before carry forward (in the order they were saved); a key no longer in COLS is ignored.
const colsDefault = () => COLS.filter(c => c[3]).map(c => c[0]);
function cleanCols(list) { const known = new Set(COLS.map(c => c[0])); return [...new Set((Array.isArray(list) ? list : []).filter(k => known.has(k)))]; }
const colsOn = () => { const v = store.get("fpl.cols"); return Array.isArray(v) ? cleanCols(v) : colsDefault(); };

/* ---------- saved table views (FL-156 idea 1) and density (idea 10) ----------
   A view keeps the columns and their order, the search, the filters, the sort and the forecast period (S.xh, which never
   touches the Planner). Saved on this device only (Ade, 13 Nov): "fpl.playerviews" = [{name, state}], with the one in
   use in "fpl.playerview". Missing or ambiguous, never guessed: an unreadable list loads as no views; a view naming a
   column or sort that no longer exists drops it (sort falls back to the default); a filter value the menus don't offer
   is kept, as the price menus already add a value set from elsewhere; a view saved before periods existed keeps the
   current period. "Default" is every filter cleared, the default columns and xP sorted high to low; it leaves the
   forecast period as it is (a preference of its own). */
const PV_DEFAULT = { q: "", pos: "ALL", team: "ALL", minp: "", maxp: "", minform: "", own: "any", minnail: "", minxmin: "", fxtop: "", sort: "xp5", dir: -1 };
const PV_KEYS = Object.keys(PV_DEFAULT);
const PV_NAME_MAX = 40;
function pvList() {
  const v = store.get("fpl.playerviews");
  return Array.isArray(v) ? v.filter(x => x && typeof x.name === "string" && x.name.trim() && x.state && typeof x.state === "object") : [];
}
function pvState() {
  const st = { cols: colsOn(), xh: S.xh };
  PV_KEYS.forEach(k => { st[k] = S[k] ?? PV_DEFAULT[k]; });
  return st;
}
function pvApply(st) {
  store.set("fpl.cols", Array.isArray(st.cols) && cleanCols(st.cols).length ? cleanCols(st.cols) : null);
  PV_KEYS.forEach(k => { S[k] = st[k] ?? PV_DEFAULT[k]; });
  S.pos = ["ALL", "GKP", "DEF", "MID", "FWD"].includes(S.pos) ? S.pos : "ALL";
  if (S.sort !== "name" && !COLS.some(c => c[0] === S.sort)) { S.sort = PV_DEFAULT.sort; S.dir = PV_DEFAULT.dir; }
  S.dir = S.dir === 1 ? 1 : -1;
  if (st.xh != null) setForecast(+st.xh);
}
const pvActive = () => { const n = store.get("fpl.playerview"); return pvList().find(v => v.name === n) || null; };
const pvSame = (a, b) => JSON.stringify(a) === JSON.stringify(b);
// a view's state as it would be applied, so "changed" compares like with like
function pvNorm(st) { const o = { cols: cleanCols(st.cols).length ? cleanCols(st.cols) : colsDefault(), xh: st.xh ?? S.xh }; PV_KEYS.forEach(k => { o[k] = st[k] ?? PV_DEFAULT[k]; }); return o; }
function pvChanged() { const a = pvActive(); return a ? !pvSame(pvNorm(a.state), pvNorm(pvState())) : !pvSame(pvNorm({ ...PV_DEFAULT, cols: colsDefault(), xh: S.xh }), pvNorm(pvState())); }
S.pvEdit = null; S.pvMsg = "";
function pvSaveAs(name, mode) {
  name = String(name || "").trim().slice(0, PV_NAME_MAX);
  if (!name) { S.pvMsg = "Give the view a name."; return false; }
  const list = pvList(), cur = list.find(v => v.name === store.get("fpl.playerview")) || null;   // edit the list that gets saved
  const clash = list.find(v => v.name.toLowerCase() === name.toLowerCase() && !(mode === "rename" && cur && v.name === cur.name));
  if (clash) { S.pvMsg = `There's already a view called "${clash.name}".`; return false; }
  if (mode === "rename" && cur) { cur.name = name; store.set("fpl.playerviews", list); }
  else { list.push({ name, state: pvState() }); store.set("fpl.playerviews", list); }
  store.set("fpl.playerview", name); S.pvEdit = null; S.pvMsg = mode === "rename" ? `Renamed to "${name}".` : `Saved "${name}".`;
  return true;
}
function pvUpdate() { const list = pvList(), cur = list.find(v => v.name === store.get("fpl.playerview")); if (!cur) return; cur.state = pvState(); store.set("fpl.playerviews", list); S.pvMsg = `Updated "${cur.name}".`; }
function pvDelete() { const n = store.get("fpl.playerview"); store.set("fpl.playerviews", pvList().filter(v => v.name !== n)); store.set("fpl.playerview", null); S.pvMsg = `Deleted "${n}". The table stays as it is.`; }
function pvSelect(name) {
  const v = pvList().find(x => x.name === name);
  if (v) { pvApply(v.state); store.set("fpl.playerview", v.name); S.pvMsg = ""; }
  else { pvApply({ ...PV_DEFAULT, cols: null }); store.set("fpl.playerview", null); S.pvMsg = ""; }
  S.pvEdit = null;
}
S.pdens = store.get("fpl.pdensity") === "comfy" ? "comfy" : "compact";
function pvBar() {
  const list = pvList(), cur = pvActive(), changed = pvChanged();
  const opts = `<option value="">Default (all players)</option>${list.map(v => `<option value="${esc(v.name)}" ${cur && cur.name === v.name ? "selected" : ""}>${esc(v.name)}</option>`).join("")}`;
  const edit = S.pvEdit === "delete" && cur ? `<span class="pv-form" role="group" aria-label="Confirm delete"><span>Delete "${esc(cur.name)}"?</span>
      <button class="btn" type="button" data-pvact="confirm-delete">Delete</button><button class="btn" type="button" data-pvact="cancel">Cancel</button></span>`
    : S.pvEdit ? `<form class="pv-form" id="pvForm"><input id="pvName" maxlength="${PV_NAME_MAX}" aria-label="${S.pvEdit === "rename" ? "New name for this view" : "Name for the new view"}" placeholder="View name" value="${S.pvEdit === "rename" && cur ? esc(cur.name) : ""}">
      <button class="btn primary" type="submit">${S.pvEdit === "rename" ? "Rename" : "Save"}</button><button class="btn" type="button" data-pvact="cancel">Cancel</button></form>` : "";
  // Update sits out in the open when it applies; the rest of a saved view's actions wait in Manage, so on a phone the
  // players are still near the top
  const acts = S.pvEdit ? "" : `${cur && changed ? `<button class="btn" type="button" data-pvact="update">Update view</button>` : ""}
      ${cur ? `<details class="pv-manage"><summary>Manage</summary><div class="pv-menu" role="group" aria-label="Manage ${esc(cur.name)}">
        <button class="btn" type="button" data-pvact="new">Save as new view</button><button class="btn" type="button" data-pvact="rename">Rename</button><button class="btn" type="button" data-pvact="delete">Delete</button></div></details>`
        : `<button class="btn" type="button" data-pvact="new">Save view</button>`}`;
  return `<div class="filters pv-bar">
      <label class="pv-lbl" for="pvSel">My views</label><select id="pvSel">${opts}</select>
      ${changed ? `<span class="pill mut" title="The table differs from ${cur ? `"${esc(cur.name)}" as saved` : "the default"}">Changed</span>` : ""}
      ${acts}${edit}
      <div class="seg pv-dens" role="group" aria-label="Table density">${[["compact", "Compact"], ["comfy", "Comfortable"]].map(([k, l]) => `<button type="button" data-dens="${k}" aria-pressed="${S.pdens === k}">${l}</button>`).join("")}</div>
    </div>${S.pvMsg ? `<p class="note pv-msg" role="status">${esc(S.pvMsg)}</p>` : ""}`;
}
/* ---------- filter presets (FL-156 idea 13) ----------
   A preset only fills in the normal filter bar (so you see its limits there, change them there, and Save view keeps the
   result); it keeps your position, search, columns and forecast period and clears every other filter. Before it is
   applied, the bar says what it will set and clear (S.presetAsk), with Apply and Cancel. Definitions reuse what the app
   already does:
     Budget starters  price cap for the position (GKP and DEF £4.5m, MID £5.5m, FWD £6.0m; £5.5m with All) and
                      Nailed 70+, the rule Home's budget picks use (tags.js), sorted by xP per £m
     Low-owned        the ownership filter's "Differentials (under 5%)" and xMins 60+ so they play, sorted by xP
     Strong fixtures  clubs in the top 6 for fixtures over the forecast period (attack for MID/FWD, clean-sheet chance
                      for GKP/DEF, as the Fixtures page ranks them, fixtures.js teamRun) and Nailed 60+, sorted by xP
   Fixture ranks: a blank gameweek adds nothing and a double adds both games; a club with no fixture data ranks last. */
const BUDGET_CAP = { GKP: 4.5, DEF: 4.5, MID: 5.5, FWD: 6, ALL: 5.5 };
const PRESETS = {
  budget: { name: "Budget starters", set: () => ({ maxp: String(BUDGET_CAP[S.pos] ?? 5.5), minnail: "70", sort: "val", dir: -1 }) },
  lowown: { name: "Low-owned options", set: () => ({ own: "diff", minxmin: "60", sort: "xp5", dir: -1 }) },
  fixtures: { name: "Strong fixtures", set: () => ({ fxtop: "6", minnail: "60", sort: "xp5", dir: -1 }) },
};
const PRESET_CLEARS = ["team", "minp", "maxp", "minform", "own", "minnail", "minxmin", "fxtop"];
// each club's rank (1 = easiest) for attack and for defence over the forecast period
function fixtureRanks() {
  const gws = fcGws(), att = {}, def = {};
  Object.values(T).forEach(t => {
    const run = typeof teamRun === "function" && t.far ? teamRun(t) : {};
    att[t.id] = gws.reduce((a, g) => a + (run[g] || []).reduce((b, x) => b + x.xgf, 0), 0);
    def[t.id] = gws.reduce((a, g) => a + (run[g] || []).reduce((b, x) => b + x.cs, 0), 0);
  });
  const rank = o => Object.fromEntries(Object.keys(o).sort((a, b) => o[b] - o[a]).map((id, k) => [id, k + 1]));
  return { att: rank(att), def: rank(def) };
}
const fxKind = p => (p.pos === "GKP" || p.pos === "DEF" ? "def" : "att");
// what a preset would change, in words: [{label, from, to}], set and cleared
function presetDiff(key) {
  const set = { ...PRESET_CLEARS.reduce((o, k) => ({ ...o, [k]: PV_DEFAULT[k] }), {}), ...PRESETS[key].set() };
  return Object.entries(set).filter(([k, v]) => String(S[k] ?? "") !== String(v) && !(k === "dir")).map(([k, v]) => ({ k, from: filterTxt(k, S[k]), to: filterTxt(k, v) }));
}
function filterTxt(k, v) {
  if (v == null || v === "" || v === "ALL" || v === "any") return null;
  const lab = { team: () => T[v]?.name, minp: () => `from £${(+v).toFixed(1)}m`, maxp: () => `up to £${(+v).toFixed(1)}m`, minform: () => `form ${v}+`,
    own: () => ({ diff: "under 5% owned", mid: "5% to 20% owned", template: "20%+ owned" })[v], minnail: () => `Nailed ${v}+`, minxmin: () => `xMins ${v}+`,
    fxtop: () => `fixtures: top ${v} clubs (${fcLabel()})`, sort: () => `sorted by ${colLabel(v, COLS.find(c => c[0] === v)?.[1] || v)}` };
  return lab[k] ? lab[k]() : String(v);
}
function presetAsk() {
  const key = S.presetAsk; if (!PRESETS[key]) return "";
  const d = presetDiff(key), sets = d.filter(x => x.to).map(x => x.to), clears = d.filter(x => !x.to && x.from).map(x => x.from);
  return `<div class="verdict preset-ask" role="group" aria-label="${PRESETS[key].name}">
    <p style="margin:0"><b>${PRESETS[key].name}</b> ${sets.length ? `sets ${sets.join(", ")}` : "changes nothing you haven't already set"}${clears.length ? `, and clears ${clears.join(", ")}` : ""}. Your position, search, columns and forecast period stay.${key === "budget" && S.pos === "ALL" ? " Pick a position first for its own cap (GKP and DEF £4.5m, MID £5.5m, FWD £6.0m)." : ""}</p>
    <div style="display:flex;gap:8px;margin-top:8px"><button class="btn primary" type="button" data-preset-apply="${key}">Apply</button><button class="btn" type="button" data-preset-cancel="1">Cancel</button></div></div>`;
}
function presetApply(key) {
  if (!PRESETS[key]) return;
  PRESET_CLEARS.forEach(k => { S[k] = PV_DEFAULT[k]; });
  Object.assign(S, PRESETS[key].set());
  S.presetAsk = null;
}
S.presetAsk = null;
// Columns picker rows: shown columns first, in their order, each with move left / right; then the hidden ones
function colPickRows(on) {
  const shown = colsOn(), lab = k => colLabel(k, COLS.find(c => c[0] === k)[1]);
  const row = (k, i) => `<div class="cp-row"><label><input type="checkbox" data-col="${k}" checked> ${lab(k)}</label>
      <span class="cp-mv"><button type="button" class="btn sm icon-only" data-colmove="${k}:-1" aria-label="Move ${esc(lab(k))} left" ${i === 0 ? "disabled" : ""}>↑</button><button type="button" class="btn sm icon-only" data-colmove="${k}:1" aria-label="Move ${esc(lab(k))} right" ${i === shown.length - 1 ? "disabled" : ""}>↓</button></span></div>`;
  return shown.map(row).join("") + COLS.filter(c => !on.has(c[0])).map(([k]) => `<div class="cp-row"><label><input type="checkbox" data-col="${k}"> ${lab(k)}</label></div>`).join("");
}
function colMove(k, d) {
  const c = colsOn(), i = c.indexOf(k), j = i + d;
  if (i < 0 || j < 0 || j >= c.length) return;
  [c[i], c[j]] = [c[j], c[i]]; store.set("fpl.cols", c);
}
function nailedPill(p) {
  const n = p.nailed ?? 0, c = n >= 85 ? "good" : n >= 60 ? "warn" : "bad";
  return `<span class="pill ${c}" title="${esc(p.mflag || (n >= 85 ? "Nailed on" : n >= 60 ? "Usually starts" : "Rotation or bench risk"))}">${n}</span>`;
}
const COLTERM = { xgi90_4: "xgi", nailed: "nailed", xmin: "xmins", xp1: "xp", xp5: "xp" };
// FL-156: the "xp5" and "val" columns follow the forecast period (S.xh); their keys stay the same so saved column
// choices (fpl.cols) and sort keep working. "xP next" stays the next gameweek, whatever the period.
const colLabel = (k, l) => k === "xp5" ? `xP ${fcLabel()}` : k === "val" ? `xP ${fcLabel()}/£m` : l;
function priceCell(p) {
  const v = p.price_proj?.[0]; if (v == null) return "–";
  const w = Math.min(100, Math.abs(v)) * 0.5;
  return `<span class="minibar ${v < 0 ? "neg" : ""}" style="width:${w}px" title="${v.toFixed(0)}% towards a ${v < 0 ? "fall" : "rise"}"></span> <span class="mono">${v.toFixed(0)}%</span>`;
}
function vPlayers() {
  const t10 = p => D.crowd?.top10k.own[p.id] || 0;
  let rows = D.players.slice();
  if (S.pos !== "ALL") rows = rows.filter(p => p.pos === S.pos);
  if (S.team !== "ALL") rows = rows.filter(p => String(p.team) === String(S.team));
  if (S.minp) rows = rows.filter(p => p.price >= +S.minp);
  if (S.maxp) rows = rows.filter(p => p.price <= +S.maxp);
  if (S.minform) rows = rows.filter(p => +p.form >= +S.minform);
  if (S.own === "diff") rows = rows.filter(p => p.own < 5);
  else if (S.own === "mid") rows = rows.filter(p => p.own >= 5 && p.own < 20);
  else if (S.own === "template") rows = rows.filter(p => p.own >= 20);
  if (S.minnail) rows = rows.filter(p => (p.nailed ?? 0) >= +S.minnail);
  if (S.minxmin) rows = rows.filter(p => (p.xmin ?? 0) >= +S.minxmin);
  if (S.fxtop) { const r = fixtureRanks(); rows = rows.filter(p => (r[fxKind(p)][p.team] ?? 99) <= +S.fxtop); }
  if (S.q) { const q = S.q.toLowerCase(); rows = rows.filter(p => (p.name + " " + p.full).toLowerCase().includes(q)); }
  const val = p => S.sort === "t10k" ? t10(p) : S.sort === "val" ? fcTot(p).sum / p.price : S.sort === "xp5" ? fcTot(p).sum : S.sort === "team" ? T[p.team].short
    : S.sort === "pc" ? (p.price_proj?.[0] ?? 0) : ["name", "pos"].includes(S.sort) ? p[S.sort] : +p[S.sort] || 0;
  rows.sort((a, b) => { const x = val(a), y = val(b); return (x > y ? 1 : x < y ? -1 : 0) * S.dir; });
  const shown = rows.slice(0, 150), on = new Set(colsOn()), cols = colsOn().map(k => COLS.find(c => c[0] === k));
  const cell = {
    team: p => T[p.team].short, pos: p => p.pos, price: p => p.price.toFixed(1), form: p => f1(p.form), pts: p => p.pts,
    xg: p => (p.xg ?? 0).toFixed(1), xa: p => (p.xa ?? 0).toFixed(1), xgi90_4: p => p.xgi90_4.toFixed(2), own: p => p.own.toFixed(1),
    t10k: p => D.crowd ? t10(p).toFixed(0) + "%" : "–", nailed: p => nailedPill(p), xmin: p => p.xmin, xp1: p => xpCell(p.id, D.meta.next_gw),
    xp5: p => fcTxt(p, true), val: p => (fcTot(p).sum / p.price).toFixed(2), pc: p => priceCell(p),
  };
  const teamOpts = Object.values(T).sort((a, b) => a.name.localeCompare(b.name)).map(t => `<option value="${t.id}" ${String(S.team) === String(t.id) ? "selected" : ""}>${t.name}</option>`).join("");
  // a limit set elsewhere (the homepage's Budget options) is added to the list so the menu shows it
  const prices = [...new Set([4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 9, 10, 12, 15, ...[S.minp, S.maxp].filter(Boolean).map(Number)])].sort((a, b) => a - b);
  const priceSel = (id, cur, any, op) => `<select id="${id}" aria-label="${any}"><option value="">${any}</option>${prices.map(x => `<option ${+cur === x ? "selected" : ""} value="${x}">${op} £${x.toFixed(1)}m</option>`).join("")}</select>`;
  const active = [S.pos !== "ALL", S.team !== "ALL", S.minp, S.maxp, S.minform, S.own && S.own !== "any", S.minnail, S.minxmin, S.fxtop, S.q].filter(Boolean).length;
  const head = `<th class="sort sticky-col" data-sort="name" ${S.sort === "name" ? `aria-sort="${S.dir < 0 ? "descending" : "ascending"}"` : ""}>Player${S.sort === "name" ? (S.dir < 0 ? " ↓" : " ↑") : ""}</th>` +
    cols.map(([k, l, n]) => `<th class="sort ${n ? "n" : ""}" data-sort="${k}" ${S.sort === k ? `aria-sort="${S.dir < 0 ? "descending" : "ascending"}"` : ""}>${COLTERM[k] ? term(COLTERM[k], colLabel(k, l)) : colLabel(k, l)}${S.sort === k ? (S.dir < 0 ? " ↓" : " ↑") : ""}</th>`).join("");
  const body = shown.map(p => `<tr class="${MINE.has(p.id) ? "mine" : ""}">
      <td class="sticky-col"><span class="pcell"><label class="cmp-hit"><input type="checkbox" data-cmp="${p.id}" ${S.cmp.includes(p.id) ? "checked" : ""} aria-label="Compare ${esc(p.name)}"></label>
        <button data-p="${p.id}" class="pname linkish">${esc(p.name)}</button>${p.status !== "a" ? `<span class="pill ${p.status === "d" ? "warn" : "bad"}" title="${esc(p.news)}">${fplChance(p.chance)}</span>` : ""}${playerTags(p, 2)}</span></td>
      ${cols.map(([k, , n]) => `<td class="${n ? "n" : ""}">${cell[k](p)}</td>`).join("")}</tr>`).join("");
  return `<div class="panel explorer${S.pdens === "comfy" ? " dens-comfy" : ""}">
    <div class="bar"><h2>Players</h2><span class="muted" aria-live="polite">${rows.length} player${rows.length === 1 ? "" : "s"}${rows.length > 150 ? ", top 150 shown" : ""}</span></div>
    ${pvBar()}
    <div class="filters presets" role="group" aria-label="Quick presets"><span class="pv-lbl">Presets</span>${Object.entries(PRESETS).map(([k, p]) => `<button class="btn preset-btn" type="button" data-preset="${k}" aria-pressed="${S.presetAsk === k}">${p.name}</button>`).join("")}
      <select id="presetSel" class="preset-sel" aria-label="Presets"><option value="">Choose a preset…</option>${Object.entries(PRESETS).map(([k, p]) => `<option value="${k}" ${S.presetAsk === k ? "selected" : ""}>${p.name}</option>`).join("")}</select></div>
    ${presetAsk()}
    <div class="filters">
      <input type="search" id="q" placeholder="Search players" value="${esc(S.q)}" aria-label="Search players">
      <div class="seg" role="group" aria-label="Forecast period">${fcButtons()}</div>
      <div class="seg" role="group" aria-label="Position">${["ALL", "GKP", "DEF", "MID", "FWD"].map(x => `<button data-fpos="${x}" aria-pressed="${S.pos === x}">${x === "ALL" ? "All" : x}</button>`).join("")}</div>
    </div>
    <div class="filters">
      <select id="fteam" aria-label="Team"><option value="ALL">All teams</option>${teamOpts}</select>
      ${priceSel("fmin", S.minp, "Min price", "From")}${priceSel("fmax", S.maxp, "Max price", "Up to")}
      <select id="fform" aria-label="Minimum form"><option value="">Any form</option>${[2, 3, 4, 5, 6, 8].map(x => `<option ${+S.minform === x ? "selected" : ""} value="${x}">Form ${x}+</option>`).join("")}</select>
      <select id="fown" aria-label="Ownership"><option value="any">Any ownership</option>${[["diff", "Differentials (under 5%)"], ["mid", "5% to 20% owned"], ["template", "Template (20%+)"]].map(([v, l]) => `<option value="${v}" ${S.own === v ? "selected" : ""}>${l}</option>`).join("")}</select>
      ${(() => { const n = [S.minnail, S.minxmin, S.fxtop].filter(Boolean).length; return `<button class="btn more-f-btn" type="button" data-morefilters="1" aria-expanded="${!!S.moreF}">More filters${n ? ` (${n})` : ""}</button>`; })()}
      <span class="more-f${S.moreF ? " open" : ""}"><select id="fnail" aria-label="Minimum Nailed"><option value="">Any Nailed</option>${[60, 70, 80, 90].map(x => `<option ${+S.minnail === x ? "selected" : ""} value="${x}">Nailed ${x}+</option>`).join("")}</select>
      <select id="fxmin" aria-label="Minimum expected minutes"><option value="">Any xMins</option>${[45, 60, 70, 80].map(x => `<option ${+S.minxmin === x ? "selected" : ""} value="${x}">xMins ${x}+</option>`).join("")}</select>
      <select id="ffx" aria-label="Fixtures over the forecast period"><option value="">Any fixtures</option>${[4, 6, 8, 10].map(x => `<option ${+S.fxtop === x ? "selected" : ""} value="${x}">Fixtures: top ${x} clubs</option>`).join("")}</select></span>
      ${active ? `<button class="btn ghost sm" data-fclear="1">Clear filters (${active})</button>` : ""}
      <details class="colpick"><summary>Columns</summary><div class="colpick-body" role="group" aria-label="Columns to show">
        ${colPickRows(on)}
        <button class="btn ghost sm" data-colreset="1">Reset columns</button></div></details>
    </div>
    ${compareHTML()}
    ${shown.length ? `<div class="tablebox"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`
      : stateView({ title: "No players match", body: "Loosen a filter, or clear them all to see every player.", action: `<button class="btn" data-fclear="1">Clear filters</button>` })}
    <p class="note">Yellow edge = in your squad. Tick players to compare them side by side. Nailed = how sure a player is to start and play most of the game (0–100). xGI/90 L4 = expected goal involvement per 90 over the last 4 gameweeks. xP ${fcLabel()} = projected points over the forecast period you pick above (blank gameweeks count 0; * = some gameweeks have no projection yet, left out); xP next = GW${D.meta.next_gw} only. <span class="asm">Grey italic</span> xP = assumed (no official return date or chance from FPL). Price change = progress towards a change at the next update${nextPriceUpdate() ? ` (${priceUpdateTxt(nextPriceUpdate())})` : ""}.</p></div>`;
}
function compareHTML() {
  if (!S.cmp.length) return "";
  const ps = S.cmp.map(i => P[i]).filter(Boolean), g = D.meta.next_gw, gws = fcGws();
  const t10 = p => D.crowd?.top10k?.own?.[p.id] ?? null;
  const pct = x => x == null ? "–" : Math.round(x) + "%";
  // [label, value fn, better: 1 higher / -1 lower / 0 neither, format, glossary key]
  const groups = [
    ["Projections", [["xP GW" + g, p => p.xp1, 1, f1, "xp"], [`xP ${fcLabel()}`, p => fcTot(p).sum, 1, (x, p) => fcTxt(p), "xp"],
      ["Chance of 10+", p => (p.dist?.[g]?.[0] ?? 0) * 100, 1, pct], ["Chance of 2 or fewer", p => (p.dist?.[g]?.[2] ?? 0) * 100, -1, pct]]],
    ["Minutes", [["Nailed", p => p.nailed, 1, x => x, "nailed"], ["Expected minutes", p => p.xmin, 1, x => x, "xmins"], [`Mins ${"L4"}`, p => p.mins4, 1, x => x, "l4"]]],
    ["Attack", [["xGI/90 L4", p => p.xgi90_4, 1, x => x.toFixed(2), "xgi"], ["xGI/90 model", p => p.xgi90, 1, x => x.toFixed(2), "xgi"],
      ["In box/90", p => p.us?.sib90 ?? 0, 1, x => x.toFixed(1), "inbox"], ["Big chances/90", p => p.us?.bc90 ?? 0, 1, x => x.toFixed(2), "bigchance"],
      ["Created/90", p => p.us?.cc90 ?? 0, 1, x => x.toFixed(1), "created"], ["Goals − xG", p => p.g_xg, 0, x => (x > 0 ? "+" : "") + x.toFixed(1)]]],
    ["Defence and bonus", [["DC chance", p => p.dc_rate * 100, 1, pct, "dc"], ["BPS/90 L4", p => p.bf4?.bps90 ?? 0, 1, x => x.toFixed(0), "bps"]]],
    ["Season", [["Points", p => p.pts, 1, x => x], ["Goals, assists", p => p.goals + p.assists, 1, (x, p) => `${p.goals}, ${p.assists}`], ["Form", p => p.form, 1, f1]]],
    ["Price and ownership", [["Price", p => p.price, -1, money], ["Price change tonight", p => p.price_proj?.[0] ?? 0, 0, x => (x > 0 ? "+" : "") + x.toFixed(0) + "%"],
      ["Owned (all)", p => p.own, 0, x => x.toFixed(1) + "%"], ["Owned (top 10k)", p => t10(p) ?? -1, 0, x => x < 0 ? "–" : x.toFixed(0) + "%", "eo"]]],
  ];
  const cell = (fn, dir, fmt) => { const vals = ps.map(fn), best = dir === 1 ? Math.max(...vals) : dir === -1 ? Math.min(...vals) : null;
    return ps.map((p, k) => `<td class="n ${ps.length > 1 && dir && vals[k] === best && vals.some(v => v !== best) ? "best" : ""}">${fmt(vals[k], p)}</td>`).join(""); };
  const fxRow = `<tr><th scope="row">${gws.length === 1 ? `GW${gws[0]} fixture` : `Next ${gws.length} fixtures`}</th>${ps.map(p => `<td><div class="cmp-fx">${gws.map(x => { const f = fxFor(p.team, x);
      return `<span title="GW${x}">${f.length ? f.map(y => fdrChip(y, { gw: x })).join("") : blankChip(x)}<small>${xpCell(p.id, x)}</small></span>`; }).join("")}</div></td>`).join("")}</tr>`;
  const news = ps.some(p => p.status !== "a") ? `<tr><th scope="row">News</th>${ps.map(p => `<td>${p.status !== "a" ? `<span class="pill ${p.status === "d" ? "warn" : "bad"}">${esc(p.news || "Flagged")}</span>` : '<span class="muted">Fit</span>'}</td>`).join("")}</tr>` : "";
  return `<div class="panel cmp-table" id="cmpPanel"><div class="bar"><h3>Comparing ${ps.length} player${ps.length > 1 ? "s" : ""}</h3><span class="muted">${ps.length < 4 ? "Tick up to 4 in the list, or press Compare in any player's panel" : "Up to 4 at a time"}</span></div>
    <div class="tablebox"><table><thead><tr><th></th>${ps.map(p => `<th scope="col"><button data-p="${p.id}" class="pname linkish">${esc(p.name)}</button><br><span class="muted">${T[p.team].short} · ${p.pos}${MINE.has(p.id) ? " · yours" : ""}</span><br>${playerTags(p, 4)} <button class="btn ghost sm" data-uncmp="${p.id}" aria-label="Remove ${esc(p.name)}">✕</button></th>`).join("")}</tr></thead>
    <tbody>${news}${fxRow}${groups.map(([h, rows]) => `<tr class="cmp-h"><th colspan="${ps.length + 1}">${h}</th></tr>${rows.map(([l, fn, dir, fmt, gk]) => `<tr><th scope="row">${gk ? term(gk, l) : l}</th>${cell(fn, dir, fmt)}</tr>`).join("")}`).join("")}</tbody></table></div>
    <p class="note">Highlighted = best of the group. Fixture chips show FPL difficulty with projected points underneath.</p></div>`;
}

