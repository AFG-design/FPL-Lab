// Event binding after each render.
/* ---------- events ---------- */
// one-off highlight on the move just added in "Your moves" (the flash is CSS and is off for reduced motion)
function flashMove(g, inId) {
  const row = $(`#app .move[data-mv="${g}:${inId}"]`); if (!row) return;
  row.classList.add("flash"); setTimeout(() => row.classList.remove("flash"), 1000);
}
function bind() {
  const on = (sel, fn, ev = "onclick") => document.querySelectorAll(sel).forEach(el => el[ev] = () => fn(el));
  on("[data-p]", b => openPlayer(+b.dataset.p));
  // lineup style (components/pitch.js): a display preference only; keeps the toggle where it was on screen
  on("[data-lineup]", b => {
    const v = b.dataset.lineup; if (v === S.lineup) return;
    const top = b.getBoundingClientRect().top, idx = [...document.querySelectorAll("[data-lineup]")].indexOf(b);
    S.lineup = v; store.set("fpl.lineup", v); render();
    const nb = document.querySelectorAll("[data-lineup]")[idx]; if (!nb) return;
    window.scrollBy(0, nb.getBoundingClientRect().top - top); nb.focus({ preventScroll: true });
  });
  on("[data-reason]", b => { const [g, o, i, k] = b.dataset.reason.split(":"); openReason(+g, +o, +i, k); });
  on("[data-vmgw]", b => { S.vmgw = b.dataset.vmgw; render(); });
  on("[data-fx]", b => { S.fxMode = b.dataset.fx; store.set("fpl.fxMode", S.fxMode); render(); });
  on("[data-fxn]", b => { S.fxN = b.dataset.fxn === "all" ? "all" : +b.dataset.fxn; render(); });
  on("[data-fxsort]", b => { S.fxSort = b.dataset.fxsort; render(); });
  on("[data-field]", b => { S.field = b.dataset.field; render(); });
  on("[data-mode]", b => {
    const mode = b.dataset.mode, k = SB.source.startsWith("plan:") && recommendedPlan(mode);
    if (k) useModelPlan(k, mode);
    else { rememberPlan(); S.mode = mode; store.set("fpl.mode", mode); saveSandbox(); }
    render();
  });
  on("[data-sync]", () => openSync());
  on("[data-replan]", () => runReplan());
  on("[data-setcap]", b => { const [g, id] = b.dataset.setcap.split(":").map(Number); setOv(g, o => { o.cap = id || null; }); render(); });
  on("[data-horizon]", b => { setHorizon(+b.dataset.horizon); render(); });
  on("[data-pair]", b => {
    const [o1, n1, o2, n2] = b.dataset.pair.split(":").map(Number), g = SB.gw;
    editPlan(() => {
      for (const [o, n] of [[o1, n1], [o2, n2]]) {
        const same = SB.moves.find(m => m.gw === g && m.in === o);
        if (same) same.in = n; else { SB.moves = SB.moves.filter(m => !(m.gw >= g && m.out === o)); SB.moves.push({ gw: g, out: o, in: n }); }
      }
    });
    render();
  });
  on("[data-draftsave]", () => {
    const ds = getDrafts(); if (ds.length >= 3) return;
    const name = ($("#draftName")?.value || "").trim() || `Draft ${ds.length + 1}`;
    ds.push(tpStamp({ id: tpId(), name, ...completePlan(), saved: Date.now(), from: "Your plan" }));
    setDrafts(ds); render();
  });
  on("[data-draftload]", b => {
    const d = getDrafts()[+b.dataset.draftload]; if (!d) return;
    activatePlan(d, "custom", d.id || "i" + b.dataset.draftload); render();
  });
  on("[data-draftdel]", b => { const ds = getDrafts(); ds.splice(+b.dataset.draftdel, 1); setDrafts(ds); render(); });
  on("[data-ptab]", b => { S.ptab = b.dataset.ptab; store.set("fpl.ptab", S.ptab); render(); });
  on("[data-sugg]", b => {
    const [o, n] = b.dataset.sugg.split(":").map(Number), g = SB.gw;
    const gainTxt = (b.closest(".sugg")?.querySelector(".sg-gain")?.textContent || "").trim();
    editPlan(() => {
      const same = SB.moves.find(m => m.gw === g && m.in === o);
      if (same) same.in = n; else { SB.moves = SB.moves.filter(m => !(m.gw >= g && m.out === o)); SB.moves.push({ gw: g, out: o, in: n }); }
    });
    render();
    flashMove(g, n);
    toast(`${P[n].name} is in for ${P[o].name}.${/^\+\d/.test(gainTxt) ? ` ${gainTxt} over ${PG.length} GWs.` : ""}`);
  });
  on("[data-afgmove]", b => {
    const [o, n] = b.dataset.afgmove.split(":").map(Number), g = D.meta.next_gw;
    editPlan(() => {
      const same = SB.moves.find(m => m.gw === g && m.in === o);
      if (same) same.in = n; else { SB.moves = SB.moves.filter(m => !(m.gw >= g && m.out === o)); SB.moves.push({ gw: g, out: o, in: n }); }
    });
    render();
  });
  on("[data-unrule]", b => { const [kind, id] = b.dataset.unrule.split(":"); SB.rules[kind] = SB.rules[kind].filter(x => x !== +id); saveSandbox(); render(); });
  const hs = $("#hitsSel"); if (hs) hs.onchange = e => { SB.rules.maxHits = e.target.value === "" ? null : +e.target.value; saveSandbox(); };
  on("[data-act]", b => {
    const g = SB.gw, id = SB.sel, a = b.dataset.act;
    if (a === "lock") { SB.rules.locked = SB.rules.locked.includes(id) ? SB.rules.locked.filter(x => x !== id) : [...SB.rules.locked, id]; SB.rules.banned = SB.rules.banned.filter(x => x !== id); saveSandbox(); }
    else if (a === "reset") { delete SB.ov[g]; saveSandbox(); }
    else setOv(g, o => {
      o.start = o.start || []; o.bench = o.bench || [];
      if (a === "cap") o.cap = o.cap === id ? null : id;
      if (a === "vice") o.vice = o.vice === id ? null : id;
      if (a === "bench") { if (o.start.includes(id)) o.start = o.start.filter(x => x !== id); o.bench = [...new Set([...o.bench, id])]; if (o.cap === id) o.cap = null; }
      if (a === "start") { if (o.bench.includes(id)) o.bench = o.bench.filter(x => x !== id); o.start = [...new Set([...o.start, id])]; }
    });
    render();
  });
  on("[data-rival]", b => { S.rival = +b.dataset.rival || null; render(); if (S.rival && innerWidth < 900) document.querySelector(".grid2 > div:last-child")?.scrollIntoView({ behavior: "smooth" }); });
  on("[data-cmpteam]", b => { const v = +b.dataset.cmpteam; S.cmpTeam = S.cmpTeam === v ? null : v; WATCH.msg = ""; render(); });
  on("[data-watchadd]", b => watchEdit(+b.dataset.watchadd, true));
  on("[data-unwatch]", b => { watchEdit(+b.dataset.unwatch, false); S.cmpTeam = null; });
  // FL-156: the forecast period (Players, the xP table); never touches the Planner's horizon
  on("[data-xh]", b => { setForecast(+b.dataset.xh); render(); });
  // FL-147: FPL School review; FL-014: its share card
  on("[data-share]", b => schoolShare(b.dataset.share));
  const scf = $("#schoolForm"); if (scf) scf.onsubmit = e => { e.preventDefault(); const v = $("#schoolId").value.trim(); if (/^\d{1,10}$/.test(v) && !SCHOOL.busy) schoolRun(+v); else if (!SCHOOL.busy) { SCHOOL.err = "A team ID is a number."; SCHOOL.res = null; render(); } };
  const cf = $("#cmpForm"); if (cf) cf.onsubmit = e => { e.preventDefault(); const v = +$("#cmpId").value.trim(); if (v > 0) { S.cmpTeam = v; WATCH.msg = ""; render(); } };
  const ls = $("#leagueSel"); if (ls) ls.onchange = e => { S.league = +e.target.value; S.rival = null; render(); };
  on("[data-plan]", b => { const k = b.dataset.plan; useModelPlan(k, k.includes("_") ? k.split("_")[0] : "balanced"); render(); });
  on("[data-loadplan]", b => { const k = b.dataset.loadplan; useModelPlan(k, k.includes("_") ? k.split("_")[0] : "balanced"); render(); });
  on("[data-undoplan]", () => { undoPlan(); render(); });
  on("[data-v-go]", b => setView(b.dataset.vGo));
  document.querySelectorAll("[data-chippin]").forEach(el => { el.onchange = e => { setChipPin(el.dataset.chippin, e.target.value); render(); }; });
  on("[data-sbgw]", b => { SB.gw = +b.dataset.sbgw; SB.sel = null; render(); });
  on("[data-sbp]", b => { const id = +b.dataset.sbp; SB.sel = SB.sel === id ? null : id; SB.q = ""; render(); if (SB.sel && innerWidth < 900) $("#candPanel")?.scrollIntoView({ behavior: "smooth" }); });
  on("[data-missgw]", b => { S.missGw = +b.dataset.missgw; render(); });
  on("[data-rateplan]", b => { const [o, i] = b.dataset.rateplan.split(":").map(Number); makeTransfer(D.meta.next_gw, o, i); toast(`${P[o].name} → ${P[i].name} added to your GW${D.meta.next_gw} plan.`); render(); });
  on("[data-revgw]", b => { S.revGw = +b.dataset.revgw; render(); });
  on("[data-rotpos]", b => { S.rotPos = b.dataset.rotpos; S.rotCap = null; render(); });
  on("[data-rotcap]", b => { S.rotCap = +b.dataset.rotcap; render(); });
  on("[data-ics]", () => deadlinesICS());
  on("[data-statlabels]", b => openStatLabels(b.dataset.statlabels));
  on("[data-howto]", b => openMovesSummary(+b.dataset.howto));
  on("[data-cancel]", () => { SB.sel = null; render(); });
  on("[data-pick]", b => { makeTransfer(SB.gw, SB.sel, +b.dataset.pick); render(); });
  on("[data-undo]", b => { editPlan(() => SB.moves.splice(+b.dataset.undo, 1)); render(); });
  on("[data-reset]", () => { setPlan([], "custom"); render(); });
  on("th[data-sort]", th => { const k = th.dataset.sort; if (S.sort === k) S.dir *= -1; else { S.sort = k; S.dir = ["name", "team", "pos"].includes(k) ? 1 : -1; } render(); });
  on("[data-stsort]", th => { S.stSort = th.dataset.stsort; render(); });
  on("[data-stab]", b => { S.stab = b.dataset.stab; store.set("fpl.stab", S.stab); render(); });
  on("[data-posseg]", b => { const [k, v] = b.dataset.posseg.split(":"); S[k] = v; render(); });
  on("[data-shsort]", th => { S.shSort = th.dataset.shsort; render(); });
  on("[data-bosort]", th => { S.boSort = th.dataset.bosort; render(); });
  on("[data-stpos]", b => { S.stPos = b.dataset.stpos; render(); });
  on("[data-cmp]", c => { const id = +c.dataset.cmp; if (c.checked) { if (S.cmp.length >= 4) S.cmp.shift(); S.cmp.push(id); } else S.cmp = S.cmp.filter(x => x !== id); render(); }, "onchange");
  on("[data-uncmp]", b => { S.cmp = S.cmp.filter(x => x !== +b.dataset.uncmp); render(); });
  const tsel = $("#trendTeam"); if (tsel) tsel.onchange = e => { S.trendTeam = +e.target.value; render(); };
  const cq = $("#chartq");
  if (cq) cq.onchange = () => {
    const v = cq.value; const p = D.players.find(p => `${p.name} (${T[p.team].short})` === v);
    if (p && !S.cmp.includes(p.id)) { if (S.cmp.length >= 4) S.cmp.shift(); S.cmp.push(p.id); render(); }
  };
  const live = (id, key, obj) => {
    const el = $(id); if (!el) return;
    el.oninput = () => { obj[key] = el.value; clearTimeout(el._t); el._t = setTimeout(() => { const pos = el.selectionStart; render(); const n = $(id); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }, 200); };
  };
  live("#q", "q", S); live("#candq", "q", SB);
  // player explorer filters and column toggles
  on("[data-fpos]", b => { S.pos = b.dataset.fpos; render(); });
  [["#fteam", "team"], ["#fmin", "minp"], ["#fmax", "maxp"], ["#fform", "minform"], ["#fown", "own"], ["#fnail", "minnail"], ["#fxmin", "minxmin"], ["#ffx", "fxtop"]].forEach(([id, k]) => { const el = $(id); if (el) el.onchange = () => { S[k] = el.value; render(); }; });
  on("[data-fclear]", () => { Object.assign(S, { pos: "ALL", team: "ALL", minp: "", maxp: "", minform: "", own: "any", minnail: "", minxmin: "", fxtop: "", q: "" }); render(); });
  // FL-156: presets ask first (what they set and clear), then fill in the filter bar
  on("[data-preset]", b => { S.presetAsk = S.presetAsk === b.dataset.preset ? null : b.dataset.preset; render(); $("[data-preset-apply]")?.focus(); });
  const pss = $("#presetSel"); if (pss) pss.onchange = () => { S.presetAsk = pss.value || null; render(); $("[data-preset-apply]")?.focus(); };
  on("[data-morefilters]", () => { S.moreF = !S.moreF; render(); $("[data-morefilters]")?.focus(); });
  on("[data-preset-apply]", b => { presetApply(b.dataset.presetApply); render(); $(`[data-preset="${b.dataset.presetApply}"]`)?.focus(); });
  on("[data-preset-cancel]", () => { const k = S.presetAsk; S.presetAsk = null; render(); $(`[data-preset="${k}"]`)?.focus(); });
  const keepCols = () => { const d = $(".colpick"); return d && d.open; };
  // FL-156: a column you switch on goes at the end; switching one off keeps the others' order
  on("[data-col]", c => { const k = c.dataset.col, cur = colsOn().filter(x => x !== k); store.set("fpl.cols", c.checked ? [...cur, k] : cur); const open = keepCols(); render(); if (open) { $(".colpick").open = true; $(`[data-col="${k}"]`)?.focus(); } }, "onchange");
  on("[data-colmove]", b => { const [k, d] = b.dataset.colmove.split(":"); colMove(k, +d); render(); $(".colpick").open = true; const n = $(`[data-colmove="${b.dataset.colmove}"]`); (n && !n.disabled ? n : $(`[data-col="${k}"]`))?.focus(); });
  // FL-156: saved views and density on Players
  const pvs = $("#pvSel"); if (pvs) pvs.onchange = () => { pvSelect(pvs.value); render(); $("#pvSel")?.focus(); };
  on("[data-pvact]", b => { const a = b.dataset.pvact;
    if (a === "new" || a === "rename") { S.pvEdit = a; S.pvMsg = ""; render(); $("#pvName")?.focus(); return; }
    if (a === "delete") { S.pvEdit = "delete"; S.pvMsg = ""; render(); $('[data-pvact="cancel"]')?.focus(); return; }
    if (a === "cancel") S.pvEdit = null; else if (a === "update") pvUpdate(); else if (a === "confirm-delete") { pvDelete(); S.pvEdit = null; }
    render(); $("#pvSel")?.focus(); });
  const pvf = $("#pvForm"); if (pvf) pvf.onsubmit = e => { e.preventDefault(); pvSaveAs($("#pvName").value, S.pvEdit); render(); (S.pvEdit ? $("#pvName") : $("#pvSel"))?.focus(); };
  on("[data-dens]", b => { S.pdens = b.dataset.dens === "comfy" ? "comfy" : "compact"; store.set("fpl.pdensity", S.pdens); render(); });
  on("[data-colreset]", () => { store.set("fpl.cols", null); render(); });
  bindHome();   // homepage view switch and shortcuts (views/home.js)
  bindXp();   // xP table controls (views/xptable.js)
  bindTpaths();   // Planner → Transfer paths (views/tpaths.js)
  bindTpEdit();   // "Editing saved path" bar in Your plan
  bindPlannerViews();   // Planner view tabs (views/planner-views.js)
  bindStatsMore();   // Goals & assists, Defence and Points leaders controls (views/stats-more.js)
  // FL-122: strips that scroll sideways show it with a faded edge (components/ui.js), on Fixtures and Stats only
  if (S.view === "fixtures" || S.view === "stats") scrollStrips("#app .seg");
  if (S.view === "fixtures") bindFixtures();
}
