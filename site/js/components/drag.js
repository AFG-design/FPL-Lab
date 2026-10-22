// Drag and drop on the Planner pitch: swap a starter with a sub, reorder the bench, or drop a replacement onto a player.
// Mouse: just drag. Touch: press and hold, then drag (so normal scrolling still works).
function toast(msg) {
  let t = $("#toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; t.setAttribute("role", "status"); t.setAttribute("aria-live", "polite"); document.body.appendChild(t); }
  t.textContent = msg; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 2800);
}
function formationProblem(xi) {
  const c = { GKP: 0, DEF: 0, MID: 0, FWD: 0 }; xi.forEach(i => c[P[i].pos]++);
  if (c.GKP !== 1) return "You need exactly one goalkeeper in the XI. Swap keeper for keeper.";
  if (c.DEF < 3) return "That would leave fewer than 3 defenders.";
  if (c.MID < 2) return "That would leave fewer than 2 midfielders.";
  if (c.FWD < 1) return "That would leave no forward.";
  return c.DEF > 5 ? "Five defenders is the most you can start." : c.FWD > 3 ? "Three forwards is the most you can start." : "";
}
function makeTransfer(g, out, inn) {
  SB.prev = { moves: SB.moves.slice(), source: SB.source };
  editPlan(() => {
    const same = SB.moves.find(m => m.gw === g && m.in === out);
    if (same) { same.in = inn; if (same.in === same.out) SB.moves = SB.moves.filter(m => m !== same); }  // swap a signing made this week: still one transfer
    else { SB.moves = SB.moves.filter(m => !(m.gw >= g && m.out === out)); SB.moves.push({ gw: g, out, in: inn }); }
  });
  SB.sel = null;
}
function canBuy(g, out, inn) {
  const po = P[out], pi = P[inn], sq = squadAt(g);
  if (po.pos !== pi.pos) return `${pi.name} is a ${pi.pos}; drop him on a ${pi.pos}.`;
  if (sq.includes(inn)) return `${pi.name} is already in your squad.`;
  const budget = bankAt(g) + (D.squad.some(s => s.id === out) && !SB.moves.some(m => m.in === out) ? sellPrice(out) : po.price);
  if (pi.price > budget + 1e-9) return `Not enough money: ${money(pi.price)} needed, ${money(budget)} available.`;
  const cc = clubCounts(sq.filter(i => i !== out));
  if ((cc[pi.team] || 0) >= 3) return `You'd have 4 players from ${T[pi.team].name}.`;
  return "";
}
function dropOn(src, kind, dst) {
  const g = SB.gw, t = scoreMoves(SB.moves).weeks.find(w => w.gw === g).team;
  if (kind === "cand") {
    const why = canBuy(g, dst, src); if (why) return toast(why);
    makeTransfer(g, dst, src); render(); return toast(`${P[dst].name} → ${P[src].name} from GW${g}.`);
  }
  if (src === dst) return;
  const aXI = t.xi.includes(src), bXI = t.xi.includes(dst);
  const outfieldBench = t.bench.filter(i => P[i].pos !== "GKP");
  if (aXI === bXI) {
    if (aXI) return toast("Drop a starter onto a substitute to swap them.");
    if (P[src].pos === "GKP" || P[dst].pos === "GKP") return toast("The substitute keeper always sits first on the bench.");
    const order = outfieldBench.filter(i => i !== src); order.splice(order.indexOf(dst) + (outfieldBench.indexOf(src) < outfieldBench.indexOf(dst) ? 1 : 0), 0, src);
    setOv(g, o => { o.order = order; }); render(); return toast(`Bench order: ${order.map(i => P[i].name).join(", ")}.`);
  }
  const st = aXI ? dst : src, bn = aXI ? src : dst;
  const xi = t.xi.filter(i => i !== bn).concat(st), why = formationProblem(xi); if (why) return toast(why);
  setOv(g, o => {
    o.start = xi.slice(); o.bench = t.bench.filter(i => i !== st).concat(bn);
    o.order = outfieldBench.map(i => i === st ? bn : i).filter(i => P[i].pos !== "GKP");
    if (o.cap === bn) o.cap = null; if (o.vice === bn) o.vice = null;
  });
  render(); toast(`${P[st].name} starts, ${P[bn].name} on the bench (GW${g}).`);
}

