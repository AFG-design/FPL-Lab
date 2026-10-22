// Header, navigation and the view router.
function countdown(iso) {
  if (!iso) return "–";
  const ms = new Date(iso) - new Date();
  if (ms <= 0) return "Passed";
  const d = Math.floor(ms / 864e5), h = Math.floor(ms % 864e5 / 36e5), m = Math.floor(ms % 36e5 / 6e4);
  return d ? `${d}d ${h}h` : `${h}h ${m}m`;
}
const ukTime = iso => new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });


function header() {
  const m = D.manager, meta = D.meta;
  $("#teamName").textContent = m.team;
  $("#mgr").textContent = `${m.name}, team ${meta.team_id}`;
  const last = D.history[D.history.length - 1], prev = D.history[D.history.length - 2];
  const mv = prev && last ? prev.rank - last.rank : 0;
  const move = mv ? `<span class="${mv > 0 ? "up" : "down"}">${mv > 0 ? "▲" : "▼"} ${rankFmt(Math.abs(mv))}</span>` : `<span class="muted">No change</span>`;
  $("#score").innerHTML =
    statBadge("Overall rank", rankFmt(m.rank), { sub: move }) +
    statBadge("Points", m.points, { sub: `GW${meta.picks_gw}: ${m.gw_points ?? "–"}` }) +
    statBadge("Bank", money(m.bank), { sub: `${m.free_transfers} free transfer${m.free_transfers === 1 ? "" : "s"}` }) +
    `<div class="stat deadline"><dt>GW${meta.next_gw} deadline</dt><dd id="cd">${countdown(meta.deadline)}</dd><dd class="stat-sub">${meta.deadline ? ukTime(meta.deadline) : ""}</dd></div>`;
  const built = new Date(meta.built), ageH = (Date.now() - built) / 36e5;
  const when = built.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
  $("#meta").innerHTML = `${typeof healthBanner === "function" ? healthBanner() : ""}
    <span class="st-when">${ageH > 2 ? "" : '<span class="live-dot" aria-hidden="true"></span>'}Updated ${when}</span>
    <span class="st-note">Your GW${meta.picks_gw} squad. Transfers made on the FPL site appear after the deadline.</span>
    <span class="st-acts">
      <button class="btn ghost sm" data-refresh="1" ${REFRESH.busy ? "aria-busy=\"true\"" : ""}>${icon("refresh")}${REFRESH.busy ? "Refreshing" : "Refresh data"}</button>
      <button class="btn ghost sm" data-sync="1">${icon("sync")}${syncToken() ? "Sync on" : "Sync plan"}</button>
    </span>
    <span class="st-msg" id="refreshMsg">${esc(REFRESH.msg)}</span><span class="st-msg" id="syncMsg">${esc(SYNC.msg || "")}</span>`;
  document.querySelectorAll("#meta [data-refresh]").forEach(rb => rb.onclick = () => { if (!REFRESH.busy) startRefresh(); });
  const sb2 = $("#meta [data-sync]"); if (sb2) sb2.onclick = () => openSync();
}

/* ---------- navigation: sidebar on desktop, bottom bar + sheet on phones ---------- */
const NAV = [
  ["Matchday", [["week", "This week"], ["planner", "Planner"], ["rivals", "Rivals"]]],
  ["Analysis", [["players", "Players"], ["fixtures", "Fixtures"], ["stats", "Stats"]]],
  ["Season", [["chips", "Chips"], ["review", "Review"], ["model", "Model"]]],
];
const MORE = [["fixtures", "Fixtures", "Fixture difficulty for every team"], ["stats", "Stats", "Form, shots, set pieces, defence, bonus, value"], ["chips", "Chips", "When to play each chip"], ["review", "Review", "Your gameweeks and season so far"], ["model", "Model", "How accurate the projections are"]];
const BOTTOM = [["week", "Home"], ["planner", "Plan"], ["rivals", "Rivals"], ["players", "Players"], ["more", "More"]];
$("#sidenav").innerHTML = NAV.map(([g, items]) => `<div class="navgroup"><span class="navhead">${g}</span>${items.map(([v, l]) => `<button type="button" data-v="${v}">${icon(v)}<span>${l}</span></button>`).join("")}</div>`).join("");
$("#bottomnav").innerHTML = BOTTOM.map(([v, l]) => `<button type="button" data-v="${v}" ${v === "more" ? 'aria-haspopup="menu" aria-expanded="false" id="moreBottom"' : ""}>${icon(v)}<span>${l}</span></button>`).join("");
function moreItems() { return MORE.map(([v, l, d]) => `<button role="menuitem" data-v="${v}" aria-current="${S.view === v ? "page" : "false"}">${icon(v)}<b>${l}</b><span>${d}</span></button>`).join(""); }
function closeMore() { $("#moreSheet").hidden = true; $("#moreBottom").setAttribute("aria-expanded", "false"); }
function openMore() {
  const sh = $("#moreSheet"); sh.querySelector(".sheetbody").innerHTML = moreItems(); sh.hidden = false;
  $("#moreBottom").setAttribute("aria-expanded", "true"); sh.querySelector("button")?.focus();
}
$("#sidenav").addEventListener("click", e => { const b = e.target.closest("[data-v]"); if (b) setView(b.dataset.v); });
$("#moreSheet").addEventListener("click", e => { const b = e.target.closest("[data-v]"); closeMore(); if (b) setView(b.dataset.v); });
$("#bottomnav").addEventListener("click", e => {
  const b = e.target.closest("[data-v]"); if (!b) return;
  if (b.dataset.v === "more") { $("#moreSheet").hidden ? openMore() : closeMore(); return; }
  closeMore(); setView(b.dataset.v);
});
document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("#moreSheet").hidden) { closeMore(); $("#moreBottom").focus(); } });
function setView(v, { push = true } = {}) {
  S.view = v; store.set("fpl.view", v);
  if (push && location.hash !== "#" + v) history.pushState(null, "", "#" + v);
  render(); window.scrollTo({ top: 0 }); $("#app").focus({ preventScroll: true });
}
// back/forward buttons and links like #fixtures
addEventListener("hashchange", () => { const v = location.hash.slice(1); if (VIEWS.includes(v) && v !== S.view) setView(v, { push: false }); });

const VIEW_FN = () => ({ week: vWeek, planner: vPlanner, rivals: vRivals, review: vReview, fixtures: vFixtures, players: vPlayers, stats: vStats, chips: vChips, season: vReview, model: vModel });
function render() {
  const inMore = MORE.some(m => m[0] === S.view);
  document.querySelectorAll("#sidenav [data-v], #bottomnav [data-v]").forEach(b => {
    const on = b.dataset.v === S.view || (b.dataset.v === "more" && inMore);
    if (on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  if (!D) return;
  const fn = VIEW_FN()[S.view] || vWeek;
  let html;
  try { html = fn(); } catch (e) {
    console.error(e);
    html = stateView({ kind: "error", title: "This section couldn't be drawn", body: "Something in the latest data didn't match what this page expects. Other sections should still work, and the next data refresh may fix it.", action: `<button class="btn" data-v-go="week">Go to This week</button>` });
  }
  $("#app").innerHTML = `<section class="view view-${S.view}">${html}</section>`;
  // wide tables scroll sideways: make them reachable by keyboard
  document.querySelectorAll("#app .tablebox").forEach(t => { t.tabIndex = 0; t.setAttribute("role", "region"); t.setAttribute("aria-label", t.closest(".panel")?.querySelector("h2, h3")?.textContent || "Table"); });
  const go = $("#app [data-v-go]"); if (go) go.onclick = () => setView(go.dataset.vGo);
  bind();
}
