// Small reusable UI pieces: icons, FDRChip, StatBadge, loading skeletons and empty/error states.
// Each returns an HTML string, like the rest of the app's views.

/* ---------- icons (24px, stroke) ---------- */
const ICON_PATHS = {
  week: "M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z",
  planner: "M4 5h16v15H4zM4 10h16M9 5v15",
  rivals: "M8 4h8v4a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 12v4M8.5 20h7M10 16h4v4h-4z",
  players: "M12 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM5 20a7 7 0 0 1 14 0",
  fixtures: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4M8 14h2M14 14h2M8 17h2",
  stats: "M5 20V10M10 20V4M15 20v-7M20 20v-4",
  chips: "M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z",
  review: "M4 19h16M6 15l4-5 3 3 5-7",
  model: "M12 3a9 9 0 1 0 9 9M12 7v5l3 3M17 3h4v4",
  deadlines: "M12 21a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM12 9v4l2.5 2.5M9.5 2.5h5M12 2.5V5",
  health: "M3 12h4l2-6 4 12 2-6h6",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  vsmodel: "M4 6h6v12H4zM14 6h6v12h-6zM10 12h4",
  school: "M2 9l10-5 10 5-10 5zM6 11v5c3 2.5 9 2.5 12 0v-5M22 9v6",   // FL-147: mortarboard
  afg: "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  refresh: "M20 11a8 8 0 0 0-14.6-4.5M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5M20 20v-4h-4",
  sync: "M7 17a5 5 0 1 1 1-9.9A6 6 0 0 1 19.5 9 4 4 0 0 1 18 17zM12 12v6M9.5 15.5 12 18l2.5-2.5",
  alert: "M12 4 2.5 20h19zM12 10v4M12 17h.01",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  empty: "M4 7h16v12H4zM8 7V5h8v2M9 12h6",
};
function icon(name, cls = "") {
  const d = ICON_PATHS[name]; if (!d) return "";
  return `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${d}"/></svg>`;
}

/* ---------- FDRChip ---------- */
// Official FPL fixture difficulty: 1–2 green, 3 grey, 4–5 red. The number is always printed, so colour is never the only signal.
const FDR_WORD = { 1: "very easy", 2: "easy", 3: "medium", 4: "hard", 5: "very hard" };
function fdrChip(x, { gw, size = "", extra = "" } = {}) {
  const f = Math.min(5, Math.max(1, x.fdr || 3));
  const opp = T[x.opp];
  const tip = `${gw ? `GW${gw}: ` : ""}${opp.name} ${x.home ? "at home" : "away"}, difficulty ${f} (${FDR_WORD[f]})${x.eu ? `. Also plays ${x.eu} that week` : ""}`;
  return `<span class="fdr f${f} ${size}" title="${esc(tip)}" aria-label="${esc(tip)}">${x.home ? opp.short : opp.short.toLowerCase()}<b>${f}</b>${x.eu ? '<i class="eudot" aria-hidden="true"></i>' : ""}${extra}</span>`;
}
function fdrKey() {
  return `<span class="fdr-key" aria-label="Fixture difficulty from 1, easiest, to 5, hardest">Difficulty ${[1, 2, 3, 4, 5].map(f => `<span class="fdr f${f} xs">${f}</span>`).join("")} (capitals = home)</span>`;
}
function blankChip(gw) { return `<span class="fdr blank" title="GW${gw}: no fixture" aria-label="GW${gw}: no fixture">—</span>`; }

/* ---------- StatBadge ---------- */
// A labelled number. tone: "", "up", "down", "accent"
function statBadge(label, value, { sub = "", tone = "", big = false } = {}) {
  return `<div class="stat ${big ? "big" : ""}"><dt>${label}</dt><dd class="${tone}">${value}</dd>${sub ? `<dd class="stat-sub">${sub}</dd>` : ""}</div>`;
}

