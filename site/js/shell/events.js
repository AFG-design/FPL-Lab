// Event binding after each render.
/* ---------- events ---------- */
function bind() {
  const on = (sel, fn, ev = "onclick") => document.querySelectorAll(sel).forEach(el => el[ev] = () => fn(el));
  on("[data-p]", b => openPlayer(+b.dataset.p));
  on("[data-fx]", b => { S.fxMode = b.dataset.fx; store.set("fpl.fxMode", S.fxMode); render(); });
  on("[data-fxn]", b => { S.fxN = +b.dataset.fxn; render(); });
  on("[data-field]", b => { S.field = b.dataset.field; render(); });
  on("[data-mode]", b => {
    S.mode = b.dataset.mode; store.set("fpl.mode", S.mode);
    // a plan picked from the options follows the strategy; a hand-edited plan is kept
    if (SB.source.startsWith("plan:")) { const k = recommendedPlan(); if (k) setPlan(planMoves(D.plans[k]), "plan:" + k); }
    render();
  });
  on("[data-sync]", () => openSync());
  on("[data-replan]", () => runReplan());
  on("[data-setcap]", b => { const [g, id] = b.dataset.setcap.split(":").map(Number); setOv(g, o => { o.cap = id || null; }); render(); });
  on("[data-horizon]", b => { setHorizon(+b.dataset.horizon); render(); });
  on("[data-pair]", b => {
    const [o1, n1, o2, n2] = b.dataset.pair.split(":").map(Number), g = SB.gw;
    SB.prev = { moves: SB.moves.slice(), source: SB.source };
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
    ds.push({ name, moves: SB.moves.map(m => ({ ...m })), ov: JSON.parse(JSON.stringify(SB.ov)), mode: S.mode, saved: Date.now() });
    setDrafts(ds); render();
  });
  on("[data-draftload]", b => {
    const d = getDrafts()[+b.dataset.draftload]; if (!d) return;
    SB.prev = { moves: SB.moves.slice(), source: SB.source };
    SB.ov = JSON.parse(JSON.stringify(d.ov || {}));
    if (d.mode && MODES[d.mode]) { S.mode = d.mode; store.set("fpl.mode", S.mode); }
    setPlan(d.moves, "custom"); render();
  });
  on("[data-draftdel]", b => { const ds = getDrafts(); ds.splice(+b.dataset.draftdel, 1); setDrafts(ds); render(); });
  on("[data-ptab]", b => { S.ptab = b.dataset.ptab; store.set("fpl.ptab", S.ptab); render(); });
  on("[data-sugg]", b => {
    const [o, n] = b.dataset.sugg.split(":").map(Number), g = SB.gw;
    SB.prev = { moves: SB.moves.slice(), source: SB.source };
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
  const cf = $("#cmpForm"); if (cf) cf.onsubmit = e => { e.preventDefault(); const v = +$("#cmpId").value.trim(); if (v > 0) { S.cmpTeam = v; WATCH.msg = ""; render(); } };
  const ls = $("#leagueSel"); if (ls) ls.onchange = e => { S.league = +e.target.value; S.rival = null; render(); };
  on("[data-plan]", b => { const k = b.dataset.plan; setPlan(planMoves(D.plans[k]), "plan:" + k); render(); });
  on("[data-loadplan]", b => { const k = b.dataset.loadplan; setPlan(planMoves(D.plans[k]), "plan:" + k); render(); });
  on("[data-undoplan]", () => { if (SB.prev) { const p = SB.prev; SB.prev = null; SB.moves = p.moves; SB.source = p.source; sanitize(); saveSandbox(); render(); } });
  on("[data-v-go]", b => setView(b.dataset.vGo));
  on("[data-sbgw]", b => { SB.gw = +b.dataset.sbgw; SB.sel = null; render(); });
  on("[data-sbp]", b => { const id = +b.dataset.sbp; SB.sel = SB.sel === id ? null : id; SB.q = ""; render(); if (SB.sel && innerWidth < 900) $("#candPanel")?.scrollIntoView({ behavior: "smooth" }); });
  on("[data-howto]", b => openMovesSummary(+b.dataset.howto));
  on("[data-cancel]", () => { SB.sel = null; render(); });
  on("[data-pick]", b => { makeTransfer(SB.gw, SB.sel, +b.dataset.pick); render(); });
  on("[data-undo]", b => { SB.prev = { moves: SB.moves.slice(), source: SB.source }; editPlan(() => SB.moves.splice(+b.dataset.undo, 1)); render(); });
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
  [["#fteam", "team"], ["#fmin", "minp"], ["#fmax", "maxp"], ["#fform", "minform"], ["#fown", "own"]].forEach(([id, k]) => { const el = $(id); if (el) el.onchange = () => { S[k] = el.value; render(); }; });
  on("[data-fclear]", () => { Object.assign(S, { pos: "ALL", team: "ALL", minp: "", maxp: "", minform: "", own: "any", q: "" }); render(); });
  const keepCols = () => { const d = $(".colpick"); return d && d.open; };
  on("[data-col]", c => { const cur = new Set(colsOn()); c.checked ? cur.add(c.dataset.col) : cur.delete(c.dataset.col); store.set("fpl.cols", COLS.map(x => x[0]).filter(k => cur.has(k))); const open = keepCols(); render(); if (open) { $(".colpick").open = true; $(`[data-col="${c.dataset.col}"]`)?.focus(); } }, "onchange");
  on("[data-colreset]", () => { store.set("fpl.cols", null); render(); });
}