const DRAG = { el: null };
function dragEnd() {
  clearTimeout(DRAG.timer); cancelAnimationFrame(DRAG.raf); DRAG.ghost?.remove();
  document.querySelectorAll(".drop-ok, .drop-no, .drag-src").forEach(x => x.classList.remove("drop-ok", "drop-no", "drag-src"));
  document.body.classList.remove("dragging");
  Object.assign(DRAG, { el: null, active: false, ghost: null, over: null });
}
function dragTarget(x, y) {
  if (DRAG.ghost) DRAG.ghost.style.display = "none";
  const el = document.elementFromPoint(x, y)?.closest("#app [data-sbp]");
  if (DRAG.ghost) DRAG.ghost.style.display = "";
  return el && +el.dataset.sbp !== DRAG.id ? el : null;
}
function dragStart(x, y) {
  DRAG.active = true; document.body.classList.add("dragging"); DRAG.el.classList.add("drag-src");
  const r = DRAG.el.getBoundingClientRect(), gh = DRAG.el.cloneNode(true);
  gh.className += " drag-ghost"; gh.removeAttribute("data-sbp"); gh.removeAttribute("data-pick"); gh.setAttribute("aria-hidden", "true");
  Object.assign(gh.style, { width: r.width + "px", left: 0, top: 0 });
  DRAG.dx = x - r.left; DRAG.dy = y - r.top; document.body.appendChild(gh); DRAG.ghost = gh; dragMove(x, y);
  if (navigator.vibrate && DRAG.type !== "mouse") navigator.vibrate(15);
  DRAG.raf = requestAnimationFrame(autoScroll);
}
// scroll the page while dragging near the top or bottom edge, so far-away targets can be reached
function autoScroll() {
  if (!DRAG.active) return;
  const y = DRAG.ly ?? DRAG.y0, edge = 70, top = innerWidth >= 900 ? 100 : 0, bottom = innerHeight - (innerWidth < 900 ? 70 : 0);
  const v = y < top + edge ? -Math.ceil((top + edge - y) / 6) : y > bottom - edge ? Math.ceil((y - bottom + edge) / 6) : 0;
  if (v) { scrollBy(0, v); dragMove(DRAG.lx ?? DRAG.x0, y); }
  DRAG.raf = requestAnimationFrame(autoScroll);
}
function dragMove(x, y) {
  DRAG.ghost.style.transform = `translate(${x - DRAG.dx}px, ${y - DRAG.dy}px)`;
  const t = dragTarget(x, y);
  if (t !== DRAG.over) {
    DRAG.over?.classList.remove("drop-ok", "drop-no"); DRAG.over = t;
    if (t) t.classList.add(DRAG.kind === "cand" && P[+t.dataset.sbp]?.pos !== P[DRAG.id]?.pos ? "drop-no" : "drop-ok");
  }
}
document.addEventListener("pointerdown", e => {
  if (S.view !== "planner" || e.button > 0 || !D) return;
  const el = e.target.closest("#app [data-sbp], #app .cand[data-pick]"); if (!el) return;
  dragEnd();
  Object.assign(DRAG, { el, id: +(el.dataset.sbp || el.dataset.pick), kind: el.dataset.sbp ? "squad" : "cand", x0: e.clientX, y0: e.clientY, type: e.pointerType, active: false });
  if (e.pointerType === "mouse") e.preventDefault();   // no text selection or native image drag
  else DRAG.timer = setTimeout(() => { if (DRAG.el) dragStart(DRAG.lx ?? DRAG.x0, DRAG.ly ?? DRAG.y0); }, 380);
});
document.addEventListener("pointermove", e => {
  if (!DRAG.el) return;
  DRAG.lx = e.clientX; DRAG.ly = e.clientY;
  const d = Math.hypot(e.clientX - DRAG.x0, e.clientY - DRAG.y0);
  if (!DRAG.active) {
    if (DRAG.type === "mouse" && d > 6) dragStart(e.clientX, e.clientY);
    else if (DRAG.type !== "mouse" && d > 10) dragEnd();     // finger moved before the hold: it's a scroll
    return;
  }
  dragMove(e.clientX, e.clientY);
});
document.addEventListener("pointerup", e => {
  if (!DRAG.el) return;
  if (!DRAG.active) { dragEnd(); return; }                  // a plain tap: the normal click handles it
  const t = dragTarget(e.clientX, e.clientY), src = DRAG.id, kind = DRAG.kind;
  DRAG.suppress = true; setTimeout(() => { DRAG.suppress = false; }, 80);
  dragEnd();
  if (t) dropOn(src, kind, +t.dataset.sbp);
});
document.addEventListener("pointercancel", () => { if (!DRAG.active) dragEnd(); });
document.addEventListener("touchmove", e => { if (DRAG.active) e.preventDefault(); }, { passive: false });
document.addEventListener("contextmenu", e => { if (DRAG.el) e.preventDefault(); });
document.addEventListener("click", e => { if (DRAG.suppress) { e.stopPropagation(); e.preventDefault(); DRAG.suppress = false; } }, true);
document.addEventListener("keydown", e => { if (e.key === "Escape" && DRAG.active) dragEnd(); });