/* ---------- Scoreline: a running head-to-head score, read like a football result ---------- */
// tally(items, a, b, { lower }): each item is one contest (a gameweek, a punt). a(item) and b(item) are the two
// sides' numbers for it; the higher wins, or the lower when lower = true (misses). Compared as shown on the page
// (dp decimals), so the score always agrees with the table beside it. A contest where either side is missing
// (null or undefined: nothing saved, nothing to compare) is not scored but counted in `unscored`, never as a draw.
function tally(items, a, b, { lower = false, dp = 2 } = {}) {
  const t = { home: 0, away: 0, draws: 0, unscored: 0 };
  const r = v => Math.round(v * 10 ** dp);
  items.forEach(x => {
    const u = a(x), v = b(x);
    if (u == null || v == null || Number.isNaN(u) || Number.isNaN(v)) { t.unscored++; return; }
    const d = r(u) - r(v);
    if (!d) t.draws++; else if (d < 0 === lower) t.home++; else t.away++;
  });
  return t;
}
// scoreline("FPL Lab", "FPL", t, { what: "gameweeks", mini }): "FPL Lab 3–1 FPL", the side in front in green.
// what names the contests ("gameweeks", "punts") and goes into the caption and the screen-reader label.
function scoreline(home, away, t, { what = "gameweeks", mini = false } = {}) {
  const played = t.home + t.away + t.draws;
  if (played === 1) what = what.replace(/s$/, "");   // "1 gameweek", "1 punt"
  const lead = t.home > t.away ? "home" : t.away > t.home ? "away" : "";
  const extra = [t.draws ? `${t.draws} level` : "", t.unscored ? `${t.unscored} not scored` : ""].filter(Boolean).join(" · ");
  const state = !played ? "No result yet" : lead ? `${lead === "home" ? home : away} ahead` : "All square";
  const label = `${home} ${t.home}, ${away} ${t.away}, over ${played} ${what}${extra ? `, ${extra}` : ""}. ${state}.`;
  return `<div class="scoreline${mini ? " mini" : ""}${lead ? " lead-" + lead : ""}" role="img" aria-label="${esc(label)}">
    <span class="sl-side home">${esc(home)}</span><span class="sl-score"><b>${t.home}</b><i aria-hidden="true">–</i><b>${t.away}</b></span><span class="sl-side away">${esc(away)}</span>
    ${mini ? "" : `<span class="sl-cap">${played ? `${played} ${what}` : "No result yet"}${extra ? ` · ${extra}` : ""}</span>`}</div>`;
}

/* ---------- loading, empty and error states ---------- */
function skeleton(kind = "page") {
  const line = (w, h = 12) => `<span class="sk" style="width:${w};height:${h}px"></span>`;
  if (kind === "table") return `<div class="panel skel" aria-hidden="true">${line("40%", 20)}${Array.from({ length: 8 }, () => line("100%", 14)).join("")}</div>`;
  return `<div class="skel-page" role="status" aria-label="Loading the latest FPL data">
    <div class="skel-grid">
      <div class="panel skel">${line("55%", 22)}${line("90%")}${line("75%")}${line("85%")}${line("60%")}</div>
      <div class="panel skel pitch-skel"></div>
    </div>
  </div>`;
}
/* Season end (FL-060): after GW38's deadline FPL lists no next gameweek, so build.py sets meta.season_over and sends no
   forecast weeks or plans. Views that plan the next gameweek show this instead. Missing flag (older data.json): false. */
const seasonOver = () => !!D.meta?.season_over;
const seasonOverView = what => stateView({ title: "Season over", body: `GW${D.meta.cur_gw} was the last gameweek, so there is nothing left to ${what}. This returns when FPL opens next season.` });
function stateView({ kind = "empty", title, body = "", action = "" }) {
  return `<div class="state ${kind}" role="${kind === "error" ? "alert" : "status"}">${icon(kind === "error" ? "alert" : "empty", "state-ic")}<h2>${title}</h2>${body ? `<p>${body}</p>` : ""}${action}</div>`;
}

/* FL-122: a strip of tabs or options that is wider than its box scrolls sideways; fade the edge that has more, so it
   shows there is more to swipe to, and bring the selected option into view. Used on Fixtures and Stats (bind() in
   shell/events.js); the Planner's tabs are left alone (FL-090). A strip that fits gets no fade. */
function scrollStrips(sel) {
  document.querySelectorAll(sel).forEach(row => {
    const edge = () => { row.classList.toggle("more-r", row.scrollLeft + row.clientWidth < row.scrollWidth - 4); row.classList.toggle("more-l", row.scrollLeft > 4); };
    const on = row.querySelector('[aria-pressed="true"]');
    if (on && row.scrollWidth > row.clientWidth) row.scrollLeft = Math.max(0, on.offsetLeft - (row.clientWidth - on.offsetWidth) / 2);
    row.addEventListener("scroll", edge, { passive: true }); edge();
  });
}
