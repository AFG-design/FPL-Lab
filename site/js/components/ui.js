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
  more: "M5 12h.01M12 12h.01M19 12h.01",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  refresh: "M20 11a8 8 0 0 0-14.6-4.5M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5M20 20v-4h-4",
  sync: "M7 17a5 5 0 1 1 1-9.9A6 6 0 0 1 19.5 9 4 4 0 0 1 18 17zM12 12v6M9.5 15.5 12 18l2.5-2.5",
  alert: "M12 4 2.5 20h19zM12 10v4M12 17h.01",
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
function stateView({ kind = "empty", title, body = "", action = "" }) {
  return `<div class="state ${kind}" role="${kind === "error" ? "alert" : "status"}">${icon(kind === "error" ? "alert" : "empty", "state-ic")}<h2>${title}</h2>${body ? `<p>${body}</p>` : ""}${action}</div>`;
}
