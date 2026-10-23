// Search everywhere: one box that finds any player, manager or section from any screen ("/" or Ctrl+K).
const fold = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const SEARCH = { q: "", sel: 0, items: [] };
function searchItems(q) {
  const f = fold(q.trim()); if (!f) return [];
  const out = [];
  if (/^\d{3,9}$/.test(f)) out.push({ kind: "team", id: +f, label: `Compare team ${f}`, sub: "Any FPL team ID" });
  const words = f.split(/\s+/);
  const ps = D.players.map(p => {
    const hay = fold(p.name + " " + p.full + " " + T[p.team].short + " " + T[p.team].name);
    if (!words.every(w => hay.includes(w))) return null;
    const n = fold(p.name), score = (n === f ? 3 : n.startsWith(f) ? 2 : fold(p.full).split(" ").some(x => x.startsWith(words[0])) ? 1 : 0) + Math.min(1, p.own / 40);
    return { p, score };
  }).filter(Boolean).sort((a, b) => b.score - a.score || b.p.xp5 - a.p.xp5).slice(0, 8);
  ps.forEach(({ p }) => out.push({ kind: "player", id: p.id, label: p.name, sub: `${T[p.team].short} · ${p.pos} · £${p.price.toFixed(1)}m · ${f1(xpg(p.id, D.meta.next_gw))} xP${MINE.has(p.id) ? " · in your team" : ""}` }));
  Object.values(T).forEach(t => { if (fold(t.name).includes(f) || fold(t.short) === f) out.push({ kind: "club", id: t.id, label: t.name, sub: "Team profile: form, fixtures, likely XI, best picks" }); });
  const seen = new Set();
  watchTeams().forEach(w => { if (!seen.has(w.entry) && (fold(w.player).includes(f) || fold(w.team).includes(f))) { seen.add(w.entry); out.push({ kind: "team", id: w.entry, label: w.player, sub: `${w.team} · ${w.src}` }); } });
  MORE.concat([["week", "This week", "Your team and this week's decisions"], ["planner", "Planner", "Transfers, captains and strategy"], ["rivals", "Rivals", "The field and mini-leagues"], ["players", "Players", "Every player, filtered and sorted"]])
    .forEach(([v, l, d]) => { if (fold(l).startsWith(f) || fold(d).includes(f) && f.length > 3) out.push({ kind: "view", id: v, label: l, sub: d }); });
  return out.slice(0, 12);
}
function searchList() {
  const L = $("#searchList"); if (!L) return;
  SEARCH.items = searchItems(SEARCH.q); SEARCH.sel = Math.min(SEARCH.sel, Math.max(0, SEARCH.items.length - 1));
  L.innerHTML = SEARCH.items.length ? SEARCH.items.map((it, k) => `<li role="option" id="sr${k}" aria-selected="${k === SEARCH.sel}" data-sk="${k}">
      ${it.kind === "player" ? `<span class="sr-ic pos-${P[it.id].pos}">${P[it.id].pos}</span>` : `<span class="sr-ic">${icon(it.kind === "team" ? "rivals" : it.kind === "club" ? "fixtures" : it.id)}</span>`}
      <span class="sr-txt"><b>${esc(it.label)}</b><span>${esc(it.sub)}</span></span></li>`).join("")
    : `<li class="sr-empty">${SEARCH.q.trim() ? "Nothing found. Try a surname, a club (e.g. ARS) or a team ID." : "Type a player, club, manager, team ID or section."}</li>`;
  $("#searchIn").setAttribute("aria-activedescendant", SEARCH.items.length ? "sr" + SEARCH.sel : "");
}
function searchGo(it) {
  if (!it) return;
  $("#searchDlg").close();
  if (it.kind === "player") openPlayer(it.id);
  else if (it.kind === "view") setView(it.id);
  else if (it.kind === "club") openTeam(it.id);
  else { S.cmpTeam = it.id; setView("rivals"); setTimeout(() => $("#cmpForm")?.closest(".panel")?.scrollIntoView({ behavior: "smooth" }), 50); }
}
function openSearch() {
  if (!D) return;
  let dlg = $("#searchDlg");
  if (!dlg) {
    dlg = document.createElement("dialog"); dlg.id = "searchDlg"; dlg.setAttribute("aria-label", "Search");
    dlg.innerHTML = `<div class="search-box">${icon("search")}<input id="searchIn" type="search" role="combobox" aria-expanded="true" aria-controls="searchList" aria-autocomplete="list" autocomplete="off" spellcheck="false" placeholder="Search players, clubs, managers, sections"><button class="btn ghost sm" type="button" id="searchX">Esc</button></div><ul id="searchList" role="listbox" aria-label="Results"></ul>`;
    document.body.appendChild(dlg);
    const inp = $("#searchIn");
    inp.oninput = () => { SEARCH.q = inp.value; SEARCH.sel = 0; searchList(); };
    inp.onkeydown = e => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); const n = SEARCH.items.length; if (n) { SEARCH.sel = (SEARCH.sel + (e.key === "ArrowDown" ? 1 : n - 1)) % n; searchList(); $("#sr" + SEARCH.sel)?.scrollIntoView({ block: "nearest" }); } }
      else if (e.key === "Enter") { e.preventDefault(); searchGo(SEARCH.items[SEARCH.sel]); }
    };
    $("#searchList").onclick = e => { const li = e.target.closest("[data-sk]"); if (li) searchGo(SEARCH.items[+li.dataset.sk]); };
    $("#searchX").onclick = () => dlg.close();
    dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });
  }
  SEARCH.q = ""; SEARCH.sel = 0; $("#searchIn").value = ""; searchList();
  dlg.showModal(); $("#searchIn").focus();
}
document.querySelectorAll("[data-search]").forEach(b => b.onclick = openSearch);
document.addEventListener("keydown", e => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
  if ((e.key === "/" && !typing) || (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey))) { e.preventDefault(); openSearch(); }
});
