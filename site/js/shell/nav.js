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
  $("#mgr").textContent = `${m.name} · team ${meta.team_id}`;
  const last = D.history[D.history.length - 1], prev = D.history[D.history.length - 2];
  const mv = prev && last ? prev.rank - last.rank : 0;
  $("#score").innerHTML = `
    <div><span class="lbl">Overall rank</span><b>${rankFmt(m.rank)}</b><span class="${mv >= 0 ? "up" : "down"}" style="font-size:12px">${mv >= 0 ? "▲" : "▼"} ${rankFmt(Math.abs(mv))}</span></div>
    <div><span class="lbl">Points</span><b>${m.points}</b><span class="muted" style="font-size:12px">GW${meta.picks_gw}: ${m.gw_points ?? "–"}</span></div>
    <div><span class="lbl">Bank · FT</span><b>${money(m.bank)} · ${m.free_transfers}</b><span class="muted" style="font-size:12px">value ${money(m.value)}</span></div>
    <div class="deadline"><span class="lbl">GW${meta.next_gw} deadline</span><b id="cd">${countdown(meta.deadline)}</b><span class="muted" style="font-size:12px">${meta.deadline ? ukTime(meta.deadline) : ""}</span></div>`;
  const built = new Date(meta.built), ageH = (Date.now() - built) / 36e5;
  $("#meta").innerHTML = `<span>Data updated ${built.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" })}${ageH > 3 ? ' <span class="pill warn">stale</span>' : ""}</span>
    <span>Squad shown is your GW${meta.picks_gw} team. Transfers you make on the FPL site show up after the deadline.</span>
    <button class="btn" data-refresh="1">${REFRESH.busy ? "Refreshing…" : "Refresh data now"}</button><span id="refreshMsg">${esc(REFRESH.msg)}</span>
    <button class="btn" data-sync="1">${syncToken() ? "Sync on" : "Sync plan"}</button><span id="syncMsg">${esc(SYNC.msg || "")}</span>`;
  const rb = $("#meta [data-refresh]"); if (rb) rb.onclick = () => { if (!REFRESH.busy) startRefresh(); };
  const sb2 = $("#meta [data-sync]"); if (sb2) sb2.onclick = () => openSync();
}

const MORE = [["fixtures", "Fixtures", "Fixture tracker and team strength"], ["stats", "Stats", "Form, shots, set pieces, defence, bonus, value, teams"], ["review", "Review", "Your gameweek and season review"], ["chips", "Chips", "Chip planner"], ["model", "Model", "How accurate the projections are"]];
function moreItems() { return MORE.map(([v, l, d]) => `<button role="menuitem" data-v="${v}" aria-current="${S.view === v}"><b>${l}</b><span>${d}</span></button>`).join(""); }
function closeMore() { $("#moreMenu").hidden = true; $("#moreSheet").hidden = true; $("#moreTop").setAttribute("aria-expanded", "false"); }
$("#moreTop").addEventListener("click", e => { e.stopPropagation(); const m = $("#moreMenu"); m.innerHTML = moreItems(); m.hidden = !m.hidden; $("#moreTop").setAttribute("aria-expanded", String(!m.hidden)); });
$("#moreMenu").addEventListener("click", e => { const b = e.target.closest("[data-v]"); if (b) { closeMore(); setView(b.dataset.v); } });
$("#moreSheet").addEventListener("click", e => { const b = e.target.closest("[data-v]"); closeMore(); if (b) setView(b.dataset.v); });
$("#bottomnav").addEventListener("click", e => {
  const b = e.target.closest("[data-v]"); if (!b) return;
  if (b.dataset.v === "more") { const sh = $("#moreSheet"); sh.querySelector(".sheetbody").innerHTML = moreItems(); sh.hidden = !sh.hidden; return; }
  closeMore(); setView(b.dataset.v);
});
document.addEventListener("click", e => { if (!e.target.closest(".morewrap") && !e.target.closest("#bottomnav") && !e.target.closest("#moreSheet")) closeMore(); });
function setView(v) {
  S.view = v; store.set("fpl.view", v);
  render(); window.scrollTo({ top: 0 });
}
$("#tabs").addEventListener("click", e => { const b = e.target.closest("button[data-v]"); if (b && !b.closest(".moremenu")) setView(b.dataset.v); });

function render() {
  const inMore = MORE.some(m => m[0] === S.view);
  document.querySelectorAll("#tabs > button[data-v], #bottomnav button[data-v]").forEach(b => b.setAttribute("aria-selected", b.dataset.v === S.view || (b.dataset.v === "more" && inMore)));
  const mt = $("#moreTop"); mt.setAttribute("aria-selected", String(inMore)); mt.textContent = inMore ? `${MORE.find(m => m[0] === S.view)[1]} ▾` : "More ▾";
  const fn = { week: vWeek, planner: vPlanner, rivals: vRivals, review: vReview, fixtures: vFixtures, players: vPlayers, stats: vStats, chips: vChips, season: vReview, model: vModel }[S.view] || vWeek;
  $("#app").innerHTML = `<section class="view">${fn()}</section>`;
  bind();
}
